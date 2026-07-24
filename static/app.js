const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const backendEl = document.getElementById("backend");
const modeEl = document.getElementById("mode");
const modelEl = document.getElementById("model");
const pullBtn = document.getElementById("pullModel");
const ingestBtn = document.getElementById("ingestRag");
const preloadBtn = document.getElementById("preloadModel");
const trainBtn = document.getElementById("trainUnsloth");
const settingsBtn = document.getElementById("settingsBtn");
const topSettingsBtn = document.getElementById("topSettingsBtn");
const hermesNewSessionBtn = document.getElementById("hermesNewSession");
const settingsModal = document.getElementById("settingsModal");
const settingsForm = document.getElementById("settingsForm");

// Migrate legacy HackGPT localStorage keys once after brand rename
(function migrateSecuraIqStorage() {
  try {
    const pairs = [
      ["hackgpt.auth.token", "securaiq.auth.token"],
      ["hackgpt.theme", "securaiq.theme"],
      ["hackgpt.chats.v1", "securaiq.chats.v1"],
      ["hackgpt.kpi.snap", "securaiq.kpi.snap"],
      ["hackgpt.checklist.integrations", "securaiq.checklist.integrations"],
    ];
    for (const [from, to] of pairs) {
      if (!localStorage.getItem(to)) {
        const v = localStorage.getItem(from);
        if (v != null) localStorage.setItem(to, v);
      }
    }
  } catch (_) {
    /* ignore */
  }
})();
const settingsTrainBtn = document.getElementById("settingsTrainBtn");
const hermesRefreshStatusBtn = document.getElementById("hermesRefreshStatus");
const finetuneHint = document.getElementById("finetuneHint");
const lanTipEl = document.getElementById("lanTip");
const menuToggle = document.getElementById("menuToggle");
const sidebarEl = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const controlsEl = document.getElementById("controls");
const quickEl = document.getElementById("quickPrompts");
const emptyStateEl = document.getElementById("emptyState");
const newChatBtn = document.getElementById("newChatBtn");
const chatListEl = document.getElementById("chatList");
const topbarChatTitleEl = document.getElementById("topbarChatTitle");
const topbarModeEl = document.getElementById("topbarMode");
const themeToggleBtn = document.getElementById("themeToggle");
const themeToggleTopBtn = document.getElementById("themeToggleTop");
const themeToggleLabel = document.getElementById("themeToggleLabel");
const metaThemeColor = document.getElementById("metaThemeColor");
const ragEl = document.getElementById("useRag");
const webSearchEl = document.getElementById("useWebSearch");
const netAssessEl = document.getElementById("useNetAssess");
const localToolsEl = document.getElementById("useLocalTools");
const authorizedTargetEl = document.getElementById("authorizedTarget");
const targetIpEl = document.getElementById("targetIp");
const toolsStatusEl = document.getElementById("toolsStatus");
const statusEl = document.getElementById("status");
const liveBarEl = document.getElementById("liveBar");
const livePhaseEl = document.getElementById("livePhase");
const liveMetaEl = document.getElementById("liveMeta");
const liveActivityEl = document.getElementById("liveActivity");
const engagementSelectEl = document.getElementById("engagementSelect");
const newEngagementBtn = document.getElementById("newEngagementBtn");
const authBtn = document.getElementById("authBtn");
const authModal = document.getElementById("authModal");
const authForm = document.getElementById("authForm");
const uploadBtn = document.getElementById("uploadBtn");
const fileUploadInput = document.getElementById("fileUploadInput");
const exportMdBtn = document.getElementById("exportMdBtn");
const emptyLeadEl = document.getElementById("emptyLead");
const toolsPaletteEl = document.getElementById("toolsPalette");
const toolsPaletteGridEl = document.getElementById("toolsPaletteGrid");
const toolsPaletteOutEl = document.getElementById("toolsPaletteOut");

/** Selected cyber tool ids for chat + /api/tools/run */
let selectedTools = [];
let toolsCatalogCache = [];
window.getSelectedTools = () => selectedTools.slice();
window.setSelectedTools = (ids) => {
  selectedTools = Array.isArray(ids) ? ids.filter(Boolean) : [];
  syncToolsPaletteSelection();
  updateToolsChipState();
};
const attachBtn = document.getElementById("attachBtn");
const chatAttachInput = document.getElementById("chatAttachInput");
const attachChipsEl = document.getElementById("attachChips");
const composerEl = document.getElementById("composer");
/** @type {{ file: File, id?: string }[]} */
let pendingAttachments = [];
const MAX_CHAT_ATTACHMENTS = 8;
const gapBtn = document.getElementById("gapBtn");
const dashboardBtn = document.getElementById("dashboardBtn");
const riskBtn = document.getElementById("riskBtn");
const vulnBtn = document.getElementById("vulnBtn");
const assetBtn = document.getElementById("assetBtn");
const remBtn = document.getElementById("remBtn");
const playbookBtn = document.getElementById("playbookBtn");
const campaignBtn = document.getElementById("campaignBtn");
const gapModal = document.getElementById("gapModal");
const gapForm = document.getElementById("gapForm");
const gapResult = document.getElementById("gapResult");
const dashModal = document.getElementById("dashModal");
const dashBody = document.getElementById("dashBody");
const riskModal = document.getElementById("riskModal");
const riskForm = document.getElementById("riskForm");
const riskList = document.getElementById("riskList");
const vulnModal = document.getElementById("vulnModal");
const vulnList = document.getElementById("vulnList");
const vulnFileInput = document.getElementById("vulnFileInput");
const assetModal = document.getElementById("assetModal");
const assetForm = document.getElementById("assetForm");
const assetList = document.getElementById("assetList");
const remModal = document.getElementById("remModal");
const remBoard = document.getElementById("remBoard");
const playbookModal = document.getElementById("playbookModal");
const playbookForm = document.getElementById("playbookForm");
const playbookList = document.getElementById("playbookList");
const campaignModal = document.getElementById("campaignModal");
const campaignForm = document.getElementById("campaignForm");
const campaignList = document.getElementById("campaignList");
const AUTH_TOKEN_KEY = "securaiq.auth.token";
let authToken = localStorage.getItem(AUTH_TOKEN_KEY) || "";
let serverChatId = null;
let authEnabled = false;
const setupPanelEl = document.getElementById("setupPanel");
const setupTitleEl = document.getElementById("setupTitle");
const setupTextEl = document.getElementById("setupText");
const setupPrimaryEl = document.getElementById("setupPrimary");
const setupDismissEl = document.getElementById("setupDismiss");
/** @type {"" | "copy" | "preload" | "settings" | "docs"} */
let setupAction = "";
let setupDismissedKey = sessionStorage.getItem("setupDismissed") || "";

const CHAT_STORE_KEY = "securaiq.chats.v1";
const CHAT_STORE_LEGACY = "hackgpt.chats.v1";
function authHeaders(extra = {}) {
  const h = { ...extra };
  if (authToken) h.Authorization = `Bearer ${authToken}`;
  return h;
}
window.authHeaders = authHeaders;

async function refreshAuthStatus() {
  try {
    const res = await fetch("/api/auth/status", { headers: authHeaders() });
    const data = await res.json();
    authEnabled = Boolean(data.auth_enabled);
    const hint = document.getElementById("authStatusHint");
    if (hint) {
      if (!authEnabled) hint.textContent = "Auth disabled (open local mode). Enable AUTH_ENABLED for team use.";
      else if (data.user) hint.textContent = `Signed in as ${data.user.username} (${data.user.role})`;
      else hint.textContent = "Auth required — login or register.";
    }
    if (authBtn) authBtn.textContent = data.user && authEnabled ? `Account (${data.user.username})` : "Account";
  } catch {
    /* ignore */
  }
}

function openAuth() {
  authModal?.classList.remove("hidden");
  refreshAuthStatus();
}
function closeAuth() {
  authModal?.classList.add("hidden");
}

async function loadEngagements() {
  if (!engagementSelectEl) return;
  try {
    const res = await fetch("/api/engagements", { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const cur = engagementSelectEl.value;
    engagementSelectEl.innerHTML = '<option value="">Local (no engagement)</option>';
    for (const e of data.engagements || []) {
      const opt = document.createElement("option");
      opt.value = e.id;
      opt.textContent = e.name;
      engagementSelectEl.appendChild(opt);
    }
    if (cur) engagementSelectEl.value = cur;
  } catch {
    /* ignore */
  }
}

async function ensureServerChat() {
  if (serverChatId) return serverChatId;
  const body = {
    title: "New chat",
    mode: modeEl?.value || "default",
    engagement_id: engagementSelectEl?.value || null,
  };
  const res = await fetch("/api/chats", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  const chat = await res.json();
  serverChatId = chat.id;
  return serverChatId;
}

async function createEngagement() {
  const name = prompt("Engagement name (e.g. HTB lab / Client ACME)");
  if (!name) return;
  const scope = prompt("Scope notes (authorized targets / VPN)") || "";
  const res = await fetch("/api/engagements", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name, scope_notes: scope }),
  });
  if (!res.ok) {
    appendMessage("assistant", renderMarkdown(`**Engagement failed:** HTTP ${res.status}`), true);
    return;
  }
  const eng = await res.json();
  await loadEngagements();
  if (engagementSelectEl) engagementSelectEl.value = eng.id;
  appendMessage("assistant", renderMarkdown(`**Engagement created:** ${eng.name}`), true);
}

async function uploadFile() {
  const files = fileUploadInput?.files;
  if (!files?.length) return;
  for (const f of Array.from(files)) {
    await uploadOneFile(f, true);
  }
  if (fileUploadInput) fileUploadInput.value = "";
}

async function uploadOneFile(file, showToast) {
  const fd = new FormData();
  fd.append("file", file);
  const eng = engagementSelectEl?.value;
  const q = eng ? `?engagement_id=${encodeURIComponent(eng)}&ingest=true` : "?ingest=true";
  const res = await fetch(`/api/files${q}`, { method: "POST", headers: authHeaders(), body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (showToast) {
      appendMessage("assistant", renderMarkdown(`**Upload failed:** ${data.detail || res.status}`), true);
    }
    throw new Error(data.detail || `Upload failed (${res.status})`);
  }
  if (showToast) {
    appendMessage(
      "assistant",
      renderMarkdown(`**Uploaded** \`${data.filename}\` (${data.size_bytes} bytes)${data.ingested ? " → RAG" : ""}`),
      true
    );
  }
  return data;
}

function renderAttachChips() {
  if (!attachChipsEl) return;
  if (!pendingAttachments.length) {
    attachChipsEl.classList.add("hidden");
    attachChipsEl.innerHTML = "";
    return;
  }
  attachChipsEl.classList.remove("hidden");
  attachChipsEl.innerHTML = pendingAttachments
    .map(
      (a, i) =>
        `<span class="attach-chip"><span title="${a.file.name}">${a.file.name}</span>` +
        `<button type="button" data-rm="${i}" aria-label="Remove">×</button></span>`
    )
    .join("");
  attachChipsEl.querySelectorAll("button[data-rm]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-rm"));
      pendingAttachments.splice(idx, 1);
      renderAttachChips();
    });
  });
}

function queueChatFiles(fileList) {
  const incoming = Array.from(fileList || []);
  for (const f of incoming) {
    if (pendingAttachments.length >= MAX_CHAT_ATTACHMENTS) break;
    if (pendingAttachments.some((p) => p.file.name === f.name && p.file.size === f.size)) continue;
    pendingAttachments.push({ file: f });
  }
  renderAttachChips();
}

async function uploadPendingAttachments() {
  const ids = [];
  const names = [];
  for (const item of pendingAttachments) {
    if (item.id) {
      ids.push(item.id);
      names.push(item.file.name);
      continue;
    }
    const data = await uploadOneFile(item.file, false);
    item.id = data.id;
    ids.push(data.id);
    names.push(data.filename || item.file.name);
  }
  return { ids, names };
}

async function exportCurrentChat() {
  try {
    const cid = await ensureServerChat();
    if (!cid) throw new Error("Could not create server chat");
    const res = await fetch(`/api/chats/${cid}/export`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const md = await res.text();
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `securaiq-report-${cid.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Export failed:** ${err.message}`), true);
  }
}

function openGap() {
  gapModal?.classList.remove("hidden");
  gapResult?.classList.add("hidden");
}
function closeGap() {
  gapModal?.classList.add("hidden");
}
function openDash() {
  dashModal?.classList.remove("hidden");
  loadDashboard();
}
function closeDash() {
  dashModal?.classList.add("hidden");
}

async function runGapAnalysis(e) {
  e?.preventDefault?.();
  const framework_id = document.getElementById("gapFramework")?.value || "iso27001";
  const title = document.getElementById("gapTitle")?.value?.trim() || "Gap assessment";
  const evidence = document.getElementById("gapEvidence")?.value?.trim() || "";
  if (!evidence) {
    appendMessage("assistant", renderMarkdown("**Gap analysis:** paste some evidence or notes first."), true);
    return;
  }
  const btn = document.getElementById("gapRunBtn");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch("/api/gap/run", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        framework_id,
        title,
        evidence,
        engagement_id: engagementSelectEl?.value || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderGapResult(data);
    appendMessage(
      "assistant",
      renderMarkdown(
        `**Gap analysis complete** — ${data.framework_name}: **${data.compliance_percent}%**\n\n${data.executive_summary}\n\nUse **Export report** in Gap analysis, or open **Dashboard**.`
      ),
      true
    );
    if (typeof loadCommandCenter === "function") loadCommandCenter();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Gap analysis failed:** ${err.message}`), true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderGapResult(data) {
  if (!gapResult) return;
  const counts = data.counts || {};
  const gaps = (data.top_gaps || [])
    .slice(0, 8)
    .map(
      (g) =>
        `<li><strong>${escapeHtml(g.control_id)}</strong> (${escapeHtml(g.status)}) — ${escapeHtml(g.title)}</li>`
    )
    .join("");
  const rems = (data.remediations || [])
    .slice(0, 8)
    .map(
      (r) =>
        `<li data-rem="${escapeHtml(r.id)}"><strong>${escapeHtml(r.control_id)}</strong> — ${escapeHtml(r.title)}
         <button type="button" class="btn-secondary rem-done" data-id="${escapeHtml(r.id)}">Mark done</button></li>`
    )
    .join("");
  gapResult.classList.remove("hidden");
  gapResult.innerHTML = `
    <div class="gap-score">${escapeHtml(data.compliance_percent)}% compliance</div>
    <div class="gap-counts">
      <span class="gap-chip">implemented ${counts.implemented || 0}</span>
      <span class="gap-chip">partial ${counts.partial || 0}</span>
      <span class="gap-chip">missing ${counts.missing || 0}</span>
      <span class="gap-chip">remediation tasks ${data.remediations_created || 0}</span>
    </div>
    <p>${escapeHtml(data.executive_summary || "")}</p>
    <p class="sidebar-label">Top gaps</p>
    <ul>${gaps || "<li>None</li>"}</ul>
    <p class="sidebar-label">Remediation tracker (DB)</p>
    <ul id="remList">${rems || "<li>None</li>"}</ul>
    <button type="button" class="btn-sidebar" id="gapExportBtn">Export report (Markdown)</button>
  `;
  document.getElementById("gapExportBtn")?.addEventListener("click", () => exportGap(data.id));
  gapResult.querySelectorAll(".rem-done").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      await fetch(`/api/gap/remediations/${id}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "done" }),
      });
      btn.closest("li")?.remove();
      refreshActiveWorkspace("remediations");
    });
  });
  refreshActiveWorkspace("remediations");
  refreshActiveWorkspace("frameworks");
}

