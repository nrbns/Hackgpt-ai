# SecuraIQ compliance frameworks (current editions)

Catalogs live in `data/frameworks/*.json` and power `GET /api/frameworks`, gap analysis, remediations, and audit packs.

| ID | Standard | Notes |
|----|----------|-------|
| iso27001 | ISO/IEC 27001:2022 Annex A | Full 93 controls |
| iso27701 | ISO/IEC 27701:2025 PIMS | Standalone privacy MS |
| nist_csf | NIST CSF 2.0 | Govern–Recover outcomes |
| nist_800_53 | NIST SP 800-53 Rev. 5 | Priority AC–SR controls |
| nist_800_171 | NIST SP 800-171 | CUI protection |
| cmmc_l2 | CMMC 2.0 Level 2 | DFARS / CUI practices |
| cis_controls | CIS Controls v8.1 | IG1 essentials |
| soc2 | SOC 2 TSC | 2017 TSC / 2022 points of focus |
| pci_dss | PCI DSS v4.0.1 | Priority requirements |
| hipaa | HIPAA Security Rule | 45 CFR Part 164 |
| gdpr | GDPR | Core articles |
| nis2 | NIS2 Directive | Art. 20–23 themes |
| owasp_asvs | OWASP ASVS 5.0 | Chapter requirements |
| owasp_top10 | OWASP Top 10:2025 | Risk categories |

## Workflow

1. Collect evidence (policies, configs, tickets, screenshots) in Evidence.
2. Run gap analysis (`POST /api/gap/run`) with framework_id + evidence text and/or file_ids.
3. Review Frameworks → Open controls (status, owner, evidence, risk).
4. Close remediations and link evidence; export Markdown assessment or audit ZIP.

Scoring is keyword/evidence heuristic with optional manual status overrides — attach formal artifacts before audit assertion.
