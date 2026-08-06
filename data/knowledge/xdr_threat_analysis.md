# XDR threat analysis (authorized SOC / lab)

Cross-telemetry investigation for enterprise XDR and SOC queues. Scope: systems you own, tabletop injects, and authorized labs only.

## Analysis loop

1. **Alert summary** — severity, rule/name, entities (host, user, IP, hash, mailbox)
2. **Correlate** — EDR + identity + email + network/DNS + cloud audit + vuln/KEV overlap
3. **Attack chain** — ATT&CK timeline from initial access through impact
4. **Blast radius** — accounts, assets, data classes at risk
5. **Verdict** — true positive / suspicious / false positive + confidence
6. **Response** — contain → eradicate → recover; hand off to IR when needed
7. **Detection debt** — Sigma / KQL / SPL / Elastic ideas to catch earlier

## Telemetry sources

| Stream | Typical signals |
|--------|-----------------|
| Endpoint / EDR | Process trees, file drops, persistence, lateral movement |
| Identity | Impossible travel, MFA fatigue, OAuth consent, privileged group changes |
| Email | Phishing URL/attachment, BEC language, spoofed domains |
| Network / NDR | C2-like beacons, unusual DNS, east-west anomalies |
| Cloud | CloudTrail / Activity logs, public buckets, key misuse |
| Vuln | Critical CVEs on same asset as alert; CISA KEV overlap |

## Triage heuristics

- Same user + host + time window across streams raises confidence
- Lone unsigned binary with no identity/email corroboration → verify before containment
- Living-off-the-land (PowerShell, rundll32, wmic) needs parent/child + network context
- Prefer MITRE technique IDs in narratives and detections

## Hard boundaries

- No ransomware kits, stealers, C2 builders, or evasion for real victims
- Crimeware questions → sandbox analysis + detection engineering only
- Always include remediation and detection notes with offensive technique detail