async function exportGap(assessmentId) {
  try {
    const res = await fetch(`/api/gap/assessments/${assessmentId}/export`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const md = await res.text();
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `securaiq-gap-${assessmentId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Gap export failed:** ${err.message}`), true);
  }
}

async function loadDashboard() {
  if (!dashBody) return;
  try {
    const res = await fetch("/api/dashboard", { headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(formatApiDetail(data.detail, `HTTP ${res.status}`));
    const fws = (data.frameworks || [])
      .map(
        (f) =>
          `<li><strong>${escapeHtml(f.framework_id)}</strong>: ${escapeHtml(f.compliance_percent)}% — ${escapeHtml(
            f.title || ""
          )}</li>`
      )
      .join("");
    const recs = (data.recommendations || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
    const risks = (data.findings?.top_risks || [])
      .map((r) => `<li>Score ${escapeHtml(r.risk_score)}: ${escapeHtml(r.threat)}</li>`)
      .join("");
    const vulns = (data.findings?.top_vulns || [])
      .map((v) => `<li>${escapeHtml(v.severity)}: ${escapeHtml(v.cve || "")} ${escapeHtml(v.title)}</li>`)
      .join("");
    dashBody.innerHTML = `
      <div class="dash-score-row">
        <div class="dash-metric"><span>Compliance</span><strong>${data.compliance_score}%</strong></div>
        <div class="dash-metric"><span>Open risks</span><strong>${data.risks_open || 0}</strong></div>
        <div class="dash-metric"><span>Open vulns</span><strong>${data.vulnerabilities_open || 0}</strong></div>
        <div class="dash-metric"><span>Remediations</span><strong>${data.remediations_open || 0}</strong></div>
        <div class="dash-metric"><span>Assets</span><strong>${data.assets_total || 0}</strong></div>
        <div class="dash-metric"><span>Campaigns</span><strong>${data.campaigns_active || 0}</strong></div>
      </div>
      <p class="hint">${data.assessment_count || 0} gap assessments · ${data.playbooks_total || 0} playbooks · avg risk ${data.avg_open_risk_score || 0}</p>
      <p class="sidebar-label">Framework scores</p>
      <ul>${fws || "<li>No gap assessments yet</li>"}</ul>
      <p class="sidebar-label">Top risks</p>
      <ul>${risks || "<li>None</li>"}</ul>
      <p class="sidebar-label">Top vulnerabilities</p>
      <ul>${vulns || "<li>None</li>"}</ul>
      <p class="sidebar-label">Recommendations</p>
      <ul>${recs}</ul>
    `;
  } catch (err) {
    dashBody.innerHTML = `<p class="hint">Dashboard unavailable: ${err.message}</p>`;
  }
}

function openRisk() {
  riskModal?.classList.remove("hidden");
  loadRisks();
}
function closeRisk() {
  riskModal?.classList.add("hidden");
}
function openVuln() {
  vulnModal?.classList.remove("hidden");
  loadVulns();
}
function closeVuln() {
  vulnModal?.classList.add("hidden");
}

async function loadRisks() {
  if (!riskList) return;
  const res = await fetch("/api/risks", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.risks || [])
    .map(
      (r) =>
        `<li><strong>${escapeHtml(r.risk_score)}</strong> ${escapeHtml(r.threat)} · ${escapeHtml(
          r.asset_name || "—"
        )} · ${escapeHtml(r.status)}
         <button type="button" class="btn-secondary risk-mitigate" data-id="${escapeHtml(r.id)}">Mitigate</button></li>`
    )
    .join("");
  riskList.innerHTML = `<p class="sidebar-label">Register (${(data.risks || []).length})</p><ul>${rows || "<li>Empty</li>"}</ul>`;
  riskList.querySelectorAll(".risk-mitigate").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/risks/${btn.getAttribute("data-id")}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "mitigated" }),
      });
      loadRisks();
      refreshActiveWorkspace("risks");
    });
  });
}

async function submitRisk(e) {
  e.preventDefault();
  const body = {
    threat: document.getElementById("riskThreat")?.value?.trim(),
    vulnerability: document.getElementById("riskVuln")?.value?.trim() || "",
    asset_name: document.getElementById("riskAsset")?.value?.trim() || "",
    impact: Number(document.getElementById("riskImpact")?.value || 3),
    likelihood: Number(document.getElementById("riskLikelihood")?.value || 3),
    owner: document.getElementById("riskOwner")?.value?.trim() || "",
    mitigation: document.getElementById("riskMitigation")?.value?.trim() || "",
    engagement_id: engagementSelectEl?.value || null,
  };
  const res = await fetch("/api/risks", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    notifyUser(`**Risk create failed:** ${formatApiDetail(err.detail, res.status)}`);
    return;
  }
  riskForm?.reset();
  document.getElementById("riskImpact").value = "3";
  document.getElementById("riskLikelihood").value = "3";
  closeRisk();
  loadRisks();
  refreshActiveWorkspace("risks");
  notifyUser("**Risk added** to the register.");
}

async function loadVulns() {
  if (!vulnList) return;
  const res = await fetch("/api/vulnerabilities", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.vulnerabilities || [])
    .slice(0, 40)
    .map(
      (v) =>
        `<li><strong>${escapeHtml(v.severity)}</strong> ${escapeHtml(v.cve || "")} — ${escapeHtml(v.title)}
         <button type="button" class="btn-secondary vuln-close" data-id="${escapeHtml(v.id)}">Close</button></li>`
    )
    .join("");
  vulnList.innerHTML = `<p class="sidebar-label">Findings (${(data.vulnerabilities || []).length})</p><ul>${rows || "<li>Empty — import a scan</li>"}</ul>`;
  vulnList.querySelectorAll(".vuln-close").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/vulnerabilities/${btn.getAttribute("data-id")}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "closed" }),
      });
      loadVulns();
      refreshActiveWorkspace("vulns");
    });
  });
}

async function importVulns() {
  const f = vulnFileInput?.files?.[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  const eng = engagementSelectEl?.value;
  const q = eng ? `?engagement_id=${encodeURIComponent(eng)}` : "";
  const res = await fetch(`/api/vulnerabilities/import${q}`, { method: "POST", headers: authHeaders(), body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    notifyUser(`**Vuln import failed:** ${formatApiDetail(data.detail, res.status)}`);
    return;
  }
  notifyUser(`**Imported ${data.imported} vulnerabilities** into the register.`);
  if (vulnFileInput) vulnFileInput.value = "";
  closeVuln();
  loadVulns();
  refreshActiveWorkspace("vulns");
}

function openAsset() {
  assetModal?.classList.remove("hidden");
  loadAssets();
}
function closeAsset() {
  assetModal?.classList.add("hidden");
}
function openRem() {
  remModal?.classList.remove("hidden");
  loadRemediations();
}
function closeRem() {
  remModal?.classList.add("hidden");
}
function openPlaybook() {
  playbookModal?.classList.remove("hidden");
  loadPlaybooks();
}
function closePlaybook() {
  playbookModal?.classList.add("hidden");
}
function openCampaign() {
  campaignModal?.classList.remove("hidden");
  loadCampaigns();
}
function closeCampaign() {
  campaignModal?.classList.add("hidden");
}

async function loadAssets() {
  if (!assetList) return;
  const res = await fetch("/api/assets", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.assets || [])
    .map(
      (a) =>
        `<li><strong>${escapeHtml(a.name)}</strong> · ${escapeHtml(a.asset_type)} · ${escapeHtml(
          a.criticality
        )} · ${escapeHtml(a.owner || "—")}
         <button type="button" class="btn-secondary asset-del" data-id="${escapeHtml(a.id)}">Delete</button></li>`
    )
    .join("");
  assetList.innerHTML = `<p class="sidebar-label">Inventory (${(data.assets || []).length})</p><ul>${rows || "<li>Empty</li>"}</ul>`;
  assetList.querySelectorAll(".asset-del").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/assets/${btn.getAttribute("data-id")}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      loadAssets();
      refreshActiveWorkspace("assets");
    });
  });
}

async function submitAsset(e) {
  e.preventDefault();
  const body = {
    name: document.getElementById("assetName")?.value?.trim(),
    asset_type: document.getElementById("assetType")?.value || "server",
    criticality: document.getElementById("assetCriticality")?.value || "medium",
    owner: document.getElementById("assetOwner")?.value?.trim() || "",
    notes: document.getElementById("assetNotes")?.value?.trim() || "",
    engagement_id: engagementSelectEl?.value || null,
  };
  const res = await fetch("/api/assets", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    notifyUser(`**Asset create failed:** ${formatApiDetail(err.detail, res.status)}`);
    return;
  }
  assetForm?.reset();
  document.getElementById("assetCriticality").value = "medium";
  closeAsset();
  loadAssets();
  refreshActiveWorkspace("assets");
  notifyUser("**Asset added.**");
}

async function loadRemediations() {
  if (!remBoard) return;
  const res = await fetch("/api/gap/remediations", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.remediations || [])
    .map(
      (r) =>
        `<li><strong>${escapeHtml(r.control_id)}</strong> — ${escapeHtml(r.title)}
         <span class="gap-chip">${escapeHtml(r.status)}</span> · ${escapeHtml(r.owner || "unassigned")}
         ${r.status !== "done" ? `<button type="button" class="btn-secondary rem-done" data-id="${escapeHtml(r.id)}">Mark done</button>` : ""}</li>`
    )
    .join("");
  remBoard.innerHTML = `<p class="sidebar-label">Tasks (${(data.remediations || []).length})</p><ul>${rows || "<li>Empty — run Gap analysis first</li>"}</ul>`;
  remBoard.querySelectorAll(".rem-done").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/gap/remediations/${btn.getAttribute("data-id")}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "done" }),
      });
      loadRemediations();
      refreshActiveWorkspace("remediations");
    });
  });
}

async function loadPlaybooks() {
  if (!playbookList) return;
  const res = await fetch("/api/playbooks", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.playbooks || [])
    .map(
      (p) =>
        `<li><strong>${escapeHtml(p.title)}</strong> · ${escapeHtml(p.category)} · ${escapeHtml(p.severity)}
         <pre class="playbook-steps">${escapeHtml(p.steps || "")}</pre>
         <button type="button" class="btn-secondary pb-del" data-id="${escapeHtml(p.id)}">Delete</button></li>`
    )
    .join("");
  playbookList.innerHTML = `<p class="sidebar-label">Playbooks (${(data.playbooks || []).length})</p><ul>${rows || "<li>Empty</li>"}</ul>`;
  playbookList.querySelectorAll(".pb-del").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/playbooks/${btn.getAttribute("data-id")}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      loadPlaybooks();
      refreshActiveWorkspace("playbooks");
    });
  });
}

async function submitPlaybook(e) {
  e.preventDefault();
  const body = {
    title: document.getElementById("playbookTitle")?.value?.trim(),
    category: document.getElementById("playbookCategory")?.value || "ir",
    severity: document.getElementById("playbookSeverity")?.value || "high",
    steps: document.getElementById("playbookSteps")?.value?.trim() || "",
    engagement_id: engagementSelectEl?.value || null,
  };
  const res = await fetch("/api/playbooks", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    notifyUser(`**Playbook create failed:** ${formatApiDetail(err.detail, res.status)}`);
    return;
  }
  playbookForm?.reset();
  document.getElementById("playbookSeverity").value = "high";
  closePlaybook();
  loadPlaybooks();
  refreshActiveWorkspace("playbooks");
  notifyUser("**Playbook saved.**");
}

async function loadCampaigns() {
  if (!campaignList) return;
  const res = await fetch("/api/campaigns", { headers: authHeaders() });
  const data = await res.json();
  const rows = (data.campaigns || [])
    .map((c) => {
      const sent = Number(c.sent_count || 0);
      const clickRate = sent ? Math.round((100 * Number(c.click_count || 0)) / sent) : 0;
      const reportRate = sent ? Math.round((100 * Number(c.report_count || 0)) / sent) : 0;
      return `<li><strong>${escapeHtml(c.name)}</strong> · ${escapeHtml(c.status)} · ${escapeHtml(c.campaign_type)}
        <br/><span class="hint">${escapeHtml(c.audience || "—")} · click ${clickRate}% · report ${reportRate}%</span>
        <button type="button" class="btn-secondary camp-run" data-id="${escapeHtml(c.id)}">Mark running</button>
        <button type="button" class="btn-secondary camp-del" data-id="${escapeHtml(c.id)}">Delete</button></li>`;
    })
    .join("");
  campaignList.innerHTML = `<p class="sidebar-label">Campaigns (${(data.campaigns || []).length})</p><ul>${rows || "<li>Empty</li>"}</ul>`;
  campaignList.querySelectorAll(".camp-run").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/campaigns/${btn.getAttribute("data-id")}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "running" }),
      });
      loadCampaigns();
      refreshActiveWorkspace("campaigns");
    });
  });
  campaignList.querySelectorAll(".camp-del").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/campaigns/${btn.getAttribute("data-id")}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      loadCampaigns();
      refreshActiveWorkspace("campaigns");
    });
  });
}

async function submitCampaign(e) {
  e.preventDefault();
  const body = {
    name: document.getElementById("campaignName")?.value?.trim(),
    campaign_type: document.getElementById("campaignType")?.value || "phishing_sim",
    status: document.getElementById("campaignStatus")?.value || "planned",
    audience: document.getElementById("campaignAudience")?.value?.trim() || "",
    sent_count: Number(document.getElementById("campaignSent")?.value || 0),
    click_count: Number(document.getElementById("campaignClicks")?.value || 0),
    report_count: Number(document.getElementById("campaignReports")?.value || 0),
    notes: document.getElementById("campaignNotes")?.value?.trim() || "",
    engagement_id: engagementSelectEl?.value || null,
  };
  const res = await fetch("/api/campaigns", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    notifyUser(`**Campaign create failed:** ${formatApiDetail(err.detail, res.status)}`);
    return;
  }
  campaignForm?.reset();
  document.getElementById("campaignSent").value = "0";
  document.getElementById("campaignClicks").value = "0";
  document.getElementById("campaignReports").value = "0";
  closeCampaign();
  loadCampaigns();
  refreshActiveWorkspace("campaigns");
  notifyUser("**Campaign saved.**");
}

