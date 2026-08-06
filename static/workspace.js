/* Remaining Command Center workspaces: modules tables, intel, reports, SOC, evidence, AI tabs */
(function () {
  const qs = (id) => document.getElementById(id);

  function authHeaders(extra) {
    if (typeof window.authHeaders === "function") return window.authHeaders(extra || {});
    const h = Object.assign({}, extra || {});
    const t = localStorage.getItem("securaiq.auth.token");
    if (t) h.Authorization = `Bearer ${t}`;
    return h;
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function createServiceNowIncident({ summary, description, remediationId }, btn) {
    if (btn) btn.disabled = true;
    try {
      const res = await fetch("/api/integrations/servicenow/incident", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          short_description: summary,
          description: description || "",
          remediation_id: remediationId || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      const msg = data.url
        ? `**ServiceNow:** [${data.number || data.sys_id || "incident"}](${data.url})`
        : `**ServiceNow:** ${data.number || data.sys_id || "created"}`;
      if (typeof notifyUser === "function") notifyUser(msg);
      else if (typeof appendMessage === "function") appendMessage("assistant", renderMarkdown(msg), true);
      return data;
    } catch (err) {
      const msg = `**ServiceNow failed:** ${err.message}`;
      if (typeof notifyUser === "function") notifyUser(msg);
      else if (typeof appendMessage === "function") appendMessage("assistant", renderMarkdown(msg), true);
      else alert(err.message);
      return null;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function downloadApiExport(url, filename) {
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function hideAllViews() {
    document.querySelectorAll(".workspace-view").forEach((el) => el.classList.add("hidden"));
  }

  function setComposerMode(view) {
    const wrap = qs("composerWrap");
    const fab = qs("aiFab");
    if (!wrap) return;
    const isChat = view === "chat";
    const isCommand = view === "command";
    const isPage = !isChat && !isCommand;
    wrap.classList.toggle("is-command", isCommand);
    wrap.classList.toggle("is-page", isPage);
    wrap.classList.toggle("is-chat", isChat);
    wrap.classList.toggle("is-floating", !isChat);
    if (isChat) {
      wrap.classList.remove("is-open");
      fab?.classList.add("hidden");
      fab?.setAttribute("aria-expanded", "false");
    } else {
      // Docked footer becomes FAB + floating panel so modules keep full canvas.
      if (!wrap.classList.contains("is-open")) fab?.classList.remove("hidden");
    }
  }

  function openFloatingAssistant() {
    if (typeof window.openAiAssistant === "function") window.openAiAssistant();
  }

  function wireAskAiButtons(rootId) {
    qs(rootId)?.querySelectorAll(".ws-ask-ai").forEach((btn) => {
      btn.addEventListener("click", () => {
        let payload = {};
        try {
          payload = JSON.parse(btn.getAttribute("data-json") || "{}");
        } catch (e) {}
        if (typeof window.askAboutEntity === "function") {
          window.askAboutEntity(btn.getAttribute("data-kind"), payload);
        }
      });
    });
  }

  function setPageComposerHint(view) {
    const input = qs("input");
    const wrap = qs("composerWrap");
    if (!input || !wrap) return;
    const hints = {
      assets: "Ask AI about an asset, or type a hardening question…",
      risks: "Ask AI to prioritize risks or draft mitigations…",
      vulns: "Ask AI to triage a CVE, or paste scan findings…",
      remediations: "Ask AI for control implementation guidance…",
      soc: "Ask AI for IR steps on an incident…",
      intel: "Ask AI for a threat brief on a CVE or IOC…",
      reports: "Ask AI to draft an executive or technical report…",
      evidence: "Ask AI what evidence is missing for an audit…",
      playbooks: "Ask AI to expand or tabletop a playbook…",
      campaigns: "Ask AI to design an awareness campaign…",
      orgs: "Ask about RBAC / tenancy for your engagement…",
    };
    if (view === "chat") {
      input.placeholder = "Ask SecuraIQ…";
      wrap.classList.remove("is-page-context");
    } else if (hints[view]) {
      input.placeholder = hints[view];
      wrap.classList.add("is-page-context");
    } else {
      input.placeholder = "Ask SecuraIQ…";
      wrap.classList.remove("is-page-context");
    }
  }

  window.showWorkspace = function showWorkspace(view, opts) {
    opts = opts || {};
    hideAllViews();
    const map = {
      command: "viewCommand",
      chat: "viewChat",
      assets: "viewAssets",
      risks: "viewRisks",
      vulns: "viewVulns",
      remediations: "viewRemediations",
      playbooks: "viewPlaybooksPage",
      campaigns: "viewCampaignsPage",
      intel: "viewIntel",
      reports: "viewReports",
      soc: "viewSoc",
      evidence: "viewEvidence",
      orgs: "viewOrgs",
      frameworks: "viewFrameworks",
      integrations: "viewIntegrations",
      billing: "viewBilling",
      graph: "viewGraph",
      automation: "viewAutomation",
    };
    const id = map[view] || "viewCommand";
    const panel = qs(id);
    if (panel) panel.classList.remove("hidden");
    if (view === "chat" || view === "command") {
      if (typeof showView === "function") showView(view, opts);
      setPageComposerHint(view);
      return;
    }
    if (typeof window.__setSecuraIQView === "function") window.__setSecuraIQView(view);
    setComposerMode(view);
    setPageComposerHint(view);
    document.querySelectorAll(".nav-item[data-view], .nav-link[data-workspace]").forEach((el) => {
      const v = el.getAttribute("data-view") || el.getAttribute("data-workspace");
      el.classList.toggle("active", v === view);
    });
    const title = qs("topbarChatTitle");
    if (title) {
      const labels = {
        command: "Command Center",
        chat: "AI Assistant",
        assets: "Assets",
        risks: "Risk Register",
        vulns: "Vulnerabilities",
        remediations: "Remediations",
        playbooks: "Playbooks",
        campaigns: "Campaigns",
        intel: "Threat Intelligence",
        reports: "Reports",
        soc: "SOC",
        evidence: "Evidence Locker",
        orgs: "Organizations",
        frameworks: "Frameworks",
        integrations: "Integrations",
        billing: "Billing",
        graph: "Knowledge Graph",
        automation: "Automation",
      };
      title.textContent = labels[view] || "SecuraIQ";
    }
    if (view === "command" && typeof loadCommandCenter === "function") loadCommandCenter();
    if (view === "chat" && typeof syncEmptyState === "function") syncEmptyState();
    if (view === "assets") renderAssetsPage();
    if (view === "risks") renderRisksPage();
    if (view === "vulns") renderVulnsPage();
    if (view === "remediations") renderRemsPage();
    if (view === "playbooks") renderPlaybooksPage();
    if (view === "campaigns") renderCampaignsPage();
    if (view === "intel") renderIntelPage();
    if (view === "reports") renderReportsPage();
    if (view === "soc") renderSocPage();
    if (view === "evidence") renderEvidencePage();
    if (view === "orgs") renderOrgsPage();
    if (view === "frameworks") renderFrameworksPage();
    if (view === "integrations") renderIntegrationsPage();
    if (view === "billing") renderBillingPage();
    if (view === "graph") renderGraphPage();
    if (view === "automation") renderAutomationPage();
    if (typeof closeSidebar === "function") closeSidebar();
  };

  // Do not override showView — app.js owns chat/command; we extend via showWorkspace + nav.
  async function renderTable(targetId, headers, rowsHtml, emptyText) {
    const el = qs(targetId);
    if (!el) return;
    if (!rowsHtml) {
      el.innerHTML = `<div class="page-empty">
        <p class="page-empty-title">${escapeHtml(emptyText || "Nothing here yet")}</p>
        <p class="hint">Starts empty — add data when you’re ready.</p>
      </div>`;
      return;
    }
    el.innerHTML = `
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>`;
  }

  async function renderAssetsPage() {
    const res = await fetch("/api/assets", { headers: authHeaders() });
    const data = await res.json();
    const assets = data.assets || [];
    const typeBuckets = {
      server: 0,
      endpoint: 0,
      container: 0,
      cloud: 0,
      repository: 0,
      database: 0,
      application: 0,
      domain: 0,
      api: 0,
      other: 0,
    };
    assets.forEach((a) => {
      const t = String(a.asset_type || "other").toLowerCase();
      if (t in typeBuckets) typeBuckets[t] += 1;
      else if (/host|vm|server/.test(t)) typeBuckets.server += 1;
      else if (/endpoint|laptop|workstation/.test(t)) typeBuckets.endpoint += 1;
      else if (/container|k8s|pod/.test(t)) typeBuckets.container += 1;
      else if (/aws|azure|gcp|cloud/.test(t)) typeBuckets.cloud += 1;
      else if (/repo|git/.test(t)) typeBuckets.repository += 1;
      else if (/db|sql|postgres|mongo/.test(t)) typeBuckets.database += 1;
      else if (/app|service/.test(t)) typeBuckets.application += 1;
      else if (/domain|dns/.test(t)) typeBuckets.domain += 1;
      else if (/api/.test(t)) typeBuckets.api += 1;
      else typeBuckets.other += 1;
    });
    const rows = assets
      .map(
        (a) => `<tr>
        <td><strong>${escapeHtml(a.name)}</strong></td>
        <td>${escapeHtml(a.asset_type)}</td>
        <td>${escapeHtml(a.criticality)}</td>
        <td>${escapeHtml(a.owner || "—")}</td>
        <td class="ws-actions">
          <button type="button" class="btn-secondary ws-ask-ai" data-kind="asset" data-json="${escapeHtml(
            JSON.stringify({ id: a.id, name: a.name, asset_type: a.asset_type, criticality: a.criticality })
          )}">Ask AI</button>
          <button type="button" class="btn-secondary ws-edit-asset" data-id="${a.id}" data-name="${escapeHtml(a.name)}" data-owner="${escapeHtml(a.owner || "")}" data-crit="${escapeHtml(a.criticality)}">Edit</button>
          <button type="button" class="btn-secondary ws-del-asset" data-id="${a.id}">Delete</button>
        </td>
      </tr>`
      )
      .join("");
    const el = qs("assetsPageBody");
    if (!el) return;
    const core = ["server", "endpoint", "container", "cloud", "repository", "database", "application", "domain", "api"];
    const tileHtml = core
      .map((k) => `<div class="asset-type-tile"><span>${escapeHtml(k)}</span><strong>${typeBuckets[k] || 0}</strong></div>`)
      .join("");
    el.innerHTML = `
      <div class="asset-type-grid" aria-label="Asset classes">${tileHtml}</div>
      ${
        rows
          ? `<div class="data-table-wrap"><table class="data-table"><thead><tr>
              <th>Name</th><th>Type</th><th>Criticality</th><th>Owner</th><th></th>
            </tr></thead><tbody>${rows}</tbody></table></div>`
          : `<div class="page-empty"><p class="page-empty-title">No assets yet</p>
             <p class="hint">Add servers, repos, cloud accounts, and APIs to map attack surface.</p></div>`
      }`;
    wireAskAiButtons("assetsPageBody");
    qs("assetsPageBody")?.querySelectorAll(".ws-edit-asset").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const name = prompt("Asset name:", btn.getAttribute("data-name") || "");
        if (!name?.trim()) return;
        const owner = prompt("Owner:", btn.getAttribute("data-owner") || "") ?? "";
        const criticality = prompt("Criticality (low/medium/high/critical):", btn.getAttribute("data-crit") || "medium") ?? "medium";
        await fetch(`/api/assets/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ name: name.trim(), owner, criticality }),
        });
        renderAssetsPage();
      });
    });
    qs("assetsPageBody")?.querySelectorAll(".ws-del-asset").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/assets/${btn.getAttribute("data-id")}`, { method: "DELETE", headers: authHeaders() });
        renderAssetsPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
  }

  async function renderRisksPage() {
    const res = await fetch("/api/risks", { headers: authHeaders() });
    const data = await res.json();
    const rows = (data.risks || [])
      .map(
        (r) => `<tr>
        <td>${escapeHtml(r.threat)}</td>
        <td>${r.likelihood}</td>
        <td>${r.impact}</td>
        <td><strong>${r.risk_score}</strong></td>
        <td>${escapeHtml(r.owner || "—")}</td>
        <td>${escapeHtml(r.status)}</td>
        <td>${escapeHtml(r.mitigation || "—")}</td>
        <td class="ws-actions">
          <button type="button" class="btn-secondary ws-ask-ai" data-kind="risk" data-json="${escapeHtml(
            JSON.stringify({
              id: r.id,
              threat: r.threat,
              risk_score: r.risk_score,
              likelihood: r.likelihood,
              impact: r.impact,
            })
          )}">Ask AI</button>
          <button type="button" class="btn-secondary ws-mitigate" data-id="${r.id}">Mitigate</button>
          <button type="button" class="btn-secondary ws-del-risk" data-id="${r.id}">Delete</button>
        </td>
      </tr>`
      )
      .join("");
    await renderTable(
      "risksPageBody",
      ["Risk", "L", "I", "Score", "Owner", "Status", "Mitigation", ""],
      rows,
      "No risks yet"
    );
    wireAskAiButtons("risksPageBody");
    qs("risksPageBody")?.querySelectorAll(".ws-mitigate").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/risks/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ status: "mitigated" }),
        });
        renderRisksPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
    qs("risksPageBody")?.querySelectorAll(".ws-del-risk").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this risk?")) return;
        await fetch(`/api/risks/${btn.getAttribute("data-id")}`, { method: "DELETE", headers: authHeaders() });
        renderRisksPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
  }
  let _vulnFilters = { q: "", severity: "", status: "", source: "", owner: "" };
  let _vulnSelectedId = "";

  function vulnAgeDays(v) {
    const raw = v.created_at || v.updated_at || "";
    if (!raw) return null;
    const t = Date.parse(raw);
    if (Number.isNaN(t)) return null;
    return Math.max(0, Math.floor((Date.now() - t) / 86400000));
  }

  function renderVulnDetail(v) {
    const panel = qs("vulnDetailPanel");
    if (!panel) return;
    if (!v) {
      panel.innerHTML = `<p class="hint">Select a finding to see AI summary, patch guidance, and evidence.</p>`;
      return;
    }
    const age = vulnAgeDays(v);
    const src = (v.source || "").split(":")[0] || "import";
    const refs = [];
    if (v.cve) refs.push(`https://nvd.nist.gov/vuln/detail/${encodeURIComponent(v.cve)}`);
    panel.innerHTML = `
      <header class="entity-detail-head">
        <p class="sev sev-${escapeHtml(v.severity)}">${escapeHtml(v.severity || "—")}</p>
        <h2>${escapeHtml(v.cve || "Finding")}</h2>
        <p class="entity-detail-title">${escapeHtml(v.title || "")}</p>
      </header>
      <dl class="entity-meta">
        <div><dt>CVSS</dt><dd>${escapeHtml(v.cvss != null ? v.cvss : "—")}</dd></div>
        <div><dt>Asset</dt><dd>${escapeHtml(v.asset_name || "—")}</dd></div>
        <div><dt>Owner</dt><dd>${escapeHtml(v.owner || "Unassigned")}</dd></div>
        <div><dt>Status</dt><dd>${escapeHtml(v.status || "open")}</dd></div>
        <div><dt>SLA</dt><dd>${escapeHtml(v.sla_due || "—")}</dd></div>
        <div><dt>Age</dt><dd>${age == null ? "—" : age + "d"}</dd></div>
        <div><dt>Scanner</dt><dd>${escapeHtml(src)}</dd></div>
        <div><dt>Exploit</dt><dd>${v.cve ? "Check KEV / advisory" : "—"}</dd></div>
      </dl>
      <section class="entity-section">
        <h3>AI Summary</h3>
        <p class="hint">Use the assistant for root cause, attack path, and suggested fix without leaving this page.</p>
        <div class="cc-action-row">
          <button type="button" class="btn-primary-cc ws-ask-ai" data-kind="vuln" data-json="${escapeHtml(
            JSON.stringify({
              id: v.id,
              cve: v.cve,
              title: v.title,
              severity: v.severity,
              asset_name: v.asset_name,
              cvss: v.cvss,
            })
          )}">Ask AI</button>
          <button type="button" class="btn-secondary ws-vuln-ai" data-prompt="root">Root cause</button>
          <button type="button" class="btn-secondary ws-vuln-ai" data-prompt="patch">Suggest fix</button>
          <button type="button" class="btn-secondary ws-vuln-ai" data-prompt="ticket">Generate ticket</button>
        </div>
      </section>
      <section class="entity-section">
        <h3>References</h3>
        <ul class="entity-refs">
          ${
            refs.length
              ? refs.map((u) => `<li><a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(u)}</a></li>`).join("")
              : "<li class='hint'>No CVE reference</li>"
          }
        </ul>
      </section>
      <section class="entity-section">
        <h3>MITRE / Evidence / Timeline</h3>
        <p class="hint">Map techniques via Knowledge Graph · attach evidence on triage · SLA ${escapeHtml(
          v.sla_due || "unset"
        )} · updated ${escapeHtml(v.updated_at || v.created_at || "—")}</p>
      </section>
      <div class="cc-action-row">
        <button type="button" class="btn-primary-cc ws-triage-vuln" data-id="${escapeHtml(v.id)}" data-jira="0">Triage</button>
        <button type="button" class="btn-secondary ws-triage-vuln" data-id="${escapeHtml(v.id)}" data-jira="1">Triage+Jira</button>
        <button type="button" class="btn-secondary ws-vuln-jira" data-id="${escapeHtml(v.id)}">Jira</button>
        <button type="button" class="btn-secondary ws-vuln-sn" data-id="${escapeHtml(v.id)}" data-title="${escapeHtml(v.title || v.cve || "")}">ServiceNow</button>
        <button type="button" class="btn-secondary ws-close-vuln" data-id="${escapeHtml(v.id)}">Close</button>
      </div>`;
    wireAskAiButtons("vulnDetailPanel");
    wireVulnActionButtons(panel);
    panel.querySelectorAll(".ws-vuln-ai").forEach((btn) => {
      btn.addEventListener("click", () => {
        const kind = btn.getAttribute("data-prompt");
        const prompts = {
          root: `Root-cause analysis for ${v.cve || ""} — ${v.title || v.id} on asset ${v.asset_name || "?"}. Include contributing config issues and blast radius.`,
          patch: `Suggest fix and verify steps for ${v.cve || ""} — ${v.title || v.id} (severity=${v.severity}, CVSS=${v.cvss ?? "?"}).`,
          ticket: `Draft a Jira-ready remediation ticket for ${v.cve || ""} — ${v.title || v.id} with acceptance criteria and SLA.`,
        };
        if (typeof window.runNavPrompt === "function") {
          window.runNavPrompt("blueteam", prompts[kind] || prompts.patch, { stay: true });
        }
      });
    });
  }

  function wireVulnActionButtons(root) {
    root?.querySelectorAll(".ws-triage-vuln").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        const withJira = btn.getAttribute("data-jira") === "1";
        try {
          const res = await fetch(`/api/vulnerabilities/${btn.getAttribute("data-id")}/triage`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ owner: "SecOps", create_jira: withJira }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.detail || res.status);
          if (typeof notifyUser === "function") {
            let msg = `**Triaged** → risk \`${(data.risk || {}).risk_score ?? "?"}\` · remediation created.`;
            if (withJira) {
              if (data.jira?.key) {
                msg += data.jira.url
                  ? ` Jira: [${data.jira.key}](${data.jira.url}).`
                  : ` Jira: \`${data.jira.key}\`.`;
              } else if (data.jira_error) {
                msg += ` Jira failed: ${data.jira_error}`;
              }
            }
            notifyUser(msg);
          }
          renderVulnsPage();
      loadVulnSampleButtons();
          if (typeof loadCommandCenter === "function") loadCommandCenter();
        } catch (err) {
          if (typeof notifyUser === "function") notifyUser(`**Triage failed:** ${err.message}`);
          else alert(err.message);
        } finally {
          btn.disabled = false;
        }
      });
    });
    root?.querySelectorAll(".ws-vuln-jira").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          const res = await fetch(`/api/vulnerabilities/${btn.getAttribute("data-id")}/jira`, {
            method: "POST",
            headers: authHeaders(),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.detail || res.status);
          if (typeof notifyUser === "function") {
            notifyUser(data.url ? `**Jira:** [${data.key}](${data.url})` : `**Jira:** ${data.key || "created"}`);
          }
        } catch (err) {
          if (typeof notifyUser === "function") notifyUser(`**Jira failed:** ${err.message}`);
          else alert(err.message);
        }
      });
    });
    root?.querySelectorAll(".ws-vuln-sn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const title = btn.getAttribute("data-title") || "Vulnerability";
        await createServiceNowIncident(
          {
            summary: `[SecuraIQ] ${title}`.slice(0, 160),
            description: `Vulnerability ${btn.getAttribute("data-id")} from SecuraIQ register.`,
          },
          btn
        );
      });
    });
    root?.querySelectorAll(".ws-close-vuln").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/vulnerabilities/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ status: "closed" }),
        });
        renderVulnsPage();
      loadVulnSampleButtons();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
  }

  function filteredVulns() {
    const f = _vulnFilters;
    const q = (f.q || "").trim().toLowerCase();
    return _vulnCache.filter((v) => {
      if (f.severity && (v.severity || "").toLowerCase() !== f.severity) return false;
      if (f.status && (v.status || "").toLowerCase() !== f.status) return false;
      if (f.source) {
        const src = ((v.source || "").split(":")[0] || "").toLowerCase();
        if (src !== f.source) return false;
      }
      if (f.owner && !(v.owner || "").toLowerCase().includes(f.owner.toLowerCase())) return false;
      if (q) {
        const blob = `${v.cve || ""} ${v.title || ""} ${v.asset_name || ""} ${v.owner || ""}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }

  function paintVulnTable() {
    const list = filteredVulns().slice(0, 200);
    const rows = list
      .map((v) => {
        const age = vulnAgeDays(v);
        const src = (v.source || "").split(":")[0] || "—";
        const selected = v.id === _vulnSelectedId ? " is-selected" : "";
        return `<tr class="vuln-row${selected}" data-id="${escapeHtml(v.id)}" tabindex="0">
        <td>${escapeHtml(v.cve || "—")}</td>
        <td><span class="sev sev-${escapeHtml(v.severity)}">${escapeHtml(v.severity)}</span></td>
        <td>${escapeHtml(v.cvss != null ? v.cvss : "—")}</td>
        <td>${escapeHtml(v.asset_name || "—")}</td>
        <td>${escapeHtml(v.owner || "—")}</td>
        <td>${escapeHtml(v.status)}</td>
        <td>${escapeHtml(v.sla_due || "—")}</td>
        <td>${age == null ? "—" : age + "d"}</td>
        <td>${escapeHtml(src)}</td>
      </tr>`;
      })
      .join("");
    const el = qs("vulnsPageBody");
    if (!el) return;
    if (!rows) {
      el.innerHTML = `<div class="page-empty">
        <p class="page-empty-title">No matching vulnerabilities</p>
        <p class="hint">Adjust filters or import a scanner export (Trivy, Semgrep, ZAP, …).</p>
      </div>`;
      renderVulnDetail(null);
      return;
    }
    el.innerHTML = `
      <p class="hint"><strong>Golden path:</strong> Import → select finding → Triage → Jira → verify → Close. Showing ${list.length} of ${_vulnCache.length}.</p>
      <div class="data-table-wrap">
        <table class="data-table vuln-table">
          <thead><tr>
            <th>CVE</th><th>Severity</th><th>CVSS</th><th>Asset</th><th>Owner</th>
            <th>Status</th><th>SLA</th><th>Age</th><th>Scanner</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
    el.querySelectorAll(".vuln-row").forEach((row) => {
      const open = () => {
        _vulnSelectedId = row.getAttribute("data-id") || "";
        const v = _vulnCache.find((x) => x.id === _vulnSelectedId);
        el.querySelectorAll(".vuln-row").forEach((r) => r.classList.toggle("is-selected", r === row));
        renderVulnDetail(v || null);
      };
      row.addEventListener("click", open);
      row.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      });
    });
    if (_vulnSelectedId) {
      const still = list.find((v) => v.id === _vulnSelectedId) || list[0];
      _vulnSelectedId = still?.id || "";
      renderVulnDetail(still || null);
    } else if (list[0]) {
      _vulnSelectedId = list[0].id;
      renderVulnDetail(list[0]);
      el.querySelector(`.vuln-row[data-id="${String(list[0].id).replace(/"/g, "")}"]`)?.classList.add("is-selected");
    }
  }

  function paintVulnFilters() {
    const bar = qs("vulnFilterBar");
    if (!bar) return;
    const sevs = [...new Set(_vulnCache.map((v) => (v.severity || "").toLowerCase()).filter(Boolean))];
    const statuses = [...new Set(_vulnCache.map((v) => (v.status || "").toLowerCase()).filter(Boolean))];
    const sources = [
      ...new Set(_vulnCache.map((v) => ((v.source || "").split(":")[0] || "").toLowerCase()).filter(Boolean)),
    ];
    bar.innerHTML = `
      <input type="search" id="vulnFilterQ" class="filter-input" placeholder="Search CVE, title, asset…" value="${escapeHtml(
        _vulnFilters.q
      )}" />
      <select id="vulnFilterSev" class="filter-select" title="Severity">
        <option value="">Severity</option>
        ${sevs.map((s) => `<option value="${escapeHtml(s)}" ${_vulnFilters.severity === s ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}
      </select>
      <select id="vulnFilterStatus" class="filter-select" title="Status">
        <option value="">Status</option>
        ${statuses
          .map((s) => `<option value="${escapeHtml(s)}" ${_vulnFilters.status === s ? "selected" : ""}>${escapeHtml(s)}</option>`)
          .join("")}
      </select>
      <select id="vulnFilterSource" class="filter-select" title="Scanner">
        <option value="">Scanner</option>
        ${sources
          .map((s) => `<option value="${escapeHtml(s)}" ${_vulnFilters.source === s ? "selected" : ""}>${escapeHtml(s)}</option>`)
          .join("")}
      </select>
      <input type="text" id="vulnFilterOwner" class="filter-input filter-input-sm" placeholder="Owner" value="${escapeHtml(
        _vulnFilters.owner
      )}" />
      <button type="button" class="btn-ghost" id="vulnFilterReset">Reset</button>`;
    const sync = () => {
      _vulnFilters = {
        q: qs("vulnFilterQ")?.value || "",
        severity: qs("vulnFilterSev")?.value || "",
        status: qs("vulnFilterStatus")?.value || "",
        source: qs("vulnFilterSource")?.value || "",
        owner: qs("vulnFilterOwner")?.value || "",
      };
      paintVulnTable();
    };
    ["vulnFilterQ", "vulnFilterSev", "vulnFilterStatus", "vulnFilterSource", "vulnFilterOwner"].forEach((id) => {
      qs(id)?.addEventListener("input", sync);
      qs(id)?.addEventListener("change", sync);
    });
    qs("vulnFilterReset")?.addEventListener("click", () => {
      _vulnFilters = { q: "", severity: "", status: "", source: "", owner: "" };
      paintVulnFilters();
      paintVulnTable();
    });
  }

  async function renderVulnsPage() {
    const res = await fetch("/api/vulnerabilities", { headers: authHeaders() });
    const data = await res.json();
    _vulnCache = data.vulnerabilities || [];
    paintVulnFilters();
    paintVulnTable();
  }

  async function renderRemsPage() {
    const res = await fetch("/api/gap/remediations", { headers: authHeaders() });
    const data = await res.json();
    const rows = (data.remediations || [])
      .map(
        (r) => `<tr>
        <td>${escapeHtml(r.control_id)}</td>
        <td>${escapeHtml(r.title)}</td>
        <td>${escapeHtml(r.owner || "unassigned")}</td>
        <td>${escapeHtml(r.status)}</td>
        <td>${escapeHtml(r.due_date || "—")}</td>
        <td class="ws-actions">
          ${
            r.status !== "done"
              ? `<button type="button" class="btn-secondary ws-rem-done" data-id="${r.id}">Mark done</button>`
              : ""
          }
          <button type="button" class="btn-secondary ws-ask-ai" data-kind="remediation" data-json="${escapeHtml(
            JSON.stringify({ id: r.id, control_id: r.control_id, title: r.title })
          )}">Ask AI</button>
          <button type="button" class="btn-secondary ws-rem-jira" data-id="${r.id}" data-title="${escapeHtml(
            r.title
          )}" data-control="${escapeHtml(r.control_id)}">Jira</button>
          <button type="button" class="btn-secondary ws-rem-sn" data-id="${r.id}" data-title="${escapeHtml(
            r.title
          )}" data-control="${escapeHtml(r.control_id)}">ServiceNow</button>
        </td>
      </tr>`
      )
      .join("");
    await renderTable(
      "remsPageBody",
      ["Control", "Title", "Owner", "Status", "Due", ""],
      rows,
      "No remediations — run Gap analysis"
    );
    wireAskAiButtons("remsPageBody");
    qs("remsPageBody")?.querySelectorAll(".ws-rem-done").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/gap/remediations/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ status: "done" }),
        });
        renderRemsPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
    qs("remsPageBody")?.querySelectorAll(".ws-rem-jira").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const title = btn.getAttribute("data-title") || "Remediation";
        const control = btn.getAttribute("data-control") || "";
        btn.disabled = true;
        try {
          const res = await fetch("/api/integrations/jira/issue", {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
              remediation_id: id,
              summary: `[SecuraIQ] ${control} — ${title}`.slice(0, 255),
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(
            typeof window.formatApiDetail === "function"
              ? window.formatApiDetail(data.detail, `HTTP ${res.status}`)
              : data.detail || `HTTP ${res.status}`
          );
          const msg = data.url
            ? `**Jira created:** [${data.key}](${data.url})`
            : `**Jira created:** ${data.key || "ok"}`;
          if (typeof window.notifyUser === "function") window.notifyUser(msg);
          else if (typeof appendMessage === "function") appendMessage("assistant", renderMarkdown(msg), true);
          else alert(data.key || "Jira issue created");
        } catch (err) {
          if (typeof window.notifyUser === "function") window.notifyUser(`**Jira failed:** ${err.message}`);
          else if (typeof appendMessage === "function")
            appendMessage("assistant", renderMarkdown(`**Jira failed:** ${err.message}`), true);
          else alert(err.message);
        } finally {
          btn.disabled = false;
        }
      });
    });
    qs("remsPageBody")?.querySelectorAll(".ws-rem-sn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const title = btn.getAttribute("data-title") || "Remediation";
        const control = btn.getAttribute("data-control") || "";
        await createServiceNowIncident(
          {
            summary: `[SecuraIQ] ${control} — ${title}`.slice(0, 160),
            remediationId: btn.getAttribute("data-id"),
          },
          btn
        );
      });
    });
    if (!window.__securaiqRemFormWired) {
      window.__securaiqRemFormWired = true;
      qs("remCreateForm")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const title = qs("remNewTitle")?.value?.trim();
        if (!title) return;
        const res = await fetch("/api/gap/remediations", {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            title,
            control_id: qs("remNewControl")?.value?.trim() || "MC",
            owner: qs("remNewOwner")?.value?.trim() || "",
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          alert(data.detail || `HTTP ${res.status}`);
          return;
        }
        qs("remNewTitle").value = "";
        qs("remNewControl").value = "";
        qs("remNewOwner").value = "";
        renderRemsPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    }
  }

  async function renderPlaybooksPage() {
    const res = await fetch("/api/playbooks", { headers: authHeaders() });
    const data = await res.json();
    const rows = (data.playbooks || [])
      .map(
        (p) => `<tr>
        <td><strong>${escapeHtml(p.title)}</strong></td>
        <td>${escapeHtml(p.category)}</td>
        <td>${escapeHtml(p.severity)}</td>
        <td><pre class="mini-pre">${escapeHtml(p.steps || "")}</pre></td>
      </tr>`
      )
      .join("");
    await renderTable("playbooksPageBody", ["Title", "Category", "Severity", "Steps"], rows, "No playbooks");
  }

  async function renderCampaignsPage() {
    const res = await fetch("/api/campaigns", { headers: authHeaders() });
    const data = await res.json();
    const rows = (data.campaigns || [])
      .map((c) => {
        const sent = Number(c.sent_count || 0);
        const click = sent ? Math.round((100 * Number(c.click_count || 0)) / sent) : 0;
        const report = sent ? Math.round((100 * Number(c.report_count || 0)) / sent) : 0;
        return `<tr>
          <td>${escapeHtml(c.name)}</td>
          <td>${escapeHtml(c.status)}</td>
          <td>${escapeHtml(c.audience || "—")}</td>
          <td>${click}%</td>
          <td>${report}%</td>
        </tr>`;
      })
      .join("");
    await renderTable(
      "campaignsPageBody",
      ["Campaign", "Status", "Audience", "Click %", "Report %"],
      rows,
      "No campaigns"
    );
  }

  async function renderIntelPage() {
    const body = qs("intelPageBody");
    if (!body) return;
    const [watchRes, vulnRes, kevRes, catalogRes] = await Promise.all([
      fetch("/api/intel/watch", { headers: authHeaders() }),
      fetch("/api/vulnerabilities", { headers: authHeaders() }),
      fetch("/api/intel/kev?limit=12", { headers: authHeaders() }),
      fetch("/api/intel/free/catalog", { headers: authHeaders() }),
    ]);
    const watch = (await watchRes.json()).watch || [];
    const vulns = ((await vulnRes.json()).vulnerabilities || [])
      .filter((v) => (v.severity || "") === "critical" || (v.cve || "").startsWith("CVE-"))
      .slice(0, 12);
    const kevData = await kevRes.json().catch(() => ({}));
    const kevItems = kevData.items || [];
    const catalog = await catalogRes.json().catch(() => ({}));
    const catalogItems = catalog.items || [];
    const counts = catalog.counts || {};
    const statusClass = (st) => {
      if (st === "live") return "ok";
      if (st === "keyed") return "";
      if (st === "skipped") return "warn";
      return "";
    };
    body.innerHTML = `
      <section class="cc-panel" style="margin-bottom:1rem">
        <header><h2>IOC / CVE lookup</h2>
          <span class="hint"><a href="https://free-apis.github.io/#/categories/Security" target="_blank" rel="noopener">Free APIs Security</a></span>
        </header>
        <form id="intelLookupForm" class="inline-form">
          <input id="intelLookupQ" placeholder="IP, domain, URL, email, hash, or CVE-…" required style="min-width:16rem" />
          <button type="submit">Lookup</button>
        </form>
        <pre id="intelLookupOut" class="tools-palette-out hidden"></pre>
      </section>
      <div class="ws-grid-2">
        <section class="cc-panel">
          <header><h2>Watchlist</h2>
            <button type="button" class="btn-secondary" id="intelKevSync">Sync CISA KEV</button>
          </header>
          <ul class="cc-list">${
            watch.length
              ? watch
                  .map(
                    (w) =>
                      `<li><strong>${escapeHtml(w.kind)}</strong> ${escapeHtml(w.value)}
                      <span class="hint">${escapeHtml((w.notes || "").slice(0, 80))}</span>
                      <button type="button" class="btn-secondary ws-del-watch" data-id="${w.id}">Remove</button></li>`
                  )
                  .join("")
              : `<li class="hint">No watched CVEs / IOCs yet — sync KEV or add manually</li>`
          }</ul>
          <form id="intelWatchForm" class="inline-form">
            <input id="intelValue" placeholder="CVE-2024-...." required />
            <button type="submit">Add</button>
          </form>
          <form id="intelNvdForm" class="inline-form" style="margin-top:0.5rem">
            <input id="intelNvdCve" placeholder="Lookup NVD CVE…" required />
            <button type="submit">NVD</button>
          </form>
          <pre id="intelNvdOut" class="tools-palette-out hidden"></pre>
        </section>
        <section class="cc-panel">
          <header><h2>CISA KEV (recent)</h2></header>
          <ul class="cc-list">${
            kevItems.length
              ? kevItems
                  .map(
                    (k) =>
                      `<li><strong>${escapeHtml(k.cve || "")}</strong> ${escapeHtml(k.vendor || "")} ${escapeHtml(
                        k.product || ""
                      )}
                      <span class="hint">${escapeHtml(k.name || "")}</span></li>`
                  )
                  .join("")
              : `<li class="hint">${escapeHtml(kevData.detail || "KEV feed unavailable offline")}</li>`
          }</ul>
          <header style="margin-top:1rem"><h2>Critical in register</h2></header>
          <ul class="cc-list">${
            vulns.length
              ? vulns
                  .map((v) => `<li><strong>${escapeHtml(v.severity)}</strong> ${escapeHtml(v.cve || "")} — ${escapeHtml(v.title)}</li>`)
                  .join("")
              : `<li class="hint">Import vulns to populate</li>`
          }</ul>
          <button type="button" class="cc-action" id="intelAskAi">Ask AI for weekly threat brief</button>
        </section>
      </div>
      <section class="cc-panel" style="margin-top:1rem">
        <header><h2>Free Security APIs</h2>
          <span class="hint">${catalog.total || 0} listed · live ${counts.live || 0} · keyed ${counts.keyed || 0} · catalog ${counts.catalog || 0} · skipped ${counts.skipped || 0}</span>
        </header>
        <div class="integ-status-strip" id="intelCatalogStrip">
          ${catalogItems
            .map(
              (it) =>
                `<a class="integ-pill integ-chip ${statusClass(it.status)}" href="${escapeHtml(it.docs || "#")}" target="_blank" rel="noopener" title="${escapeHtml(
                  it.notes || it.auth || ""
                )}">${escapeHtml(it.name)} · ${escapeHtml(it.status)}${it.key_configured ? " ✓" : ""}</a>`
            )
            .join("")}
        </div>
        <p class="hint">Add optional keys in Settings to unlock AbuseIPDB, VirusTotal, Shodan, HIBP, URLhaus, EmailRep, and more.</p>
        <div class="cc-action-row" style="margin-top:0.75rem">
          <button type="button" class="btn-secondary" id="intelFeedMsrc">MSRC updates</button>
          <button type="button" class="btn-secondary" id="intelFeedFilterlists">FilterLists</button>
          <button type="button" class="btn-secondary" id="intelFeedPassword">Password exposure check</button>
        </div>
        <pre id="intelFeedOut" class="tools-palette-out hidden"></pre>
      </section>`;
    qs("intelLookupForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = qs("intelLookupQ")?.value?.trim();
      const out = qs("intelLookupOut");
      if (!q || !out) return;
      out.classList.remove("hidden");
      out.textContent = "Looking up…";
      const res = await fetch(`/api/intel/lookup?q=${encodeURIComponent(q)}`, { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        out.textContent = data.detail || `HTTP ${res.status}`;
        return;
      }
      const lines = [
        `kind: ${data.kind} · ok ${data.providers_ok} · failed ${data.providers_failed}`,
        "",
      ];
      for (const r of data.results || []) {
        const src = r.source || "?";
        const summary = JSON.stringify(r.data || r, null, 0).slice(0, 400);
        lines.push(`[${src}] ${summary}`);
      }
      if ((data.errors || []).length) {
        lines.push("", "errors:");
        for (const err of data.errors) lines.push(`- ${err.provider}: ${err.error}`);
      }
      out.textContent = lines.join("\n");
    });
    qs("intelKevSync")?.addEventListener("click", async () => {
      const res = await fetch("/api/intel/kev/sync", { method: "POST", headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      if (typeof notifyUser === "function") notifyUser(`**KEV sync:** added ${data.added ?? "?"} items`);
      renderIntelPage();
    });
    qs("intelWatchForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const value = qs("intelValue")?.value?.trim();
      if (!value) return;
      await fetch("/api/intel/watch", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ kind: value.toUpperCase().startsWith("CVE-") ? "cve" : "ioc", value }),
      });
      renderIntelPage();
    });
    qs("intelNvdForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const cve = qs("intelNvdCve")?.value?.trim();
      if (!cve) return;
      const out = qs("intelNvdOut");
      const res = await fetch(`/api/intel/nvd/${encodeURIComponent(cve)}`, { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      if (out) {
        out.classList.remove("hidden");
        out.textContent = res.ok
          ? `${data.cve} · CVSS ${data.cvss ?? "—"} · ${data.severity || ""}\n${data.description || ""}`
          : data.detail || `HTTP ${res.status}`;
      }
    });
    body.querySelectorAll(".ws-del-watch").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/intel/watch/${btn.getAttribute("data-id")}`, { method: "DELETE", headers: authHeaders() });
        renderIntelPage();
      });
    });
    qs("intelAskAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function") {
        runNavPrompt(
          "research",
          "Summarize latest critical CVEs and KEV items relevant to Windows and cloud this week"
        );
      }
    });
    const showIntelFeed = async (url, label) => {
      const out = qs("intelFeedOut");
      if (!out) return;
      out.classList.remove("hidden");
      out.textContent = `Loading ${label}…`;
      const res = await fetch(url, { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      out.textContent = res.ok ? JSON.stringify(data, null, 2) : data.detail || `HTTP ${res.status}`;
    };
    qs("intelFeedMsrc")?.addEventListener("click", () => showIntelFeed("/api/intel/msrc", "MSRC"));
    qs("intelFeedFilterlists")?.addEventListener("click", () => showIntelFeed("/api/intel/filterlists", "FilterLists"));
    qs("intelFeedPassword")?.addEventListener("click", async () => {
      const pwd = prompt("Check password exposure (HIBP k-anonymity — not stored or shown):");
      if (!pwd) return;
      const out = qs("intelFeedOut");
      if (!out) return;
      out.classList.remove("hidden");
      out.textContent = "Checking…";
      // POST body only — never put passwords in the URL/query string
      const res = await fetch("/api/intel/password/check", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ password: pwd }),
      });
      const data = await res.json().catch(() => ({}));
      out.textContent = res.ok
        ? `Exposed: ${data.exposed ? "yes" : "no"} · breach count: ${data.count ?? 0}\n${data.note || ""}`
        : data.detail || `HTTP ${res.status}`;
    });
  }

  async function renderReportsPage() {
    const body = qs("reportsPageBody");
    if (!body) return;
    const res = await fetch("/api/reports", { headers: authHeaders() });
    const data = await res.json();
    const items = data.reports || [];
    body.innerHTML = `
      <div class="reports-list">
        ${
          items.length
            ? items
                .map(
                  (r) => `<button type="button" class="report-card" data-href="${escapeHtml(r.href)}" data-kind="${escapeHtml(
                    r.kind || ""
                  )}">
                    <span class="report-kind">${escapeHtml(r.kind)}</span>
                    <strong>${escapeHtml(r.title)}</strong>
                  </button>`
                )
                .join("")
            : `<p class="hint">No reports yet — run gap analysis or add risks/vulns.</p>`
        }
      </div>
      <div class="cc-action-row" style="margin-top:1rem">
        <button type="button" class="cc-action" id="reportExecPdf">Download executive PDF</button>
        <button type="button" class="cc-action" id="reportExecDocx">Executive DOCX</button>
        <button type="button" class="cc-action" id="reportRisksPdf">Risks PDF</button>
        <button type="button" class="cc-action" id="reportVulnsPdf">Vulns PDF</button>
        <button type="button" class="cc-action" id="reportComplianceDocx">Compliance DOCX</button>
        <button type="button" class="cc-action" id="reportRisksXlsx">Risks Excel</button>
        <button type="button" class="cc-action" id="reportVulnsXlsx">Vulns Excel</button>
        <button type="button" class="cc-action" id="reportExecAi">Generate executive report (AI)</button>
        <button type="button" class="cc-action" id="reportBoardAi">Board report (AI)</button>
        <button type="button" class="cc-action" id="reportSecurityAi">Security report (AI)</button>
        <button type="button" class="cc-action" id="reportTechAi">Generate technical report (AI)</button>
      </div>`;
    body.querySelectorAll(".report-card").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const href = btn.getAttribute("data-href");
        const kind = btn.getAttribute("data-kind") || "";
        if (!href) return;
        try {
          if (kind === "pdf" || href.endsWith(".pdf")) {
            const name = href.split("/").pop() || "securaiq-report.pdf";
            if (typeof window.downloadBinary === "function") {
              await window.downloadBinary(href, name, "application/pdf");
            } else {
              const r = await fetch(href, { headers: authHeaders() });
              const buf = await r.arrayBuffer();
              const a = document.createElement("a");
              a.href = URL.createObjectURL(new Blob([buf], { type: "application/pdf" }));
              a.download = name;
              a.click();
            }
          } else if (kind === "docx" || href.endsWith(".docx") || kind === "xlsx" || href.endsWith(".xlsx")) {
            const name = href.split("/").pop() || "securaiq-report.bin";
            const mime = href.endsWith(".xlsx")
              ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            if (typeof window.downloadBinary === "function") {
              await window.downloadBinary(href, name, mime);
            }
          } else if (typeof downloadMd === "function") {
            await downloadMd(href, `securaiq-report.md`);
          } else {
            const r = await fetch(href, { headers: authHeaders() });
            const md = await r.text();
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
            a.download = "securaiq-report.md";
            a.click();
          }
        } catch (err) {
          alert(err.message || "Download failed");
        }
      });
    });
    qs("reportExecPdf")?.addEventListener("click", () => {
      if (typeof window.downloadBinary === "function") {
        window.downloadBinary("/api/reports/executive.pdf", "securaiq-executive.pdf", "application/pdf").catch((e) =>
          alert(e.message)
        );
      }
    });
    const bin = (href, name, mime) => {
      if (typeof window.downloadBinary === "function") {
        window.downloadBinary(href, name, mime).catch((e) => alert(e.message));
      }
    };
    qs("reportExecDocx")?.addEventListener("click", () =>
      bin(
        "/api/reports/executive.docx",
        "securaiq-executive.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      )
    );
    qs("reportRisksPdf")?.addEventListener("click", () =>
      bin("/api/reports/risks.pdf", "securaiq-risks.pdf", "application/pdf")
    );
    qs("reportVulnsPdf")?.addEventListener("click", () =>
      bin("/api/reports/vulns.pdf", "securaiq-vulns.pdf", "application/pdf")
    );
    qs("reportComplianceDocx")?.addEventListener("click", () =>
      bin(
        "/api/reports/compliance.docx",
        "securaiq-compliance.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      )
    );
    qs("reportRisksXlsx")?.addEventListener("click", () =>
      bin(
        "/api/reports/risks.xlsx",
        "securaiq-risks.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      )
    );
    qs("reportVulnsXlsx")?.addEventListener("click", () =>
      bin(
        "/api/reports/vulns.xlsx",
        "securaiq-vulns.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      )
    );
    qs("reportExecAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("ciso", "Generate an executive security status report from our current posture");
    });
    qs("reportBoardAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("ciso", "Draft a board report: security score, top risks, compliance %, and decisions needed");
    });
    qs("reportSecurityAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("blueteam", "Generate a technical security report covering critical vulns, remediations, and verify steps");
    });
    qs("reportTechAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("assess", "Generate a technical findings report with remediation owners and SLAs");
    });
  }

  async function renderXdrPanel() {
    const el = qs("xdrPanelBody");
    if (!el) return;
    try {
      const [statusRes, detRes, patchRes] = await Promise.all([
        fetch("/api/xdr/status", { headers: authHeaders() }),
        fetch("/api/xdr/detections?limit=8", { headers: authHeaders() }),
        fetch("/api/xdr/patches", { headers: authHeaders() }),
      ]);
      const statusData = await statusRes.json();
      const detData = await detRes.json();
      const patchData = await patchRes.json();
      const vendors = statusData.vendors || {};
      const vendorLabels = { sophos: "Sophos", crowdstrike: "CrowdStrike", sentinelone: "SentinelOne", defender: "Defender" };
      const vendorChips = `<ul class="integ-status-list">${Object.entries(vendors)
        .map(
          ([id, v]) =>
            `<li class="${v.configured ? "ok" : "muted"}"><span>${escapeHtml(vendorLabels[id] || id)}</span><strong>${
              v.configured ? "Connected" : "Not configured"
            }</strong></li>`
        )
        .join("")}</ul>`;
      const anyConfigured = Object.values(vendors).some((v) => v.configured);
      const events = detData.events || [];
      const eventsHtml = events.length
        ? events
            .map(
              (e) =>
                `<li><strong>${escapeHtml(e.severity)}</strong> [${escapeHtml(e.vendor)}] ${escapeHtml(e.title)}${
                  e.host ? ` — <code>${escapeHtml(e.host)}</code>` : ""
                }</li>`
            )
            .join("")
        : `<li class="hint">${anyConfigured ? "No detections synced yet" : "Connect an EDR vendor in Settings to see live detections here"}</li>`;
      const patchTotal = patchData.total_missing_patches || 0;
      el.innerHTML = `
        ${vendorChips}
        <div class="cc-kpi-grid" style="margin:0.5rem 0">
          <article class="cc-kpi"><span>Missing patches (open)</span><strong>${patchTotal}</strong></article>
          <article class="cc-kpi"><span>Hosts with patch gaps</span><strong>${patchData.hosts_with_gaps || 0}</strong></article>
        </div>
        <p class="hint">Recent detections</p>
        <ul class="cc-list">${eventsHtml}</ul>
        <p class="hint">Set vendor credentials in Settings (Sophos/CrowdStrike/SentinelOne/Defender) — detections and missing-patch data sync automatically every ${Math.round(
          (window.__xdrIntervalSec || 1800) / 60
        )} min, or click "Sync now".</p>`;
    } catch (err) {
      el.innerHTML = `<p class="hint">XDR panel unavailable: ${escapeHtml(err.message)}</p>`;
    }
  }

  async function renderWazuhPanel() {
    const el = qs("wazuhPanelBody");
    if (!el) return;
    try {
      const [stRes, agRes, alRes] = await Promise.all([
        fetch("/api/wazuh/status", { headers: authHeaders() }),
        fetch("/api/wazuh/agents?limit=12", { headers: authHeaders() }),
        fetch("/api/wazuh/alerts?limit=8", { headers: authHeaders() }),
      ]);
      const st = await stRes.json().catch(() => ({}));
      const ag = await agRes.json().catch(() => ({}));
      const al = await alRes.json().catch(() => ({}));
      const ping = st.ping || {};
      const agents = ag.agents || [];
      const events = al.events || [];
      const statusChip = st.configured
        ? ping.ok
          ? `<span class="auto-job-status status-done">connected</span>`
          : `<span class="auto-job-status status-error">auth/error</span>`
        : `<span class="auto-job-status status-planned">not configured</span>`;
      const agentsHtml = agents.length
        ? agents
            .map(
              (a) =>
                `<li><strong>${escapeHtml(a.status || "?")}</strong> ${escapeHtml(a.name || a.agent_id || "")}
                ${a.ip ? ` · <code>${escapeHtml(a.ip)}</code>` : ""}
                ${a.os ? ` · ${escapeHtml(a.os)}` : ""}</li>`
            )
            .join("")
        : `<li class="hint">${st.configured ? "No agents synced yet — click Sync Wazuh" : "Set Wazuh credentials in Settings"}</li>`;
      const alertsHtml = events.length
        ? events
            .map(
              (e) =>
                `<li><strong>${escapeHtml(e.severity)}</strong> ${escapeHtml(e.title || "")}${
                  e.host ? ` — <code>${escapeHtml(e.host)}</code>` : ""
                }</li>`
            )
            .join("")
        : `<li class="hint">${
            st.configured
              ? st.indexer_configured
                ? "No alerts yet"
                : "No Indexer — showing agent/vuln signals after sync"
              : "Configure Wazuh to pull SIEM data"
          }</li>`;
      el.innerHTML = `
        <p>${statusChip}
          ${st.base_url ? `<span class="hint">${escapeHtml(st.base_url)}</span>` : ""}
          ${st.indexer_configured ? '<span class="hint">Indexer on</span>' : '<span class="hint">Indexer off</span>'}
          ${ping.api_version ? `<span class="hint">API ${escapeHtml(ping.api_version)}</span>` : ""}
          ${ping.error && st.configured ? `<span class="hint">${escapeHtml(ping.error)}</span>` : ""}
        </p>
        <div class="ws-grid-2">
          <div>
            <p class="hint">Agents (${agents.length})</p>
            <ul class="cc-list">${agentsHtml}</ul>
          </div>
          <div>
            <p class="hint">Recent Wazuh events</p>
            <ul class="cc-list">${alertsHtml}</ul>
          </div>
        </div>
        <p class="hint">Settings → Wazuh SIEM. Optional Indexer URL enables full alert search on wazuh-alerts*.</p>`;
    } catch (err) {
      el.innerHTML = `<p class="hint">Wazuh panel unavailable: ${escapeHtml(err.message)}</p>`;
    }
  }

  async function renderSocPage() {
    const body = qs("socPageBody");
    if (!body) return;
    body.innerHTML = `<p class="hint">Loading…</p>`;
    let data = {};
    try {
      const res = await fetch("/api/soc", { headers: authHeaders() });
      data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `SOC failed (${res.status})`);
    } catch (err) {
      body.innerHTML = `<p class="hint">Could not load SOC: ${escapeHtml(err.message || String(err))}</p>`;
      return;
    }
    const incidents = data.incidents || [];
    const alerts = data.alerts || [];
    body.innerHTML = `
      <div class="cc-kpi-grid">
        <article class="cc-kpi"><span>Open incidents</span><strong>${data.incidents_open || 0}</strong></article>
        <article class="cc-kpi"><span>Critical/high vulns</span><strong>${data.critical_vulns || 0}</strong></article>
        <article class="cc-kpi"><span>Playbooks</span><strong>${data.playbooks || 0}</strong></article>
      </div>
      <div class="ws-grid-2" style="margin-top:1rem">
        <section class="cc-panel">
          <header><h2>Alerts</h2></header>
          <ul class="cc-list">${
            alerts.length
              ? alerts.map((a) => `<li><strong>${escapeHtml(a.kind)}</strong> ${escapeHtml(a.title)}</li>`).join("")
              : `<li class="hint">No alerts</li>`
          }</ul>
        </section>
        <section class="cc-panel">
          <header><h2>Open incidents</h2></header>
          <ul class="cc-list">${
            incidents.length
              ? incidents
                  .map(
                    (i) =>
                      `<li><strong>${escapeHtml(i.severity)}</strong> ${escapeHtml(i.title)}
                      <button type="button" class="btn-secondary ws-ask-ai" data-kind="incident" data-json="${escapeHtml(
                        JSON.stringify({ id: i.id, title: i.title, severity: i.severity })
                      )}">Ask AI</button>
                      <button type="button" class="btn-secondary ws-close-inc" data-id="${i.id}">Close</button>
                      <button type="button" class="btn-secondary ws-del-inc" data-id="${i.id}">Delete</button></li>`
                  )
                  .join("")
              : `<li class="hint">No open incidents</li>`
          }</ul>
          <form id="incidentForm" class="inline-form">
            <input id="incidentTitle" placeholder="New incident title" required />
            <select id="incidentSeverity"><option value="critical">Critical</option><option value="high" selected>High</option><option value="medium">Medium</option></select>
            <button type="submit">Create</button>
          </form>
        </section>
      </div>
      <section class="cc-panel" id="xdrPanel" style="margin-top:1rem">
        <header><h2>XDR / EDR</h2><button type="button" class="btn-secondary" id="xdrSyncBtn">Sync now</button></header>
        <div id="xdrPanelBody"><p class="hint">Loading…</p></div>
      </section>
      <section class="cc-panel" id="wazuhPanel" style="margin-top:1rem">
        <header><h2>Wazuh SIEM</h2><button type="button" class="btn-secondary" id="wazuhSyncBtn">Sync Wazuh</button></header>
        <div id="wazuhPanelBody"><p class="hint">Loading…</p></div>
      </section>`;
    renderXdrPanel();
    renderWazuhPanel();
    qs("xdrSyncBtn")?.addEventListener("click", async () => {
      const btn = qs("xdrSyncBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Syncing…"; }
      try {
        await fetch("/api/xdr/sync", { method: "POST", headers: authHeaders() });
      } catch {
        /* job runs async */
      }
      setTimeout(renderXdrPanel, 2500);
      if (btn) { btn.disabled = false; btn.textContent = "Sync now"; }
    });
    qs("wazuhSyncBtn")?.addEventListener("click", async () => {
      const btn = qs("wazuhSyncBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Syncing…"; }
      try {
        const res = await fetch("/api/wazuh/sync", { method: "POST", headers: authHeaders() });
        const data = await res.json().catch(() => ({}));
        if (!res.ok && typeof notifyUser === "function") {
          notifyUser(`**Wazuh sync failed:** ${data.detail || res.status}`);
        } else if (typeof notifyUser === "function") {
          notifyUser(`**Wazuh sync queued** · job \`${(data.job && data.job.id) || "?"}\``);
        }
      } catch (err) {
        if (typeof notifyUser === "function") notifyUser(`**Wazuh sync error:** ${err.message || err}`);
      }
      setTimeout(renderWazuhPanel, 2800);
      setTimeout(renderXdrPanel, 2800);
      if (btn) { btn.disabled = false; btn.textContent = "Sync Wazuh"; }
    });
    qs("incidentForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await fetch("/api/incidents", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          title: qs("incidentTitle")?.value?.trim(),
          severity: qs("incidentSeverity")?.value || "high",
        }),
      });
      renderSocPage();
    });
    wireAskAiButtons("socPageBody");
    body.querySelectorAll(".ws-close-inc").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/incidents/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ status: "closed" }),
        });
        renderSocPage();
      });
    });
    body.querySelectorAll(".ws-del-inc").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this incident?")) return;
        await fetch(`/api/incidents/${btn.getAttribute("data-id")}`, { method: "DELETE", headers: authHeaders() });
        renderSocPage();
        if (typeof loadCommandCenter === "function") loadCommandCenter();
      });
    });
  }

  async function renderEvidencePage() {
    const body = qs("evidencePageBody");
    if (!body) return;
    const [filesRes, linksRes, remsRes] = await Promise.all([
      fetch("/api/files", { headers: authHeaders() }),
      fetch("/api/evidence", { headers: authHeaders() }),
      fetch("/api/gap/remediations", { headers: authHeaders() }),
    ]);
    const filesData = await filesRes.json().catch(() => ({}));
    const linksData = await linksRes.json().catch(() => ({}));
    const remsData = await remsRes.json().catch(() => ({}));
    const files = filesData.files || filesData.items || [];
    const links = linksData.evidence || [];
    const rems = remsData.remediations || [];
    const remOpts = rems
      .map((r) => `<option value="${escapeHtml(r.id)}">${escapeHtml(r.control_id)} — ${escapeHtml(r.title)}</option>`)
      .join("");
    const fileOpts = files
      .map((f) => `<option value="${escapeHtml(f.id)}">${escapeHtml(f.filename || f.name || f.id)}</option>`)
      .join("");
    const fmtTs = (ts) => {
      if (!ts) return "—";
      const d = new Date(Number(ts) * (Number(ts) < 1e12 ? 1000 : 1));
      return Number.isNaN(d.getTime()) ? String(ts) : d.toLocaleDateString();
    };
    body.innerHTML = `
      <p class="hint">Evidence Control Center — map artifacts to controls with owner, status, and expiry for audits.</p>
      <section class="cc-panel">
        <header><h2>Evidence register</h2></header>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Evidence</th>
                <th>Owner</th>
                <th>Mapped control</th>
                <th>Status</th>
                <th>Expiry</th>
                <th>Comments</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${
                links.length
                  ? links
                      .map((l) => {
                        const owner = l.owner || l.remediation_owner || "Unassigned";
                        return `<tr>
                          <td><strong>${escapeHtml(l.filename || l.file_id || "file")}</strong>
                            <div class="hint">${escapeHtml(l.remediation_title || "")}</div></td>
                          <td>${escapeHtml(owner)}</td>
                          <td><code>${escapeHtml(l.control_id || "—")}</code></td>
                          <td><span class="wq-badge pri-${escapeHtml((l.status || "accepted").toLowerCase())}">${escapeHtml(
                            l.status || "accepted"
                          )}</span></td>
                          <td>${escapeHtml(l.expiry || "—")}</td>
                          <td>${escapeHtml(l.notes || "—")}</td>
                          <td>
                            <button type="button" class="btn-secondary ws-edit-ev" data-id="${escapeHtml(l.id)}"
                              data-owner="${escapeHtml(l.owner || "")}" data-control="${escapeHtml(l.control_id || "")}"
                              data-status="${escapeHtml(l.status || "accepted")}" data-expiry="${escapeHtml(l.expiry || "")}"
                              data-notes="${escapeHtml(l.notes || "")}">Edit</button>
                            <button type="button" class="btn-secondary ws-del-ev" data-id="${escapeHtml(l.id)}">Remove</button>
                          </td>
                        </tr>`;
                      })
                      .join("")
                  : `<tr><td colspan="7" class="hint">No evidence links yet — upload and link below</td></tr>`
              }
            </tbody>
          </table>
        </div>
        <p class="hint" style="margin-top:0.5rem">${links.length} linked · ${files.length} files in locker · last refresh ${fmtTs(
          Date.now() / 1000
        )}</p>
      </section>
      <div class="ws-grid-2" style="margin-top:1rem">
        <section class="cc-panel">
          <header><h2>Files</h2></header>
          <div class="data-table-wrap">
            <table class="data-table">
              <thead><tr><th>File</th><th>Size</th><th>Uploaded</th></tr></thead>
              <tbody>
                ${
                  files.length
                    ? files
                        .map(
                          (f) =>
                            `<tr><td>${escapeHtml(f.filename || f.name || f.id)}</td><td>${escapeHtml(
                              String(f.size_bytes || f.size || "—")
                            )}</td><td>${escapeHtml(fmtTs(f.created_at))}</td></tr>`
                        )
                        .join("")
                    : `<tr><td colspan="3" class="hint">No files yet — use Upload</td></tr>`
                }
              </tbody>
            </table>
          </div>
        </section>
        <section class="cc-panel">
          <header><h2>Link evidence</h2></header>
          <form id="evidenceLinkForm" class="inline-form" style="flex-direction:column;align-items:stretch;gap:0.5rem">
            <select id="evidenceFileId" required ${files.length ? "" : "disabled"}>
              <option value="">Select file</option>${fileOpts}
            </select>
            <select id="evidenceRemId">
              <option value="">No remediation (control note only)</option>${remOpts}
            </select>
            <input id="evidenceControlId" placeholder="Mapped control (e.g. A.5.1)" />
            <input id="evidenceOwner" placeholder="Owner" />
            <select id="evidenceStatus">
              <option value="accepted">accepted</option>
              <option value="review">review</option>
              <option value="draft">draft</option>
              <option value="expired">expired</option>
              <option value="rejected">rejected</option>
            </select>
            <input id="evidenceExpiry" type="date" title="Expiry" />
            <input id="evidenceNotes" placeholder="Comments" />
            <button type="submit" ${files.length ? "" : "disabled"}>Link evidence</button>
          </form>
        </section>
      </div>
      <div class="cc-action-row" style="margin-top:1rem">
        <button type="button" class="cc-action" id="evidenceAsk">Ask AI: missing evidence</button>
        <button type="button" class="btn-secondary" data-workspace="frameworks">Open frameworks</button>
        <button type="button" class="btn-secondary" data-workspace="remediations">Open controls</button>
      </div>`;
    qs("evidenceLinkForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fileId = qs("evidenceFileId")?.value;
      if (!fileId) return;
      await fetch("/api/evidence", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          file_id: fileId,
          remediation_id: qs("evidenceRemId")?.value || null,
          control_id: qs("evidenceControlId")?.value?.trim() || "",
          owner: qs("evidenceOwner")?.value?.trim() || "",
          status: qs("evidenceStatus")?.value || "accepted",
          expiry: qs("evidenceExpiry")?.value || "",
          notes: qs("evidenceNotes")?.value?.trim() || "",
        }),
      });
      renderEvidencePage();
    });
    body.querySelectorAll(".ws-del-ev").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/evidence/${btn.getAttribute("data-id")}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        renderEvidencePage();
      });
    });
    body.querySelectorAll(".ws-edit-ev").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const owner = window.prompt("Owner", btn.getAttribute("data-owner") || "") ?? null;
        if (owner === null) return;
        const control = window.prompt("Mapped control", btn.getAttribute("data-control") || "") ?? null;
        if (control === null) return;
        const status = window.prompt("Status (draft|review|accepted|expired|rejected)", btn.getAttribute("data-status") || "accepted");
        if (status === null) return;
        const expiry = window.prompt("Expiry (YYYY-MM-DD)", btn.getAttribute("data-expiry") || "");
        if (expiry === null) return;
        const notes = window.prompt("Comments", btn.getAttribute("data-notes") || "");
        if (notes === null) return;
        await fetch(`/api/evidence/${btn.getAttribute("data-id")}`, {
          method: "PATCH",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ owner, control_id: control, status, expiry, notes }),
        });
        renderEvidencePage();
      });
    });
    qs("evidenceAsk")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("ciso", "Summarize evidence needed for our next ISO 27001 audit and list expiry risks");
    });
    body.querySelectorAll("[data-workspace]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        showWorkspace(el.getAttribute("data-workspace"));
      });
    });
  }

  async function renderOrgsPage() {
    const body = qs("orgsPageBody");
    if (!body) return;
    const res = await fetch("/api/orgs", { headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    const orgs = data.organizations || [];
    const roles = data.roles || ["admin", "analyst", "viewer", "client"];
    body.innerHTML = `
      <div class="ws-grid-2">
        <section class="cc-panel">
          <header><h2>Your organizations</h2></header>
          <ul class="cc-list" id="orgsList">${
            orgs.length
              ? orgs
                  .map(
                    (o) =>
                      `<li><button type="button" class="linkish ws-org-pick" data-id="${o.id}">
                        <strong>${escapeHtml(o.name)}</strong> <span class="hint">${escapeHtml(o.member_role || o.role || "")}</span>
                      </button></li>`
                  )
                  .join("")
              : `<li class="hint">No orgs yet — create one for multi-user tenancy</li>`
          }</ul>
          <form id="orgCreateForm" class="inline-form">
            <input id="orgName" placeholder="Organization name" required />
            <button type="submit">Create</button>
          </form>
        </section>
        <section class="cc-panel">
          <header><h2>Members</h2></header>
          <div id="orgMembersBody"><p class="hint">Select an organization</p></div>
          <form id="orgMemberForm" class="inline-form" style="margin-top:0.75rem;display:none">
            <input id="orgMemberUser" placeholder="Username" required />
            <select id="orgMemberRole">${roles.map((r) => `<option value="${r}">${r}</option>`).join("")}</select>
            <button type="submit">Add member</button>
          </form>
        </section>
      </div>
      <p class="hint" style="margin-top:1rem">Roles: admin · analyst · viewer · client. MFA (TOTP) and OIDC SSO available in Settings → Enterprise auth.</p>`;
    let selectedOrg = null;
    async function loadMembers(orgId) {
      selectedOrg = orgId;
      const membersBody = qs("orgMembersBody");
      const form = qs("orgMemberForm");
      if (form) form.style.display = "flex";
      const mres = await fetch(`/api/orgs/${orgId}/members`, { headers: authHeaders() });
      const mdata = await mres.json().catch(() => ({}));
      if (!mres.ok) {
        membersBody.innerHTML = `<p class="hint">${escapeHtml(mdata.detail || "Cannot load members")}</p>`;
        return;
      }
      const members = mdata.members || [];
      membersBody.innerHTML = `<ul class="cc-list">${
        members.length
          ? members
              .map((m) => `<li><strong>${escapeHtml(m.username || m.user_id)}</strong> — ${escapeHtml(m.role)}</li>`)
              .join("")
          : `<li class="hint">No members</li>`
      }</ul>`;
    }
    qs("orgCreateForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = qs("orgName")?.value?.trim();
      if (!name) return;
      await fetch("/api/orgs", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ name }),
      });
      renderOrgsPage();
    });
    body.querySelectorAll(".ws-org-pick").forEach((btn) => {
      btn.addEventListener("click", () => loadMembers(btn.getAttribute("data-id")));
    });
    qs("orgMemberForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!selectedOrg) return;
      const username = qs("orgMemberUser")?.value?.trim();
      if (!username) return;
      const res = await fetch(`/api/orgs/${selectedOrg}/members`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          username,
          role: qs("orgMemberRole")?.value || "analyst",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data.detail || `HTTP ${res.status}`);
        return;
      }
      qs("orgMemberUser").value = "";
      loadMembers(selectedOrg);
    });
    if (orgs.length) loadMembers(orgs[0].id);
  }

  async function renderFrameworksPage() {
    const body = qs("frameworksPageBody");
    if (!body) return;
    const [fwRes, dashRes, remRes, evRes] = await Promise.all([
      fetch("/api/frameworks", { headers: authHeaders() }),
      fetch("/api/dashboard", { headers: authHeaders() }),
      fetch("/api/gap/remediations", { headers: authHeaders() }),
      fetch("/api/evidence", { headers: authHeaders() }),
    ]);
    const fws = (await fwRes.json().catch(() => ({}))).frameworks || [];
    const dash = await dashRes.json().catch(() => ({}));
    const rems = (await remRes.json().catch(() => ({}))).remediations || [];
    const evidence = (await evRes.json().catch(() => ({}))).evidence || [];
    const scored = {};
    (dash.frameworks || []).forEach((f) => {
      scored[f.framework_id] = f;
    });
    const statsById = {};
    (dash.framework_control_stats || []).forEach((s) => {
      statsById[s.framework_id] = s;
    });
    let totImpl = 0;
    let totPartial = 0;
    let totMissing = 0;
    let pctSum = 0;
    let pctN = 0;
    Object.values(statsById).forEach((st) => {
      const c = st.counts || {};
      totImpl += c.implemented || 0;
      totPartial += c.partial || 0;
      totMissing += c.missing || 0;
    });
    (dash.frameworks || []).forEach((f) => {
      if (f.compliance_percent != null) {
        pctSum += Number(f.compliance_percent) || 0;
        pctN += 1;
      }
    });
    const avgPct = pctN ? Math.round(pctSum / pctN) : Math.round(Number(dash.compliance_score) || 0);
    const openRems = rems.filter((r) => (r.status || "") !== "done").length;
    const riskScore = dash.security_index != null ? Math.round(Number(dash.security_index)) : "—";
    const maturity =
      avgPct >= 80 ? "Managed" : avgPct >= 50 ? "Defined" : avgPct > 0 ? "Initial" : "Ad hoc";
    const remByControl = {};
    rems.forEach((r) => {
      const cid = (r.control_id || "").toUpperCase();
      if (cid && !remByControl[cid]) remByControl[cid] = r;
    });
    const evByControl = {};
    evidence.forEach((e) => {
      const cid = (e.control_id || "").toUpperCase();
      if (!cid) return;
      if (!evByControl[cid]) evByControl[cid] = [];
      evByControl[cid].push(e);
    });

    async function openControlCenter(frameworkId, assessmentId) {
      const detailEl = qs("fwControlDetail");
      if (!detailEl) return;
      detailEl.innerHTML = `<p class="hint">Loading controls…</p>`;
      let aid = assessmentId;
      if (!aid) {
        const listRes = await fetch("/api/gap/assessments", { headers: authHeaders() });
        const list = (await listRes.json().catch(() => ({}))).assessments || [];
        const match = list.find((a) => a.framework_id === frameworkId);
        aid = match?.id;
      }
      if (!aid) {
        const catRes = await fetch(`/api/frameworks/${encodeURIComponent(frameworkId)}`, { headers: authHeaders() });
        const catalog = catRes.ok ? await catRes.json().catch(() => ({})) : {};
        const controls = catalog.controls || [];
        detailEl.innerHTML = `<p class="hint">No assessment for this framework yet — run gap analysis to score controls.</p>
          <button type="button" class="cc-action fw-run-gap" data-id="${escapeHtml(frameworkId)}">Run gap</button>
          ${
            controls.length
              ? `<div class="data-table-wrap" style="margin-top:1rem"><table class="data-table"><thead><tr><th>Control</th><th>Title</th></tr></thead><tbody>${controls
                  .slice(0, 40)
                  .map(
                    (c) =>
                      `<tr><td>${escapeHtml(c.id || c.control_id || "")}</td><td>${escapeHtml(c.title || c.name || "")}</td></tr>`
                  )
                  .join("")}</tbody></table></div>`
              : ""
          }`;
        detailEl.querySelector(".fw-run-gap")?.addEventListener("click", () => {
          if (typeof openGap === "function") openGap();
          const sel = document.getElementById("gapFramework");
          if (sel) sel.value = frameworkId;
        });
        return;
      }
      const res = await fetch(`/api/gap/assessments/${aid}`, { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        detailEl.innerHTML = `<p class="hint">Could not load assessment</p>`;
        return;
      }
      const rows = data.results || data.top_gaps || [];
      const counts = data.counts || {};
      detailEl.innerHTML = `
        <header class="fw-detail-head">
          <div>
            <h2>${escapeHtml(data.framework_name || frameworkId)}</h2>
            <p class="hint">${data.control_count || rows.length} controls · ${Number(
              data.compliance_percent || 0
            )}% · ${counts.implemented || 0} implemented · ${counts.partial || 0} partial · ${
              counts.missing || 0
            } missing</p>
          </div>
          <div class="cc-action-row">
            <button type="button" class="btn-secondary" id="fwExportAssessment">Export assessment</button>
            <button type="button" class="btn-secondary" id="fwDetailClose">Close</button>
          </div>
        </header>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Control</th>
                <th>Evidence</th>
                <th>Owner</th>
                <th>Risk</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${
                rows.length
                  ? rows
                      .slice(0, 80)
                      .map((r) => {
                        const cid = r.control_id || "";
                        const rem = remByControl[(cid || "").toUpperCase()];
                        const evs = evByControl[(cid || "").toUpperCase()] || [];
                        const status = r.status || "missing";
                        const risk =
                          status === "missing" ? "high" : status === "partial" ? "medium" : "low";
                        return `<tr>
                          <td><strong>${escapeHtml(cid)}</strong>
                            <div class="hint">${escapeHtml(r.title || "")}</div></td>
                          <td>${
                            evs.length
                              ? escapeHtml(evs.map((e) => e.filename || e.file_id).join(", "))
                              : `<span class="hint">${escapeHtml(
                                  (r.matched_keywords || []).slice(0, 3).join(", ") || "None linked"
                                )}</span>`
                          }</td>
                          <td>${escapeHtml(rem?.owner || "Unassigned")}</td>
                          <td><span class="wq-badge pri-${risk}">${risk}</span></td>
                          <td><span class="wq-badge pri-${
                            status === "implemented" ? "low" : status === "partial" ? "medium" : "high"
                          }">${escapeHtml(status)}</span></td>
                          <td>
                            <button type="button" class="btn-secondary fw-ctrl-ask"
                              data-id="${escapeHtml(cid)}" data-title="${escapeHtml(r.title || "")}">Ask AI</button>
                            <button type="button" class="btn-secondary" data-workspace="evidence">Evidence</button>
                          </td>
                        </tr>`;
                      })
                      .join("")
                  : `<tr><td colspan="6" class="hint">No control results</td></tr>`
              }
            </tbody>
          </table>
        </div>`;
      qs("fwDetailClose")?.addEventListener("click", () => {
        detailEl.innerHTML = "";
        detailEl.classList.add("hidden");
      });
      qs("fwExportAssessment")?.addEventListener("click", async () => {
        try {
          await downloadApiExport(`/api/gap/assessments/${aid}/export`, `securaiq-gap-${frameworkId}.md`);
          if (typeof notifyUser === "function") notifyUser("**Gap assessment exported** as Markdown.");
        } catch (err) {
          alert(err.message || "Export failed");
        }
      });
      detailEl.classList.remove("hidden");
      detailEl.querySelectorAll(".fw-ctrl-ask").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (typeof runNavPrompt === "function") {
            runNavPrompt(
              "ciso",
              `For control ${btn.getAttribute("data-id")} (${btn.getAttribute(
                "data-title"
              )}): list required evidence, owner role, residual risk, and a 14-day remediation plan.`
            );
          }
        });
      });
      detailEl.querySelectorAll("[data-workspace]").forEach((el) => {
        el.addEventListener("click", (e) => {
          e.preventDefault();
          showWorkspace(el.getAttribute("data-workspace"));
        });
      });
    }

    body.innerHTML = `
      <div class="comp-kpi-row" aria-label="Compliance health">
        <div class="comp-kpi"><span>Implemented</span><strong>${totImpl}</strong></div>
        <div class="comp-kpi"><span>Partial</span><strong>${totPartial}</strong></div>
        <div class="comp-kpi"><span>Missing</span><strong>${totMissing}</strong></div>
        <div class="comp-kpi"><span>Coverage</span><strong>${avgPct}%</strong></div>
        <div class="comp-kpi"><span>Evidence</span><strong>${evidence.length}</strong></div>
        <div class="comp-kpi"><span>Open remediations</span><strong>${openRems}</strong></div>
        <div class="comp-kpi"><span>Risk score</span><strong>${riskScore}</strong></div>
        <div class="comp-kpi"><span>Maturity</span><strong>${maturity}</strong></div>
      </div>
      <div class="fw-grid">
        ${
          fws.length
            ? fws
                .map((f) => {
                  const s = scored[f.id];
                  const st = statsById[f.id] || {};
                  const c = st.counts || {};
                  const pct = s ? Number(s.compliance_percent || 0) : null;
                  const total =
                    st.controls_total ||
                    f.control_count ||
                    (c.implemented || 0) + (c.partial || 0) + (c.missing || 0);
                  return `<article class="fw-card">
                    <header>
                      <h2>${escapeHtml(f.name)}</h2>
                      <span class="hint">${escapeHtml(f.version || "")}</span>
                    </header>
                    <p class="fw-meta"><strong>${total || f.control_count || 0}</strong> controls ·
                      <strong>${c.implemented || 0}</strong> implemented ·
                      <strong>${c.partial || 0}</strong> partial ·
                      <strong>${c.missing || 0}</strong> missing</p>
                    <div class="cc-bar"><i style="width:${pct != null ? pct : 0}%"></i></div>
                    <p class="fw-score">${pct != null ? `${pct}% assessed` : "Not assessed yet"}</p>
                    <div class="cc-action-row">
                      <button type="button" class="cc-action fw-open-controls" data-id="${escapeHtml(
                        f.id
                      )}" data-aid="${escapeHtml(st.assessment_id || s?.id || "")}">Open controls</button>
                      <button type="button" class="btn-secondary fw-run-gap" data-id="${escapeHtml(f.id)}">Run gap</button>
                      <button type="button" class="btn-secondary fw-ask" data-id="${escapeHtml(
                        f.id
                      )}" data-name="${escapeHtml(f.name)}">Ask AI</button>
                    </div>
                  </article>`;
                })
                .join("")
            : `<p class="hint">No frameworks installed</p>`
        }
      </div>
      <section id="fwControlDetail" class="cc-panel fw-control-detail hidden" style="margin-top:1.25rem"></section>
      <section class="cc-panel" style="margin-top:1.25rem">
        <header><h2>Evidence mapper workflow</h2></header>
        <ol class="fw-steps">
          <li>Upload policies / screenshots in Evidence</li>
          <li>Run gap analysis against a framework</li>
          <li>Open controls — review Evidence · Owner · Risk · Status</li>
          <li>Assign remediations and link evidence</li>
          <li>Export PDF / Markdown reports for stakeholders</li>
        </ol>
        <div class="cc-action-row">
          <button type="button" class="cc-action" data-workspace="evidence">Open evidence</button>
          <button type="button" class="cc-action" data-workspace="remediations">Open controls</button>
          <button type="button" class="cc-action" data-workspace="reports">Open reports</button>
        </div>
      </section>`;
    body.querySelectorAll(".fw-open-controls").forEach((btn) => {
      btn.addEventListener("click", () =>
        openControlCenter(btn.getAttribute("data-id"), btn.getAttribute("data-aid") || "")
      );
    });
    body.querySelectorAll(".fw-run-gap").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (typeof openGap === "function") openGap();
        const sel = document.getElementById("gapFramework");
        if (sel && btn.getAttribute("data-id")) sel.value = btn.getAttribute("data-id");
      });
    });
    body.querySelectorAll(".fw-ask").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (typeof runNavPrompt === "function") {
          runNavPrompt(
            "ciso",
            `Map our current security narrative to ${btn.getAttribute("data-name")} and list missing evidence for the top 10 gaps.`
          );
        }
      });
    });
    body.querySelectorAll("[data-workspace]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        showWorkspace(el.getAttribute("data-workspace"));
      });
    });
  }

  function renderIntegrationsPage() {
    const body = qs("integrationsPageBody");
    if (!body) return;
    try {
      localStorage.setItem("securaiq.checklist.integrations", "1");
    } catch {
      /* ignore */
    }
    body.innerHTML = `
      <p class="hint">Orchestrate mature tools — Connect opens the real path in SecuraIQ (import, settings, webhooks). Planned items stay disabled until shipped.</p>
      <div class="integ-status-strip" id="integStatusStrip"><span class="hint">Checking connection status…</span></div>
      <section class="cc-panel" id="integMvpPanel">
        <header><h2>Recommended MVP</h2></header>
        <div id="integMvp" class="integ-grid"><p class="hint">Loading…</p></div>
      </section>
      <section class="cc-panel" style="margin-top:1rem">
        <header><h2>All integrations</h2></header>
        <p class="hint" id="integCounts"></p>
        <div id="integCatalog" class="integ-catalog integ-catalog-all"><p class="hint">Loading…</p></div>
      </section>
      <section class="cc-panel" style="margin-top:1rem">
        <header><h2>AI agents</h2></header>
        <p class="hint">Launch a role prompt in AI Workspace (authorized / lab scope).</p>
        <div id="integAgents" class="integ-chips"></div>
      </section>
      <section class="cc-panel" style="margin-top:1rem">
        <header><h2>Enterprise features</h2></header>
        <div id="integEnterprise" class="integ-grid"></div>
      </section>
      <div class="integ-grid" id="integQuick" style="margin-top:1rem"></div>
      <section class="cc-panel" style="margin-top:1.25rem" id="resetPanel">
        <header><h2>Reset workspace</h2></header>
        <p class="hint">Clear assets, vulns, risks, incidents, and related data for this user. Starts Mission Control from zero. Does not delete your login.</p>
        <label class="toggle"><input type="checkbox" id="resetClearRag" /> Also clear RAG knowledge index on reset</label>
        <div class="cc-action-row" style="margin-top:0.75rem">
          <button type="button" class="btn-secondary" id="workspaceResetBtn">Reset to empty</button>
        </div>
      </section>
      <section class="cc-panel" style="margin-top:1.25rem" id="webhookPanel">
        <header><h2>Outbound webhooks</h2></header>
        <p class="hint">Bridge to n8n / Temporal / Slack. Events: vuln.imported, remediation.created, *</p>
        <form id="webhookForm" class="inline-form" style="flex-wrap:wrap;gap:0.5rem">
          <input id="webhookName" placeholder="Name" required />
          <input id="webhookUrl" placeholder="https://…" required style="min-width:240px" />
          <button type="submit">Add webhook</button>
        </form>
        <ul id="webhookList" class="cc-list" style="margin-top:0.75rem"><li class="hint">No webhooks yet</li></ul>
        <button type="button" class="btn-secondary" id="webhookTest">Dispatch test event</button>
      </section>`;

    const statusClass = (s) => {
      const live = ["shipped", "import", "path", "path+import", "partial", "Available"].includes(s);
      return live ? "low" : "medium";
    };

    const actionBtn = (ua, idAttr) => {
      const a = ua || { kind: "planned", label: "Planned" };
      if (a.kind === "planned") {
        return `<button type="button" class="btn-secondary integ-connect" disabled title="Not shipped yet">${escapeHtml(
          a.label || "Planned"
        )}</button>`;
      }
      const attrs = [
        `data-kind="${escapeHtml(a.kind)}"`,
        a.target ? `data-target="${escapeHtml(a.target)}"` : "",
        a.focus ? `data-focus="${escapeHtml(a.focus)}"` : "",
        idAttr ? `data-id="${escapeHtml(idAttr)}"` : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `<button type="button" class="cc-action integ-connect" ${attrs}>${escapeHtml(
        a.label || "Connect"
      )}</button>`;
    };

    function runConnect(btn) {
      const kind = btn.getAttribute("data-kind");
      const target = btn.getAttribute("data-target");
      const focus = btn.getAttribute("data-focus");
      if (kind === "workspace" && target) {
        showWorkspace(target);
        return;
      }
      if (kind === "webhooks") {
        qs("webhookPanel")?.scrollIntoView({ behavior: "smooth" });
        qs("webhookUrl")?.focus();
        return;
      }
      if (kind === "settings") {
        qs("settingsBtn")?.click();
        const focusMap = {
          jira: "setJiraUrl",
          ai: "setOllamaUrl",
          tools: "setLocalToolsEnabled",
          keys: "apiKeyName",
          audit: "auditLogList",
          wazuh: "setWazuhUrl",
        };
        const targetId = focusMap[focus] || (focus ? `set${focus[0].toUpperCase()}${focus.slice(1)}` : null);
        if (targetId) {
          setTimeout(() => {
            const el = document.getElementById(targetId);
            el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
            if (el && typeof el.focus === "function" && el.tagName !== "DIV") el.focus();
          }, 220);
        }
        return;
      }
      if (kind === "info" && typeof notifyUser === "function") {
        notifyUser(`**${btn.closest(".integ-card")?.querySelector("h2")?.textContent || "Integration"}** is available in this build — no extra connector required.`);
      }
    }

    function wireConnectButtons(root) {
      root?.querySelectorAll(".integ-connect:not([disabled])").forEach((btn) => {
        btn.addEventListener("click", () => runConnect(btn));
      });
    }

    async function loadStatusStrip() {
      const strip = qs("integStatusStrip");
      if (!strip) return;
      try {
        const [setRes, hookRes, ghRes] = await Promise.all([
          fetch("/api/settings", { headers: authHeaders() }),
          fetch("/api/webhooks", { headers: authHeaders() }),
          fetch("/api/integrations/github/status", { headers: authHeaders() }),
        ]);
        const settings = await setRes.json().catch(() => ({}));
        const hooks = await hookRes.json().catch(() => ({}));
        const gh = await ghRes.json().catch(() => ({}));
        const jiraOk = Boolean(settings.jira_base_url && settings.jira_api_token_set);
        const hookCount = (hooks.webhooks || []).length;
        const ghOk = Boolean(gh.configured);
        const backend = settings.model_backend || settings.MODEL_BACKEND || "local";
        strip.innerHTML = `
          <span class="integ-pill ${jiraOk ? "ok" : ""}">Jira: ${jiraOk ? "configured" : "not set"}</span>
          <span class="integ-pill ${ghOk ? "ok" : ""}">GitHub: ${ghOk ? "webhook ready" : "not set"}</span>
          <span class="integ-pill ${hookCount ? "ok" : ""}">Webhooks: ${hookCount}</span>
          <span class="integ-pill ok">AI backend: ${escapeHtml(String(backend))}</span>
          <span class="integ-pill">Scanners: import via Vulns</span>`;
      } catch {
        strip.innerHTML = `<span class="hint">Status unavailable</span>`;
      }
    }

    async function loadCatalog() {
      try {
        const res = await fetch("/api/integrations/catalog", { headers: authHeaders() });
        const data = await res.json();
        const mvp = qs("integMvp");
        if (mvp) {
          mvp.innerHTML = (data.mvp || [])
            .map(
              (i) => `<article class="integ-card">
              <h2>${escapeHtml(i.tool)}</h2>
              <p class="hint">${escapeHtml(i.category)}</p>
              <span class="wq-badge pri-${statusClass(i.status)}">${escapeHtml(i.status)}</span>
              <div class="cc-action-row integ-card-actions">${actionBtn(i.ui_action)}</div>
            </article>`
            )
            .join("");
          wireConnectButtons(mvp);
        }
        const counts = qs("integCounts");
        if (counts && data.counts) {
          counts.textContent = `${data.counts.total} tools · ${data.counts.actionable} actionable · ${data.counts.planned} planned`;
        }
        const cat = qs("integCatalog");
        if (cat) {
          cat.innerHTML = (data.groups || [])
            .map((g) => {
              const cards = (g.items || [])
                .map(
                  (it) => `<article class="integ-card integ-card-sm">
                    <h2>${escapeHtml(it.name)}</h2>
                    <p class="hint">${escapeHtml(it.hint || g.label)}</p>
                    <span class="wq-badge pri-${statusClass(it.status)}">${escapeHtml(it.status)}</span>
                    <div class="cc-action-row integ-card-actions">${actionBtn(it.ui_action, it.id)}</div>
                  </article>`
                )
                .join("");
              return `<div class="integ-group"><h3>${escapeHtml(g.label)} (${(g.items || []).length})</h3><div class="integ-grid">${cards}</div></div>`;
            })
            .join("");
          wireConnectButtons(cat);
        }
        const agents = qs("integAgents");
        if (agents) {
          const list = data.agents || [];
          agents.innerHTML = list
            .map((a) => {
              if (typeof a === "string") {
                return `<button type="button" class="integ-chip integ-agent" data-mode="ciso" data-prompt="${escapeHtml(
                  `Act as ${a}: help with authorized security work in our workspace`
                )}"><strong>${escapeHtml(a)}</strong></button>`;
              }
              return `<button type="button" class="integ-chip integ-agent" data-mode="${escapeHtml(
                a.mode || "ciso"
              )}" data-prompt="${escapeHtml(a.prompt || a.name)}"><strong>${escapeHtml(
                a.name
              )}</strong></button>`;
            })
            .join("");
          agents.querySelectorAll(".integ-agent").forEach((btn) => {
            btn.addEventListener("click", () => {
              if (typeof runNavPrompt === "function") {
                runNavPrompt(btn.getAttribute("data-mode"), btn.getAttribute("data-prompt"));
              }
            });
          });
        }
        const ent = qs("integEnterprise");
        if (ent) {
          ent.innerHTML = (data.enterprise_features || [])
            .map(
              (f) => `<article class="integ-card integ-card-sm">
              <h2>${escapeHtml(f.name)}</h2>
              <span class="wq-badge pri-${statusClass(f.status)}">${escapeHtml(f.status)}</span>
              <div class="cc-action-row integ-card-actions">${actionBtn(f.ui_action, f.id)}</div>
            </article>`
            )
            .join("");
          wireConnectButtons(ent);
        }
        const quick = qs("integQuick");
        if (quick) {
          quick.innerHTML = `
            <article class="integ-card">
              <h2>Jira</h2>
              <p class="hint">Create issues from remediations</p>
              <span class="wq-badge pri-low">shipped</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="settings" data-focus="jira">Configure</button>
              </div>
            </article>
            <article class="integ-card">
              <h2>Scanner import</h2>
              <p class="hint">Trivy, Semgrep, Grype, ZAP, Bandit, Checkov, Gitleaks, SonarQube</p>
              <span class="wq-badge pri-low">import</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="workspace" data-target="vulns">Open vulns</button>
              </div>
            </article>
            <article class="integ-card">
              <h2>Webhooks / n8n</h2>
              <p class="hint">Starts empty — add a webhook below</p>
              <span class="wq-badge pri-low">shipped</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="webhooks">Manage</button>
              </div>
            </article>
            <article class="integ-card">
              <h2>Threat intel</h2>
              <p class="hint">Watchlist + CISA KEV sync</p>
              <span class="wq-badge pri-low">shipped</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="workspace" data-target="intel">Open intel</button>
              </div>
            </article>
            <article class="integ-card">
              <h2>Frameworks</h2>
              <p class="hint">ISO / NIST / CIS / SOC2 / PCI / HIPAA / GDPR / ASVS</p>
              <span class="wq-badge pri-low">shipped</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="workspace" data-target="frameworks">Open frameworks</button>
              </div>
            </article>
            <article class="integ-card">
              <h2>AI Router</h2>
              <p class="hint">Ollama, OpenRouter, Groq, OpenAI…</p>
              <span class="wq-badge pri-low">shipped</span>
              <div class="cc-action-row" style="margin-top:0.75rem">
                <button type="button" class="cc-action integ-connect" data-kind="settings" data-focus="ai">AI settings</button>
              </div>
            </article>`;
          wireConnectButtons(quick);
        }
      } catch (err) {
        const mvp = qs("integMvp");
        if (mvp) mvp.innerHTML = `<p class="hint">Catalog unavailable: ${escapeHtml(err.message || String(err))}</p>`;
      }
    }
    loadCatalog();
    loadStatusStrip();
    loadVulnSampleButtons();

    qs("workspaceResetBtn")?.addEventListener("click", async () => {
      if (!confirm("Reset this workspace to empty? This cannot be undone.")) return;

      // Two-step approval: request a code (delivered to Notifications), then
      // the user must read and re-enter it — not just click through a dialog.
      const reqRes = await fetch("/api/workspace/reset/request-code", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
      });
      if (!reqRes.ok) {
        const errData = await reqRes.json().catch(() => ({}));
        if (typeof notifyUser === "function")
          notifyUser(`**Reset failed:** ${errData.detail || reqRes.status}`);
        return;
      }
      const code = prompt(
        "A confirmation code was sent to your Notifications (bell icon). Enter it to confirm the reset:"
      );
      if (!code) return;

      const res = await fetch("/api/workspace/reset", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          confirm: true,
          confirm_code: code.trim(),
          clear_rag: Boolean(qs("resetClearRag")?.checked),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (typeof notifyUser === "function") notifyUser(`**Reset failed:** ${data.detail || res.status}`);
        return;
      }
      try {
        localStorage.removeItem("securaiq.kpi.snap");
      } catch {
        /* ignore */
      }
      if (typeof notifyUser === "function") {
        notifyUser("**Workspace reset** — Mission Control starts from zero. Reload recommended.");
      }
      if (typeof loadCommandCenter === "function") loadCommandCenter();
      else location.reload();
    });

    async function loadHooks() {
      const res = await fetch("/api/webhooks", { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      const list = qs("webhookList");
      const hooks = data.webhooks || [];
      if (!list) return;
      list.innerHTML = hooks.length
        ? hooks
            .map(
              (h) =>
                `<li><strong>${escapeHtml(h.name)}</strong> <span class="hint">${escapeHtml(h.url)}</span>
                <button type="button" class="btn-secondary ws-del-hook" data-id="${escapeHtml(h.id)}">Remove</button></li>`
            )
            .join("")
        : `<li class="hint">No webhooks yet</li>`;
      list.querySelectorAll(".ws-del-hook").forEach((btn) => {
        btn.addEventListener("click", async () => {
          await fetch(`/api/webhooks/${btn.getAttribute("data-id")}`, { method: "DELETE", headers: authHeaders() });
          loadHooks();
          loadStatusStrip();
        });
      });
      loadStatusStrip();
    }
    qs("webhookForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await fetch("/api/webhooks", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: qs("webhookName")?.value?.trim(),
          url: qs("webhookUrl")?.value?.trim(),
          events: ["*"],
        }),
      });
      qs("webhookName").value = "";
      qs("webhookUrl").value = "";
      loadHooks();
    });
    qs("webhookTest")?.addEventListener("click", async () => {
      const res = await fetch("/api/webhooks/dispatch", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ event: "test", payload: { message: "SecuraIQ webhook test" } }),
      });
      const data = await res.json().catch(() => ({}));
      if (typeof notifyUser === "function") notifyUser(`**Webhooks:** sent ${data.sent ?? 0}`);
    });
    loadHooks();
  }

  async function renderGraphPage() {
    const body = qs("graphPageBody");
    if (!body) return;
    body.innerHTML = `<p class="hint">Loading graph…</p>`;
    const [gRes, lRes] = await Promise.all([
      fetch("/api/graph", { headers: authHeaders() }),
      fetch("/api/graph/links", { headers: authHeaders() }),
    ]);
    const data = await gRes.json().catch(() => ({}));
    const linksData = await lRes.json().catch(() => ({}));
    if (!gRes.ok) {
      body.innerHTML = `<p class="hint">${escapeHtml(data.detail || "Graph unavailable")}</p>`;
      return;
    }
    const counts = data.counts || {};
    const byType = counts.by_type || {};
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    const links = linksData.links || [];
    body.innerHTML = `
      <div class="asset-breakdown-grid" style="margin-bottom:1rem">
        ${Object.entries(byType)
          .map(([k, v]) => `<div class="ab-tile"><span>${escapeHtml(k)}</span><strong>${v}</strong></div>`)
          .join("")}
      </div>
      <p class="hint">${counts.nodes || 0} nodes · ${counts.edges || 0} edges · ${links.length} manual links</p>
      <div class="graph-path" aria-label="Attack surface path">
        <span>Repo</span><i></i><span>Container</span><i></i><span>Image</span><i></i><span>Cloud</span><i></i><span>Server</span><i></i><span>Vuln</span><i></i><span>Incident</span><i></i><span>Compliance</span>
      </div>
      <div class="ws-grid-2">
        <section class="cc-panel">
          <header><h2>Nodes</h2></header>
          <ul class="cc-list">${nodes
            .slice(0, 60)
            .map(
              (n) =>
                `<li><strong>${escapeHtml(n.type)}</strong> ${escapeHtml(n.label)}
                <span class="hint">${escapeHtml(JSON.stringify(n.meta || {}).slice(0, 60))}</span></li>`
            )
            .join("")}</ul>
        </section>
        <section class="cc-panel">
          <header><h2>Relationships</h2></header>
          <ul class="cc-list">${edges
            .slice(0, 40)
            .map(
              (e) =>
                `<li><code>${escapeHtml(e.from)}</code> —${escapeHtml(e.relation)}→ <code>${escapeHtml(
                  e.to
                )}</code></li>`
            )
            .join("")}</ul>
          <button type="button" class="cc-action" id="graphAskAi" style="margin-top:0.75rem">Ask AI to explain top attack paths</button>
        </section>
      </div>
      <section class="cc-panel" style="margin-top:1rem">
        <header><h2>Add entity link</h2></header>
        <form id="graphLinkForm" class="inline-form" style="flex-wrap:wrap;gap:0.5rem">
          <input id="glSrcType" placeholder="src type (asset)" required />
          <input id="glSrcId" placeholder="src id" required />
          <input id="glRel" placeholder="relation" value="related" />
          <input id="glDstType" placeholder="dst type (vuln)" required />
          <input id="glDstId" placeholder="dst id" required />
          <button type="submit">Link</button>
        </form>
        <ul class="cc-list" style="margin-top:0.75rem">${
          links.length
            ? links
                .slice(0, 30)
                .map(
                  (l) =>
                    `<li><code>${escapeHtml(l.src_type)}:${escapeHtml(l.src_id)}</code> —${escapeHtml(
                      l.relation || "related"
                    )}→ <code>${escapeHtml(l.dst_type)}:${escapeHtml(l.dst_id)}</code></li>`
                )
                .join("")
            : `<li class="hint">No manual links yet</li>`
        }</ul>
      </section>`;
    qs("graphAskAi")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function") {
        runNavPrompt(
          "assess",
          "Using our asset-vuln-risk-control graph, explain the top 5 attack paths and priority remediations."
        );
      }
    });
    qs("graphLinkForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const res = await fetch("/api/graph/links", {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            src_type: qs("glSrcType")?.value?.trim(),
            src_id: qs("glSrcId")?.value?.trim(),
            relation: qs("glRel")?.value?.trim() || "related",
            dst_type: qs("glDstType")?.value?.trim(),
            dst_id: qs("glDstId")?.value?.trim(),
          }),
        });
        const out = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(out.detail || res.status);
        renderGraphPage();
      } catch (err) {
        alert(err.message || "Link failed");
      }
    });
  }

  async function renderBillingPage() {
    const body = qs("billingPageBody");
    if (!body) return;
    body.innerHTML = `<p class="hint">Loading billing…</p>`;
    let dash = {};
    let plat = {};
    let usage = {};
    let plans = [];
    try {
      const [dRes, healthRes, platRes, usageRes, plansRes] = await Promise.all([
        fetch("/api/dashboard", { headers: authHeaders() }),
        fetch("/api/health").catch(() => null),
        fetch("/api/platform/status", { headers: authHeaders() }).catch(() => null),
        fetch("/api/billing/usage", { headers: authHeaders() }).catch(() => null),
        fetch("/api/billing/plans").catch(() => null),
      ]);
      dash = await dRes.json().catch(() => ({}));
      if (healthRes && healthRes.ok) plat = await healthRes.json().catch(() => ({}));
      const platStatus = platRes && platRes.ok ? await platRes.json().catch(() => ({})) : {};
      plat = { ...plat, ...platStatus };
      usage = usageRes && usageRes.ok ? await usageRes.json().catch(() => ({})) : {};
      const plansData = plansRes && plansRes.ok ? await plansRes.json().catch(() => ({})) : {};
      plans = Object.entries(plansData.plans || {}).map(([id, p]) => ({ id, ...p }));
    } catch {
      /* ignore */
    }
    const limit = usage.messages_limit == null ? "unlimited" : usage.messages_limit;
    const planCards = plans.length
      ? plans
          .map(
            (p) => `<article class="cc-panel integ-card-sm">
              <h3>${escapeHtml(p.label || p.id)}</h3>
              <p class="hint">${p.price_usd == null ? "Contact sales" : p.price_usd === 0 ? "Free" : `$${p.price_usd}/mo`}</p>
              <p>${p.messages_per_month == null ? "Unlimited messages" : `${p.messages_per_month} messages/mo`}</p>
              ${
                p.id !== "free" && p.id !== (usage.plan || "free")
                  ? `<button type="button" class="btn-secondary billing-upgrade" data-plan="${escapeHtml(p.id)}">Upgrade</button>`
                  : p.id === (usage.plan || "free")
                    ? `<span class="hint">Current plan</span>`
                    : ""
              }
            </article>`
          )
          .join("")
      : `<p class="hint">Community / local — self-hosted</p>`;
    body.innerHTML = `
      <div class="billing-grid">
        <section class="cc-panel">
          <header><h2>Subscription</h2></header>
          <p><strong>${escapeHtml(usage.plan_label || usage.plan || "Community")}</strong></p>
          <p class="hint">${usage.messages_used_this_month ?? 0} / ${escapeHtml(String(limit))} messages this month
            ${usage.enforcement_enabled ? "" : " (soft limit)"}</p>
          <div class="integ-grid" style="margin-top:1rem">${planCards}</div>
        </section>
        <section class="cc-panel">
          <header><h2>Workspace usage</h2></header>
          <ul class="cc-list">
            <li>Assets — <strong>${dash.assets_total || 0}</strong></li>
            <li>Open risks — <strong>${dash.risks_open || 0}</strong></li>
            <li>Open vulns — <strong>${dash.vulnerabilities_open || 0}</strong></li>
            <li>Remediations — <strong>${dash.remediations_open || 0}</strong></li>
            <li>Gap assessments — <strong>${dash.assessment_count || 0}</strong></li>
            <li>Playbooks — <strong>${dash.playbooks_total || 0}</strong></li>
          </ul>
        </section>
        <section class="cc-panel">
          <header><h2>Platform</h2></header>
          <p class="hint">${escapeHtml(plat.status || "Local · no cloud billing")}</p>
          <ul class="cc-list">
            <li>Backend — ${escapeHtml(String(plat.backend || "—"))}</li>
            <li>Model — ${escapeHtml(String(plat.model || "—"))}</li>
            <li>RAG docs — ${escapeHtml(String(plat.rag_documents ?? "—"))}</li>
            <li>Vector store — ${escapeHtml(String(plat.vector_store || "—"))}</li>
            <li>Scanners — ${escapeHtml(String((plat.scanners || []).length || "—"))} import adapters</li>
            <li>Intel feeds — ${escapeHtml(String((plat.intel_feeds || []).length || "—"))} wired</li>
          </ul>
        </section>
        <section class="cc-panel">
          <header><h2>Invoices</h2></header>
          <p class="hint">Stripe checkout when <code>STRIPE_SECRET_KEY</code> is configured. Local mode has no invoices.</p>
        </section>
      </div>`;
    body.querySelectorAll(".billing-upgrade").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const plan = btn.getAttribute("data-plan");
        btn.disabled = true;
        try {
          const res = await fetch("/api/billing/checkout", {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
              plan,
              success_url: `${window.location.origin}/?billing=success`,
              cancel_url: `${window.location.origin}/?billing=cancel`,
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
          if (data.url) window.location.href = data.url;
          else if (typeof notifyUser === "function") notifyUser("**Checkout session created.**");
        } catch (err) {
          alert(err.message || "Checkout unavailable");
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  async function loadVulnSampleButtons() {
    const row = qs("vulnsSampleRow");
    if (!row) return;
    try {
      const res = await fetch("/api/vulnerabilities/samples", { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      const samples = data.samples || [];
      if (!samples.length) {
        row.innerHTML = `<span class="hint">No lab fixtures in data/samples/</span>`;
        return;
      }
      row.innerHTML = samples
        .map((s) => {
          const label = (s.id || "").replace(/-lab$/, "").replace(/-/g, " ");
          return `<button type="button" class="btn-secondary vulns-sample-btn" data-sample-id="${escapeHtml(
            s.id
          )}">${escapeHtml(label)}</button>`;
        })
        .join("");
      row.querySelectorAll(".vulns-sample-btn").forEach((btn) => {
        btn.addEventListener("click", () => importLabSample(btn.getAttribute("data-sample-id")));
      });
    } catch {
      row.innerHTML = `<span class="hint">Could not load lab fixtures</span>`;
    }
  }

  async function importLabSample(sampleId) {
    try {
      const res = await fetch(`/api/vulnerabilities/samples/${encodeURIComponent(sampleId)}/import`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data.detail || `Import failed (${res.status})`);
        return;
      }
      if (typeof notifyUser === "function") {
        notifyUser(
          `**Lab sample imported:** ${data.adapter || sampleId} · ${data.imported || 0} findings (authorized fixture)`
        );
      }
      showWorkspace("vulns");
      renderVulnsPage();
      loadVulnSampleButtons();
      if (typeof loadCommandCenter === "function") loadCommandCenter();
    } catch (err) {
      alert(err.message || "Sample import failed");
    }
  }

  function renderAutomationPage() {
    const body = qs("automationPageBody");
    if (!body) return;
    body.innerHTML = `<p class="hint">Loading jobs…</p>`;
    refreshAutomationPage();
  }

  async function refreshAutomationPage() {
    const body = qs("automationPageBody");
    if (!body) return;
    let jobs = [];
    let prefect = {};
    try {
      const res = await fetch("/api/jobs?limit=40", { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      jobs = data.jobs || [];
      prefect = data.prefect || {};
      if (!res.ok) throw new Error(data.detail || `Jobs failed (${res.status})`);
    } catch (err) {
      body.innerHTML = `<p class="hint">Could not load jobs: ${escapeHtml(err.message || String(err))}</p>`;
      return;
    }
    if (!prefect.installed && !prefect.ready) {
      try {
        const pr = await fetch("/api/prefect/status", { headers: authHeaders() });
        prefect = (await pr.json().catch(() => ({}))) || prefect;
      } catch {
        /* ignore */
      }
    }
    const engineDefault = prefect.ready ? "prefect" : "local";
    const fmtWhen = (ts) => {
      if (ts == null || ts === "") return "-";
      const n = Number(ts);
      const d = Number.isFinite(n) && n > 1e11 ? new Date(n) : Number.isFinite(n) ? new Date(n * 1000) : new Date(ts);
      return Number.isNaN(d.getTime()) ? String(ts) : d.toLocaleString();
    };
    const jobRows =
      jobs.length > 0
        ? jobs
            .map((j) => {
              const st = String(j.status || "unknown").toLowerCase();
              const eng = (j.payload && j.payload._engine) || (j.result && j.result.engine) || "-";
              const summary =
                j.error ||
                (j.result && (j.result.path || j.result.count != null || j.result.duration_sec != null)
                  ? JSON.stringify(j.result).slice(0, 120)
                  : "");
              return `<li data-job-id="${escapeHtml(j.id)}">
                  <div>
                    <strong>${escapeHtml(j.kind || "?")}</strong>
                    <span class="hint">${escapeHtml(eng)} · ${escapeHtml(fmtWhen(j.created_at))}</span>
                    ${summary ? `<span class="hint">${escapeHtml(String(summary).slice(0, 140))}</span>` : ""}
                  </div>
                  <span class="auto-job-status status-${escapeHtml(st)}">${escapeHtml(st)}</span>
                  <span class="hint">${escapeHtml(fmtWhen(j.finished_at || j.started_at))}</span>
                </li>`;
            })
            .join("")
        : `<li class="hint">No runs yet - enqueue KEV sync, XDR sync, or a board report below.</li>`;
    const logLines = jobs
      .slice(0, 12)
      .map((j) => {
        const st = j.status || "?";
        const when = fmtWhen(j.finished_at || j.started_at || j.created_at);
        return `<div class="auto-log-line"><code>${escapeHtml(when)}</code> <strong>${escapeHtml(
          j.kind || ""
        )}</strong> ${escapeHtml(st)}${j.error ? ` - ${escapeHtml(String(j.error).slice(0, 80))}` : ""}</div>`;
      })
      .join("");
    body.innerHTML = `
      <section class="cc-panel auto-flow-panel">
        <header><h2>Golden-path workflow</h2>
          <p class="hint">Visual pipeline for authorized scan → decision → ticket → verify. Jobs below power the automation spine.</p>
        </header>
        <div class="auto-flow" role="list">
          ${["Trigger", "Scan", "AI triage", "Risk", "Approval", "Ticket", "Notify", "Close"]
            .map(
              (step, i) =>
                `<div class="auto-flow-step" role="listitem"><span>${i + 1}</span><strong>${step}</strong></div>${
                  i < 7 ? '<span class="auto-flow-arrow" aria-hidden="true">→</span>' : ""
                }`
            )
            .join("")}
        </div>
      </section>
      <section class="cc-panel">
        <header><h2>Prefect</h2>
          <p class="hint">${escapeHtml(prefect.hint || "Optional job orchestrator")}</p>
        </header>
        <p>
          <span class="auto-job-status status-${prefect.ready ? "done" : prefect.installed ? "partial" : "planned"}">
            ${prefect.ready ? "ready" : prefect.installed ? "installed" : "not installed"}
          </span>
          ${prefect.version ? `<span class="hint">v${escapeHtml(prefect.version)}</span>` : ""}
          ${prefect.api_url ? `<span class="hint">${escapeHtml(prefect.api_url)}</span>` : ""}
        </p>
        <div class="cc-action-row auto-run-row">
          <label class="hint">Engine
            <select id="autoJobEngine" class="composer-select">
              <option value="auto">auto (${escapeHtml(engineDefault)})</option>
              <option value="local">local</option>
              <option value="prefect" ${prefect.installed ? "" : "disabled"}>prefect</option>
            </select>
          </label>
          <button type="button" class="btn-primary-cc" data-job-kind="kev_sync">Run KEV sync</button>
          <button type="button" class="btn-secondary" data-job-kind="xdr_sync">Run XDR sync</button>
          <button type="button" class="btn-secondary" data-job-kind="wazuh_sync">Run Wazuh sync</button>
          <button type="button" class="btn-secondary" data-job-kind="report_export">Export board PDF</button>
        </div>
      </section>
      <div class="auto-grid">
        <section class="cc-panel">
          <header><h2>Jobs</h2></header>
          <ul class="auto-job-list">${jobRows}</ul>
        </section>
        <section class="cc-panel">
          <header><h2>Triggers &amp; webhooks</h2></header>
          <p class="hint">Wire scanner webhooks and chatops under Integrations. Prefect wraps the same handlers when enabled.</p>
          <div class="cc-action-row">
            <button type="button" class="cc-action" data-workspace="integrations">Open integrations</button>
            <button type="button" class="btn-secondary" data-workspace="reports">Reports</button>
          </div>
        </section>
        <section class="cc-panel">
          <header><h2>Execution logs</h2></header>
          <div class="auto-log">
            ${logLines || `<p class="hint">No automated runs yet - enqueue a job above.</p>`}
          </div>
        </section>
      </div>`;
    body.querySelectorAll("[data-workspace]").forEach((el) => {
      el.addEventListener("click", () => showWorkspace(el.getAttribute("data-workspace")));
    });
    body.querySelectorAll("[data-job-kind]").forEach((btn) => {
      btn.addEventListener("click", () => enqueueAutomationJob(btn.getAttribute("data-job-kind")));
    });
  }

  async function enqueueAutomationJob(kind) {
    if (!kind) return;
    const engine = qs("autoJobEngine")?.value || "auto";
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ kind, engine, payload: {} }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg || `Enqueue failed (${res.status})`);
        return;
      }
      if (typeof notifyUser === "function") {
        notifyUser(`**Job queued:** \`${kind}\` (${engine}) · id \`${data.id || "?"}\``);
      }
      setTimeout(() => refreshAutomationPage(), 600);
      setTimeout(() => refreshAutomationPage(), 2500);
    } catch (err) {
      alert(err.message || "Enqueue failed");
    }
  }

  function wireAutomationControls() {
    if (window.__securaiqAutoWired) return;
    window.__securaiqAutoWired = true;
    qs("automationAskDesign")?.addEventListener("click", () => {
      const btn = qs("automationAskDesign");
      const mode = btn?.getAttribute("data-mode") || "ciso";
      const prompt = btn?.getAttribute("data-prompt") || "";
      if (typeof window.runNavPrompt === "function") window.runNavPrompt(mode, prompt, { stay: true });
    });
    qs("automationRefreshJobs")?.addEventListener("click", () => refreshAutomationPage());
  }
  wireAutomationControls();
  window.refreshAutomationPage = refreshAutomationPage;

  function wireWorkspaceNav() {
    if (window.__securaiqWsNavWired) return;
    window.__securaiqWsNavWired = true;
    document.querySelectorAll("[data-workspace]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        showWorkspace(el.getAttribute("data-workspace"));
      });
    });
    // notifBtn now opens the real notifications panel (wired in app.js).
    // "Open SOC" inside that panel still uses the generic [data-workspace] handler above.

    document.querySelectorAll(".ai-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const wsTab = tab.getAttribute("data-workspace-tab");
        if (wsTab) {
          showWorkspace(wsTab);
          return;
        }
        if (tab.hasAttribute("data-open-palette")) {
          if (typeof showView === "function") showView("chat");
          if (typeof window.openAiTab === "function") window.openAiTab("tools");
          if (typeof window.openToolsPalette === "function") window.openToolsPalette(true);
          return;
        }
        const name = tab.getAttribute("data-ai-tab");
        if (typeof window.openAiTab === "function") window.openAiTab(name);
        else {
          document.querySelectorAll(".ai-tab").forEach((t) => t.classList.remove("active"));
          tab.classList.add("active");
          document.querySelectorAll(".ai-tab-panel").forEach((p) => p.classList.add("hidden"));
          qs(`aiTab-${name}`)?.classList.remove("hidden");
          if (name === "files") refreshAiFilesTab();
          if (name === "tools") refreshAiToolsTab();
          if (name === "memory") refreshAiMemoryTab();
          if (name === "tasks") refreshAiTasksTab();
        }
      });
    });
  }

  async function refreshAiTasksTab() {
    const el = qs("aiTab-tasks");
    if (!el) return;
    const res = await fetch("/api/dashboard", { headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    const queue = data.work_queue || [];
    el.innerHTML = `<div class="saas-tab-head"><h2>AI work queue</h2></div>`;
    if (typeof window.renderWorkQueue === "function") {
      const host = document.createElement("div");
      host.id = "ccWorkQueue";
      el.appendChild(host);
      window.renderWorkQueue(queue);
    } else {
      el.innerHTML += `<ul class="cc-list">${queue
        .map((w) => `<li><strong>${escapeHtml(w.priority)}</strong> ${escapeHtml(w.title)}</li>`)
        .join("")}</ul>`;
    }
  }
  window.refreshAiTasksTab = refreshAiTasksTab;

  async function refreshAiFilesTab() {
    const el = qs("aiTab-files");
    if (!el) return;
    const res = await fetch("/api/files", { headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    const files = data.files || data.items || [];
    el.innerHTML = `
      <div class="saas-tab-head">
        <h2>Workspace files</h2>
        <button type="button" class="btn-secondary" id="aiFilesUpload">Upload</button>
      </div>
      ${
        files.length
          ? `<ul class="cc-list">${files
              .map(
                (f) =>
                  `<li><strong>${escapeHtml(f.filename || f.name || f.id)}</strong>
                  <span class="hint">${escapeHtml(String(f.size_bytes || f.size || ""))}</span></li>`
              )
              .join("")}</ul>`
          : `<p class="hint">No uploaded files — use Upload to feed RAG / evidence.</p>`
      }
      <button type="button" class="cc-action" id="aiFilesAsk" style="margin-top:1rem">Ask AI about attached evidence</button>`;
    qs("aiFilesUpload")?.addEventListener("click", () => qs("fileUploadInput")?.click());
    qs("aiFilesAsk")?.addEventListener("click", () => {
      if (typeof runNavPrompt === "function")
        runNavPrompt("ciso", "Summarize uploaded evidence and what controls it supports");
    });
  }
  window.refreshAiFilesTab = refreshAiFilesTab;

  async function refreshAiToolsTab() {
    const el = qs("aiTab-tools");
    if (!el) return;
    const res = await fetch("/api/tools");
    const data = await res.json();
    const selected = typeof window.getSelectedTools === "function" ? window.getSelectedTools() : [];
    el.innerHTML = `
      <div class="saas-tab-head">
        <h2>Cyber tools suite</h2>
        <button type="button" class="btn-primary-cc" id="aiToolsOpenPalette">Open palette</button>
      </div>
      <p class="hint">${data.available_count || 0}/${data.count || 0} ready — select tools, set Auth + lab target, then Run or chat with them.</p>
      <div class="tools-cat-grid" style="margin:0.75rem 0">
        ${(data.tools || [])
          .map(
            (t) => `<button type="button" class="tool-pick ${t.available ? "" : "unavailable"} ${
              selected.includes(t.id) ? "selected" : ""
            }" data-id="${escapeHtml(t.id)}" ${t.available ? "" : "disabled"}>
              <span><strong>${escapeHtml(t.name || t.id)}</strong>
              <small>${t.available ? (t.heavy ? "heavy" : "ready") : "missing"}</small></span>
            </button>`
          )
          .join("")}
      </div>
      <div class="cc-action-row">
        <button type="button" class="cc-action" id="aiToolsRun">Run selected</button>
        <button type="button" class="cc-action" id="aiToolsChat">Chat with selected</button>
        <button type="button" class="btn-secondary" id="aiToolsClear">Clear</button>
      </div>`;
    el.querySelectorAll(".tool-pick").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.classList.contains("unavailable")) return;
        const id = btn.getAttribute("data-id");
        let cur = typeof window.getSelectedTools === "function" ? window.getSelectedTools() : [];
        if (cur.includes(id)) cur = cur.filter((x) => x !== id);
        else cur = cur.concat(id);
        if (typeof window.setSelectedTools === "function") window.setSelectedTools(cur);
        btn.classList.toggle("selected", cur.includes(id));
      });
    });
    qs("aiToolsOpenPalette")?.addEventListener("click", () => {
      if (typeof window.openToolsPalette === "function") window.openToolsPalette(true);
    });
    qs("aiToolsRun")?.addEventListener("click", () => {
      if (typeof window.runSelectedTools === "function") window.runSelectedTools();
    });
    qs("aiToolsChat")?.addEventListener("click", () => {
      const tools = typeof window.getSelectedTools === "function" ? window.getSelectedTools() : [];
      if (typeof window.openAiTab === "function") window.openAiTab("chat");
      if (typeof runNavPrompt === "function") {
        runNavPrompt(
          "assess",
          tools.length
            ? `Use tools ${tools.join(", ")} on the authorized/lab target and summarize findings with remediations.`
            : "Recommend which built-in cyber tools to run for a typical lab web app assessment."
        );
      }
    });
    qs("aiToolsClear")?.addEventListener("click", () => {
      if (typeof window.setSelectedTools === "function") window.setSelectedTools([]);
      refreshAiToolsTab();
    });
  }
  window.refreshAiToolsTab = refreshAiToolsTab;

  async function refreshAiMemoryTab() {
    const el = qs("aiTab-memory");
    if (!el) return;
    const eng = qs("engagementSelect")?.value;
    if (!eng) {
      el.innerHTML = `<p class="hint">Select or create a Project/engagement to store memories. Memories are injected into AI chat context automatically.</p>
        <button type="button" class="cc-action" id="aiMemNew">Create engagement</button>`;
      qs("aiMemNew")?.addEventListener("click", () => qs("newEngagementBtn")?.click());
      return;
    }
    const res = await fetch(`/api/engagements/${eng}/memories`, { headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    const mems = data.memories || data.items || [];
    el.innerHTML = `
      <div class="saas-tab-head"><h2>Engagement memory</h2></div>
      <ul class="cc-list">${
        mems.length
          ? mems
              .map((m) => `<li><strong>${escapeHtml(m.key)}</strong> — ${escapeHtml(m.value)}</li>`)
              .join("")
          : `<li class="hint">No memories yet</li>`
      }</ul>
      <form id="aiMemForm" class="inline-form" style="margin-top:0.75rem">
        <input id="aiMemKey" placeholder="key (e.g. scope)" required />
        <input id="aiMemVal" placeholder="value" required />
        <button type="submit">Save</button>
      </form>`;
    qs("aiMemForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await fetch(`/api/engagements/${eng}/memories`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          key: qs("aiMemKey")?.value?.trim(),
          value: qs("aiMemVal")?.value?.trim(),
        }),
      });
      refreshAiMemoryTab();
    });
  }
  window.refreshAiMemoryTab = refreshAiMemoryTab;

  // Upgrade global search to API results panel
  if (!window.__securaiqSearchWired) {
    window.__securaiqSearchWired = true;
    const searchEl = qs("globalSearch");
    const resultsEl = qs("searchResults");
    const route = {
      asset: "assets",
      risk: "risks",
      vuln: "vulns",
      remediation: "remediations",
      playbook: "playbooks",
      campaign: "campaigns",
      incident: "soc",
      intel: "intel",
    };

    function hideSearchResults() {
      resultsEl?.classList.add("hidden");
      if (resultsEl) resultsEl.innerHTML = "";
    }

    async function runGlobalSearch(q) {
      if (!q || !resultsEl) return;
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, { headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      const results = data.results || [];
      if (!results.length) {
        resultsEl.innerHTML = `<button type="button" class="search-hit" data-ask="1">No register hits — ask AI about “${escapeHtml(
          q
        )}”</button>`;
        resultsEl.classList.remove("hidden");
        resultsEl.querySelector("[data-ask]")?.addEventListener("click", () => {
          hideSearchResults();
          if (typeof runNavPrompt === "function") runNavPrompt("default", `Find and explain: ${q}`);
        });
        return;
      }
      resultsEl.innerHTML = results
        .slice(0, 12)
        .map(
          (r) =>
            `<button type="button" class="search-hit" data-kind="${escapeHtml(r.kind || "")}">
              <span class="search-kind">${escapeHtml(r.kind || "")}</span>
              <strong>${escapeHtml(r.title || r.name || r.id || "")}</strong>
              <span class="hint">${escapeHtml(r.meta || r.subtitle || r.summary || "")}</span>
            </button>`
        )
        .join("");
      resultsEl.classList.remove("hidden");
      resultsEl.querySelectorAll(".search-hit").forEach((btn) => {
        btn.addEventListener("click", () => {
          const kind = btn.getAttribute("data-kind");
          hideSearchResults();
          showWorkspace(route[kind] || "command");
        });
      });
    }

    if (searchEl) {
      searchEl.addEventListener("keydown", async (e) => {
        if (e.key === "Escape") {
          hideSearchResults();
          return;
        }
        if (e.key !== "Enter") return;
        e.preventDefault();
        e.stopImmediatePropagation();
        await runGlobalSearch(searchEl.value.trim());
      });
      searchEl.addEventListener("input", () => {
        if (!searchEl.value.trim()) hideSearchResults();
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest?.(".topbar-search-wrap")) hideSearchResults();
      });
    }
  }

  function rewireModuleButtons() {
    if (window.__securaiqRewireDone) return;
    window.__securaiqRewireDone = true;
    const map = {
      assetBtn: "assets",
      riskBtn: "risks",
      vulnBtn: "vulns",
      remBtn: "remediations",
      playbookBtn: "playbooks",
      campaignBtn: "campaigns",
      exportChatBtn: "reports",
      reportsBtn: "reports",
      navEvidence: "evidence",
      orgsBtn: "orgs",
      frameworksBtn: "frameworks",
      dashboardBtn: "command",
    };
    Object.entries(map).forEach(([id, view]) => {
      const el = qs(id);
      if (!el) return;
      el.addEventListener(
        "click",
        (e) => {
          e.preventDefault();
          e.stopImmediatePropagation();
          if (view === "command") {
            if (typeof showView === "function") showView("command");
            else showWorkspace("command");
          } else showWorkspace(view);
        },
        true
      );
    });

    const openers = [
      ["assetsOpenCreate", () => typeof openAsset === "function" && openAsset()],
      ["risksOpenCreate", () => typeof openRisk === "function" && openRisk()],
      ["vulnsOpenImport", () => typeof openVuln === "function" && openVuln()],
      ["mcImportScanners", () => showWorkspace("vulns")],
      [
        "vulnsOpenExport",
        () => typeof downloadMd === "function" && downloadMd("/api/vulnerabilities/export", "securaiq-vulns.md"),
      ],
      ["remsOpenGap", () => typeof openGap === "function" && openGap()],
      ["playbooksOpenCreate", () => typeof openPlaybook === "function" && openPlaybook()],
      ["campaignsOpenCreate", () => typeof openCampaign === "function" && openCampaign()],
      ["evidenceUploadBtn", () => qs("fileUploadInput")?.click()],
      ["frameworksRunGap", () => typeof openGap === "function" && openGap()],
    ];
    openers.forEach(([id, fn]) => {
      const el = qs(id);
      if (el) el.addEventListener("click", fn);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireWorkspaceNav();
    rewireModuleButtons();
  });
  // Scripts load at end of body — wire once immediately; DOMContentLoaded is a no-op if already fired
  if (document.readyState === "loading") {
    /* wait for DOMContentLoaded */
  } else {
    wireWorkspaceNav();
    rewireModuleButtons();
  }
})();
