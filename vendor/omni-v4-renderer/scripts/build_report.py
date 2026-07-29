#!/usr/bin/env python3
"""Build an Omniwaresoft-style database health-check DOCX from normalized JSON."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


BLUE = "4F81BD"
TEAL = "006B86"
LIGHT_BLUE = "C6D9F1"
EVIDENCE = "F2F2F2"
ORANGE = "F79646"
GREEN = "70AD47"
RED = "C00000"
GRAY = "7F7F7F"
WHITE = "FFFFFF"
CJK_FONT = "Microsoft JhengHei"
VALID_STATUSES = {"正常", "注意", "待確認", "異常", "資料不足", "不適用"}
STATUS_COLOR = {
    "正常": GREEN,
    "注意": ORANGE,
    "待確認": ORANGE,
    "異常": RED,
    "資料不足": GRAY,
    "不適用": GRAY,
}


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=100, bottom=100, end=100) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_repeat_table_header(table) -> None:
    if table.rows:
        repeat_header(table.rows[0])


TABLE_WIDTH_DXA = 9860
NARROW_HEADERS = {
    "狀態", "章節", "版本", "目前版本", "建議版本", "Bloat", "Scan", "Size",
    "Super", "Create role", "Create DB", "Inherit", "Conn limit", "CPU", "RAM", "容量", "已用", "使用率",
    "CVSS 分數", "CVSS", "風險程度", "修正版本",
}
WIDE_HEADERS = {
    "Output", "Privileges", "修正內容", "摘要", "觀察", "建議", "影響", "發現", "Index", "Table", "元件",
    "CVSS 向量／來源",
}


def display_width(value: str) -> int:
    return sum(2 if ord(char) > 127 else 1 for char in str(value))


def infer_table_widths(table) -> list[int]:
    if not table.rows:
        return [TABLE_WIDTH_DXA]
    column_count = len(table.rows[0].cells)
    scores: list[float] = []
    for index in range(column_count):
        header = table.rows[0].cells[index].text.strip()
        values = [row.cells[index].text.strip() for row in table.rows[:25] if index < len(row.cells)]
        max_width = max((display_width(value) for value in values), default=1)
        if header in NARROW_HEADERS:
            score = 1.0
        elif header == "CVE":
            score = 1.55
        elif header in WIDE_HEADERS:
            score = min(5.4, max(2.8, max_width / 15))
        elif header in {"Role", "Schema", "主機名稱", "Database", "OS", "Service IP", "掛載點", "項目"}:
            score = min(3.2, max(1.35, max_width / 11))
        else:
            score = min(3.8, max(1.15, max_width / 13))
        scores.append(score)
    total_score = sum(scores) or 1
    widths = [max(560, round(TABLE_WIDTH_DXA * score / total_score)) for score in scores]
    delta = TABLE_WIDTH_DXA - sum(widths)
    widths[scores.index(max(scores))] += delta
    return widths


def apply_table_widths(table, widths: list[int]) -> None:
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.insert(0, tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    for index, grid_col in enumerate(table._tbl.tblGrid.gridCol_lst):
        if index < len(widths):
            grid_col.set(qn("w:w"), str(widths[index]))
    for row in table.rows:
        grid_index = 0
        for tc in row._tr.tc_lst:
            grid_span = tc.tcPr.gridSpan
            span = int(grid_span.val) if grid_span is not None else 1
            cell_width = sum(widths[grid_index:grid_index + span])
            tc_w = tc.tcPr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc.tcPr.append(tc_w)
            tc_w.set(qn("w:w"), str(cell_width))
            tc_w.set(qn("w:type"), "dxa")
            grid_index += span


def format_run(run, *, name="Arial", size=10, bold=False, color=None, italic=False) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, end])
    format_run(run, size=8, color=GRAY)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.1

    for style_name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
        style = doc.styles[style_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(BLUE)
        style.paragraph_format.space_before = Pt(10)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.text = "歐立威科技｜資料庫健檢報告"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in header.runs:
        format_run(run, size=8, color=GRAY)

    footer = section.footer.paragraphs[0]
    left = footer.add_run("(02) 2558-2656  ｜  https://www.omniwaresoft.com.tw/                         ")
    format_run(left, size=8, color=GRAY)
    add_page_number(footer)


def is_database_chapter(chapter: dict[str, Any]) -> bool:
    if str(chapter.get("source_scope", "")).strip().lower() == "database":
        return True
    title = str(chapter.get("title", "")).strip().lower()
    return any(token in title for token in ("資料庫", "database", "postgresql", "enterprisedb", "epas", "sql"))


def validate_and_select_database_source(data: dict[str, Any]) -> str:
    """Require all database report items to use the one Primary (or standalone) node."""
    nodes = data.get("nodes") or []
    roles: dict[str, str] = {
        str(node.get("hostname", "")).strip(): str(node.get("role", "")).strip().lower()
        for node in nodes
        if str(node.get("hostname", "")).strip()
    }
    primary_hosts = [hostname for hostname, role in roles.items() if role == "primary"]
    has_replica_topology = any(role in {"standby", "dr", "replica"} for role in roles.values())
    selected = str(data.get("database_source_hostname", "")).strip()

    if has_replica_topology:
        if len(primary_hosts) != 1:
            raise ValueError("Primary/Standby or Primary/DR topology requires exactly one identifiable Primary node")
        if not selected:
            selected = primary_hosts[0]
        if selected != primary_hosts[0]:
            raise ValueError(
                f"Database evidence must use Primary {primary_hosts[0]!r}; {selected!r} is not an allowed database source"
            )
    elif selected:
        if selected not in roles:
            raise ValueError(f"database_source_hostname {selected!r} does not match any node hostname")
        if primary_hosts and selected not in primary_hosts:
            raise ValueError(f"Database evidence must use Primary {primary_hosts[0]!r}; {selected!r} is not allowed")
    elif len(primary_hosts) == 1:
        selected = primary_hosts[0]
    else:
        standalone_hosts = [hostname for hostname, role in roles.items() if role == "standalone"]
        if len(standalone_hosts) == 1:
            selected = standalone_hosts[0]
        elif len(nodes) == 1 and roles:
            selected = next(iter(roles))

    if not selected:
        raise ValueError("A Primary or standalone database_source_hostname is required")

    for chapter in data.get("chapters") or []:
        if not is_database_chapter(chapter):
            continue
        for section in chapter.get("sections") or []:
            for item in section.get("items") or []:
                item_node = str(item.get("node", "")).strip()
                if item_node and item_node != selected:
                    raise ValueError(
                        f"Database item {item.get('title', '')!r} uses {item_node!r}; "
                        f"only Primary {selected!r} is allowed"
                    )
                item["node"] = selected

    data["database_source_hostname"] = selected
    return selected


def validate_cve_metadata(data: dict[str, Any]) -> None:
    """Require authoritative CVSS metadata for every CVE rendered in section 5.1."""
    required = ("cvss_score", "severity", "cvss_version", "vector", "score_source")
    for update in data.get("version_updates") or []:
        for cve in update.get("cves") or []:
            missing = [key for key in required if not str(cve.get(key, "")).strip()]
            if missing:
                raise ValueError(
                    f"{cve.get('id', 'CVE')} is missing required CVSS metadata: {', '.join(missing)}; "
                    "use '未公布／待確認' when an authoritative value is unavailable"
                )


def add_cover(doc: Document, data: dict[str, Any]) -> None:
    for _ in range(3):
        doc.add_paragraph()
    product = data.get("product", {})
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(product.get("name") or "PostgreSQL / EDB")
    format_run(r, size=28, bold=True, color=TEAL)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(data.get("customer", ""))
    format_run(r, size=21, bold=True, color=BLUE)

    nodes = data.get("nodes") or []
    system_name = data.get("system_name") or (nodes[0].get("hostname") if nodes else "")
    if system_name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"系統／主機：{system_name}")
        format_run(r, size=11, color=GRAY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{data.get('period', '')} 資料庫健檢報告")
    format_run(r, size=18, bold=True)

    if product.get("version"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Database Version：{product['version']}")
        format_run(r, size=11, color=GRAY)

    doc.add_paragraph()
    table = doc.add_table(rows=4, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    values = [
        data.get("cover_company_name") or "歐立威科技",
        f"歐立威資料庫工程師 {data['engineer_name']}",
        "(02) 2558-2656",
        "https://www.omniwaresoft.com.tw/",
    ]
    for index, (row, value) in enumerate(zip(table.rows, values)):
        cell = row.cells[0]
        cell.width = Cm(11)
        set_cell_margins(cell, 70, 100, 70, 100)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cell.paragraphs[0].add_run(value)
        format_run(run, size=9, bold=index == 0, color=WHITE if index == 0 else None)
        if index == 0:
            shade(cell, TEAL)

    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(data.get("report_date", ""))
    format_run(r, size=10, color=GRAY)
    doc.add_page_break()


def add_heading(doc: Document, number: str, title: str, level: int) -> None:
    text = f"{number} {title}".strip()
    doc.add_heading(text, level=level)


def report_prose(value: Any) -> str:
    """Remove sentence-ending periods from generated prose, never raw evidence."""
    lines = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.rstrip()
        line = line.replace("。", "；")
        line = re.sub(r"[；．.]$", "", line)
        lines.append(line)
    return "\n".join(lines)


def next_major_number(data: dict[str, Any]) -> int:
    numbers = [
        int(str(chapter.get("number", "")))
        for chapter in data.get("chapters", [])
        if str(chapter.get("number", "")).isdigit()
    ]
    return max(numbers or [2]) + 1


def reference_parts(value: Any) -> set[str]:
    return {part for part in re.split(r"[/,、\s]+", str(value or "").strip()) if part}


def concise_finding(item: dict[str, Any]) -> str:
    observation = report_prose(item.get("observation", ""))
    lines = [line.strip() for line in observation.splitlines() if line.strip()]
    for line in lines:
        if not line.startswith("結論："):
            return line
    return lines[0] if lines else "需納入後續確認"


def complete_summary(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every non-normal assessment plus unmatched non-normal extras."""
    rows: list[dict[str, Any]] = []
    covered_references: set[str] = set()
    seen: set[tuple[str, str, str]] = set()

    for chapter in data.get("chapters", []):
        for section in chapter.get("sections") or []:
            if is_omitted_history(section.get("title")):
                continue
            reference = str(section.get("number", ""))
            for item in section.get("items") or []:
                if is_omitted_history(item.get("title")):
                    continue
                status = item.get("status", "待確認")
                if status not in VALID_STATUSES:
                    status = "待確認"
                if status == "正常":
                    continue
                title = str(item.get("title", "健檢項目"))
                if item.get("node"):
                    title = f"{title}（{item['node']}）"
                entry = {
                    "status": status,
                    "item": title,
                    "finding": concise_finding(item),
                    "recommendation": report_prose(item.get("recommendation", "")) or "待補充後續處理方式",
                    "reference": reference,
                }
                key = (reference, title, status)
                if key not in seen:
                    rows.append(entry)
                    seen.add(key)
                covered_references.add(reference)

    updates_reference = f"{next_major_number(data)}.1"
    for update in data.get("version_updates") or []:
        current = str(update.get("current", "")).strip()
        recommended = str(update.get("recommended", "")).strip()
        if not recommended or current == recommended:
            continue
        entry = {
            "status": "注意",
            "item": "版本更新",
            "finding": report_prose(update.get("summary", "")) or f"目前版本 {current} 可更新至 {recommended}",
            "recommendation": "規劃維護期更新並完成回歸測試",
            "reference": updates_reference,
        }
        key = (updates_reference, entry["item"], entry["status"])
        if key not in seen:
            rows.append(entry)
            seen.add(key)
        covered_references.add(updates_reference)

    for raw_entry in data.get("summary") or []:
        status = raw_entry.get("status", "待確認")
        if status not in VALID_STATUSES:
            status = "待確認"
        if status == "正常":
            continue
        entry_references = reference_parts(raw_entry.get("reference", ""))
        if entry_references and entry_references & covered_references:
            continue
        entry = {
            "status": status,
            "item": report_prose(raw_entry.get("item", "健檢項目")),
            "finding": report_prose(raw_entry.get("finding", "")) or "需納入後續確認",
            "recommendation": report_prose(raw_entry.get("recommendation", "")) or "待補充後續處理方式",
            "reference": str(raw_entry.get("reference", "")),
        }
        key = (entry["reference"], entry["item"], entry["status"])
        if key not in seen:
            rows.append(entry)
            seen.add(key)
    return rows