async function downloadMd(url, name) {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const md = await res.text();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadBinary(url, name, mime) {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([buf], { type: mime || "application/octet-stream" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
window.downloadBinary = downloadBinary;
window.downloadMd = downloadMd;

const THEME_KEY = "securaiq.theme";

const LIVE_PHASE_LABELS = {
  start: "Preparing…",
  think: "Thinking…",
  route: "Routing intent…",
  intel: "Loading threat intel…",
  search: "Searching the web…",
  assess: "Probing target…",
  tools: "Running security tools…",
  rag: "Reading knowledge & attachments…",
  model: "Writing answer…",
  done: "Live",
  error: "Pipeline error",
};

const THINK_STEPS = [
  { id: "think", label: "Understand the ask & constraints" },
  { id: "search", label: "Gather live context" },
  { id: "assess", label: "Probe authorized target" },
  { id: "tools", label: "Run security tools" },
  { id: "rag", label: "Use knowledge & attachments" },
  { id: "model", label: "Compose the answer" },
];

function setLiveState(state, phaseText, activity) {
  if (!liveBarEl) return;
  liveBarEl.classList.remove("live-on", "live-busy", "live-off");
  liveBarEl.classList.add(state);
  if (livePhaseEl && phaseText) livePhaseEl.textContent = phaseText;
  if (liveActivityEl && activity !== undefined) liveActivityEl.textContent = activity || "";
}

function applyLiveMarker(phase) {
  const label = LIVE_PHASE_LABELS[phase] || phase;
  updateThinkingUI(phase);
  if (phase === "done") {
    setLiveState("live-on", "Live", "");
    finishThinkingUI(true);
    return;
  }
  if (phase === "error") {
    setLiveState("live-off", label, "");
    finishThinkingUI(false);
    return;
  }
  setLiveState("live-busy", label, phase);
}

/** @type {HTMLElement | null} */
let activeThinkingEl = null;
/** @type {Set<string>} */
let thinkingSeen = new Set();

function startThinkingUI(bubble) {
  thinkingSeen = new Set(["start"]);
  activeThinkingEl = document.createElement("div");
  activeThinkingEl.className = "thinking-card";
  activeThinkingEl.innerHTML = `
    <div class="thinking-head">
      <span class="thinking-pulse" aria-hidden="true"></span>
      <strong>Thinking</strong>
      <span class="thinking-sub">planning a precise security answer</span>
    </div>
    <ol class="thinking-steps">
      ${THINK_STEPS.map((s) => `<li data-step="${s.id}" class="pending">${s.label}</li>`).join("")}
    </ol>
  `;
  bubble.textContent = "";
  bubble.appendChild(activeThinkingEl);
  bubble.classList.add("thinking");
  bubble.classList.remove("typing");
}

function updateThinkingUI(phase) {
  if (!activeThinkingEl) return;
  thinkingSeen.add(phase);
  const items = activeThinkingEl.querySelectorAll(".thinking-steps li");
  items.forEach((li) => {
    const id = li.getAttribute("data-step");
    li.classList.remove("pending", "active", "done");
    if (thinkingSeen.has(id) && id !== phase) li.classList.add("done");
    else if (id === phase) li.classList.add("active");
    else li.classList.add("pending");
  });
  const sub = activeThinkingEl.querySelector(".thinking-sub");
  if (sub) sub.textContent = LIVE_PHASE_LABELS[phase] || phase;
}

function finishThinkingUI(ok) {
  if (!activeThinkingEl) return;
  const card = activeThinkingEl;
  activeThinkingEl = null;
  card.classList.add(ok ? "thinking-done" : "thinking-error");
  const head = card.querySelector("strong");
  if (head) head.textContent = ok ? "Thought process" : "Interrupted";
  const sub = card.querySelector(".thinking-sub");
  if (sub) sub.textContent = ok ? "ready — streaming answer" : "pipeline error";
  // keep a compact summary briefly, then remove when answer replaces bubble
  return card;
}

function stripLiveMarkers(text) {
  return text
    .replace(/\[\[router:([^\]|]+)\|([^\]|]*)\|([^\]]*)\]\]/gi, (_, agent, intent, backend) => {
      if (livePhaseEl) {
        livePhaseEl.textContent = `${agent}${intent ? ` · ${intent}` : ""}${backend ? ` → ${backend}` : ""}`;
      }
      return "";
    })
    .replace(/\[\[live:route:([a-z0-9_-]+)\]\]/gi, (_, intent) => {
      applyLiveMarker("route");
      if (liveActivityEl) liveActivityEl.textContent = intent;
      return "";
    })
    .replace(/\[\[live:([a-z0-9_-]+)\]\]/gi, (_, phase) => {
      applyLiveMarker(phase.toLowerCase());
      return "";
    });
}

function startRealtimeFeed() {
  if (!window.EventSource) {
    setLiveState("live-off", "SSE unsupported", "");
    return;
  }
  try {
    const es = new EventSource("/api/realtime");
    es.onopen = () => setLiveState("live-on", "Live", "");
    es.onmessage = (ev) => {
      if (streaming) return;
      try {
        const data = JSON.parse(ev.data);
        if (data.error) {
          setLiveState("live-off", "Feed error", data.error);
          return;
        }
        const ready = data.backend_ready || data.backend_status === "loads_on_chat";
        setLiveState(ready ? "live-on" : "live-off", ready ? "Live" : "Backend offline", "");
        if (liveMetaEl) {
          liveMetaEl.textContent = `${data.backend || "?"} · ${data.model || "?"} · tools ${data.tools_available || 0}/${data.tools_total || 0} · RAG ${data.rag_documents ?? "—"}`;
        }
        if (toolsStatusEl && data.tools_available != null) {
          toolsStatusEl.textContent = `Tools ${data.tools_available}/${data.tools_total} ready`;
        }
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => setLiveState("live-off", "Reconnecting…", "");
  } catch {
    setLiveState("live-off", "Realtime offline", "");
  }
}

function getTheme() {
  const t = document.documentElement.getAttribute("data-theme");
  return t === "dark" ? "dark" : "light";
}

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* ignore */
  }
  if (metaThemeColor) {
    metaThemeColor.setAttribute("content", next === "dark" ? "#0c1117" : "#0f6e6a");
  }
  const appleBar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (appleBar) {
    appleBar.setAttribute("content", next === "dark" ? "black-translucent" : "default");
  }
  if (themeToggleLabel) {
    themeToggleLabel.textContent = next === "dark" ? "Light mode" : "Dark mode";
  }
  const tip = next === "dark" ? "Switch to light mode" : "Switch to dark mode";
  themeToggleBtn?.setAttribute("title", tip);
  themeToggleTopBtn?.setAttribute("title", tip);
}

function toggleTheme() {
  applyTheme(getTheme() === "dark" ? "light" : "dark");
}

function initTheme() {
  let theme = "light";
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") theme = saved;
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) theme = "dark";
  } catch {
    /* ignore */
  }
  applyTheme(theme);
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") return;
      applyTheme(e.matches ? "dark" : "light");
    });
  } catch {
    /* ignore */
  }
}
const MAX_CHATS = 40;
const MAX_MESSAGES = 40;

/** @type {{role: string, content: string}[]} */
let history = [];
let streaming = false;
/** @type {Record<string, string[]>} */
let quickPrompts = {};
let lastSetupCommand = "";
let backendReady = false;
let hermesSessionId = localStorage.getItem("hermesSessionId") || "";
let resetHermesNext = false;
let autoSwitchAttempted = false;
/** @type {string} */
let currentChatId = "";
/** @type {{id: string, title: string, createdAt: number, updatedAt: number, mode: string, messages: {role: string, content: string}[]}[]} */
let chatStore = [];

function on(el, event, handler) {
  if (el) el.addEventListener(event, handler);
}

function uid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;
}

