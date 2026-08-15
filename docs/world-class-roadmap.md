# SecuraIQ — What It Takes to Be World-Class

Grounded in a full inventory of the actual codebase (Aug 2026) plus a comparison against how the industry leaders (CrowdStrike Falcon, Splunk Enterprise Security, Microsoft Sentinel) structure integrations and real-time detection in 2026. No hype — every claim below is either cited to a file in this repo or to an external source.

## Current state, honestly

`app/integrations_catalog.py` carries **136 entries**: 70 shipped, 48 planned, 10 partial (key-gated), 5 commercial-only, 3 PATH-tool. That spans EDR/XDR (Sophos, CrowdStrike, SentinelOne, Defender), SIEM (Wazuh), cloud posture (AWS Security Hub, Azure Defender, GCP SCC), case management (TheHive, ServiceNow, Jira), code security (SonarQube live + 7 scanner import adapters), chat (Slack, Teams), 15 compliance frameworks, and roughly 20 threat-intel feeds split across two catalogs.

Real-time is genuinely real, not marketing: an in-process event bus (`app/realtime_bus.py`) that every write path publishes to, an SSE endpoint that wakes on publish instead of polling, a true push stream from CrowdStrike's Falcon Streaming API, a 60-second near-real-time poll for the three EDR vendors that don't offer a client-held stream, and four separate inbound webhook paths (GitHub, Wazuh, generic XDR ingest, Stripe) with real signature/secret verification — not one shared fake endpoint.

**One real gap found and fixed this pass:** Pulsedive and MalwareBazaar were fully wired, working lookups (`app/free_security_apis.py`) but invisible in the Integrations UI because they only existed in a secondary catalog file, not the main one. Added to `app/integrations_catalog.py` so they're discoverable.

## What separates "very good" from "industry-leading"

**STIX/TAXII support.** This is the actual gap, not a nice-to-have. STIX 2.1 (JSON) is the standard language threat intel moves in; TAXII is how it's exchanged between a TIP, SIEM, SOAR, and EDR. Every serious intel platform speaks it. SecuraIQ currently integrates threat intel one bespoke connector at a time (OTX, GreyNoise, URLScan, MSRC, ...) — that works, but it means every new feed is custom code. A STIX/TAXII ingest+export layer would let SecuraIQ plug into MISP, ISACs, and government feeds instantly, and would let it *feed* intel back out to other tools the same way. This is the single highest-leverage addition on the intel side. [STIX/TAXII overview — Flare](https://flare.io/learn/resources/blog/stix-threat-intelligence), [Sekoia glossary](https://www.sekoia.com/glossary/stix)

**Realtime bus is explicitly single-process.** `app/realtime_bus.py`'s own docstring says "single-process alpha only — swap for Redis pub/sub when multi-worker lands." That's an honest, correct call for where the product is now, but it's the ceiling on scale — running more than one app worker breaks the live push guarantee silently. Redis pub/sub (or NATS) is the concrete next step, and the compose profile groundwork (`redis_url` setting) already exists.

**Only one vendor has true push; the rest are a fast poll.** CrowdStrike's Falcon Streaming API is genuine push. Sophos, SentinelOne, and Defender are on a well-labeled 60-second poll (`near_realtime_poll`, honestly not disguised as a stream). SentinelOne has its own native webhook support and Defender/Sentinel can stream through Event Hub — both could get the same treatment CrowdStrike got, closing the gap to true sub-second push across all four.

**No response-action layer.** The industry's current direction — confirmed by this pass's research — is XDR, SIEM, and SOAR literally merging into one plane; CrowdStrike Next-Gen SIEM, Splunk ES, and Cortex XSIAM all ship SOAR-style automation now, not just detection. [SIEM/XDR landscape 2026 — Deepak Gupta](https://guptadeepak.com/top-5-siem-tools-of-2026-microsoft-sentinel-vs-splunk-vs-the-rest/) SecuraIQ can create incidents and fire outbound webhooks/notifications, but has no playbook engine that takes an *action* (isolate a host, block an IP, auto-close a false positive) with a human-approval gate — which would be a natural extension of the approval-gate pattern already built for destructive AI actions.

**Container/Kubernetes security is entirely unbuilt.** Falco, Kubescape, Trivy-for-K8s, kube-bench, kube-hunter, Terrascan, tfsec — all `planned`, zero live code. For any cloud-native buyer this is a checkbox they'll ask about immediately.

**SCM coverage is GitHub-only.** GitLab, Azure DevOps, and Bitbucket are all `planned`. Splunk/CrowdStrike-class competitors don't have this gap.

**SCIM exists as a scaffold** (`scim_enabled` flag, `app/scim_api.py`) — worth confirming it's actually complete end-to-end, since it's a hard requirement for most enterprise security buyers, not optional.

## What's already genuinely differentiated

Five disciplines correlated through one knowledge graph (`app/knowledge_graph.py`) instead of five point solutions in five tabs — most competitors, including the leaders above, are still fundamentally one discipline with acquired bolt-ons. Local-first architecture where the AI, vector store, and tool runs never have to leave the machine — a structural advantage for regulated/classified buyers that cloud-only SIEM/XDR/GRC SaaS can't match. Honest status labeling on every single integration (shipped/partial/planned, visible in the same catalog the UI renders from) — genuinely rare in a market where vendors routinely sell roadmap as product.

## Priority order

1. STIX/TAXII ingest+export — multiplies intel-feed coverage without writing N more bespoke connectors.
2. Redis-backed realtime bus — removes the single-process ceiling before it becomes a real customer's outage.
3. SentinelOne + Defender native push (webhook / Event Hub) — closes the "only CrowdStrike is truly real-time" gap.
4. Response-action/playbook engine with approval gates — matches where the whole category is moving.
5. Container/K8s security connectors — closes a checkbox gap for cloud-native buyers.
6. GitLab/Azure DevOps/Bitbucket webhooks — mirrors the GitHub pattern already proven out.
7. Confirm SCIM is actually complete, not just scaffolded.

None of this requires legal counsel or a live vendor tenant to *start* — items 1, 2, 4, 5, and 6 are pure engineering and can begin immediately. Item 3 needs the vendor consoles configured the same way CrowdStrike's was. Verifying all of it against real accounts remains the standing caveat on everything in this codebase.