def add_contents(doc: Document, data: dict[str, Any]) -> None:
    add_heading(doc, "", "目錄", 1)
    entries = [("1", "專案說明"), ("2", "系統架構與環境")]
    for chapter in data.get("chapters", []):
        entries.append((str(chapter.get("number", "")), chapter.get("title", "")))
    next_number = max([int(n) for n, _ in entries if n.isdigit()] or [2]) + 1
    if data.get("version_updates") or complete_summary(data):
        entries.append((str(next_number), "更新與建議"))
    for number, title in entries:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.4)
        r = p.add_run(f"{number}. {title}")
        format_run(r, size=11, bold=True, color=BLUE)
    doc.add_page_break()


def add_paragraphs(doc: Document, paragraphs: list[str]) -> None:
    for text in paragraphs or []:
        p = doc.add_paragraph()
        p.add_run(report_prose(text))


def style_table(table, header=True, first_col=False, column_widths=None) -> list[int]:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = column_widths or infer_table_widths(table)
    apply_table_widths(table, widths)
    for r_index, row in enumerate(table.rows):
        prevent_row_split(row)
        for c_index, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if len(table.rows) > 24:
                set_cell_margins(cell, top=35, start=80, bottom=35, end=80)
            else:
                set_cell_margins(cell)
            if header and r_index == 0:
                shade(cell, LIGHT_BLUE)
            elif first_col and c_index == 0:
                shade(cell, LIGHT_BLUE)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    format_run(run, size=9, bold=header and r_index == 0)
    if header:
        set_repeat_table_header(table)
    return widths