function titleFromMessages(messages) {
  const firstUser = (messages || []).find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return "New chat";
  const t = firstUser.content.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 42)}…` : t;
}

function formatChatTime(ts) {
  const d = new Date(ts || Date.now());
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function loadChatStore() {
  try {
    let raw = localStorage.getItem(CHAT_STORE_KEY);
    if (!raw) {
      raw = localStorage.getItem(CHAT_STORE_LEGACY);
      if (raw) {
        localStorage.setItem(CHAT_STORE_KEY, raw);
      }
    }
    if (!raw) {
      chatStore = [];
      currentChatId = "";
      return;
    }
    const data = JSON.parse(raw);
    chatStore = Array.isArray(data.chats) ? data.chats : [];
    currentChatId = data.currentId || (chatStore[0] && chatStore[0].id) || "";
  } catch {
    chatStore = [];
    currentChatId = "";
  }
}

function saveChatStore() {
  try {
    localStorage.setItem(
      CHAT_STORE_KEY,
      JSON.stringify({
        currentId: currentChatId,
        chats: chatStore.slice(0, MAX_CHATS),
      })
    );
  } catch {
    /* quota / private mode */
  }
}

function getCurrentChat() {
  return chatStore.find((c) => c.id === currentChatId) || null;
}

function persistCurrentChat() {
  const chat = getCurrentChat();
  if (!chat) return;
  chat.messages = history.slice(-MAX_MESSAGES);
  chat.updatedAt = Date.now();
  chat.mode = modeEl?.value || chat.mode || "default";
  chat.title = titleFromMessages(chat.messages);
  chatStore = [chat, ...chatStore.filter((c) => c.id !== chat.id)].slice(0, MAX_CHATS);
  saveChatStore();
  renderChatList();
  updateChatTitle();
}

function updateChatTitle() {
  const chat = getCurrentChat();
  const title = chat?.title || "New chat";
  if (topbarChatTitleEl) topbarChatTitleEl.textContent = title;
  document.title = `${title} — SecuraIQ`;
}

function renderTranscript(messages) {
  chatEl.innerHTML = "";
  for (const msg of messages || []) {
    if (msg.role === "assistant") {
      appendMessage("assistant", renderMarkdown(msg.content || ""), true);
    } else if (msg.role === "user") {
      appendMessage("user", msg.content || "", false);
    }
  }
  syncEmptyState();
  chatEl.scrollTop = chatEl.scrollHeight;
}

function renderChatList() {
  if (!chatListEl) return;
  chatListEl.innerHTML = "";
  const sorted = [...chatStore].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  for (const chat of sorted) {
    const row = document.createElement("div");
    row.className = `chat-item${chat.id === currentChatId ? " active" : ""}`;
    row.setAttribute("role", "listitem");

    const main = document.createElement("button");
    main.type = "button";
    main.className = "chat-item-main";
    main.title = chat.title || "Chat";
    main.innerHTML = `<span class="chat-item-title">${escapeHtml(chat.title || "New chat")}</span>
      <span class="chat-item-meta">${escapeHtml(formatChatTime(chat.updatedAt))}</span>`;
    main.addEventListener("click", () => openChat(chat.id));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "chat-item-delete";
    del.title = "Delete chat";
    del.setAttribute("aria-label", "Delete chat");
    del.textContent = "×";
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteChat(chat.id);
    });

    row.append(main, del);
    chatListEl.appendChild(row);
  }
}

function createChat(activate = true, { clearUi = true } = {}) {
  const chat = {
    id: uid(),
    title: "New chat",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    mode: modeEl?.value || "default",
    messages: [],
  };
  chatStore = [chat, ...chatStore].slice(0, MAX_CHATS);
  if (activate) {
    currentChatId = chat.id;
    if (clearUi) {
      history = [];
      chatEl.innerHTML = "";
      syncEmptyState();
    }
    updateChatTitle();
  }
  saveChatStore();
  renderChatList();
  return chat;
}

function openChat(id) {
  if (typeof showView === "function") showView("chat", { skipFocus: true });
  if (streaming) return;
  if (!id || id === currentChatId) {
    closeSidebar();
    return;
  }
  const chat = chatStore.find((c) => c.id === id);
  if (!chat) return;

  // Save current before switching
  persistCurrentChat();

  currentChatId = chat.id;
  history = (chat.messages || []).slice(-MAX_MESSAGES);
  if (chat.mode && modeEl) {
    modeEl.value = chat.mode;
    updateModeLabel();
    renderQuickPrompts();
  }
  renderTranscript(history);
  updateChatTitle();
  saveChatStore();
  renderChatList();
  closeSidebar();
  inputEl?.focus();
}

function deleteChat(id) {
  if (streaming) return;
  const next = chatStore.filter((c) => c.id !== id);
  chatStore = next;
  if (currentChatId === id) {
    if (chatStore.length) {
      currentChatId = chatStore[0].id;
      history = (chatStore[0].messages || []).slice(-MAX_MESSAGES);
      renderTranscript(history);
      if (chatStore[0].mode && modeEl) {
        modeEl.value = chatStore[0].mode;
        updateModeLabel();
        renderQuickPrompts();
      }
    } else {
      createChat(true);
      return;
    }
  }
  saveChatStore();
  renderChatList();
  updateChatTitle();
}

function newChat() {
  if (streaming) return;
  const current = getCurrentChat();
  if (current && (!history || history.length === 0)) {
    // Already on empty chat
    chatEl.innerHTML = "";
    syncEmptyState();
    updateChatTitle();
    closeSidebar();
    inputEl?.focus();
    renderChatList();
    return;
  }
  persistCurrentChat();
  createChat(true);
  closeSidebar();
  inputEl?.focus();
}

function ensureActiveChat() {
  loadChatStore();
  if (!currentChatId || !getCurrentChat()) {
    if (chatStore.length) {
      currentChatId = chatStore[0].id;
    } else {
      createChat(true);
      return;
    }
  }
  const chat = getCurrentChat();
  history = (chat.messages || []).slice(-MAX_MESSAGES);
  if (chat.mode && modeEl) {
    modeEl.value = chat.mode;
  }
  renderTranscript(history);
  updateChatTitle();
  renderChatList();
  updateModeLabel();
}

if (typeof marked !== "undefined" && marked.setOptions) {
  marked.setOptions({ breaks: true, gfm: true });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatApiDetail(detail, fallback) {
  if (detail == null || detail === "") return fallback || "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "string" ? d : d?.msg || JSON.stringify(d)))
      .join("; ");
  }
  if (typeof detail === "object" && detail.msg) return String(detail.msg);
  try {
    return JSON.stringify(detail);
  } catch {
    return fallback || "Request failed";
  }
}

/** Refresh the open module page after modal CRUD so tables stay in sync. */
function refreshActiveWorkspace(view) {
  if (typeof loadCommandCenter === "function") loadCommandCenter();
  if (typeof window.showWorkspace !== "function") return;
  const map = {
    assets: "assets",
    risks: "risks",
    vulns: "vulns",
    remediations: "remediations",
    playbooks: "playbooks",
    campaigns: "campaigns",
    frameworks: "frameworks",
  };
  const target = map[view];
  if (!target) return;
  const panel = document.querySelector(`.workspace-view[data-view-panel="${target}"]`);
  const visible = panel && !panel.classList.contains("hidden");
  if (visible) window.showWorkspace(target);
}

function notifyUser(md, opts) {
  opts = opts || {};
  const text = String(md || "");
  // Prefer visible toast on module pages; also mirror to chat when asked
  let toast = document.getElementById("securaiqToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "securaiqToast";
    toast.className = "securaiq-toast hidden";
    toast.setAttribute("role", "status");
    document.body.appendChild(toast);
  }
  toast.innerHTML = typeof renderMarkdown === "function" ? renderMarkdown(text) : escapeHtml(text);
  toast.classList.remove("hidden");
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.add("hidden"), 4500);
  if (opts.toChat && typeof appendMessage === "function") {
    if (opts.openChat && typeof showView === "function") showView("chat");
    appendMessage("assistant", typeof renderMarkdown === "function" ? renderMarkdown(text) : text, true);
  }
}
window.notifyUser = notifyUser;
window.formatApiDetail = formatApiDetail;
window.refreshActiveWorkspace = refreshActiveWorkspace;

function renderMarkdown(text) {
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    return marked.parse(text);
  }
  return `<pre class="md-fallback">${escapeHtml(text)}</pre>`;
}


/* === COMMAND_CENTER_V29 === */

function wireCommandCenterUi() {
  if (window.__securaiqCcWired) return;
  window.__securaiqCcWired = true;
  const navCmd = document.getElementById("navCommand");
  const navAi = document.getElementById("navChat");
  on(navCmd, "click", () => showView("command"));
  on(navAi, "click", () => showView("chat"));
  document.getElementById("riskMatrixBtn")?.addEventListener("click", () => {
    showView("command");
    setTimeout(() => document.getElementById("ccHeatMap")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  });
  // Collapsible nav groups
  document.querySelectorAll("[data-nav-group] .nav-group-toggle").forEach((btn) => {
    const group = btn.closest("[data-nav-group]");
    const expanded = btn.getAttribute("aria-expanded") !== "false";
    group?.classList.toggle("collapsed", !expanded);
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") !== "false";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      group?.classList.toggle("collapsed", open);
    });
  });
  // Top enterprise nav
  on(document.getElementById("topSettingsBtn"), "click", () => openSettings());
  on(document.getElementById("topProfileBtn"), "click", () => openAuth());
  on(document.getElementById("topProjectsBtn"), "click", () => {
    document.getElementById("engagementSelect")?.focus();
    notifyUser("**Projects** — use the Project selector in the sidebar (engagements).");
  });
  document.querySelectorAll("[data-open-settings]").forEach((el) => el.addEventListener("click", () => openSettings()));
  document.querySelectorAll("[data-open-auth]").forEach((el) => el.addEventListener("click", () => openAuth()));
  document.querySelectorAll("[data-open-upload]").forEach((el) =>
    el.addEventListener("click", () => fileUploadInput?.click())
  );
  document.querySelectorAll("[data-module]").forEach((el) => {
    el.addEventListener("click", (e) => {
      const mod = el.getAttribute("data-module");
      const ws = el.getAttribute("data-workspace");
      if (ws && typeof window.showWorkspace === "function") {
        e.preventDefault();
        window.showWorkspace(ws);
        return;
      }
      handleModuleAction(mod);
    });
  });
  document.querySelectorAll("[data-view][data-prompt], [data-view][data-mode], [data-view][data-ai-tab], .agent-chip").forEach((el) => {
    if (el.id === "navCommand" || el.id === "navChat") return;
    el.addEventListener("click", () => {
      const view = el.getAttribute("data-view");
      if (view === "chat" || el.classList.contains("agent-chip")) {
        if (el.getAttribute("data-ai-tab")) {
          showView("chat");
          openAiTab(el.getAttribute("data-ai-tab"));
          if (el.getAttribute("data-ai-tab") === "tools") openToolsPalette(true);
          return;
        }
        runNavPrompt(el.getAttribute("data-mode"), el.getAttribute("data-prompt"));
      } else if (view === "command") {
        showView("command");
      }
    });
  });
  document.querySelectorAll(".intent-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const intent = chip.getAttribute("data-intent");
      showView("chat");
      if (intent === "attach") {
        chatAttachInput?.click();
        return;
      }
      if (intent === "search") {
        if (webSearchEl) webSearchEl.checked = true;
        chip.classList.add("active");
        inputEl?.focus();
        return;
      }
      if (intent === "tools") {
        openAiTab("tools");
        openToolsPalette(true);
        return;
      }
      const mode = chip.getAttribute("data-mode");
      const prompt = chip.getAttribute("data-prompt");
      runNavPrompt(mode, prompt);
    });
  });
  // Global search handled by workspace.js (API search) — fallback only if not present
  if (!window.__securaiqSearchWired) {
    const search = document.getElementById("globalSearch");
    on(search || globalSearchEl, "keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const el = search || globalSearchEl;
        handleGlobalSearch(el && el.value ? el.value : "");
      }
    });
  }
  wireToolsPalette();
  document.querySelectorAll("#emptySuite .suite-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.getAttribute("data-ai-tab")) {
        showView("chat");
        openAiTab(btn.getAttribute("data-ai-tab"));
        if (btn.getAttribute("data-ai-tab") === "tools") openToolsPalette(true);
      } else if (btn.getAttribute("data-workspace") && typeof window.showWorkspace === "function") {
        window.showWorkspace(btn.getAttribute("data-workspace"));
      } else if (btn.getAttribute("data-module")) {
        handleModuleAction(btn.getAttribute("data-module"));
      }
    });
  });
}

function openAiTab(name) {
  document.querySelectorAll(".ai-tab").forEach((t) => {
    t.classList.toggle("active", t.getAttribute("data-ai-tab") === name);
  });
  document.querySelectorAll(".ai-tab-panel").forEach((p) => p.classList.add("hidden"));
  const panel = document.getElementById(`aiTab-${name}`);
  if (panel) panel.classList.remove("hidden");
  if (name === "tools" && typeof window.refreshAiToolsTab === "function") window.refreshAiToolsTab();
  if (name === "files" && typeof window.refreshAiFilesTab === "function") window.refreshAiFilesTab();
  if (name === "memory" && typeof window.refreshAiMemoryTab === "function") window.refreshAiMemoryTab();
  if (name === "tasks" && typeof window.refreshAiTasksTab === "function") window.refreshAiTasksTab();
}
window.openAiTab = openAiTab;

function updateToolsChipState() {
  const chip = document.querySelector('.intent-chip[data-intent="tools"]');
  if (chip) chip.classList.toggle("active", selectedTools.length > 0);
  if (localToolsEl && selectedTools.length) localToolsEl.checked = true;
  if (toolsStatusEl && selectedTools.length) {
    toolsStatusEl.textContent = `Selected tools: ${selectedTools.join(", ")}`;
  }
}

function syncToolsPaletteSelection() {
  if (!toolsPaletteGridEl) return;
  toolsPaletteGridEl.querySelectorAll(".tool-pick").forEach((el) => {
    const id = el.getAttribute("data-id");
    el.classList.toggle("selected", selectedTools.includes(id));
    const cb = el.querySelector("input");
    if (cb) cb.checked = selectedTools.includes(id);
  });
}

function openToolsPalette(forceOpen) {
  if (!toolsPaletteEl) return;
  const opening = forceOpen || toolsPaletteEl.classList.contains("hidden");
  toolsPaletteEl.classList.toggle("hidden", !opening);
  if (opening) renderToolsPalette().catch(() => {});
}
window.openToolsPalette = openToolsPalette;

async function renderToolsPalette() {
  if (!toolsPaletteGridEl) return;
  try {
    const res = await fetch("/api/tools");
    const data = await res.json();
    toolsCatalogCache = data.tools || [];
    const byCat = {};
    toolsCatalogCache.forEach((t) => {
      const c = t.category || "other";
      (byCat[c] = byCat[c] || []).push(t);
    });
    toolsPaletteGridEl.innerHTML = Object.entries(byCat)
      .map(
        ([cat, tools]) =>
          `<div class="tools-cat"><p class="sidebar-label">${escapeHtml(cat)}</p><div class="tools-cat-grid">${tools
            .map(
              (t) => `<label class="tool-pick ${t.available ? "" : "unavailable"} ${
                selectedTools.includes(t.id) ? "selected" : ""
              }" data-id="${escapeHtml(t.id)}" title="${escapeHtml(t.description || "")}">
                <input type="checkbox" ${selectedTools.includes(t.id) ? "checked" : ""} ${
                t.available ? "" : "disabled"
              } />
                <span><strong>${escapeHtml(t.name || t.id)}</strong>
                <small>${t.available ? (t.heavy ? "heavy" : "ready") : "not installed"}</small></span>
              </label>`
            )
            .join("")}</div></div>`
      )
      .join("");
    toolsPaletteGridEl.querySelectorAll(".tool-pick").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (el.classList.contains("unavailable")) return;
        e.preventDefault();
        const id = el.getAttribute("data-id");
        if (selectedTools.includes(id)) selectedTools = selectedTools.filter((x) => x !== id);
        else selectedTools.push(id);
        syncToolsPaletteSelection();
        updateToolsChipState();
      });
    });
    const hint = document.getElementById("toolsPaletteHint");
    if (hint) {
      hint.textContent = `${data.available_count || 0}/${data.count || 0} ready · select & run on authorized/lab targets`;
    }
  } catch (err) {
    toolsPaletteGridEl.innerHTML = `<p class="hint">Tools unavailable: ${escapeHtml(err.message)}</p>`;
  }
}

function wireToolsPalette() {
  if (window.__securaiqToolsWired) return;
  window.__securaiqToolsWired = true;
  on(document.getElementById("toolsPaletteClose"), "click", () => toolsPaletteEl?.classList.add("hidden"));
  on(document.getElementById("toolsPaletteClear"), "click", () => {
    selectedTools = [];
    syncToolsPaletteSelection();
    updateToolsChipState();
    loadToolsStatus();
  });
  on(document.getElementById("toolsPaletteUseChat"), "click", () => {
    if (localToolsEl) localToolsEl.checked = true;
    toolsPaletteEl?.classList.add("hidden");
    openAiTab("chat");
    if (inputEl && selectedTools.length && !inputEl.value.trim()) {
      inputEl.value = `Run ${selectedTools.join(", ")} on the authorized/lab target and summarize findings with remediations.`;
      resizeInput();
    }
    inputEl?.focus();
    updateToolsChipState();
  });
  on(document.getElementById("toolsPaletteRun"), "click", () => runSelectedTools());
}

async function runSelectedTools() {
  const target = targetIpEl?.value?.trim() || "";
  const authorized = authorizedTargetEl?.checked || false;
  if (!selectedTools.length) {
    appendMessage("assistant", renderMarkdown("**Select at least one tool** in the palette first."), true);
    return;
  }
  if (!target) {
    appendMessage(
      "assistant",
      renderMarkdown("**Set a Target IP (lab)** and check **Auth** for owned/lab systems before running tools."),
      true
    );
    showView("chat");
    targetIpEl?.focus();
    return;
  }
  showView("chat");
  openAiTab("chat");
  appendMessage(
    "user",
    `Run tools [${selectedTools.join(", ")}] on ${target}${authorized ? " (authorized)" : ""}`
  );
  const bubble = appendMessage("assistant", "Running cyber tools…", false);
  try {
    const res = await fetch("/api/tools/run", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        target,
        tools: selectedTools,
        authorized_target: authorized,
        message: `authorized assessment of ${target}`,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    let md = data.markdown || data.output || "";
    if (!md && Array.isArray(data.runs)) {
      md = data.runs
        .map((r) => {
          const status = r.ok ? "OK" : "FAIL";
          const body = r.output || r.error || JSON.stringify(r);
          return `### ${r.name || r.tool || r.id} [${status}]\n\`\`\`\n${body}\n\`\`\``;
        })
        .join("\n\n");
    }
    if (!md) md = "```json\n" + JSON.stringify(data, null, 2) + "\n```";
    bubble.innerHTML = renderMarkdown(
      `**Tool run ${data.ok ? "complete" : "finished with errors"}** · target \`${data.target || target}\`\n\n${md}`
    );
    if (toolsPaletteOutEl) {
      toolsPaletteOutEl.classList.remove("hidden");
      toolsPaletteOutEl.textContent = typeof md === "string" ? md.slice(0, 4000) : JSON.stringify(data, null, 2);
    }
  } catch (err) {
    bubble.innerHTML = renderMarkdown(`**Tool run failed:** ${err.message}`);
  }
}
window.runSelectedTools = runSelectedTools;

/** Ask AI about an ops entity (asset/risk/vuln/rem/incident). */
function askAboutEntity(kind, payload) {
  const p = payload || {};
  const map = {
    asset: {
      mode: "assess",
      prompt: `Triage asset "${p.name || p.id}" (type=${p.asset_type || "?"}, criticality=${p.criticality || "?"}). Suggest monitoring, hardening, and mapping to risks/vulns.`,
    },
    risk: {
      mode: "ciso",
      prompt: `Analyze risk "${p.threat || p.id}" (score=${p.risk_score || "?"}, L=${p.likelihood} I=${p.impact}). Propose mitigation owners, SLA, and residual risk.`,
    },
    vuln: {
      mode: "blueteam",
      prompt: `Triage vulnerability ${p.cve || ""} — ${p.title || p.id} (severity=${p.severity || "?"}, asset=${p.asset_name || "?"}). Give exploitability notes, detection, and patch/workaround steps for an authorized environment.`,
    },
    remediation: {
      mode: "ciso",
      prompt: `Draft implementation guidance for remediation ${p.control_id || ""} — ${p.title || p.id}. Include evidence to collect, owner checklist, and verification steps.`,
    },
    incident: {
      mode: "ir",
      prompt: `Incident response plan for "${p.title || p.id}" (severity=${p.severity || "high"}). Cover contain, eradicate, recover, and comms for an authorized org.`,
    },
  };
  const cfg = map[kind] || { mode: "default", prompt: `Explain and recommend actions for ${kind}: ${JSON.stringify(p)}` };
  runNavPrompt(cfg.mode, cfg.prompt);
}
window.askAboutEntity = askAboutEntity;

let currentView = "command";
window.__setSecuraIQView = function (v) {
  currentView = v === "chat" ? "chat" : v === "command" ? "command" : "page";
};
const viewCommandEl = document.getElementById("viewCommand");
const viewChatEl = document.getElementById("viewChat");
const composerWrapEl = document.getElementById("composerWrap");
const globalSearchEl = document.getElementById("globalSearch");
const navCommandBtn = document.getElementById("navCommand");
const navChatBtn = document.getElementById("navChat");

function setNavActive(view) {
  document.querySelectorAll(".nav-item[data-view]").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-view") === view);
  });
}

function showView(view, opts = {}) {
  const moduleViews = new Set([
    "assets", "risks", "vulns", "remediations", "playbooks", "campaigns",
    "intel", "reports", "soc", "evidence", "orgs", "frameworks",
    "integrations", "billing", "graph",
  ]);
  if (moduleViews.has(view) && typeof window.showWorkspace === "function") {
    window.showWorkspace(view, opts);
    return;
  }
  currentView = view === "chat" ? "chat" : "command";
  viewCommandEl?.classList.toggle("hidden", currentView !== "command");
  viewChatEl?.classList.toggle("hidden", currentView !== "chat");
  // Hide module pages when returning to chat/command
  document.querySelectorAll(".workspace-view[data-module-page]").forEach((el) => el.classList.add("hidden"));
  composerWrapEl?.classList.toggle("is-command", currentView === "command");
  composerWrapEl?.classList.toggle("is-page", false);
  composerWrapEl?.classList.toggle("is-chat", currentView === "chat");
  setNavActive(currentView);
  if (topbarChatTitleEl) {
    topbarChatTitleEl.textContent = currentView === "command" ? "Mission Control" : (getCurrentChat()?.title || "AI Workspace");
  }
  if (currentView === "command") {
    loadCommandCenter();
  } else {
    syncEmptyState();
    if (!opts.skipFocus) inputEl?.focus();
  }
  closeSidebar();
}

