# SecuraIQ User Manual

Authorized AI Security OS for labs, owned systems, CTFs, blue-team workflows, and GRC — not a general chatbot and not for unauthorized access.

**Open the app:** [http://127.0.0.1:8080](http://127.0.0.1:8080)  
**In-app copy:** [/manual/](/manual/) (when the server is running)

---

## 1. What SecuraIQ is for

| Use | Examples |
|-----|----------|
| Posture & decisions | Mission Control score, morning brief, work queue |
| Vuln workflow | Import scan → triage → Jira → verify → close |
| Compliance & risk | Frameworks, gap analysis, evidence, risk register |
| AI assistance | Floating assistant or AI Workspace (agents first) |
| Labs / CTF | Local tools, authorized target probe, playbooks |

**Not for:** malware distribution, credential theft, C2, or attacking systems you do not own or have written permission to test.

---

## 2. Start the application

### Windows

```powershell
.\scripts\run_proper.ps1
```

Quick start: `.\scripts\start.ps1`

### Linux / macOS

```bash
bash scripts/run_proper.sh
```

Then open **http://127.0.0.1:8080**.

### Models

Use Settings or the Advanced model routing panel to pick **Ollama**, **LM Studio**, or another configured backend. Pull a small model first (for example `ollama pull tinyllama`) so chat works offline.

---

## 3. Five pillars (sidebar)

1. **Mission Control** — morning brief, KPIs, charts, heat map, MITRE coverage, work queue  
2. **AI Workspace** — full chat, canvas, memory, files, tools, automation tab  
3. **Security Operations** — assets, vulnerabilities, threat intel, incidents, playbooks, campaigns  
4. **Compliance & Risk** — frameworks, gap analysis, controls, evidence, policies, risk register, knowledge graph  
5. **Automation** — visual golden-path workflow, jobs, triggers, reports  

Collapsed groups: **Cloud & Development**, **Administration** (orgs, integrations, billing, settings, account).

---

## 4. AI Assistant (floating)

On Mission Control and module pages the bottom chat bar is replaced by a bottom-right **AI Assistant** button.

| Action | Result |
|--------|--------|
| Click **Assistant** | Opens the floating panel |
| Use action chips | Executive Summary, Root Cause, Attack Path, Ticket, Report, Fix, Playbook, Investigation |
| **Ask AI** on a finding | Fills the assistant without leaving the page |
| **Workspace** | Opens the full AI Workspace |
| **Close** or `Esc` | Closes the panel |

Choose an **Agent** (SOC Analyst, Compliance Officer, …). Model backend/name stay under **Advanced model routing**.

---

## 5. Golden path (recommended daily flow)

```
Import scan  →  AI triage  →  Assign / Jira  →  Evidence  →  Report
```

1. **Vulnerabilities** → **Import scan** (or Lab fixtures for demos)  
2. Select a finding → review the right-hand detail panel  
3. **Triage** or **Triage+Jira**  
4. Attach **Evidence** and track **Remediations**  
5. Export from **Reports** (Markdown / PDF where enabled)  
6. Check **Mission Control** workflow counters and morning brief  

---

## 6. Module guides

### Mission Control

- Greeting + AI morning summary  
- Security score, compliance, critical/high, incidents, assets  
- Severity / asset / integration charts, risk heat map, MITRE strip  
- Work queue with Ask AI / open actions  

### Vulnerabilities

- Filters: search, severity, status, scanner, owner  
- Table: CVE, severity, CVSS, asset, owner, status, SLA, age, scanner  
- Detail panel: AI summary actions, references, triage / Jira / close  

### Compliance & frameworks

- KPI strip: implemented / partial / missing / coverage / evidence / maturity  
- Framework cards → **Open controls** → evidence, owner, risk, status  
- **Run gap** for ISO / NIST / CIS-style assessments  

### Assets

- Class tiles (server, endpoint, container, cloud, repo, database, app, domain, API)  
- Inventory table with Ask AI per asset  

### Automation

- Visual pipeline: Trigger → Scan → AI → Risk → Approval → Ticket → Notify → Close  
- Jobs and webhook pointers → Integrations  

### Knowledge graph

- Correlated assets, vulns, risks, controls, incidents for attack-path questions  
- Interactive force-graph viz is still evolving; lists and Ask AI paths work today  

### Integrations

- Connect scanners (Trivy, Semgrep, …), Jira, Slack webhooks, cloud stubs  
- Prefer **Connect** paths that open import/settings rather than fake “connected” badges  

### Reports

- Executive / technical / risk / vuln exports  
- Use AI **Generate Report** for narrative drafts, then export  

### Administration

- Organizations & members (when auth is on)  
- Settings: API keys, theme, model backends  
- Account: login / register when `AUTH_ENABLED=true`  
- Billing & audit (admin) as configured  

---

## 7. Global search & notifications

- Top search: assets, risks, vulns, controls — or ask AI if nothing matches  
- Notifications badge routes toward SOC / tasks (expanding over time)  

---

## 8. Tools & authorized probing

In the assistant or AI Workspace:

- Enable **Tools** / open the **Tools** palette  
- Set a **lab/owned Target IP** and check **Auth** before probe-style tools  
- Built-ins (DNS, ports, HTTP, headers) work without extra installs; PATH tools appear when installed  

---

## 9. Auth, projects, theme

| Topic | How |
|-------|-----|
| Auth off | Local open mode (default for solo lab use) |
| Auth on | `AUTH_ENABLED=true` — Account → login/register |
| Project / engagement | Sidebar **Project** selector + **+ New** |
| Theme | Sidebar theme toggle (light/dark) |
| Uploads | Upload evidence / RAG files from sidebar or AI Files tab |

---

## 10. Safety & legal

- Authorized labs, HTB/THM-style ranges, PortSwigger, and systems you own only  
- Draft legal pages: [/legal/](/legal/)  
- AI can be wrong — verify remediations and tickets before production change  

---

## 11. Troubleshooting

| Symptom | Try |
|---------|-----|
| Page looks old | Hard refresh (`Ctrl+F5`) |
| Chat fails | Check Ollama/LM Studio is running; Settings → backend/model |
| Empty Mission Control | Import a scan or run gap analysis |
| Jira fails | Configure Jira in Settings / env; use Triage without Jira first |
| Port in use | Change `PORT` in `.env` or stop the other process |

Developer docs: [README](../README.md), [enterprise integrations](enterprise-integrations.md), [AI router](ai-router.md), [launch readiness](launch-readiness.md).