def add_environment(doc: Document, data: dict[str, Any]) -> None:
    add_heading(doc, "1.", "專案說明", 1)
    add_heading(doc, "1.1", "專案背景與目的", 2)
    purpose = data.get("purpose") or [
        "確保使用資料庫之系統正常運行。",
        "避免可預期之狀況發生。",
        "穩定資料庫效能。",
        "確認備份機制，降低營運風險。",
    ]
    for index, text in enumerate(purpose, 1):
        p = doc.add_paragraph()
        p.add_run(f"{index}. {report_prose(text)}")
    add_heading(doc, "1.2", "維護週期與健檢頻率", 2)
    doc.add_paragraph(report_prose(data.get("maintenance_period") or "本次健檢期間依客戶提供資料為準"))

    doc.add_page_break()
    add_heading(doc, "2.", "系統架構與環境", 1)
    add_heading(doc, "2.1", "架構總覽", 2)
    nodes = data.get("nodes") or []
    headers = ["角色", "主機名稱", "OS", "Database", "CPU", "RAM", "Service IP", "元件"]
    table = doc.add_table(rows=1, cols=len(headers))
    for idx, value in enumerate(headers):
        table.rows[0].cells[idx].text = value
    for node in nodes:
        cells = table.add_row().cells
        values = [
            node.get("role", ""),
            node.get("hostname", ""),
            node.get("os", ""),
            node.get("database", ""),
            node.get("cpu", ""),
            node.get("ram", ""),
            node.get("service_ip", ""),
            ", ".join(node.get("components") or []),
        ]
        for idx, value in enumerate(values):
            cells[idx].text = str(value)
    style_table(table)

    add_heading(doc, "2.2", "軟體與網路架構", 2)
    architecture = data.get("architecture_image")
    if architecture:
        path = Path(architecture)
        if path.exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(path), width=Cm(16.5))
        else:
            doc.add_paragraph("架構圖檔案不存在，請補充確認")
    elif len(nodes) == 1:
        doc.add_paragraph("本環境為單一資料庫節點；詳細網路與應用程式連線關係以客戶提供資訊為準")
    else:
        doc.add_paragraph("節點清單如上；尚未取得足以繪製完整拓撲的關係資料")