async function loadCommandCenter() {
  if (window.__securaiqCcLoading) return;
  window.__securaiqCcLoading = true;
  const scoreEl = document.getElementById("ccScore");
  const compEl = document.getElementById("ccCompliance");
  const barEl = document.getElementById("ccComplianceBar");
  const critEl = document.getElementById("ccCrit");
  const risksEl = document.getElementById("ccRisks");
  const remsEl = document.getElementById("ccRems");
  const assetsEl = document.getElementById("ccAssets");
  const fwEl = document.getElementById("ccFrameworks");
  const riskListEl = document.getElementById("ccTopRisks");
  const vulnListEl = document.getElementById("ccTopVulns");
  try {
    const res = await fetch("/api/dashboard", { headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(formatApiDetail(data.detail, `HTTP ${res.status}`));
    const mc = data.mission_control || {};
    const compliance = Number(data.compliance_score || 0);
    const openRisks = Number(data.risks_open || 0);
    const crit = Number(data.vulnerabilities_critical_high || 0);
    const openRems = Number(data.remediations_open || 0);
    const index = Number(data.security_index != null ? data.security_index : mc.security_score) || 0;

    // KPI trend deltas via localStorage snapshot
    const snapKey = "securaiq.kpi.snap";
    let prev = {};
    try {
      prev = JSON.parse(localStorage.getItem(snapKey) || "{}");
    } catch {
      prev = {};
    }
    const delta = (cur, key) => {
      if (prev[key] == null) return "New";
      const d = cur - Number(prev[key] || 0);
      if (d === 0) return "→ flat";
      return d > 0 ? `↑ ${d}` : `↓ ${Math.abs(d)}`;
    };
    const setTrend = (id, text, goodUp) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = text;
      el.classList.toggle("up", text.startsWith("↑") && goodUp);
      el.classList.toggle("down", text.startsWith("↓") && goodUp);
      el.classList.toggle("up-bad", text.startsWith("↑") && !goodUp);
      el.classList.toggle("down-good", text.startsWith("↓") && !goodUp);
    };

    if (scoreEl) scoreEl.textContent = String(index);
    if (compEl) compEl.textContent = `${compliance}%`;
    if (barEl) barEl.style.width = `${Math.min(100, compliance)}%`;
    if (critEl) critEl.textContent = String(crit);
    if (risksEl) risksEl.textContent = String(openRisks);
    if (remsEl) remsEl.textContent = String(openRems);
    if (assetsEl) assetsEl.textContent = String(data.assets_total || 0);
    setTrend("ccScoreTrend", delta(index, "index"), true);
    setTrend("ccCompTrend", delta(compliance, "comp"), true);
    setTrend("ccCritTrend", delta(crit, "crit"), false);
    setTrend("ccRiskTrend", delta(openRisks, "risks"), false);
    setTrend("ccRemTrend", delta(openRems, "rems"), false);
    setTrend("ccAssetTrend", delta(Number(data.assets_total || 0), "assets"), true);
    localStorage.setItem(
      snapKey,
      JSON.stringify({
        index,
        comp: compliance,
        crit,
        risks: openRisks,
        rems: openRems,
        assets: data.assets_total || 0,
        at: Date.now(),
      })
    );

    // Mission context header
    const setTxt = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v;
    };
    setTxt("mcOrgName", mc.organization || "Local workspace");
    setTxt("mcSecurityScore", String(mc.security_score != null ? mc.security_score : index));
    setTxt("mcFramework", mc.framework || "—");
    setTxt("mcEnvironment", mc.environment || "Lab / local");
    const lastScan = mc.last_scan;
    if (lastScan) {
      const d = new Date(Number(lastScan) * (Number(lastScan) < 1e12 ? 1000 : 1));
      setTxt("mcLastScan", Number.isNaN(d.getTime()) ? String(lastScan) : d.toLocaleString());
    } else setTxt("mcLastScan", "No scans yet");
    const today = mc.today || {};
    const emptyWorkspace =
      !(today.critical_findings || 0) &&
      !(today.open_risks || 0) &&
      !(today.open_actions || 0) &&
      !(today.open_incidents || 0) &&
      !(data.assets_total || 0) &&
      !(data.intel?.watch_count || 0);
    setTxt(
      "mcTodaySummary",
      emptyWorkspace
        ? "Empty by design — choose a path below when you’re ready."
        : `Today: ${today.critical_findings || 0} critical/high · ${today.open_risks || 0} open risks · ${
            today.open_actions || 0
          } actions · ${today.open_incidents || 0} incidents`
    );

    const viewCommand = document.getElementById("viewCommand");
    const liveDash = document.getElementById("mcLiveDashboard");
    viewCommand?.classList.toggle("mc-is-empty", emptyWorkspace);
    if (liveDash) liveDash.hidden = emptyWorkspace;

    const firstRun = document.getElementById("mcFirstRun");
    if (firstRun) {
      firstRun.classList.toggle("hidden", !emptyWorkspace);
      wireMissionFirstRunOnce();
      syncChecklistProgress(data);
    }

    if (emptyWorkspace) {
      window.__securaiqCcLoading = false;
      return;
    }

    // Work queue
    renderWorkQueue(data.work_queue || []);

    const recEl = document.getElementById("ccRecommendedToday");
    if (recEl) {
      const top = (data.work_queue || []).slice(0, 4);
      recEl.innerHTML = top.length
        ? `<ul class="mc-rec-list">${top
            .map(
              (w) =>
                `<li><span class="wq-badge pri-${escapeHtml(
                  (w.priority || "medium").toLowerCase()
                )}">${escapeHtml((w.priority || "medium").toUpperCase())}</span>
                <strong>${escapeHtml(w.title)}</strong></li>`
            )
            .join("")}</ul>`
        : `<p class="hint">Empty queue — add risks, vulns, or a gap assessment to prioritize work.</p>`;
    }

    const todayEl = document.getElementById("ccTodayList");
    if (todayEl) {
      todayEl.innerHTML = `
        <li><strong>${today.critical_findings || 0}</strong> critical / high findings</li>
        <li><strong>${today.open_risks || 0}</strong> open risks</li>
        <li><strong>${today.open_actions || 0}</strong> open remediation actions</li>
        <li><strong>${today.open_incidents || 0}</strong> open incidents</li>
        <li><strong>${compliance}%</strong> compliance · framework <strong>${escapeHtml(
          mc.framework || "—"
        )}</strong></li>`;
    }

    // Pending approvals
    const apEl = document.getElementById("ccApprovals");
    if (apEl) {
      const rows = data.pending_approvals || [];
      apEl.innerHTML = rows.length
        ? rows
            .map((a) => {
              const ws = a.kind === "incident" ? "soc" : "remediations";
              return `<li class="cc-clickable" data-workspace="${ws}">
                <span class="wq-badge pri-medium">${escapeHtml(a.kind || "item")}</span>
                <strong>${escapeHtml(a.title || "")}</strong>
                <span class="hint">${escapeHtml(a.owner || "")} · ${escapeHtml(a.status || "")}</span>
              </li>`;
            })
            .join("")
        : `<li class="hint">No pending approvals — remediations and incidents needing human review appear here.</li>`;
      apEl.querySelectorAll("[data-workspace]").forEach((li) =>
        li.addEventListener("click", () => window.showWorkspace?.(li.getAttribute("data-workspace")))
      );
    }

    // Threat intel strip
    const intelEl = document.getElementById("ccIntel");
    if (intelEl) {
      const intel = data.intel || {};
      const watch = intel.watch || [];
      if (watch.length) {
        intelEl.innerHTML = watch
          .map(
            (w) =>
              `<li class="cc-clickable" data-workspace="intel"><strong>${escapeHtml(
                w.value || ""
              )}</strong> <span class="hint">${escapeHtml(w.kind || "")} · ${escapeHtml(
                (w.notes || "").slice(0, 60)
              )}</span></li>`
          )
          .join("");
      } else {
        intelEl.innerHTML = `<li class="hint">No watchlist items — open Threat intel to add CVEs or sync CISA KEV.</li>
          <li><button type="button" class="cc-action" data-workspace="intel">Open threat intel</button></li>`;
      }
      intelEl.querySelectorAll("[data-workspace]").forEach((el) =>
        el.addEventListener("click", () => window.showWorkspace?.(el.getAttribute("data-workspace")))
      );
    }

    // Frameworks with control stats when available
    if (fwEl) {
      const stats = data.framework_control_stats || [];
      const fws = stats.length ? stats : data.frameworks || [];
      fwEl.innerHTML = fws.length
        ? fws
            .map((f) => {
              const pct = Number(f.compliance_percent || 0);
              const c = f.counts || {};
              const total = f.controls_total || (c.implemented || 0) + (c.partial || 0) + (c.missing || 0);
              const id = f.framework_id || f.id;
              return `<li class="cc-maturity">
                <div class="fw-line"><span>${escapeHtml(id)}</span><strong>${pct}%</strong></div>
                <div class="cc-bar"><i style="width:${pct}%"></i></div>
                ${
                  total
                    ? `<span class="hint">${total} controls · ${c.implemented || 0} in · ${c.partial || 0} partial · ${
                        c.missing || 0
                      } missing</span>`
                    : ""
                }
              </li>`;
            })
            .join("")
        : `<li class="hint">No gap assessments yet — run Gap analysis</li>`;
    }

    // Asset breakdown
    const abEl = document.getElementById("ccAssetBreakdown");
    if (abEl) {
      const ab = data.asset_breakdown || {};
      abEl.innerHTML = `
        <div class="asset-breakdown-grid">
          <button type="button" class="ab-tile" data-workspace="assets"><span>Servers</span><strong>${ab.server || 0}</strong></button>
          <button type="button" class="ab-tile" data-workspace="assets"><span>Endpoints</span><strong>${ab.endpoint || 0}</strong></button>
          <button type="button" class="ab-tile" data-workspace="assets"><span>Cloud</span><strong>${ab.cloud || 0}</strong></button>
          <button type="button" class="ab-tile" data-workspace="assets"><span>Containers</span><strong>${ab.container || 0}</strong></button>
        </div>`;
      abEl.querySelectorAll("[data-workspace]").forEach((b) =>
        b.addEventListener("click", () => window.showWorkspace?.(b.getAttribute("data-workspace")))
      );
    }

    // Timeline
    const tlEl = document.getElementById("ccTimeline");
    if (tlEl) {
      const events = data.timeline || [];
      tlEl.innerHTML = events.length
        ? events
            .map((e) => {
              const ts = e.ts ? new Date(Number(e.ts) * (Number(e.ts) < 1e12 ? 1000 : 1)) : null;
              const when = ts && !Number.isNaN(ts.getTime()) ? ts.toLocaleString() : "—";
              return `<li><span class="tl-when">${escapeHtml(when)}</span>
                <strong>${escapeHtml(e.label || "")}</strong>
                <span class="hint">${escapeHtml(e.detail || "")}</span></li>`;
            })
            .join("")
        : `<li class="hint">No activity yet</li>`;
    }

    // MITRE
    const mitreEl = document.getElementById("ccMitre");
    if (mitreEl) {
      const rows = data.mitre_coverage || [];
      mitreEl.innerHTML = rows.length
        ? rows
            .map(
              (r) =>
                `<div class="mitre-row"><span>${escapeHtml(r.tactic)}</span>
                <div class="cc-bar"><i style="width:${Number(r.coverage) || 0}%"></i></div>
                <strong>${Number(r.coverage) || 0}%</strong></div>`
            )
            .join("")
        : `<p class="hint">Import vulns / playbooks to estimate coverage</p>`;
    }

    if (riskListEl) {
      const rows = data.findings?.top_risks || [];
      riskListEl.innerHTML = rows.length
        ? rows
            .map(
              (r) =>
                `<li class="cc-clickable"><strong>${escapeHtml(r.risk_score)}</strong> ${escapeHtml(
                  r.threat || ""
                )}</li>`
            )
            .join("")
        : `<li class="hint">No open risks</li>`;
      riskListEl.querySelectorAll(".cc-clickable").forEach((li) =>
        li.addEventListener("click", () => window.showWorkspace?.("risks"))
      );
    }
    if (vulnListEl) {
      const rows = data.findings?.top_vulns || [];
      vulnListEl.innerHTML = rows.length
        ? rows
            .map(
              (v) =>
                `<li class="cc-clickable"><strong>${escapeHtml(v.severity)}</strong> ${escapeHtml(
                  v.cve || ""
                )} — ${escapeHtml(v.title || "")}</li>`
            )
            .join("")
        : `<li class="hint">No critical findings</li>`;
      vulnListEl.querySelectorAll(".cc-clickable").forEach((li) =>
        li.addEventListener("click", () => window.showWorkspace?.("vulns"))
      );
    }
    const meta = document.getElementById("ccMeta");
    if (meta) {
      meta.textContent = `${data.playbooks_total || 0} playbooks · ${data.campaigns_active || 0} campaigns · ${
        data.assessment_count || 0
      } assessments · Mission Control`;
    }
    await renderRiskHeatMap();
  } catch (err) {
    if (scoreEl) scoreEl.textContent = "--";
    if (fwEl) fwEl.innerHTML = `<li class="hint">Dashboard unavailable: ${escapeHtml(err.message)}</li>`;
  } finally {
    window.__securaiqCcLoading = false;
  }
}

function syncChecklistProgress(data) {
  const mc = data.mission_control || {};
  const today = mc.today || {};
  let integVisited = false;
  try {
    integVisited = localStorage.getItem("securaiq.checklist.integrations") === "1";
  } catch {
    /* ignore */
  }
  const marks = {
    org: (mc.organization || "") !== "Local workspace" && (mc.organization || "") !== "—",
    assets: Number(data.assets_total || 0) > 0,
    scan: Number(today.critical_findings || 0) + Number(data.vulnerabilities_open || 0) > 0,
    gap: Number(data.assessment_count || 0) > 0,
    report: Number(data.assessment_count || 0) > 0 || Number(data.assets_total || 0) > 0,
    integrations: integVisited,
  };
  document.querySelectorAll("#mcChecklist li[data-step]").forEach((li) => {
    const step = li.getAttribute("data-step");
    if (marks[step]) li.classList.add("done");
    else li.classList.remove("done");
  });
}

function wireMissionFirstRunOnce() {
  if (window.__securaiqFirstRunWired) return;
  window.__securaiqFirstRunWired = true;
  document.querySelectorAll("#mcChecklist .mc-check-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ws = btn.getAttribute("data-workspace");
      const mod = btn.getAttribute("data-module");
      if (ws && typeof window.showWorkspace === "function") window.showWorkspace(ws);
      else if (mod === "gap") openGap();
    });
  });
  document.querySelectorAll("#mcFirstRun [data-workspace]").forEach((btn) => {
    if (btn.classList.contains("mc-check-btn")) return;
    btn.addEventListener("click", () => {
      const ws = btn.getAttribute("data-workspace");
      if (ws && typeof window.showWorkspace === "function") window.showWorkspace(ws);
    });
  });
}

function renderWorkQueue(items) {
  const el = document.getElementById("ccWorkQueue");
  if (!el) return;
  if (!items.length) {
    el.innerHTML = `<p class="hint">Empty queue — use the quick-start checklist or import your first scan.</p>`;
    return;
  }
  el.innerHTML = items
    .map((w) => {
      const pri = (w.priority || "medium").toLowerCase();
      return `<article class="wq-item pri-${escapeHtml(pri)}">
        <div class="wq-top">
          <span class="wq-badge">${escapeHtml(pri)}</span>
          <strong>${escapeHtml(w.title)}</strong>
        </div>
        <div class="wq-meta">
          <span>Owner: ${escapeHtml(w.owner || "Unassigned")}</span>
          <span>Due: ${escapeHtml(w.due || "—")}</span>
          <span>Status: ${escapeHtml(w.status || "open")}</span>
        </div>
        <div class="wq-actions">
          <button type="button" class="btn-secondary wq-ask" data-mode="${escapeHtml(
            w.mode || "ciso"
          )}" data-prompt="${escapeHtml(w.prompt || w.title)}">Ask AI</button>
          <button type="button" class="btn-primary-cc wq-task" data-title="${escapeHtml(
            w.title
          )}" data-workspace="${escapeHtml(w.workspace || "remediations")}" data-action="${escapeHtml(
        w.action || "task"
      )}">Create task</button>
        </div>
      </article>`;
    })
    .join("");
  el.querySelectorAll(".wq-ask").forEach((btn) => {
    btn.addEventListener("click", () => runNavPrompt(btn.getAttribute("data-mode"), btn.getAttribute("data-prompt")));
  });
  el.querySelectorAll(".wq-task").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.getAttribute("data-action");
      const title = btn.getAttribute("data-title") || "Mission task";
      const ws = btn.getAttribute("data-workspace");
      if (action === "gap") {
        openGap();
        return;
      }
      if (action === "report" && ws) {
        window.showWorkspace?.(ws);
        return;
      }
      // Create remediation-style task when possible
      try {
        const res = await fetch("/api/gap/remediations", {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            control_id: "MC",
            title,
            status: "open",
            owner: "Unassigned",
            recommendation: title,
          }),
        });
        if (res.ok) {
          notifyUser(`**Task created:** ${title}`);
          window.showWorkspace?.("remediations");
        } else {
          // fallback: open remediations / ask AI
          notifyUser(`**Open module** to track: ${title}`);
          if (ws) window.showWorkspace?.(ws);
        }
      } catch {
        if (ws) window.showWorkspace?.(ws);
      }
    });
  });
}
window.renderWorkQueue = renderWorkQueue;

