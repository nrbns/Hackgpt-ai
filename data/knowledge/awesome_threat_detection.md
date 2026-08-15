# Awesome Threat Detection (curated)

SecuraIQ surfaces the [0x4D31/awesome-threat-detection](https://github.com/0x4d31/awesome-threat-detection) list for authorized blue-team and hunt workflows.

## Use in SecuraIQ
- **Intel** workspace → Threat Detection catalog (search + category filter)
- API: `GET /api/intel/threat-detection?q=sigma&category=Detection`
- Refresh: `POST /api/intel/threat-detection/refresh`

## High-value starting points
| Area | Examples |
|------|----------|
| Detection rules | Sigma, Snort/Suricata, YARA, Splunk ESCU, Elastic detections |
| Endpoint | Sysmon (+ modular configs), osquery, Velociraptor, Wazuh |
| Network | Zeek, Suricata, Security Onion, Brim |
| Labs | DetectionLab, HELK, Atomic Red Team |
| Frameworks | MITRE ATT&CK Navigator, CAR, EQL |

## Hunt workflow with this catalog
1. Pick a hypothesis (ATT&CK technique or LOLBAS pattern)
2. Find matching **Detection Rules** / **Endpoint** / **Network** entries
3. Map to your SIEM/EDR (Wazuh, Defender hunting KQL, Sigma→Uncoder)
4. Validate in an authorized lab (DetectionLab / Atomic)
5. Convert true positives into durable detections + remediations

## Reminder
Only use tools and datasets against systems you own or are authorized to assess. Prefer detection/remediation notes alongside any offensive simulation content.
