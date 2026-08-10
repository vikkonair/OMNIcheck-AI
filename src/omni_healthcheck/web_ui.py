"""Self-contained M9.2 browser UI served by FastAPI."""

INDEX_HTML = r"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OMNIcheck AI</title>
  <style>
    :root { color-scheme: light; font-family: Arial, "Noto Sans TC", sans-serif;
      --brand:#087c91; --brand-dark:#075d6c; --ink:#18323f; --muted:#69808b;
      --line:#d8e3e8; --bg:#f3f7f9; --ok:#177245; --warn:#a46608; --bad:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); }
    header { padding:22px max(24px, 5vw); color:white; background:var(--brand); }
    header h1 { margin:0 0 4px; font-size:25px; }
    header p { margin:0; opacity:.9; }
    main { max-width:1180px; margin:24px auto; padding:0 20px 60px; }
    .steps { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px; }
    .step { padding:8px 12px; border:1px solid var(--line); border-radius:999px;
      background:white; color:var(--muted); font-size:14px; }
    .step.active { color:white; background:var(--brand); border-color:var(--brand); }
    section { background:white; padding:22px; margin-bottom:18px; border-radius:12px;
      box-shadow:0 4px 18px #19384512; }
    h2 { margin:0 0 6px; font-size:20px; }
    h3 { margin:18px 0 10px; font-size:16px; }
    p { line-height:1.55; }
    .muted { color:var(--muted); }
    .grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:14px; }
    label { display:block; font-size:14px; font-weight:600; }
    input, select { width:100%; margin-top:6px; padding:10px 11px; border:1px solid #bfcdd3;
      border-radius:7px; background:white; color:var(--ink); font:inherit; }
    input:focus, select:focus, button:focus { outline:3px solid #67bed055; outline-offset:1px; }
    input[type=checkbox] { width:auto; margin:0 6px 0 0; }
    button { border:0; border-radius:7px; padding:10px 15px; font:inherit; cursor:pointer; }
    button.primary { color:white; background:var(--brand); }
    button.primary:hover { background:var(--brand-dark); }
    button.secondary { color:var(--ink); background:#e7f0f3; }
    button.danger { color:var(--bad); background:#fff0ee; }
    button:disabled { cursor:not-allowed; opacity:.55; }
    .actions { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:18px; }
    .node { border-top:1px solid var(--line); padding:16px 0; }
    .node:first-child { border-top:0; }
    .node-head { display:grid; grid-template-columns:2fr 1fr auto; gap:10px; align-items:end; }
    .services { display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; }
    .services label { font-weight:400; }
    .drop { display:block; border:2px dashed #9eb7c1; padding:24px; border-radius:10px;
      text-align:center; background:#f9fbfc; cursor:pointer; }
    .drop:hover { border-color:var(--brand); }
    .drop input { position:absolute; width:1px; height:1px; opacity:0; }
    .summary { margin-top:12px; padding:11px 13px; border-radius:7px; background:#edf5f7; }
    .topology-review { margin-top:14px; padding:14px; border:1px solid var(--line);
      border-radius:8px; background:#f9fbfc; white-space:pre-line; line-height:1.55; }
    .message { display:none; margin-top:14px; padding:11px 13px; border-radius:7px; white-space:pre-wrap; }
    .message.show { display:block; }
    .message.info { background:#edf5f7; }
    .message.ok { color:var(--ok); background:#edf8f2; }
    .message.error { color:var(--bad); background:#fff0ee; }
    .progress { height:9px; margin-top:12px; overflow:hidden; border-radius:99px; background:#dce8ec; }
    .progress span { display:block; width:0; height:100%; background:var(--brand); transition:width .25s; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:10px 8px; text-align:left; border-bottom:1px solid var(--line); }
    th { color:var(--muted); font-size:13px; }
    .status { display:inline-block; padding:4px 8px; border-radius:999px; background:#e8f0f3; font-size:13px; }
    .status.succeeded { color:var(--ok); background:#e4f5eb; }
    .status.failed { color:var(--bad); background:#ffebe8; }
    .download-list { display:grid; gap:8px; margin-top:12px; }
    .download-list a { display:flex; justify-content:space-between; padding:10px 12px;
      border:1px solid var(--line); border-radius:7px; color:var(--brand-dark); text-decoration:none; }
    .hidden { display:none !important; }
    @media (max-width:720px) {
      .grid, .node-head { grid-template-columns:1fr; }
      table { display:block; overflow-x:auto; }
    }
  </style>
</head>
<body>
<header><h1>OMNIcheck AI</h1><p>On-premises Database Health Check</p></header>
<main>
  <div class="steps" aria-label="操作步驟">
    <span class="step active" id="step1">1 案件資料</span>
    <span class="step" id="step2">2 節點架構</span>
    <span class="step" id="step3">3 上傳與執行</span>
    <span class="step" id="step4">4 下載結果</span>
  </div>

  <form id="jobForm">
    <section>
      <h2>案件資料</h2>
      <p class="muted">填寫本次健檢的基本資料，不需要再編輯 JSON。</p>
      <div class="grid">
        <label>客戶名稱 *<input id="customer" required placeholder="例如：範例科技"></label>
        <label>系統名稱<input id="systemName" placeholder="例如：ERP Production"></label>
        <label>健檢期間 *<input id="period" required placeholder="例如：2026-H2"></label>
        <label>工程師<input id="engineer" value="XXX"></label>
        <label>資料庫產品 *
          <select id="product"><option>PostgreSQL</option><option value="EPAS">EDB Postgres Advanced Server</option></select>
        </label>
        <label>健檢類型
          <select id="firstHealthcheck"><option value="true">首次健檢</option><option value="false">定期健檢</option></select>
        </label>
      </div>
    </section>

    <section>
      <h2>節點架構</h2>
      <p class="muted">至少需要一台 Primary；Standby、DR、Witness 可依客戶實際架構新增。</p>
      <div id="nodes"></div>
      <button type="button" class="secondary" id="addNode">＋ 新增節點</button>
      <p class="muted">若本次要檢查備份，請在實際執行 pgBackRest 或 Barman 的節點勾選一個主要備份來源。</p>
    </section>

    <section>
      <h2>健檢資料</h2>
      <p class="muted">請選擇搜集回來的整個資料夾，系統會保留其中的節點與分類路徑。</p>
      <label class="drop" id="dropZone">
        <strong>選擇整包健檢資料</strong><br><span class="muted">點擊選擇資料夾；也可拖曳多個檔案到此處</span>
        <input id="folderInput" type="file" webkitdirectory directory multiple>
      </label>
      <div class="summary" id="fileSummary">尚未選擇資料</div>
      <div class="actions">
        <button type="button" class="secondary" id="discoverTopology">分析節點架構</button>
      </div>
      <div class="topology-review" id="topologyReview">選擇資料後，系統會提出節點與角色候選。</div>
      <div id="evidenceMappings"></div>
      <div class="actions">
        <label><input type="checkbox" id="topologyConfirmed" disabled>我已核對並確認上述節點架構</label>
      </div>
      <div class="actions">
        <label><input type="checkbox" id="docx" checked>產生 DOCX</label>
        <label><input type="checkbox" id="pdf" checked>產生 PDF</label>
      </div>
      <div class="actions">
        <button type="submit" class="primary" id="startButton">建立案件並開始健檢</button>
      </div>
      <div class="progress hidden" id="progress"><span id="progressBar"></span></div>
      <div class="message" id="runMessage" role="status"></div>
    </section>
  </form>

  <section class="hidden" id="resultSection">
    <h2>健檢結果</h2>
    <div id="resultSummary"></div>
    <div class="download-list" id="downloads"></div>
  </section>

  <section>
    <h2>案件列表</h2>
    <p class="muted">可查看本機已建立的案件與執行狀態。</p>
    <table><thead><tr><th>客戶</th><th>期間</th><th>產品</th><th>狀態</th><th>輸入</th><th></th></tr></thead>
      <tbody id="jobs"><tr><td colspan="6">載入中…</td></tr></tbody></table>
  </section>
</main>
<script>
const state = { options:null, nodes:[{hostname:'', role:'Primary', services:[]}], files:[], jobId:null, discovery:null, evidenceMappings:[] };
const el = id => document.getElementById(id);

function setMessage(text, kind='info') {
  const box = el('runMessage'); box.textContent = text; box.className = `message show ${kind}`;
}
function setProgress(value) {
  el('progress').classList.remove('hidden'); el('progressBar').style.width = `${value}%`;
}
function formatError(body) {
  if (!body) return '發生未知錯誤';
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map(x => x.msg).join('\n');
  return JSON.stringify(body);
}
async function api(url, options={}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(formatError(body));
  return body;
}

function renderNodes() {
  const root = el('nodes'); root.replaceChildren();
  state.nodes.forEach((node, index) => {
    const row = document.createElement('div'); row.className = 'node';
    const head = document.createElement('div'); head.className = 'node-head';
    const hostLabel = document.createElement('label'); hostLabel.textContent = `節點主機名稱 ${index + 1} *`;
    const host = document.createElement('input'); host.required = true; host.placeholder = '例如：db-primary'; host.value = node.hostname;
    host.addEventListener('input', () => { const previous=node.hostname; node.hostname=host.value; state.evidenceMappings.filter(item => item.node===previous).forEach(item => item.node=node.hostname); });
    host.addEventListener('change', () => renderEvidenceMappings()); hostLabel.append(host);
    const roleLabel = document.createElement('label'); roleLabel.textContent = '角色 *';
    const role = document.createElement('select');
    (state.options?.roles || ['Primary','Standby','DR','Witness']).forEach(value => {
      const option = document.createElement('option'); option.value = value; option.textContent = value;
      option.selected = value === node.role; role.append(option);
    });
    role.addEventListener('change', () => { node.role = role.value; node.services = node.services.filter(service => serviceAllowed(service, node.role)); renderNodes(); renderEvidenceMappings(); });
    roleLabel.append(role);
    const remove = document.createElement('button'); remove.type='button'; remove.className='danger'; remove.textContent='移除';
    remove.disabled = state.nodes.length === 1; remove.addEventListener('click', () => { state.nodes.splice(index,1); renderNodes(); });
    head.append(hostLabel, roleLabel, remove); row.append(head);
    const services = document.createElement('div'); services.className='services';
    (state.options?.services || []).forEach(service => {
      if (!serviceAllowed(service.name, node.role)) return;
      const label = document.createElement('label'); const check = document.createElement('input'); check.type='checkbox';
      check.checked = node.services.includes(service.name);
      check.addEventListener('change', () => check.checked ? node.services.push(service.name) : node.services.splice(node.services.indexOf(service.name),1));
      label.append(check, document.createTextNode(service.name)); services.append(label);
    });
    row.append(services); root.append(row);
  });
}
function renderEvidenceMappings() {
  const root=el('evidenceMappings'); root.replaceChildren();
  if (!state.evidenceMappings.length) return;
  const title=document.createElement('h3'); title.textContent='Database Output 來源確認'; root.append(title);
  const note=document.createElement('p'); note.className='muted'; note.textContent='系統已辨識資料庫輸出格式，但無法只靠內容確認來源主機。請指定實際執行健檢 SQL 的節點。'; root.append(note);
  state.evidenceMappings.forEach(mapping => {
    const row=document.createElement('div'); row.className='node-head';
    const path=document.createElement('div'); path.textContent=mapping.path;
    const label=document.createElement('label'); label.textContent='來源節點 *';
    const select=document.createElement('select');
    state.nodes.forEach(node => { const option=document.createElement('option'); option.value=node.hostname; option.textContent=`${node.hostname}（${node.role}）`; option.selected=node.hostname===mapping.node; select.append(option); });
    select.addEventListener('change',()=>mapping.node=select.value); label.append(select); row.append(path,label); root.append(row);
  });
}
function serviceAllowed(name, role) {
  const service = state.options?.services.find(item => item.name === name);
  return !service || service.allowed_roles.length === 0 || service.allowed_roles.includes(role);
}
function selectedPath(file) {
  const parts = (file.webkitRelativePath || file.name).replaceAll('\\','/').split('/').filter(Boolean);
  if (parts.length > 1) parts.shift();
  return parts.join('/');
}
function updateFiles(files) {
  state.files = Array.from(files).filter(file => file.size >= 0 && file.name !== '.DS_Store');
  state.discovery=null; state.evidenceMappings=[]; renderEvidenceMappings(); el('topologyConfirmed').checked=false; el('topologyConfirmed').disabled=true;
  if (!state.files.length) { el('fileSummary').textContent='尚未選擇資料'; return; }
  const bytes = state.files.reduce((sum,file) => sum + file.size, 0);
  el('fileSummary').textContent = `已選擇 ${state.files.length} 個檔案，共 ${(bytes/1024/1024).toFixed(2)} MB`;
  el('step3').classList.add('active');
  discoverTopology();
}
function buildConfig() {
  if (!state.discovery || !el('topologyConfirmed').checked) throw new Error('請先分析資料並確認節點架構。');
  const nodes=state.nodes.map(node => ({...node, hostname:node.hostname.trim()}));
  const backupCandidates=nodes.flatMap(node => node.services
    .filter(service => service === 'pgBackRest' || service === 'Barman')
    .map(service => ({provider:service === 'Barman' ? 'barman' : 'pgbackrest', node:node.hostname})));
  if (backupCandidates.length > 1) throw new Error('目前一個案件只能指定一個主要備份來源，請只保留一個 pgBackRest 或 Barman。');
  const config={
    customer:el('customer').value.trim(), system_name:el('systemName').value.trim() || null,
    period:el('period').value.trim(), engineer:el('engineer').value.trim() || 'XXX', product:el('product').value,
    first_healthcheck:el('firstHealthcheck').value === 'true', nodes,
    scope:{include_os_from_all_nodes:true, database_primary_only:true},
    report:{template:'omni-v4', output_docx:el('docx').checked, output_pdf:el('pdf').checked},
    ai:{enabled:false, provider:'disabled'}
  };
  config.topology_confirmation={source:'deterministic_discovery',confirmed:true,
    discovery_schema_version:state.discovery.schema_version,
    nodes:state.discovery.nodes.map(node => ({hostname:node.hostname,
      suggested_role:node.suggested_role,confidence:node.confidence,
      role_evidence:node.role_evidence,conflicts:node.conflicts}))};
  if (backupCandidates.length === 1) config.backup=backupCandidates[0];
  if (state.evidenceMappings.length) config.evidence_mappings=state.evidenceMappings.map(item => ({path:item.path,node:item.node,domain:'database',source:'operator_confirmed'}));
  return config;
}
async function discoverTopology() {
  if (!state.files.length) { setMessage('請先選擇整包健檢資料。','error'); return; }
  const button=el('discoverTopology'); button.disabled=true;
  el('topologyReview').textContent='正在分析檔名、OS、EFM、PEM 與備份服務訊號…';
  el('topologyConfirmed').checked=false; el('topologyConfirmed').disabled=true;
  try {
    const form=new FormData(); const textExtensions=new Set(['txt','log','out','sql','csv','tsv','conf']);
    state.files.forEach(file => {
      const extension=file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
      const sample=textExtensions.has(extension) ? file.slice(0,512*1024) : new Blob([]);
      form.append('files',sample,selectedPath(file));
    });
    const result=await api('/api/topology/discover',{method:'POST',body:form}); state.discovery=result;
    state.nodes=result.nodes.map(node => ({hostname:node.hostname,
      role:node.suggested_role === 'Unknown' ? 'Standby' : node.suggested_role,
      services:node.services.filter(service => serviceAllowed(service,node.suggested_role))}));
    state.evidenceMappings=(result.evidence_candidates || []).map(item => ({path:item.path,node:item.suggested_node || state.nodes.find(node => node.role==='Primary')?.hostname || ''}));
    renderNodes(); renderEvidenceMappings(); el('step2').classList.add('active'); el('topologyConfirmed').disabled=false;
    const details=result.nodes.map(node => `${node.hostname} → ${node.suggested_role}（${node.confidence}）${node.services.length ? `；${node.services.join('、')}` : ''}`).join('\n');
    const warnings=result.warnings.length ? `\n注意：${result.warnings.join('；')}` : '';
    el('topologyReview').textContent=`找到 ${result.summary.node_count} 台節點：\n${details}${warnings}\n請核對上方節點角色後勾選確認。`;
  } catch(error) { state.discovery=null; el('topologyReview').textContent=`分析失敗：${error.message}`; setMessage(error.message,'error'); }
  finally { button.disabled=false; }
}
async function uploadFiles(jobId) {
  const chunkSize = 50;
  for (let start=0; start<state.files.length; start+=chunkSize) {
    const batch=state.files.slice(start,start+chunkSize); const form=new FormData();
    batch.forEach(file => form.append('files', file, selectedPath(file)));
    await api(`/api/jobs/${jobId}/files`, {method:'POST', body:form});
    setProgress(15 + Math.round(((start + batch.length) / state.files.length) * 45));
    setMessage(`正在上傳資料：${Math.min(start+batch.length,state.files.length)} / ${state.files.length}`);
  }
}
async function pollJob(jobId) {
  for (;;) {
    const job=await api(`/api/jobs/${jobId}`);
    if (job.status === 'succeeded' || job.status === 'failed') return job;
    setProgress(job.status === 'running' ? 82 : 70); setMessage(job.status === 'running' ? 'Pipeline 執行中，正在分析資料並組裝報告…' : '案件已排入處理…');
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}
async function startJob(event) {
  event.preventDefault();
  if (!state.files.length) { setMessage('請先選擇整包健檢資料。','error'); return; }
  const button=el('startButton'); button.disabled=true; el('resultSection').classList.add('hidden');
  try {
    setProgress(5); setMessage('正在建立案件…');
    const job=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(buildConfig())});
    state.jobId=job.job_id; setProgress(15); await uploadFiles(job.job_id);
    setMessage('資料上傳完成，正在啟動健檢…'); await api(`/api/jobs/${job.job_id}/run`,{method:'POST'});
    const result=await pollJob(job.job_id); setProgress(100); showResult(result);
    setMessage(result.status === 'succeeded' ? '健檢完成，可以下載結果。' : `健檢失敗：${result.error || '請查看案件錯誤'}`, result.status === 'succeeded' ? 'ok' : 'error');
    await refreshJobs();
  } catch(error) { setMessage(error.message,'error'); }
  finally { button.disabled=false; }
}
function showResult(job) {
  el('resultSection').classList.remove('hidden'); el('step4').classList.add('active');
  el('resultSummary').textContent = `${job.customer}｜${job.period}｜狀態：${job.status}`;
  const list=el('downloads'); list.replaceChildren();
  (job.outputs || []).forEach(output => {
    const link=document.createElement('a'); link.href=`/api/jobs/${job.job_id}/outputs/${encodeURIComponent(output.name)}`;
    link.download=output.name; const name=document.createElement('span'); name.textContent=output.name;
    const size=document.createElement('span'); size.textContent=`${(output.size/1024).toFixed(1)} KB`; link.append(name,size); list.append(link);
  });
  el('resultSection').scrollIntoView({behavior:'smooth'});
}
async function refreshJobs() {
  try {
    const jobs=await api('/api/jobs'); const body=el('jobs'); body.replaceChildren();
    if (!jobs.length) { const row=body.insertRow(); const cell=row.insertCell(); cell.colSpan=6; cell.textContent='尚無案件'; return; }
    jobs.forEach(job => {
      const row=body.insertRow(); [job.customer,job.period,job.product].forEach(value => { const cell=row.insertCell(); cell.textContent=value || '—'; });
      const statusCell=row.insertCell(); const status=document.createElement('span'); status.className=`status ${job.status}`; status.textContent=job.status; statusCell.append(status);
      row.insertCell().textContent=String(job.input_files || 0);
      const action=row.insertCell(); const button=document.createElement('button'); button.type='button'; button.className='secondary'; button.textContent='查看';
      button.addEventListener('click', async () => showResult(await api(`/api/jobs/${job.job_id}`))); action.append(button);
    });
  } catch(error) { el('jobs').textContent=`載入失敗：${error.message}`; }
}

el('addNode').addEventListener('click', () => { state.nodes.push({hostname:'',role:'Standby',services:[]}); renderNodes(); el('step2').classList.add('active'); });
el('discoverTopology').addEventListener('click', discoverTopology);
el('folderInput').addEventListener('change', event => updateFiles(event.target.files));
el('dropZone').addEventListener('dragover', event => event.preventDefault());
el('dropZone').addEventListener('drop', event => { event.preventDefault(); if (event.dataTransfer.files.length) updateFiles(event.dataTransfer.files); });
el('jobForm').addEventListener('submit', startJob);
(async () => { try { state.options=await api('/api/config-options'); } catch (_) {} renderNodes(); refreshJobs(); })();
</script>
</body>
</html>"""