async function renderRiskHeatMap() {
  const el = document.getElementById("ccRiskHeat");
  if (!el) return;
  try {
    const res = await fetch("/api/risks", { headers: authHeaders() });
    const data = await res.json();
    const risks = (data.risks || []).filter((r) => (r.status || "") !== "mitigated" && (r.status || "") !== "closed");
    const grid = Array.from({ length: 5 }, () => Array(5).fill(0));
    const cells = Array.from({ length: 5 }, () => Array.from({ length: 5 }, () => []));
    risks.forEach((r) => {
      const i = Math.min(5, Math.max(1, Number(r.impact) || 1)) - 1;
      const l = Math.min(5, Math.max(1, Number(r.likelihood) || 1)) - 1;
      // matrix: rows = impact high→low (4→0), cols = likelihood 1→5
      const row = 4 - i;
      grid[row][l] += 1;
      cells[row][l].push(r);
    });
    const head = `<div class="risk-heat-corner"></div>${[1, 2, 3, 4, 5]
      .map((n) => `<div class="risk-heat-label">L${n}</div>`)
      .join("")}`;
    const rows = grid
      .map((row, ri) => {
        const impact = 5 - ri;
        const cellsHtml = row
          .map((count, ci) => {
            const score = impact * (ci + 1);
            const band = score >= 15 ? "crit" : score >= 10 ? "high" : score >= 6 ? "med" : "low";
            const titles = (cells[ri][ci] || []).map((r) => r.threat).slice(0, 3).join("; ");
            return `<button type="button" class="risk-heat-cell band-${band}" data-impact="${impact}" data-likelihood="${
              ci + 1
            }" title="${count ? escapeHtml(titles) : "Empty"}">${count || ""}</button>`;
          })
          .join("");
        return `<div class="risk-heat-label">I${impact}</div>${cellsHtml}`;
      })
      .join("");
    if (!risks.length) {
      el.innerHTML = `<p class="hint">No open risks yet — add risks to populate the impact × likelihood matrix.</p>
        <button type="button" class="cc-action" id="ccRiskHeatOpen">Open risk register</button>`;
      el.querySelector("#ccRiskHeatOpen")?.addEventListener("click", () => window.showWorkspace?.("risks"));
      return;
    }
    el.innerHTML = `${head}${rows}`;
    el.querySelectorAll(".risk-heat-cell").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (typeof window.showWorkspace === "function") window.showWorkspace("risks");
      });
    });
  } catch {
    el.innerHTML = `<p class="hint">Risk matrix unavailable</p>`;
  }
}

function runNavPrompt(mode, prompt) {
  showView("chat");
  if (mode && modeEl) {
    modeEl.value = mode;
    modeEl.dispatchEvent(new Event("change"));
  }
  if (prompt && inputEl) {
    inputEl.value = prompt;
    resizeInput();
    inputEl.focus();
  }
}

function handleModuleAction(module) {
  if (module === "gap") openGap();
  else if (module === "risks") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("risks");
    openRisk();
  } else if (module === "vulns") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("vulns");
    openVuln();
  } else if (module === "assets") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("assets");
    openAsset();
  } else if (module === "rems") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("remediations");
  } else if (module === "playbooks") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("playbooks");
    openPlaybook();
  } else if (module === "campaigns") {
    if (typeof window.showWorkspace === "function") window.showWorkspace("campaigns");
    openCampaign();
  } else if (module === "dashboard") openDash();
}

function handleGlobalSearch(q) {
  const query = (q || "").trim();
  if (!query) return;
  const lower = query.toLowerCase();
  if (lower.startsWith("cve") || /CVE-\d{4}-\d+/i.test(query)) {
    runNavPrompt("research", `Threat intel brief on ${query}`);
    return;
  }
  if (lower.includes("risk")) {
    openRisk();
    return;
  }
  if (lower.includes("vuln") || lower.includes("scan")) {
    openVuln();
    return;
  }
  if (lower.includes("asset")) {
    openAsset();
    return;
  }
  if (lower.includes("gap") || lower.includes("iso") || lower.includes("nist")) {
    openGap();
    return;
  }
  if (lower.includes("playbook") || lower.includes("incident")) {
    openPlaybook();
    return;
  }
  runNavPrompt(modeEl?.value || "default", `Find and explain: ${query}`);
}

function syncEmptyState() {
  if (!emptyStateEl) return;
  const hasMessages = chatEl && chatEl.children.length > 0;
  emptyStateEl.classList.toggle("hidden", hasMessages || currentView !== "chat");
}

function appendMessage(role, content, isHtml = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "Y" : "H";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isHtml) {
    bubble.innerHTML = content;
  } else {
    bubble.textContent = content;
  }

  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role;

  div.append(avatar, label, bubble);
  chatEl.appendChild(div);
  syncEmptyState();
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function resizeInput() {
  if (!inputEl) return;
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, window.innerHeight * 0.28)}px`;
}

function closeSidebar() {
  sidebarEl?.classList.remove("open");
  sidebarBackdrop?.classList.remove("show");
  if (sidebarBackdrop) sidebarBackdrop.hidden = true;
  menuToggle?.setAttribute("aria-expanded", "false");
  document.body.classList.remove("sidebar-open");
}

function openSidebar() {
  sidebarEl?.classList.add("open");
  if (sidebarBackdrop) {
    sidebarBackdrop.hidden = false;
    requestAnimationFrame(() => sidebarBackdrop.classList.add("show"));
  }
  menuToggle?.setAttribute("aria-expanded", "true");
  document.body.classList.add("sidebar-open");
}

function updateModeLabel() {
  if (!topbarModeEl || !modeEl) return;
  const opt = modeEl.selectedOptions[0];
  topbarModeEl.textContent = opt ? opt.textContent : modeEl.value;
}

function showSetupPanel(title, text, options = {}) {
  const {
    command = "",
    action = command ? "copy" : "docs",
    tone = "error",
    key = "",
  } = typeof options === "string"
    ? { command: options, action: options ? "copy" : "docs", tone: "error", key: "" }
    : options;

  // Soft info banners can be dismissed for the session
  if (tone === "info" && key && setupDismissedKey === key) {
    hideSetupPanel();
    return;
  }

  setupTitleEl.textContent = title;
  setupTextEl.textContent = text;
  lastSetupCommand = command;
  setupAction = action;
  setupPanelEl.dataset.tone = tone;
  setupPanelEl.dataset.key = key || "";

  if (action === "preload") setupPrimaryEl.textContent = "Preload model";
  else if (action === "settings") setupPrimaryEl.textContent = "Open Settings";
  else if (action === "copy" && command) setupPrimaryEl.textContent = "Copy command";
  else setupPrimaryEl.textContent = "Open docs";

  if (setupDismissEl) {
    setupDismissEl.classList.toggle("hidden", tone === "error");
  }

  setupPanelEl.classList.remove("hidden");
}

function hideSetupPanel() {
  setupPanelEl.classList.add("hidden");
  lastSetupCommand = "";
  setupAction = "";
}

function openSettings() {
  settingsModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  loadSettingsForm();
  refreshFinetuneHint();
  loadPlatformTip();
  refreshHermesStatus();
  refreshSettingsToolsHint();
}

function closeSettings() {
  settingsModal.classList.add("hidden");
  document.body.style.overflow = "";
}

async function refreshSettingsToolsHint() {
  const hint = document.getElementById("settingsToolsHint");
  if (!hint) return;
  try {
    const res = await fetch("/api/tools");
    const data = await res.json();
    const ready = (data.tools || []).filter((t) => t.available).map((t) => t.id);
    hint.textContent = `${data.available_count || 0}/${data.count || 0} tools ready — ${ready.join(", ") || "none"}`;
  } catch {
    hint.textContent = "Tools status unavailable";
  }
}

function syncThemeSelect() {
  const el = document.getElementById("setTheme");
  if (!el) return;
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch {
    /* ignore */
  }
  if (saved === "light" || saved === "dark") el.value = saved;
  else el.value = "system";
}

function applyThemeFromSettings() {
  const el = document.getElementById("setTheme");
  if (!el) return;
  const v = el.value;
  if (v === "system") {
    try {
      localStorage.removeItem(THEME_KEY);
    } catch {
      /* ignore */
    }
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(dark ? "dark" : "light");
    try {
      localStorage.removeItem(THEME_KEY);
    } catch {
      /* ignore */
    }
  } else {
    applyTheme(v);
  }
}

function toggleMenu() {
  if (sidebarEl?.classList.contains("open")) closeSidebar();
  else openSidebar();
}

async function loadPlatformTip() {
  if (!lanTipEl) return;
  try {
    const res = await fetch("/api/platform");
    const p = await res.json();
    const urls = (p.lan_urls || []).map((u) => `<code>${u}</code>`).join(" · ");
    lanTipEl.innerHTML =
      `${p.client_note || ""}` +
      (urls ? `<br/><strong>LAN:</strong> ${urls}` : "") +
      (p.os ? `<br/><strong>Host OS:</strong> ${p.os} · Python ${p.python}` : "");
  } catch {
    lanTipEl.textContent =
      "Phones/tablets: open this app via your host LAN IP on port 8080 (same Wi‑Fi). Backends run on the host.";
  }
}

function renderQuickPrompts() {
  if (!quickEl) return;
  // Empty-start: do not auto-fill suggested prompts on the welcome screen
  quickEl.innerHTML = "";
  quickEl.classList.add("hidden");
  quickEl.setAttribute("aria-hidden", "true");
  updateModeLabel();
}

async function loadModes() {
  try {
    const res = await fetch("/api/modes");
    const data = await res.json();
    quickPrompts = data.quick_prompts || {};
    renderQuickPrompts();
  } catch {
    quickEl.innerHTML = "";
  }
}

async function loadBackend() {
  try {
    const res = await fetch("/api/backend");
    const data = await res.json();
    backendEl.value = data.backend;
  } catch {
    backendEl.value = "ollama";
  }
}

async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    modelEl.innerHTML = "";
    const backend = data.backend || backendEl.value;

    if (
      backend === "huggingface" ||
      backend === "unsloth" ||
      backend === "openai_compat" ||
      backend === "hermes" ||
      backend === "openai" ||
      backend === "openrouter" ||
      backend === "groq" ||
      backend === "together" ||
      backend === "fireworks"
    ) {
      const opt = document.createElement("option");
      opt.value = data.current;
      opt.textContent = data.current;
      modelEl.appendChild(opt);
      modelEl.value = data.current;
      return;
    }

    const added = new Set();

    for (const name of data.installed || []) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      modelEl.appendChild(opt);
      added.add(name);
    }

    for (const rec of data.recommended || []) {
      if (added.has(rec.pull)) continue;
      const opt = document.createElement("option");
      opt.value = rec.pull;
      opt.textContent = `${rec.name} (not installed)`;
      opt.dataset.notInstalled = "1";
      modelEl.appendChild(opt);
    }

    if (data.current) {
      const match = [...modelEl.options].find(
        (o) => o.value === data.current || o.value.startsWith(data.current)
      );
      if (match) modelEl.value = match.value;
    }
  } catch {
    modelEl.innerHTML = '<option value="">Models unavailable</option>';
  }
}

async function loadSettingsForm() {
  try {
    const res = await fetch("/api/settings");
    const s = await res.json();
    syncThemeSelect();
    const setChecked = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = Boolean(val);
    };
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val ?? "";
    };
    setChecked("setWebSearchEnabled", s.web_search_enabled !== false);
    setVal("setWebSearchMax", s.web_search_max_results ?? 8);
    setVal("setWebSearchTimeout", s.web_search_timeout_sec ?? 5);
    setVal("setSearxngUrl", s.searxng_url || "");
    setChecked("setLocalToolsEnabled", s.local_tools_enabled !== false);
    setChecked("setLocalToolsAuto", s.local_tools_auto !== false);
    setChecked("setLocalToolsHeavy", Boolean(s.local_tools_allow_heavy));
    setChecked("setNetAssessEnabled", s.net_assess_enabled !== false);
    setChecked("setNetAssessNmap", s.net_assess_use_nmap !== false);
    setVal("setJiraUrl", s.jira_base_url || "");
    setVal("setJiraEmail", s.jira_email || "");
    setVal("setJiraProject", s.jira_project_key || "");
    setVal("setJiraToken", "");
    const jiraHint = document.getElementById("jiraTokenHint");
    if (jiraHint) {
      jiraHint.textContent = s.jira_api_token_set
        ? "Saved: •••••••• (hidden)"
        : "Not set — required to create Jira issues";
    }
    document.getElementById("setOllamaUrl").value = s.ollama_base_url || "";
    document.getElementById("setOllamaModel").value = s.ollama_model || "";
    document.getElementById("setHfModel").value = s.hf_model || "";
    document.getElementById("setHfToken").value = "";
    document.getElementById("hfTokenHint").textContent = s.hf_token_set
      ? "Saved: •••••••• (hidden)"
      : "Not set — required for gated Hugging Face / Unsloth models";
    document.getElementById("setUnslothModel").value = s.unsloth_model || "";
    document.getElementById("setUnslothAdapter").value = s.unsloth_adapter_dir || "";
    document.getElementById("setUnslothSeq").value = s.unsloth_max_seq_length || 2048;
    document.getElementById("setUnsloth4bit").checked = Boolean(s.unsloth_load_in_4bit);
    document.getElementById("setHermesUrl").value = s.hermes_base_url || "";
    document.getElementById("setHermesModel").value = s.hermes_model || "";
    document.getElementById("setHermesKey").value = "";
    document.getElementById("hermesKeyHint").textContent = s.hermes_api_key_set
      ? "Saved: •••••••• (hidden)"
      : "Not set";
    document.getElementById("setHermesSessionKey").value = "";
    const sessionHint = document.getElementById("hermesSessionKeyHint");
    if (sessionHint) {
      sessionHint.textContent = s.hermes_session_key_set
        ? "Saved: •••••••• (hidden)"
        : "Optional — leave blank to keep";
    }
    document.getElementById("setHermesTools").checked = s.hermes_show_tool_progress !== false;
    document.getElementById("setCompatUrl").value = s.openai_compat_base_url || "";
    document.getElementById("setCompatModel").value = s.openai_compat_model || "";
    document.getElementById("setCompatKey").value = "";
    document.getElementById("compatKeyHint").textContent = s.openai_compat_api_key_set
      ? "Saved: •••••••• (hidden)"
      : "Not set";
    setChecked("setRouterEnabled", s.router_enabled !== false);
    setVal("setOpenaiKey", "");
    setVal("setOpenaiModel", s.openai_model || "gpt-4o-mini");
    setVal("setOpenrouterKey", "");
    setVal("setOpenrouterModel", s.openrouter_model || "");
    setVal("setGroqKey", "");
    setVal("setGroqModel", s.groq_model || "");
    setVal("setTogetherKey", "");
    setVal("setFireworksKey", "");
    setVal("setOllamaCoder", s.ollama_coder_model || "");
    const setHint = (id, set) => {
      const el = document.getElementById(id);
      if (el) el.textContent = set ? "Saved: •••••••• (hidden)" : "Not set";
    };
    setHint("openaiKeyHint", s.openai_api_key_set);
    setHint("openrouterKeyHint", s.openrouter_api_key_set);
    setHint("groqKeyHint", s.groq_api_key_set);
    setHint("togetherKeyHint", s.together_api_key_set);
    setHint("fireworksKeyHint", s.fireworks_api_key_set);
    await refreshSettingsToolsHint();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Settings load failed:** ${err.message}`), true);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  applyThemeFromSettings();
  const payload = {
    web_search_enabled: document.getElementById("setWebSearchEnabled")?.checked ?? true,
    web_search_max_results: Number(document.getElementById("setWebSearchMax")?.value) || 8,
    web_search_timeout_sec: Number(document.getElementById("setWebSearchTimeout")?.value) || 5,
    searxng_url: document.getElementById("setSearxngUrl")?.value.trim() || "",
    local_tools_enabled: document.getElementById("setLocalToolsEnabled")?.checked ?? true,
    local_tools_auto: document.getElementById("setLocalToolsAuto")?.checked ?? true,
    local_tools_allow_heavy: document.getElementById("setLocalToolsHeavy")?.checked ?? false,
    net_assess_enabled: document.getElementById("setNetAssessEnabled")?.checked ?? true,
    net_assess_use_nmap: document.getElementById("setNetAssessNmap")?.checked ?? true,
    jira_base_url: document.getElementById("setJiraUrl")?.value.trim() || "",
    jira_email: document.getElementById("setJiraEmail")?.value.trim() || "",
    jira_api_token: document.getElementById("setJiraToken")?.value.trim() || "",
    jira_project_key: document.getElementById("setJiraProject")?.value.trim() || "",
    ollama_base_url: document.getElementById("setOllamaUrl").value.trim(),
    ollama_model: document.getElementById("setOllamaModel").value.trim(),
    hf_model: document.getElementById("setHfModel").value.trim(),
    hf_token: document.getElementById("setHfToken").value.trim(),
    unsloth_model: document.getElementById("setUnslothModel").value.trim(),
    unsloth_adapter_dir: document.getElementById("setUnslothAdapter").value.trim(),
    unsloth_max_seq_length: Number(document.getElementById("setUnslothSeq").value) || 2048,
    unsloth_load_in_4bit: document.getElementById("setUnsloth4bit").checked,
    hermes_base_url: document.getElementById("setHermesUrl").value.trim(),
    hermes_model: document.getElementById("setHermesModel").value.trim(),
    hermes_api_key: document.getElementById("setHermesKey").value.trim(),
    hermes_session_key: document.getElementById("setHermesSessionKey").value.trim(),
    hermes_show_tool_progress: document.getElementById("setHermesTools").checked,
    openai_compat_base_url: document.getElementById("setCompatUrl").value.trim(),
    openai_compat_model: document.getElementById("setCompatModel").value.trim(),
    openai_compat_api_key: document.getElementById("setCompatKey").value.trim(),
    router_enabled: document.getElementById("setRouterEnabled")?.checked ?? true,
    openai_api_key: document.getElementById("setOpenaiKey")?.value.trim() || "",
    openai_model: document.getElementById("setOpenaiModel")?.value.trim() || "",
    openrouter_api_key: document.getElementById("setOpenrouterKey")?.value.trim() || "",
    openrouter_model: document.getElementById("setOpenrouterModel")?.value.trim() || "",
    groq_api_key: document.getElementById("setGroqKey")?.value.trim() || "",
    groq_model: document.getElementById("setGroqModel")?.value.trim() || "",
    together_api_key: document.getElementById("setTogetherKey")?.value.trim() || "",
    fireworks_api_key: document.getElementById("setFireworksKey")?.value.trim() || "",
    ollama_coder_model: document.getElementById("setOllamaCoder")?.value.trim() || "",
  };
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    // Mirror tool toggles into sidebar for this session
    if (localToolsEl) localToolsEl.checked = payload.local_tools_enabled;
    if (netAssessEl) netAssessEl.checked = payload.net_assess_enabled && (netAssessEl.checked || modeEl.value === "assess");
    if (webSearchEl && !payload.web_search_enabled) webSearchEl.checked = false;
    appendMessage("assistant", renderMarkdown("**Settings saved** to `.env` (secrets stay masked)."), true);
    await loadSettingsForm();
    await loadModels();
    await loadToolsStatus();
    await checkHealth();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Save failed:** ${err.message}`), true);
  }
}

async function refreshHermesStatus() {
  const hint = document.getElementById("hermesStatusHint");
  if (!hint) return;
  hint.textContent = "Status: checking…";
  try {
    const res = await fetch("/api/hermes/status");
    const data = await res.json();
    if (!data.reachable) {
      hint.textContent = `Status: offline — ${data.error || "start hermes gateway"}`;
      return;
    }
    const models = (data.models || []).join(", ") || data.model || "hermes-agent";
    const feats = data.capabilities?.features
      ? Object.entries(data.capabilities.features)
          .filter(([, v]) => v)
          .map(([k]) => k)
          .slice(0, 6)
          .join(", ")
      : "chat_completions";
    hint.textContent = `Status: online · models: ${models} · features: ${feats}`;
  } catch (err) {
    hint.textContent = `Status: error — ${err.message}`;
  }
}

function newHermesSession() {
  hermesSessionId = "";
  localStorage.removeItem("hermesSessionId");
  resetHermesNext = true;
  appendMessage(
    "assistant",
    renderMarkdown("**New Hermes session** — next message starts a fresh Hermes Agent transcript (tools/memory scope uses your session key)."),
    true
  );
}

async function refreshFinetuneHint() {
  try {
    const res = await fetch("/api/finetune");
    const job = await res.json();
    if (job.status === "idle") {
      finetuneHint.textContent = "Idle — trains on data/ethical_pentest_dataset.jsonl";
    } else {
      finetuneHint.textContent = `${job.status}: ${job.message || job.engine}`;
    }
    const busy = job.status === "running";
    trainBtn.disabled = busy || streaming;
    settingsTrainBtn.disabled = busy;
  } catch {
    finetuneHint.textContent = "Finetune status unavailable";
  }
}

async function startUnslothTrain() {
  const epochs = Number(document.getElementById("setTrainEpochs")?.value) || 1;
  try {
    const res = await fetch("/api/finetune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine: "unsloth", epochs }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    appendMessage(
      "assistant",
      renderMarkdown(
        `**Unsloth training started** (${data.model} → \`${data.output}\`, ${data.epochs} epoch(s)).\n\nGPU recommended. Watch status via Settings or `/api/finetune`.`
      ),
      true
    );
    refreshFinetuneHint();
    closeSettings();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Train failed to start:** ${err.message}`), true);
  }
}

async function switchModel(modelName) {
  if (!modelName) return;
  if (backendEl.value !== "ollama") return;
  await fetch("/api/models/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName }),
  });
  checkHealth();
}

async function switchBackend(backend) {
  await fetch("/api/backend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend }),
  });
  await loadModels();
  await checkHealth();
}

async function ingestRag() {
  if (streaming) return;
  ingestBtn.disabled = true;
  try {
    const res = await fetch("/api/ingest", { method: "POST" });
    const data = await res.json();
    appendMessage(
      "assistant",
      renderMarkdown(`**RAG re-indexed:** ${data.documents_ingested} documents.`),
      true
    );
    checkHealth();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Re-index failed:** ${err.message}`), true);
  } finally {
    ingestBtn.disabled = false;
  }
}

