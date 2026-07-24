# CISO all-rounder playbook

SecuraIQ in **CISO / GRC** mode balances offense understanding with defense and governance.

## Decision frame
1. Asset & data criticality
2. Threat scenarios (ransomware, BEC, insider, supply chain)
3. Control gaps (people / process / tech)
4. Residual risk acceptance vs treatment
5. Owner + due date + metric

## 30 / 60 / 90 (template)
- **30d:** MFA coverage, backup restore test, critical CVE SLA, email auth (SPF/DKIM/DMARC), EDR on endpoints
- **60d:** vuln scanning cadence (Greenbone), web DAST on staging (Burp/ZAP/Acunetix), phish sim #1, IR tabletop
- **90d:** ISO 27001 / NIST CSF gap review, detection engineering backlog, third-party risk tiering

## Metrics
- Patch SLA (Critical ≤7d)
- Vuln backlog age
- Phish report rate
- MTTD / MTTR
- Backup restore success

## Purple team
Red shows the chain; blue ships detection + control; CISO tracks residual risk to the board.
