"""M13.1 integrated browser UI built on the proven classic workflow."""

from omni_healthcheck.web_ui import INDEX_HTML as CLASSIC_INDEX_HTML


PUBLIC_UI_VERSION = "M14.2 candidate"


_OMNIWARESOFT_LOGO_DATA_URI = (
    "data:image/png;base64,"
    "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"
)


_INTEGRATED_STYLE = r"""
    /* M10.2 integrated UI: presentation only; API and Pipeline remain shared. */
    :root {
      --brand:#1677ff; --brand-dark:#075fc9; --ink:#17253b; --muted:#66758b;
      --line:#d8e2ef; --bg:#f5f8fc; --ok:#16875d; --warn:#b86600; --bad:#c0362c;
    }
    body { background:linear-gradient(180deg,#edf6ff 0,#f7f9fc 300px); }
    header { padding:0 max(24px,5vw); background:linear-gradient(115deg,#075bab 0,#1284e8 58%,#32a4f5 100%);
      border-bottom:3px solid #f5a623; box-shadow:0 8px 24px #0b47772b; }
    .brand-row { min-height:94px; max-width:1180px; margin:auto; display:flex; align-items:center;
      justify-content:space-between; gap:24px; }
    .brand-copy { min-width:0; display:flex; align-items:center; gap:24px; }
    .brand-logo { width:215px; height:auto; max-height:64px; object-fit:contain; flex:none;
      filter:drop-shadow(0 3px 8px #003a7344); }
    .product-name { min-width:0; padding-left:24px; border-left:1px solid #ffffff66; }
    .product-name .eyebrow { margin:0 0 4px; color:#d8edff; font-size:10px; font-weight:700;
      letter-spacing:1.7px; text-transform:uppercase; }
    .product-name h1 { margin:0; color:white; font-size:22px; line-height:1.25; letter-spacing:.1px; }
    .product-name p { margin:5px 0 0; color:#e2f1ff; font-size:12px; }
    .classic-link { padding:9px 14px; border:1px solid #ffffff99; border-radius:5px;
      background:#ffffff0f; color:white; text-decoration:none; font-size:13px; font-weight:600;
      white-space:nowrap; transition:background .15s ease,border-color .15s ease; }
    .classic-link.active, .classic-link:hover { background:#ffffff2b; border-color:white; }
    .header-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
    .workspace-strip { background:white; color:#53677f; padding:10px max(24px,5vw);
      border-bottom:1px solid #dce7f2; font-size:12px; }
    .workspace-strip .workspace-meta { max-width:1180px; margin:auto; display:flex; align-items:center;
      gap:8px; flex-wrap:wrap; }
    .workspace-tag { padding:3px 8px; border-radius:3px; background:#e7f3ff; color:#0867bd;
      font-size:11px; font-weight:700; letter-spacing:.4px; }
    main { margin-top:20px; }
    .integration-notice { border-left:4px solid var(--brand); background:#eef6ff;
      padding:13px 15px; margin-bottom:18px; color:#294566; border-radius:4px; }
    .integration-notice strong { color:#075fc9; }
    section { border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px #27486d0d; }
    .step { border-radius:6px; }
    input, select, button { border-radius:5px; }
    input:focus, select:focus, button:focus { outline-color:#1677ff44; }
    .product-note { display:block; margin-top:7px; color:var(--muted); font-size:12px;
      font-weight:400; line-height:1.45; }
    .review-toolbar { display:grid; grid-template-columns:2fr 1fr auto auto; gap:10px; align-items:end; }
    .review-progress { margin:14px 0; padding:12px; border-radius:5px; background:#eef6ff; white-space:pre-wrap; }
    .section-card { margin:12px 0; padding:16px; border:1px solid var(--line); border-radius:7px; background:#fbfdff; }
    .section-card-head { display:flex; gap:10px; align-items:center; justify-content:space-between; flex-wrap:wrap; }
    .section-card h3 { margin:0; }
    .section-meta { color:var(--muted); font-size:12px; }
    .narrative-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
    .narrative-grid textarea { width:100%; min-height:150px; margin-top:6px; padding:10px;
      border:1px solid #bfcdd3; border-radius:5px; resize:vertical; font:inherit; line-height:1.5; }
    .deterministic-box { margin-top:10px; padding:10px; border-left:3px solid #8ba9bf;
      background:#f1f5f8; color:#43566b; font-size:13px; white-space:pre-wrap; }
    @media (max-width:760px) {
      .brand-row { min-height:0; padding:16px 0; align-items:flex-start; }
      .brand-copy { gap:14px; flex-direction:column; align-items:flex-start; }
      .brand-logo { width:185px; max-height:54px; }
      .product-name { padding:10px 0 0; border-left:0; border-top:1px solid #ffffff55; }
      .product-name h1 { font-size:18px; }
      .classic-link { padding:7px 9px; font-size:12px; }
      .header-actions { flex-direction:column; align-items:stretch; }
      .review-toolbar, .narrative-grid { grid-template-columns:1fr; }
    }
"""