async function pullModel() {
  const modelName = modelEl.value;
  if (!modelName || streaming) return;

  streaming = true;
  pullBtn.disabled = true;
  sendBtn.disabled = true;

  const body = appendMessage("assistant", "", false);
  body.classList.add("typing");
  let fullText = `Pulling **${modelName}** via Ollama…\n\n`;

  try {
    const res = await fetch("/api/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      body.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(fullText + "\n\n**Done.** Refreshing model list…");
    await loadModels();
    await switchModel(modelName);
  } catch (err) {
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(`**Pull failed:** ${err.message}`);
  } finally {
    streaming = false;
    pullBtn.disabled = false;
    sendBtn.disabled = false;
  }
}

async function preloadModel() {
  if (streaming) return;
  if (backendEl.value !== "huggingface" && backendEl.value !== "unsloth") return;

  streaming = true;
  preloadBtn.disabled = true;
  sendBtn.disabled = true;

  const body = appendMessage("assistant", "", false);
  body.classList.add("typing");
  let fullText = `Preloading **${modelEl.value}**…\n\n`;

  try {
    const res = await fetch("/api/models/preload", { method: "POST" });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      body.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(fullText + "\n\n**Model ready.**");
    await checkHealth();
  } catch (err) {
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(`**Preload failed:** ${err.message}`);
  } finally {
    streaming = false;
    preloadBtn.disabled = false;
    sendBtn.disabled = false;
  }
}

async function ensureWorkingBackend(healthData) {
  if (autoSwitchAttempted) return false;
  if (healthData.backend_ready) return false;
  autoSwitchAttempted = true;
  try {
    const res = await fetch("/api/backends/probe");
    const probe = await res.json();
    const next = probe.recommended;
    if (!next || next === healthData.backend) {
      return false;
    }
    await switchBackend(next);
    appendMessage(
      "assistant",
      renderMarkdown(
        `**Auto-switched AI backend** to \`${next}\` because \`${healthData.backend}\` was offline.\n\nYou can change this anytime in the backend dropdown or Settings.`
      ),
      true
    );
    return true;
  } catch {
    return false;
  }
}

let lastHealthData = null;

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    lastHealthData = data;
    const rag = data.rag_documents != null ? ` · RAG:${data.rag_documents}` : "";
    const backend = data.backend;
    backendEl.value = backend;

    // Prefer ready remote backends; fall back to HuggingFace/Unsloth (loads on chat)
    const canChat =
      Boolean(data.backend_ready) ||
      data.backend_status === "loads_on_chat";
    backendReady = canChat;
    sendBtn.disabled = streaming || !backendReady;
    preloadBtn.classList.add("hidden");
    trainBtn.classList.add("hidden");
    if (hermesNewSessionBtn) hermesNewSessionBtn.classList.add("hidden");

    if (!canChat) {
      const switched = await ensureWorkingBackend(data);
      if (switched) return;
    }

    if (data.finetune) {
      const ft = data.finetune;
      if (ft.status === "running") {
        finetuneHint.textContent = `running: ${ft.message || ft.model}`;
        trainBtn.disabled = true;
      } else if (ft.status === "completed" || ft.status === "failed") {
        finetuneHint.textContent = `${ft.status}: ${ft.message}`;
        trainBtn.disabled = streaming;
      }
    }

    if (backend === "ollama") {
      modelEl.disabled = false;
      pullBtn.disabled = streaming;
      if (!data.ollama_connected) {
        statusEl.textContent = `Ollama offline${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Start Ollama",
          "No Ollama server is running yet. Start Ollama, then pull a model to enable chat.",
          { command: "ollama pull tinyllama", action: "copy", tone: "error" }
        );
      } else if (!data.ollama_has_models) {
        statusEl.textContent = `Ollama ready · pull a model${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Pull a local model",
          "Ollama is reachable, but no local model is installed yet.",
          { command: "ollama pull tinyllama", action: "copy", tone: "warn" }
        );
      } else {
        statusEl.textContent = `${backend} · ${data.model}${rag}`;
        statusEl.className = "status ok";
        hideSetupPanel();
      }
    } else {
      modelEl.disabled = false;
      pullBtn.disabled = true;
      const statusSuffix = data.backend_status === "loads_on_chat" ? " · loads on first chat" : "";

      if (backend === "openai_compat") {
        if (!data.backend_ready) {
          statusEl.textContent = `LM Studio offline${rag}`;
          statusEl.className = "status err";
          showSetupPanel(
            "LM Studio offline",
            "Start LM Studio’s local server (OpenAI-compatible) on http://localhost:1234/v1, or fix the URL/key in Settings.",
            { action: "settings", tone: "error" }
          );
        } else {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        }
      } else if (backend === "hermes") {
        if (hermesNewSessionBtn) hermesNewSessionBtn.classList.remove("hidden");
        if (!data.backend_ready) {
          statusEl.textContent = `Hermes offline${rag}`;
          statusEl.className = "status err";
          showSetupPanel(
            "Hermes Agent offline",
            "Run hermes gateway with API_SERVER_ENABLED=true. Set the API key in Settings to match API_SERVER_KEY.",
            { command: "hermes gateway", action: "copy", tone: "error" }
          );
        } else {
          const sid = hermesSessionId ? ` · sess:${hermesSessionId.slice(0, 8)}…` : "";
          statusEl.textContent = `${backend} · ${data.model}${sid}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        }
      } else if (backend === "unsloth") {
        trainBtn.classList.remove("hidden");
        preloadBtn.classList.remove("hidden");
        if (data.unsloth_model_loaded) {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        } else {
          statusEl.textContent = `${backend} · ${data.model}${statusSuffix}${rag}`;
          statusEl.className = "status ok";
          // Ready to chat — soft tip only, not an error
          const tip = data.hf_token_set
            ? "Unsloth will load on first chat. You can also Preload now."
            : "Unsloth will load on first chat. Add an HF token in Settings only for gated models.";
          showSetupPanel("Unsloth ready", tip, {
            action: "preload",
            tone: "info",
            key: "unsloth-ready",
          });
        }
      } else if (backend === "huggingface") {
        preloadBtn.classList.remove("hidden");
        const speedTip =
          "For much faster replies: install Ollama, pull a model (e.g. mistral), then set Backend → Ollama in Settings.";
        if (data.hf_model_loaded) {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          showSetupPanel("Speed tip", speedTip, { action: "settings", tone: "info", key: "hf-speed" });
        } else {
          statusEl.textContent = `${backend} · ${data.model}${statusSuffix}${rag}`;
          statusEl.className = "status ok";
          showSetupPanel(
            "Hugging Face (slower on CPU)",
            `Model loads on first message. ${speedTip}`,
            { action: "preload", tone: "warn", key: "hf-ready" }
          );
        }
      } else {
        statusEl.textContent = `${backend} · ${data.model}${rag}`;
        statusEl.className = data.backend_ready ? "status ok" : "status err";
        if (!data.backend_ready) {
          showSetupPanel(
            "Backend not ready",
            "Check Settings and README for backend setup if chat is not responding.",
            { action: "settings", tone: "error" }
          );
        } else {
          hideSetupPanel();
        }
      }
    }
  } catch {
    backendReady = false;
    sendBtn.disabled = true;
    statusEl.textContent = "Offline";
    statusEl.className = "status err";
    showSetupPanel(
      "Server offline",
      "Start the backend with .\\scripts\\start.ps1 (Windows) or bash scripts/start.sh (Linux/macOS).",
      { command: ".\\scripts\\start.ps1", action: "copy", tone: "error" }
    );
  }
}

async function sendMessage() {
  if (currentView !== "chat") showView("chat", { skipFocus: true });
  let message = inputEl.value.trim();
  const hasFiles = pendingAttachments.length > 0;
  if ((!message && !hasFiles) || streaming) return;
  if (!backendReady) {
    appendMessage(
      "assistant",
      renderMarkdown("**Backend not ready.** Check the status bar and connect a local model backend first."),
      true
    );
    return;
  }

  streaming = true;
  sendBtn.disabled = true;
  inputEl.value = "";
  resizeInput();

  let attachmentIds = [];
  let attachmentNames = [];
  try {
    if (hasFiles) {
      const up = await uploadPendingAttachments();
      attachmentIds = up.ids;
      attachmentNames = up.names;
      pendingAttachments = [];
      renderAttachChips();
    }
  } catch (err) {
    streaming = false;
    sendBtn.disabled = !backendReady;
    appendMessage("assistant", renderMarkdown(`**Attachment upload failed:** ${err.message}`), true);
    return;
  }

  if (!message && attachmentIds.length) {
    message = "Please review the attached file(s).";
  }

  const userBubble = appendMessage("user", message);
  if (attachmentNames.length) {
    const wrap = document.createElement("div");
    wrap.className = "msg-attachments";
    wrap.innerHTML = attachmentNames
      .map((n) => `<span class="msg-attach-pill">📎 ${n.replace(/</g, "&lt;")}</span>`)
      .join("");
    userBubble.appendChild(wrap);
  }

  const assistantBody = appendMessage("assistant", "", false);
  startThinkingUI(assistantBody);
  let fullText = "";
  let answerStarted = false;

  try {
    const cid = await ensureServerChat().catch(() => null);
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message,
        history,
        mode: modeEl.value,
        use_rag: ragEl.checked,
        use_web_search: webSearchEl ? webSearchEl.checked : modeEl.value === "research",
        use_net_assess: netAssessEl ? netAssessEl.checked : modeEl.value === "assess",
        use_local_tools: localToolsEl ? localToolsEl.checked : true,
        tools: selectedTools.length ? selectedTools.slice() : null,
        target: targetIpEl && targetIpEl.value.trim() ? targetIpEl.value.trim() : null,
        authorized_target: authorizedTargetEl ? authorizedTargetEl.checked : false,
        engagement_id: engagementSelectEl?.value || null,
        chat_id: cid,
        attachment_ids: attachmentIds,
        hermes_session_id: hermesSessionId || null,
        reset_hermes_session: resetHermesNext,
      }),
    });
    resetHermesNext = false;

    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${errBody ? `: ${errBody.slice(0, 120)}` : ""}`);
    }

    const headerSid = res.headers.get("X-Hermes-Session-Id");
    if (headerSid) {
      hermesSessionId = headerSid;
      localStorage.setItem("hermesSessionId", hermesSessionId);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let carry = "";

    const paintAnswer = () => {
      if (!answerStarted && fullText.trim()) {
        answerStarted = true;
        finishThinkingUI(true);
        const thinkSnap = assistantBody.querySelector(".thinking-card");
        assistantBody.classList.remove("thinking", "typing");
        assistantBody.innerHTML = "";
        if (thinkSnap) {
          thinkSnap.classList.add("thinking-collapsed");
          assistantBody.appendChild(thinkSnap);
        }
        const answer = document.createElement("div");
        answer.className = "answer-body";
        assistantBody.appendChild(answer);
      }
      const answer = assistantBody.querySelector(".answer-body");
      if (answer) answer.innerHTML = renderMarkdown(fullText);
      else if (fullText.trim()) assistantBody.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      carry = carry.replace(/\[\[hermes_session:([^\]]+)\]\]/g, (_, sid) => {
        hermesSessionId = sid;
        localStorage.setItem("hermesSessionId", hermesSessionId);
        return "";
      });
      carry = stripLiveMarkers(carry);
      if (
        (carry.includes("[[hermes_session:") || carry.includes("[[live:")) &&
        !carry.includes("]]")
      ) {
        continue;
      }
      fullText += carry;
      carry = "";
      paintAnswer();
    }
    if (carry) {
      carry = carry.replace(/\[\[hermes_session:([^\]]+)\]\]/g, (_, sid) => {
        hermesSessionId = sid;
        localStorage.setItem("hermesSessionId", hermesSessionId);
        return "";
      });
      carry = stripLiveMarkers(carry);
      fullText += carry;
      paintAnswer();
    }

    applyLiveMarker("done");
    assistantBody.classList.remove("typing", "thinking");
    if (!answerStarted) {
      finishThinkingUI(true);
      assistantBody.innerHTML = renderMarkdown(fullText || "_No response_");
    }
    const histUser =
      attachmentNames.length > 0
        ? `${message}\n\n[Attached: ${attachmentNames.join(", ")}]`
        : message;
    history.push({ role: "user", content: histUser });
    history.push({ role: "assistant", content: fullText });
    if (history.length > MAX_MESSAGES) history = history.slice(-MAX_MESSAGES);
    if (!getCurrentChat()) createChat(true, { clearUi: false });
    persistCurrentChat();
    checkHealth();
  } catch (err) {
    finishThinkingUI(false);
    assistantBody.classList.remove("typing", "thinking");
    assistantBody.innerHTML = renderMarkdown(`**Error:** ${err.message}`);
  } finally {
    streaming = false;
    sendBtn.disabled = !backendReady;
    inputEl.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);
