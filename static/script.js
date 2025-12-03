// UI interactions and fetch to /analyze
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const analyzeBtn = document.getElementById("analyzeBtn");
const resetBtn = document.getElementById("resetBtn");
const summarySection = document.getElementById("summarySection");
const checklistSection = document.getElementById("checklistSection");
const riskPanel = document.getElementById("riskPanel");
const checklistTableBody = document.querySelector("#checklistTable tbody");
const downloadCSVBtn = document.getElementById("downloadCSV");
const riskBadges = document.getElementById("riskBadges");
const suggestionsList = document.getElementById("suggestionsList");
const searchBox = document.getElementById("searchBox");
const riskFilter = document.getElementById("riskFilter");

let currentAnalysis = null;

["dragenter","dragover"].forEach(e=>{
  dropzone.addEventListener(e, ev=>{
    ev.preventDefault(); ev.stopPropagation();
    dropzone.style.borderColor = "#cfe6ff";
  });
});
["dragleave","drop"].forEach(e=>{
  dropzone.addEventListener(e, ev=>{
    ev.preventDefault(); ev.stopPropagation();
    dropzone.style.borderColor = "";
  });
});
dropzone.addEventListener("drop", ev=>{
  const files = ev.dataTransfer.files;
  fileInput.files = files;
  renderFileList();
});

fileInput.addEventListener("change", ()=>{
  renderFileList();
});

resetBtn.addEventListener("click", ()=>{
  fileInput.value = "";
  fileList.innerHTML = "";
  summarySection.style.display = "none";
  checklistSection.style.display = "none";
  riskPanel.style.display = "none";
  downloadCSVBtn.style.display = "none";
  currentAnalysis = null;
});

function renderFileList(){
  const files = fileInput.files;
  fileList.innerHTML = "";
  if (!files || files.length===0){
    fileList.innerHTML = "<div style='color:#666'>No files selected</div>";
    return;
  }
  for (let i=0;i<files.length;i++){
    const f = files[i];
    const div = document.createElement("div");
    div.className = "file-item";
    div.innerHTML = `<div>${f.name}</div><div style="color:#666">${Math.round(f.size/1024)} KB</div>`;
    fileList.appendChild(div);
  }
}

async function analyzeFiles(){
  const files = fileInput.files;
  if (!files || files.length===0){
    alert("Please select files to analyze.");
    return;
  }
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";

  const fd = new FormData();
  for (let i=0;i<files.length;i++){
    fd.append("files[]", files[i]);
  }

  try {
    const resp = await fetch("/analyze", {method:"POST", body: fd});
    if (!resp.ok){
      const txt = await resp.text();
      alert("Server error: " + txt);
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Analyze Documents 🔍";
      return;
    }
    const data = await resp.json();
    currentAnalysis = data.analysis;
    renderAnalysis(currentAnalysis);
    downloadCSVBtn.style.display = "inline-block";
    downloadCSVBtn.onclick = ()=> { window.location = data.csv; };
  } catch (err) {
    alert("Network or server error: " + err);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze Documents 🔍";
  }
}

function renderAnalysis(analysis){
  // summary section
  summarySection.style.display = "block";
  const grid = document.getElementById("summaryGrid");
  grid.innerHTML = "";
  analysis.files.forEach(f=>{
    const div = document.createElement("div");
    div.className = "summary-card";
    let html = `<strong>${f.filename}</strong>`;
    if (!f.supported){
      html += ` <div style="color:#c0421b">Rejected: ${f.note || 'unsupported'}</div>`;
    } else {
      html += `<div style="color:#374151;margin-top:6px">${f.summary || 'No summary available'}</div>`;
      html += `<div style="font-size:12px;color:#6b7280;margin-top:8px">Domain: ${f.domain}</div>`;
      if (f.obligations && f.obligations.length>0){
        html += `<div style="margin-top:8px"><em>${f.obligations.length} obligation(s) found</em></div>`;
      } else {
        html += `<div style="margin-top:8px;color:#6b7280"><em>No explicit obligations detected</em></div>`;
      }
    }
    div.innerHTML = html;
    grid.appendChild(div);
  });

  // checklist
  checklistSection.style.display = "block";
  renderChecklistTable(analysis.combined_checklist);

  // risk panel
  riskPanel.style.display = "block";
  renderRiskPanel(analysis.combined_checklist);

  // search & filter handlers
  searchBox.oninput = ()=> filterChecklist();
  riskFilter.onchange = ()=> filterChecklist();
}

function renderChecklistTable(items){
  checklistTableBody.innerHTML = "";
  if (!items || items.length===0){
    checklistTableBody.innerHTML = "<tr><td colspan='6' style='color:#666'>No obligations detected</td></tr>";
    return;
  }
  for (let it of items){
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.id}</td>
      <td>${it.document}</td>
      <td>${escapeHtml(it.sentence)}</td>
      <td>${(it.dates||[]).join(", ")}</td>
      <td>${it.risk}</td>
      <td>${it.status}</td>`;
    checklistTableBody.appendChild(tr);
  }
}

function renderRiskPanel(items){
  // compute counts
  const counts = {High:0, Medium:0, Low:0};
  for (let it of items || []){
    counts[it.risk] = (counts[it.risk]||0) + 1;
  }
  riskBadges.innerHTML = `
    <div class="badge">🔴 High: ${counts.High}</div>
    <div class="badge">🟠 Medium: ${counts.Medium}</div>
    <div class="badge">🟢 Low: ${counts.Low}</div>
  `;

  // basic suggestions (gaps)
  suggestionsList.innerHTML = "";
  // simple rule: if no privacy doc found -> suggest add retention clause
  const domains = new Set((currentAnalysis.files||[]).map(f=>f.domain));
  if (!Array.from(domains).includes("Data Privacy")){
    const li = document.createElement("li"); li.textContent = "No Data Privacy document detected — consider adding a privacy policy.";
    suggestionsList.appendChild(li);
  }
  if (!Array.from(domains).includes("Safety / Environmental")){
    const li = document.createElement("li"); li.textContent = "No Safety / Environmental document detected — consider safety procedures.";
    suggestionsList.appendChild(li);
  }
  // list any high risk sentences
  for (let it of items || []){
    if (it.risk === "High"){
      const li = document.createElement("li"); li.textContent = `High-risk clause in ${it.document}: "${it.sentence.slice(0,120)}..."`;
      suggestionsList.appendChild(li);
    }
  }
}

function filterChecklist(){
  const q = (searchBox.value||"").toLowerCase().trim();
  const rf = (riskFilter.value||"All");
  const rows = checklistTableBody.querySelectorAll("tr");
  for (let r of rows){
    const txt = r.textContent.toLowerCase();
    const risk = r.children[4].textContent;
    const matchesQ = !q || txt.indexOf(q) >= 0;
    const matchesR = (rf === "All") || (risk === rf);
    r.style.display = (matchesQ && matchesR) ? "" : "none";
  }
}

function escapeHtml(s){
  if (!s) return "";
  return s.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

// wire analyze button
analyzeBtn.addEventListener("click", analyzeFiles);
renderFileList();