def add_evidence(doc: Document, evidence: dict[str, Any]):
    evidence_type = evidence.get("type", "text")
    if evidence_type == "table":
        headers = evidence.get("headers") or []
        rows = evidence.get("rows") or []
        columns = max(len(headers), max((len(row) for row in rows), default=1))
        table = doc.add_table(rows=1 if headers else 0, cols=columns)
        if headers:
            for index in range(columns):
                table.rows[0].cells[index].text = str(headers[index] if index < len(headers) else "")
        for row in rows:
            cells = table.add_row().cells
            for index in range(columns):
                cells[index].text = str(row[index] if index < len(row) else "")
        widths = style_table(table, header=bool(headers))
        return widths, table
    elif evidence_type == "image":
        path = Path(evidence.get("path", ""))
        if path.exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            requested_width = float(evidence.get("width_cm", 16.2))
            image_width = min(16.2, max(8.0, requested_width))
            p.add_run().add_picture(str(path), width=Cm(image_width))
            if evidence.get("caption"):
                caption = doc.add_paragraph(report_prose(evidence["caption"]))
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption.paragraph_format.keep_with_next = True
                for run in caption.runs:
                    format_run(run, size=8.5, color=GRAY, italic=True)
            return [TABLE_WIDTH_DXA // 2, TABLE_WIDTH_DXA // 2], None
        else:
            return add_evidence(doc, {"type": "text", "content": "圖片證據檔案不存在。"})
    else:
        widths = [TABLE_WIDTH_DXA // 2, TABLE_WIDTH_DXA // 2]
        table = doc.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        cell = table.cell(0, 0).merge(table.cell(0, 1))
        apply_table_widths(table, widths)
        shade(cell, EVIDENCE)
        set_cell_margins(cell, 120, 120, 120, 120)
        content = str(evidence.get("content", ""))
        cell.text = ""
        for index, line in enumerate(content.splitlines() or [""]):
            paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(line)
            format_run(
                run,
                name="Consolas",
                size=float(evidence.get("font_size", 8.7)),
            )
        return widths, table


def add_assessment(doc: Document, item: dict[str, Any], column_widths=None):
    status = item.get("status", "待確認")
    if status not in VALID_STATUSES:
        status = "待確認"
    column_widths = column_widths or [TABLE_WIDTH_DXA // 2, TABLE_WIDTH_DXA // 2]
    if len(column_widths) < 2:
        column_widths = [TABLE_WIDTH_DXA // 2, TABLE_WIDTH_DXA // 2]
    column_count = max(2, len(column_widths))
    split = max(1, column_count // 2)
    table = doc.add_table(rows=1, cols=column_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    labels = [("狀態", status), ("觀察", report_prose(item.get("observation", "")))]
    if item.get("impact"):
        labels.append(("影響", report_prose(item["impact"])))
    labels.append(("建議", report_prose(item.get("recommendation", ""))))
    for row_index, (label, value) in enumerate(labels):
        row = table.rows[0] if row_index == 0 else table.add_row()
        prevent_row_split(row)
        left = row.cells[0]
        if split > 1:
            left = left.merge(row.cells[split - 1])
        right = row.cells[split]
        if split < column_count - 1:
            right = right.merge(row.cells[column_count - 1])
        left.text = label
        right.text = str(value)
        left.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_margins(left, 90, 110, 90, 110)
        set_cell_margins(right, 90, 110, 90, 110)
        shade(left, STATUS_COLOR[status] if label == "狀態" else LIGHT_BLUE)
        if label == "狀態":
            shade(right, EVIDENCE)
        for run in left.paragraphs[0].runs:
            format_run(run, size=9.5, bold=True, color=WHITE if label == "狀態" else None)
        for run in right.paragraphs[0].runs:
            format_run(run, size=9.5, bold=label == "狀態", color=STATUS_COLOR[status] if label == "狀態" else None)
    apply_table_widths(table, column_widths)
    # Keep the compact assessment block together so a lone recommendation row
    # does not spill onto the next page.
    for row in table.rows[:-1]:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def keep_item_together(evidence_table, assessment_table) -> None:
    if evidence_table is None:
        return
    # Chain the evidence to the assessment. Word/LibreOffice moves the whole
    # inspection unit to the next page when the remaining space is insufficient.
    for row in evidence_table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True


def normalized_item_name(value: Any) -> str:
    return re.sub(r"[\s_./\\-]+", "", str(value or "").lower())


def is_omitted_history(value: Any) -> bool:
    name = normalized_item_name(value)
    if "deadtuple" in name:
        return False
    return (
        "最後autovacuum" in name
        or "最後autoanalyze" in name
        or "autovacuumhistory" in name
        or "autoanalyzehistory" in name
    )


def is_schema_privilege(value: Any) -> bool:
    name = normalized_item_name(value)
    return "schema權限" in name or "schemaprivilege" in name


def is_rarely_used_index(value: Any) -> bool:
    name = normalized_item_name(value)
    return (
        "罕用索引" in name
        or "rarelyusedindex" in name
        or "rareindex" in name
        or "unusedindex" in name
    )


def index_scan_column(headers: list[Any]) -> int | None:
    normalized = [normalized_item_name(header) for header in headers]
    exact = {"scan", "idxscan", "indexscan", "indexscans", "索引掃描", "索引掃描次數"}
    for index, header in enumerate(normalized):
        if header in exact:
            return index
    for index, header in enumerate(normalized):
        if "idxscan" in header or "indexscan" in header:
            return index
    return None


def is_zero_scan(value: Any) -> bool:
    text = str(value).strip().replace(",", "")
    try:
        return float(text) == 0
    except ValueError:
        return False


def prioritize_rarely_used_index_rows(headers: list[Any], rows: list[Any]) -> list[Any]:
    scan_column = index_scan_column(headers)
    if scan_column is None:
        raise ValueError("Rarely-used-index Output lacks a recognizable Scan/idx_scan/Index scan column")
    zero_rows: list[Any] = []
    other_rows: list[Any] = []
    for row in rows:
        values = list(row) if isinstance(row, (list, tuple)) else [row]
        target = values[scan_column] if scan_column < len(values) else None
        (zero_rows if is_zero_scan(target) else other_rows).append(row)
    return (zero_rows + other_rows)[:20]


def evidence_has_visible_output(evidence: dict[str, Any]) -> bool:
    evidence_type = evidence.get("type", "text")
    if evidence_type == "table":
        return bool(evidence.get("headers") or evidence.get("rows"))
    if evidence_type == "image":
        return bool(str(evidence.get("path", "")).strip())
    return bool(str(evidence.get("content", "")).strip())


def prepare_item(item: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(item)
    evidence = prepared.get("evidence") or {}
    if not evidence_has_visible_output(evidence):
        raise ValueError(f"Inspection item lacks visible Output: {prepared.get('title', '健檢項目')}")
    if is_schema_privilege(prepared.get("title")) and evidence.get("type") == "table":
        evidence["rows"] = list(evidence.get("rows") or [])[:20]
    if is_rarely_used_index(prepared.get("title")) and evidence.get("type") == "table":
        headers = list(evidence.get("headers") or [])
        scan_column = index_scan_column(headers)
        evidence["rows"] = prioritize_rarely_used_index_rows(headers, list(evidence.get("rows") or []))
        if scan_column is not None:
            headers[scan_column] = "Index scan"
            evidence["headers"] = headers
        prepared["evidence"] = evidence
    # Source traceability is internal only. Ignore legacy packaged JSON fields.
    prepared.pop("source", None)
    prepared.pop("資料來源", None)
    return prepared


def add_item(doc: Document, item: dict[str, Any]) -> None:
    item = prepare_item(item)
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    title = item.get("title", "健檢項目")
    if item.get("node"):
        title = f"{title}（{item['node']}）"
    run = p.add_run(title)
    format_run(run, size=10.5, bold=True, color=BLUE)
    evidence_widths, evidence_table = add_evidence(doc, item.get("evidence") or {"type": "text", "content": "未提供資料"})
    long_evidence = bool(item.get("controlled_continuation")) or (
        evidence_table is not None and len(evidence_table.rows) > 24
    )
    if long_evidence:
        doc.add_page_break()
        continuation = doc.add_paragraph()
        continuation.paragraph_format.keep_with_next = True
        run = continuation.add_run(f"{title}（續：觀察與建議）")
        format_run(run, size=10.5, bold=True, color=BLUE)
    assessment_table = add_assessment(doc, item, evidence_widths)
    if not long_evidence:
        keep_item_together(evidence_table, assessment_table)


def add_chapters(doc: Document, data: dict[str, Any]) -> int:
    last_numeric = 2
    for chapter in data.get("chapters", []):
        doc.add_page_break()
        number = str(chapter.get("number", ""))
        if number.isdigit():
            last_numeric = max(last_numeric, int(number))
        add_heading(doc, f"{number}.", chapter.get("title", ""), 1)
        add_paragraphs(doc, chapter.get("paragraphs") or [])
        for section in chapter.get("sections") or []:
            if is_omitted_history(section.get("title")):
                continue
            items = [item for item in (section.get("items") or []) if not is_omitted_history(item.get("title"))]
            if not items and not (section.get("paragraphs") or []):
                continue
            add_heading(doc, str(section.get("number", "")), section.get("title", ""), 2)
            add_paragraphs(doc, section.get("paragraphs") or [])
            for item in items:
                add_item(doc, item)
    return last_numeric


def add_updates_and_summary(doc: Document, data: dict[str, Any], number: int) -> None:
    updates = data.get("version_updates") or []
    summary = complete_summary(data)
    if not updates and not summary:
        return
    doc.add_page_break()
    add_heading(doc, f"{number}.", "更新與建議", 1)
    if updates:
        add_heading(doc, f"{number}.1", "版本更新資訊摘要", 2)
        table = doc.add_table(rows=1, cols=3)
        for index, value in enumerate(("目前版本", "建議版本", "摘要")):
            table.rows[0].cells[index].text = value
        for update in updates:
            cells = table.add_row().cells
            cells[0].text = str(update.get("current", ""))
            cells[1].text = str(update.get("recommended", ""))
            cells[2].text = report_prose(update.get("summary", ""))
        style_table(table)
        cve_rows = []
        for update in updates:
            for cve in update.get("cves") or []:
                cvss_lines = [
                    str(cve.get("cvss_score", "未公布／待確認")),
                    str(cve.get("severity", "未公布／待確認")),
                    str(cve.get("cvss_version", "未公布／待確認")),
                ]
                vector = str(cve.get("vector", "")).strip()
                vector_source = [
                    vector or "未公布／待確認",
                    str(cve.get("score_source", "未公布／待確認")),
                ]
                cve_rows.append(
                    (
                        cve.get("id", ""),
                        "\n".join(cvss_lines),
                        "\n".join(vector_source),
                        update.get("recommended", ""),
                        cve.get("summary", ""),
                    )
                )
        if cve_rows:
            p = doc.add_paragraph()
            r = p.add_run("可修正 CVE 清單")
            format_run(r, size=10, bold=True, color=BLUE)
            cve_table = doc.add_table(rows=1, cols=5)
            for index, value in enumerate(("CVE", "修正版本", "CVSS", "CVSS 向量／來源", "修正內容")):
                cve_table.rows[0].cells[index].text = value
            for cve_id, cvss, vector_source, version, cve_summary in cve_rows:
                cells = cve_table.add_row().cells
                cells[0].text = str(cve_id)
                cells[1].text = str(version)
                cells[2].text = str(cvss)
                cells[3].text = str(vector_source)
                cells[4].text = report_prose(cve_summary)
            style_table(cve_table)
    if summary:
        add_heading(doc, f"{number}.2", "健檢結論與優化建議", 2)
        headers = ("狀態", "項目", "發現", "建議", "章節")
        table = doc.add_table(rows=1, cols=len(headers))
        for index, value in enumerate(headers):
            table.rows[0].cells[index].text = value
        for entry in summary:
            cells = table.add_row().cells
            values = [
                entry.get("status", ""),
                report_prose(entry.get("item", "")),
                report_prose(entry.get("finding", "")),
                report_prose(entry.get("recommendation", "")),
                entry.get("reference", ""),
            ]
            for index, value in enumerate(values):
                cells[index].text = str(value)
            if entry.get("status") in STATUS_COLOR:
                shade(cells[0], STATUS_COLOR[entry["status"]])
                for run in cells[0].paragraphs[0].runs:
                    format_run(run, size=8.5, bold=True, color=WHITE)
        style_table(table)
        for row in table.rows[:-1]:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True


def build(data: dict[str, Any], output: Path) -> None:
    engineer_name = str(data.get("engineer_name", "")).strip() or "XXX"
    data = dict(data)
    data["engineer_name"] = engineer_name
    validate_and_select_database_source(data)
    validate_cve_metadata(data)

    doc = Document()
    configure_document(doc)
    doc.core_properties.title = f"{data.get('customer', '')} {data.get('period', '')} 資料庫健檢報告"
    doc.core_properties.subject = "Database Health Check Report"
    doc.core_properties.author = "歐立威科技"

    add_cover(doc, data)
    add_contents(doc, data)
    add_environment(doc, data)
    last_number = add_chapters(doc, data)
    add_updates_and_summary(doc, data, last_number + 1)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--docx", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    build(data, args.docx)


if __name__ == "__main__":
    main()