on(pullBtn, "click", pullModel);
on(preloadBtn, "click", preloadModel);
on(trainBtn, "click", () => openSettings());
on(ingestBtn, "click", ingestRag);
on(settingsBtn, "click", openSettings);
on(topSettingsBtn, "click", openSettings);
on(authBtn, "click", openAuth);
on(gapBtn, "click", openGap);
// Module sidebar nav is owned by workspace.js (pages). Keep only gap modal opener here.
on(gapForm, "submit", runGapAnalysis);
on(riskForm, "submit", submitRisk);
on(assetForm, "submit", submitAsset);
on(playbookForm, "submit", submitPlaybook);
on(campaignForm, "submit", submitCampaign);
on(document.getElementById("remRefreshBtn"), "click", loadRemediations);
on(document.getElementById("vulnImportBtn"), "click", () => vulnFileInput?.click());
on(vulnFileInput, "change", importVulns);
on(document.getElementById("vulnExportBtn"), "click", () =>
  downloadMd("/api/vulnerabilities/export", "securaiq-vulns.md").catch((err) =>
    appendMessage("assistant", renderMarkdown(`**Export failed:** ${err.message}`), true)
  )
);
on(document.getElementById("riskExportBtn"), "click", () =>
  downloadMd("/api/risks/export", "securaiq-risks.md").catch((err) =>
    appendMessage("assistant", renderMarkdown(`**Export failed:** ${err.message}`), true)
  )
);
if (gapModal) {
  gapModal.querySelectorAll("[data-close-gap]").forEach((el) => el.addEventListener("click", closeGap));
}
if (dashModal) {
  dashModal.querySelectorAll("[data-close-dash]").forEach((el) => el.addEventListener("click", closeDash));
}
if (riskModal) {
  riskModal.querySelectorAll("[data-close-risk]").forEach((el) => el.addEventListener("click", closeRisk));
}
if (vulnModal) {
  vulnModal.querySelectorAll("[data-close-vuln]").forEach((el) => el.addEventListener("click", closeVuln));
}
if (assetModal) {
  assetModal.querySelectorAll("[data-close-asset]").forEach((el) => el.addEventListener("click", closeAsset));
}
if (remModal) {
  remModal.querySelectorAll("[data-close-rem]").forEach((el) => el.addEventListener("click", closeRem));
}
if (playbookModal) {
  playbookModal.querySelectorAll("[data-close-playbook]").forEach((el) => el.addEventListener("click", closePlaybook));
}
if (campaignModal) {
  campaignModal.querySelectorAll("[data-close-campaign]").forEach((el) => el.addEventListener("click", closeCampaign));
}
on(newEngagementBtn, "click", createEngagement);
on(uploadBtn, "click", () => fileUploadInput?.click());
on(fileUploadInput, "change", uploadFile);
on(attachBtn, "click", () => chatAttachInput?.click());
on(chatAttachInput, "change", () => {
  if (chatAttachInput?.files?.length) {
    queueChatFiles(chatAttachInput.files);
    chatAttachInput.value = "";
  }
});
if (composerEl) {
  ["dragenter", "dragover"].forEach((ev) => {
    composerEl.addEventListener(ev, (e) => {
      e.preventDefault();
      composerEl.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    composerEl.addEventListener(ev, (e) => {
      e.preventDefault();
      composerEl.classList.remove("drag-over");
    });
  });
  composerEl.addEventListener("drop", (e) => {
    const files = e.dataTransfer?.files;
    if (files?.length) queueChatFiles(files);
  });
}
on(inputEl, "paste", (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  const files = [];
  for (const it of items) {
    if (it.kind === "file") {
      const f = it.getAsFile();
      if (f) files.push(f);
    }
  }
  if (files.length) {
    e.preventDefault();
    queueChatFiles(files);
  }
});
on(exportMdBtn, "click", exportCurrentChat);
on(engagementSelectEl, "change", () => {
  serverChatId = null;
  if (currentView === "command") loadCommandCenter();
});
on(authForm, "submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("authUser")?.value?.trim();
  const password = document.getElementById("authPass")?.value || "";
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    authToken = data.token;
    localStorage.setItem(AUTH_TOKEN_KEY, authToken);
    await refreshAuthStatus();
    await loadEngagements();
    closeAuth();
    appendMessage("assistant", renderMarkdown(`**Signed in** as ${data.user.username}`), true);
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Login failed:** ${err.message}`), true);
  }
});
on(document.getElementById("authRegisterBtn"), "click", async () => {
  const username = document.getElementById("authUser")?.value?.trim();
  const password = document.getElementById("authPass")?.value || "";
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    authToken = data.token;
    localStorage.setItem(AUTH_TOKEN_KEY, authToken);
    await refreshAuthStatus();
    await loadEngagements();
    closeAuth();
    appendMessage("assistant", renderMarkdown(`**Registered** as ${data.user.username}`), true);
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Register failed:** ${err.message}`), true);
  }
});
on(document.getElementById("authLogoutBtn"), "click", async () => {
  await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
  authToken = "";
  localStorage.removeItem(AUTH_TOKEN_KEY);
  await refreshAuthStatus();
  closeAuth();
});
if (authModal) {
  authModal.querySelectorAll("[data-close-auth]").forEach((el) => el.addEventListener("click", closeAuth));
}
on(hermesNewSessionBtn, "click", newHermesSession);
on(hermesRefreshStatusBtn, "click", refreshHermesStatus);
on(menuToggle, "click", toggleMenu);
on(sidebarBackdrop, "click", closeSidebar);
on(newChatBtn, "click", () => {
  showView("chat");
  serverChatId = null;
  newChat();
});
on(themeToggleBtn, "click", toggleTheme);
on(themeToggleTopBtn, "click", toggleTheme);
on(settingsForm, "submit", saveSettings);
on(settingsTrainBtn, "click", startUnslothTrain);
on(document.getElementById("settingsRefreshTools"), "click", () => {
  refreshSettingsToolsHint();
  loadToolsStatus();
});
on(document.getElementById("setTheme"), "change", applyThemeFromSettings);
if (settingsModal) {
  settingsModal.querySelectorAll("[data-close-settings]").forEach((el) => {
    el.addEventListener("click", closeSettings);
  });
}
on(backendEl, "change", () => {
  switchBackend(backendEl.value);
  closeSidebar();
});
on(modeEl, "change", () => {
  const mode = modeEl.value;
  // Only auto-enable expensive toggles for modes that need them (keeps default chat fast)
  if (webSearchEl) webSearchEl.checked = mode === "research";
  if (netAssessEl) netAssessEl.checked = mode === "assess";
  if (localToolsEl) localToolsEl.checked = mode === "assess" || mode === "lab_offensive";
  renderQuickPrompts();
  const chat = getCurrentChat();
  if (chat) {
    chat.mode = mode;
    persistCurrentChat();
  }
  closeSidebar();
});
on(setupPrimaryEl, "click", async () => {
  if (setupAction === "preload") {
    hideSetupPanel();
    await preloadModel();
    return;
  }
  if (setupAction === "settings") {
    openSettings();
    return;
  }
  if (setupAction === "copy" && lastSetupCommand) {
    try {
      await navigator.clipboard.writeText(lastSetupCommand);
      appendMessage("assistant", renderMarkdown(`Copied command: \`${lastSetupCommand}\``), true);
    } catch {
      appendMessage("assistant", renderMarkdown(`Run this command:\n\n\`${lastSetupCommand}\``), true);
    }
    return;
  }
  appendMessage(
    "assistant",
    renderMarkdown("See `README.md` and `docs/cursor-local-models.md` for backend setup steps."),
    true
  );
});
on(setupDismissEl, "click", () => {
  const key = setupPanelEl?.dataset?.key || "";
  if (key) {
    setupDismissedKey = key;
    sessionStorage.setItem("setupDismissed", key);
  }
  hideSetupPanel();
});

on(modelEl, "change", () => {
  if (backendEl.value !== "ollama") return;
  const opt = modelEl.selectedOptions[0];
  if (opt?.dataset.notInstalled) return;
  switchModel(modelEl.value);
});

on(inputEl, "keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
on(inputEl, "input", resizeInput);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (gapModal && !gapModal.classList.contains("hidden")) closeGap();
    else if (dashModal && !dashModal.classList.contains("hidden")) closeDash();
    else if (riskModal && !riskModal.classList.contains("hidden")) closeRisk();
    else if (vulnModal && !vulnModal.classList.contains("hidden")) closeVuln();
    else if (assetModal && !assetModal.classList.contains("hidden")) closeAsset();
    else if (remModal && !remModal.classList.contains("hidden")) closeRem();
    else if (playbookModal && !playbookModal.classList.contains("hidden")) closePlaybook();
    else if (campaignModal && !campaignModal.classList.contains("hidden")) closeCampaign();
    else if (authModal && !authModal.classList.contains("hidden")) closeAuth();
    else if (settingsModal && !settingsModal.classList.contains("hidden")) closeSettings();
    else closeSidebar();
  }
});

initTheme();
loadBackend();
loadModes();
loadModels();
loadToolsStatus();
startRealtimeFeed();
ensureActiveChat();
refreshAuthStatus().then(loadEngagements);
checkHealth().then(() => {
  showWelcome();
  showView("command", { skipFocus: true });
});
wireCommandCenterUi();
setInterval(checkHealth, 90000);
setInterval(() => {
  if (currentView === "command") loadCommandCenter();
}, 120000);
resizeInput();

async function loadToolsStatus() {
  if (!toolsStatusEl) return;
  try {
    const res = await fetch("/api/tools");
    const data = await res.json();
    const avail = data.available_count ?? 0;
    const total = data.count ?? 0;
    const names = (data.tools || [])
      .filter((t) => t.available)
      .map((t) => t.id)
      .slice(0, 8)
      .join(", ");
    toolsStatusEl.textContent = `Tools ${avail}/${total} ready${names ? `: ${names}` : ""}`;
    const aw = (data.auto_awareness || ["phishing_url", "email_auth"]).join(", ");
    toolsStatusEl.title =
      `Awareness auto: ${aw}\n` +
      (data.tools || [])
        .map((t) => `${t.available ? "✓" : "·"} ${t.id} — ${t.description}`)
        .join("\n");
  } catch {
    toolsStatusEl.textContent = "Tools: unavailable";
  }
}

async function showWelcome() {
  if (emptyLeadEl) {
    emptyLeadEl.textContent =
      "Start from an empty workspace — ask a question, import a scan, or open Mission Control.";
  }
  syncEmptyState();
  renderChatList();
  updateChatTitle();
}

/* ops surfaces: /api/soc /api/reports /api/search /api/intel/watch /api/incidents */

