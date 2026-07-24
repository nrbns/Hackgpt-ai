# SecuraIQ — Enterprise Integrations

**Doctrine:** integrate mature open-source and commercial tools; SecuraIQ is the **AI orchestration layer** (findings → evidence → risk → compliance → reports), not a replacement for scanners, SIEMs, or full GRC.

```
Scanners / SIEM / Cloud / SCM
            │
            ▼
     Import · Webhooks · APIs
            │
            ▼
        SecuraIQ AI OS
   (router · agents · graph · GRC)
            │
            ▼
   Reports · Tasks · Jira · n8n
```

Full live catalog: `GET /api/integrations/catalog` (also **Administration → Integrations** in the UI).

Each catalog item includes a `ui_action` so Mission Control can **Connect** to the real path:

| `ui_action.kind` | Behavior |
|------------------|----------|
| `workspace` | Opens Vulns / Intel / Frameworks / Evidence / Orgs |
| `settings` | Opens Settings (AI Router or Jira) |
| `webhooks` | Scrolls to outbound webhook form (n8n / Slack bridge) |
| `planned` | Disabled — connector not shipped |
| `info` | Available in-build (no extra connector) |

---

## Recommended MVP (limited budget)

| Category | Tool | SecuraIQ status |
|----------|------|----------------|
| AI | Qwen + OpenRouter / Ollama | Shipped ([AI Router](./ai-router.md)) |
| SAST | Semgrep + SonarQube Community | JSON **import** |
| Secrets | Gitleaks | **import** |
| Containers / SCA | Trivy + Grype | **import** |
| IaC | Checkov | **import** |
| DAST | OWASP ZAP + Nuclei | PATH + ZAP **import** |
| Threat intel | MITRE + NVD + CISA KEV | Shipped |
| SIEM | Wazuh | Planned (webhook ingest later) |
| Automation | n8n | Webhooks shipped |
| Case mgmt | TheHive | Planned |
| Identity | Keycloak / Authentik | Planned (SSO Month 3) |
| DB | SQLite → PostgreSQL | SQLite shipped |
| Vectors | Qdrant | Optional compose profile |
| Storage | Local → MinIO | Local shipped |
| Backend | FastAPI | Shipped |
| Frontend | Mission Control (Next.js later) | Shipped |

---

## Scanner import (shipped)

Drop JSON into **Vulnerabilities → Import** (or lab fixtures):

| Adapter | Typical export |
|---------|----------------|
| Trivy | `trivy image -f json` |
| Semgrep | `semgrep --json` |
| Gitleaks | `gitleaks detect -r` |
| Grype | `grype -o json` |
| Checkov | `checkov -o json` |
| Bandit | `bandit -f json` |
| SonarQube | Issues API / export JSON |
| OWASP ZAP | Traditional JSON report |

AI interprets findings and drafts remediations — it does **not** invent scan results.

---

## Compliance frameworks

Shipped catalogs (subsets for gap analysis): ISO 27001 · ISO 27701 · NIST CSF · CIS · SOC 2 · PCI DSS · HIPAA · GDPR · OWASP ASVS.

Planned depth: NIST SP 800-53 full mapping.

---

## Platform roadmap (do not build in-house)

| Layer | Prefer |
|-------|--------|
| SIEM | Wazuh, Elastic, Security Onion |
| SOAR | n8n, Shuffle, StackStorm |
| IR | TheHive + Cortex |
| EDR telemetry | Wazuh / Velociraptor / Osquery |
| Cloud | Security Hub / Defender / SCC (read-only) |
| K8s | Kubescape, kube-bench |
| Identity | Keycloak, Authentik |
| Queues | NATS / RabbitMQ / Kafka (SaaS scale) |
| Observability | Prometheus, Grafana, Loki, OTel, Sentry |
| SCM | GitHub / GitLab / Azure DevOps / Bitbucket |
| Comms | Slack / Teams via webhooks |

Commercial tools (Nessus, Qualys, GitGuardian, Docker Scout, …) are **customer-bring-your-own-license** — SecuraIQ should ingest their exports, not reimplement them.

---

## AI agents (orchestration personas)

SOC Analyst · Threat Hunter · Malware Analyst · Compliance Officer · Risk Manager · Cloud Security Architect · Secure Code Reviewer · DevSecOps Engineer · Incident Commander · Executive Advisor

Routed via [AI Router](./ai-router.md) lanes + workspace modes.

---

## Enterprise features

| Feature | Status |
|---------|--------|
| Multi-tenancy / orgs | Shipped (basic) |
| RBAC | Shipped (basic) |
| Audit logs | Shipped |
| API keys | Shipped |
| Webhooks | Shipped |
| SSO / MFA | Planned |
| Report scheduling | Planned |
| White-labeling | Planned |

---

## Explicit non-goals

- Replacing Wazuh / Elastic / full GRC
- Shipping every connector before MVP workflows are solid
- Crimeware or unauthorized scanning workflows
