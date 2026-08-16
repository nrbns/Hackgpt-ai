# SecuraIQ — Connector validation matrix

**Rule:** do not market an integration as “supported” until a live trial tenant has been verified.

Run status checks anytime:

```bash
python scripts/connector_verify.py
python scripts/connector_verify.py --matrix
python scripts/connector_verify.py --sync   # only hits configured vendors
```

| Integration | Code in repo | Live tenant | Notes |
|-------------|--------------|-------------|-------|
| GitHub webhooks | Built | Verify with `GITHUB_WEBHOOK_SECRET` | Code-scanning alerts |
| GitLab webhooks | Built | Trial pending | |
| Jira | Built | Trial pending | Ticket create from findings |
| Slack webhook | Built | Trial pending | Critical alerts |
| Teams webhook | Built | Trial pending | |
| Wazuh / SecuraIQ SIEM | Built | Trial pending | |
| CrowdStrike | Built | Trial pending | Stream + sync |
| SentinelOne | Built | Trial pending | Near-realtime poll |
| Sophos | Built | Trial pending | Near-realtime poll |
| Microsoft Defender | Built | Trial pending | Graph hunting |
| TheHive | Built | Trial pending | |
| AWS Security Hub | Built | Trial pending | |
| Azure Defender CSPM | Built | Trial pending | |
| GCP SCC | Built | Trial pending | |

## After a successful trial

1. Mark the row **Verified** with date + operator initials.
2. Update `scripts/connector_verify.py` `VALIDATION_MATRIX`.
3. Only then use “supported” language in sales/docs.

## Preferred marketing language until verified

> Integration connectors implemented; supported configurations are being validated.