INTEGRATED_INDEX_HTML = (
    CLASSIC_INDEX_HTML
    .replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <meta name="omnicheck-ui" content="integrated-v1">',
    )
    .replace("<title>OMNIcheck AI</title>", "<title>OMNIcheck HealthCheck Studio</title>")
    .replace("  </style>", _INTEGRATED_STYLE + "\n  </style>")
    .replace(
        "<header><h1>OMNIcheck AI</h1><p>On-premises Database Health Check</p></header>",
        f"""<header><div class="brand-row">
  <div class="brand-copy">
    <img class="brand-logo" src="{_OMNIWARESOFT_LOGO_DATA_URI}" alt="歐立威科技 Omniwaresoft">
    <div class="product-name">
      <p class="eyebrow">Database HealthCheck Platform</p>
      <h1>OMNIcheck HealthCheck Studio</h1>
      <p>地端資料庫健檢與報告產製平台 · v{PUBLIC_UI_VERSION}</p>
    </div>
  </div>
  <div class="header-actions">
    <a class="classic-link active" href="/integrated">健檢作業</a>
    <a class="classic-link" href="/classic">傳統介面</a>
  </div>
</div></header>
<div class="workspace-strip"><div class="workspace-meta">
  <span class="workspace-tag">開發預覽版</span>
  <span>版本 {PUBLIC_UI_VERSION}</span><span>｜</span>
  <span>規則判定與正式報告仍由 M1～M10.1 Pipeline 執行</span>
</div></div>""",
    )
    .replace(
        "<main>",
        """<main>
  <div class="integration-notice">
    <strong>正式報告支援 EDB Postgres Advanced Server 與 PostgreSQL。</strong>
    此介面使用既有 M10.3.1 Pipeline；Primary、Topology、Scope、規則結果與 V4 Renderer 均未變更。
  </div>""",
        1,
    )
    .replace(
        """<label>資料庫產品 *
          <select id="product"><option>PostgreSQL</option><option value="EPAS">EDB Postgres Advanced Server</option></select>
        </label>""",
        """<label>資料庫產品 *
          <select id="product">
            <option value="EPAS">EDB Postgres Advanced Server</option>
            <option value="PostgreSQL">PostgreSQL</option>
          </select>
          <span class="product-note">資料庫邏輯層採 Primary-only；節點設定檔仍會比較 Primary、Standby 與 DR。</span>
        </label>""",
    )
    .replace(
        "</main>",
        r"""  <section id="sectionReviewWorkbench">
    <h2>Section 審核工作台</h2>
    <p class="muted">AI 只提供文字草稿；規則狀態、證據與 Scope 不會被改動。只有工程師核准的文字才會進入正式報告。</p>
    <div class="review-toolbar">
      <label>Job ID<input id="reviewJobId" placeholder="完成案件後會自動帶入，也可貼上 Job ID"></label>
      <label>工程師／審核者<input id="reviewActor" value="engineer"></label>
      <button type="button" class="secondary" id="loadSections">載入 Sections</button>
      <button type="button" class="primary" id="batchAIDrafts">產生已勾選 AI 草稿</button>
    </div>
    <div id="reviewProgress" class="review-progress hidden"></div>
    <div id="sectionCards"><p class="muted">尚未載入 Section。</p></div>
    <div class="actions">
      <button type="button" class="primary" id="renderApproved">依核准內容重新產報</button>
      <button type="button" class="primary" id="approveAllAndRender">整批核准 AI 草稿並產報</button>
    </div>
  </section>
</main>""",
    )
    .replace(
        "</script>",
        r"""
const reviewState = { sections:[], batchId:null };
function reviewMessage(text, kind='info') {
  const box=el('reviewProgress'); box.textContent=text; box.className=`review-progress ${kind}`;
}
function currentNarrative(item) {
  return item.reviewed || item.ai_draft || item.deterministic;
}
function renderSectionCards() {
  const root=el('sectionCards'); root.replaceChildren();
  if (!reviewState.sections.length) { const p=document.createElement('p'); p.className='muted'; p.textContent='此案件沒有可審核的 Section。'; root.append(p); return; }
  reviewState.sections.forEach(item => {
    const card=document.createElement('article'); card.className='section-card'; card.dataset.itemId=item.item_id;
    const head=document.createElement('div'); head.className='section-card-head';
    const title=document.createElement('h3'); title.textContent=`${item.section_id}｜${item.check_id}`;
    const controls=document.createElement('div');
    const select=document.createElement('input'); select.type='checkbox'; select.className='ai-select';
    select.disabled=!['generated','ai_drafted'].includes(item.workflow_status);
    const badge=document.createElement('span'); badge.className=`status ${item.workflow_status}`;
    badge.textContent=`${item.workflow_status} · rev ${item.revision}`;
    controls.append(select,badge); head.append(title,controls); card.append(head);
    const meta=document.createElement('div'); meta.className='section-meta'; meta.textContent=`節點：${item.node}｜規則狀態：${item.status}｜Renderer：${item.selected_source}`; card.append(meta);
    const deterministic=document.createElement('details'); const summary=document.createElement('summary'); summary.textContent='查看 deterministic 原文';
    const fixed=document.createElement('div'); fixed.className='deterministic-box'; fixed.textContent=`觀察：${item.deterministic.observation}\n\n建議：${item.deterministic.recommendation}`;
    deterministic.append(summary,fixed); card.append(deterministic);
    const narrative=currentNarrative(item); const grid=document.createElement('div'); grid.className='narrative-grid';
    const observationLabel=document.createElement('label'); observationLabel.textContent='觀察／結論';
    const observation=document.createElement('textarea'); observation.className='review-observation'; observation.value=narrative.observation; observationLabel.append(observation);
    const recommendationLabel=document.createElement('label'); recommendationLabel.textContent='建議';
    const recommendation=document.createElement('textarea'); recommendation.className='review-recommendation'; recommendation.value=narrative.recommendation; recommendationLabel.append(recommendation);
    grid.append(observationLabel,recommendationLabel); card.append(grid);
    const actions=document.createElement('div'); actions.className='actions';
    const save=document.createElement('button'); save.type='button'; save.className='secondary'; save.textContent='儲存工程師修改';
    save.addEventListener('click',()=>saveReview(item,observation.value,recommendation.value));
    const approve=document.createElement('button'); approve.type='button'; approve.className='primary'; approve.textContent='核准'; approve.disabled=item.workflow_status!=='reviewed';
    approve.addEventListener('click',()=>approveSection(item)); actions.append(save,approve); card.append(actions); root.append(card);
  });
}
async function loadSections() {
  const jobId=el('reviewJobId').value.trim(); if (!jobId) { reviewMessage('請輸入 Job ID。','error'); return; }
  try { reviewState.sections=await api(`/api/jobs/${jobId}/sections`); renderSectionCards(); reviewMessage(`已載入 ${reviewState.sections.length} 個 Section。`,'ok'); }
  catch(error) { reviewMessage(error.message,'error'); }
}
async function saveReview(item,observation,recommendation) {
  try { await api(`/api/jobs/${el('reviewJobId').value.trim()}/sections/${item.item_id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:item.revision,actor:el('reviewActor').value.trim(),observation,recommendation})}); await loadSections(); }
  catch(error) { reviewMessage(error.message,'error'); }
}
async function approveSection(item) {
  try { await api(`/api/jobs/${el('reviewJobId').value.trim()}/sections/${item.item_id}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:item.revision,actor:el('reviewActor').value.trim()})}); await loadSections(); }
  catch(error) { reviewMessage(error.message,'error'); }
}
async function pollAIBatch(jobId,batchId) {
  for (;;) { const batch=await api(`/api/jobs/${jobId}/ai-draft-batches/${batchId}`); reviewMessage(`AI 批次：${batch.status}\n進度：${batch.completed_items}/${batch.total_items}｜成功 ${batch.succeeded_items}｜fallback ${batch.fallback_items}｜衝突 ${batch.conflict_items}`); if (['completed','partial','failed'].includes(batch.status)) return batch; await new Promise(resolve=>setTimeout(resolve,1500)); }
}
async function createAIBatch() {
  const jobId=el('reviewJobId').value.trim(); const actor=el('reviewActor').value.trim();
  const selected=[...document.querySelectorAll('.section-card')].filter(card=>card.querySelector('.ai-select').checked).map(card=>{ const item=reviewState.sections.find(value=>value.item_id===card.dataset.itemId); return {item_id:item.item_id,expected_revision:item.revision}; });
  if (!selected.length) { reviewMessage('請先勾選至少一個尚未核准的 Section。','error'); return; }
  try { const batch=await api(`/api/jobs/${jobId}/ai-draft-batches`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor,items:selected})}); reviewState.batchId=batch.batch_id; await pollAIBatch(jobId,batch.batch_id); await loadSections(); }
  catch(error) { reviewMessage(error.message,'error'); }
}
async function renderApproved() {
  const jobId=el('reviewJobId').value.trim();
  try { const result=await api(`/api/jobs/${jobId}/sections/render`,{method:'POST'}); reviewMessage(`重新產報完成：${result.policy}`,'ok'); showResult(await api(`/api/jobs/${jobId}`)); }
  catch(error) { reviewMessage(error.message,'error'); }
}
async function approveAllAndRender() {
  const jobId=el('reviewJobId').value.trim(); const actor=el('reviewActor').value.trim();
  if (!jobId || !actor) { reviewMessage('請輸入 Job ID 與審核者。','error'); return; }
  try {
    const result=await api(`/api/jobs/${jobId}/sections/approve-all`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor})});
    await api(`/api/jobs/${jobId}/sections/render`,{method:'POST'});
    await loadSections(); reviewMessage(`已整批核准 ${result.approved} 個 AI 草稿並重新產報。`,'ok'); showResult(await api(`/api/jobs/${jobId}`));
  } catch(error) { reviewMessage(error.message,'error'); }
}
el('loadSections').addEventListener('click',loadSections);
el('batchAIDrafts').addEventListener('click',createAIBatch);
el('renderApproved').addEventListener('click',renderApproved);
el('approveAllAndRender').addEventListener('click',approveAllAndRender);
</script>""",
    )
    .replace(
        "el('resultSection').scrollIntoView({behavior:'smooth'});",
        "el('reviewJobId').value=job.job_id; el('resultSection').scrollIntoView({behavior:'smooth'});",
    )
)
