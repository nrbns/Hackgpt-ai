# Testing SecuraIQ against a lab VM

This is the real test — not code review, actual tool runs against a target you own.
I traced through `app/net_assess.py` to get the authorization rules exactly right below,
so you don't hit a false "blocked" response mid-test.

## 1. Set up the VM (host-only or NAT network only — never bridged to your real LAN for a deliberately-vulnerable box)

Pick a hypervisor you already have — VirtualBox and VMware Workstation/Player both work identically here.

**Target VM — pick one or more:**
- **Metasploitable2** — the classic intentionally-vulnerable Linux box (unpatched services, weak creds, known CVEs on FTP/SMB/RMI/etc.). Best for exercising the recon + `hardening_baseline` tool against real exposed risky ports.
- **OWASP Juice Shop** (Docker: `docker run -p 3000:3000 bkimminich/juice-shop`) — modern intentionally-vulnerable web app, good for the `http`/`headers_security`/`tls`/DAST-style tools.
- **DVWA** (Damn Vulnerable Web App) — classic web vuln targets (SQLi, XSS) if you want to test `sqlmap`/`nikto`/`zap` (only if those binaries are installed on the SecuraIQ host — they're external tools, not builtins).

**Network setup:** put the VM on VirtualBox's "Host-only Adapter" or VMware's "NAT"/"Host-only" network — this gives it a private IP (typically `192.168.56.x` for VirtualBox host-only, or `10.0.2.x`/`192.168.x.x` for NAT). That matters because of the next section.

## 2. Why you won't need to touch "Authorized target" for this

I checked `resolve_and_authorize()` in `app/net_assess.py` directly: any target that resolves to a private/RFC1918, loopback, or link-local IP is **auto-authorized** — no checkbox, no extra config. That covers every VM lab network by default. The "Authorized target" checkbox in the UI only matters if you point SecuraIQ at a **public IP you own** (e.g. a cloud VM with a real internet-facing address) — for that case you'd check it to confirm ownership, since public IPs are blocked by default.

So: get the VM's IP (`ip a` on Linux, `ipconfig` on Windows), drop it into the **Target IP** field in the composer, and go — no other setup.

## 3. What to actually run — a test checklist, not just "does it load"

Work through these in the Tools Palette (bell/wrench icon in the composer) or by asking directly ("run nmap and headers_security against 192.168.56.101"):

1. **`ports`** — confirms the port probe finds the actual open services on the VM (compare against what you know Metasploitable2/Juice Shop exposes).
2. **`http` / `headers_security` / `tls`** — confirms these return real header/cert data, not empty results.
3. **`hardening_baseline`** (new this session) — this is the one I most want real-world verification on, since I built it without being able to run it. Point it at Metasploitable2 specifically — it exposes several of the risky ports in `_RISKY_PORTS` (21 FTP, 23 Telnet, 139/445 SMB) — confirm the scored output actually flags them and the score/grade math looks sane, not just that it doesn't crash.
4. **`nmap`/`nikto`/`nuclei`** (if installed on the SecuraIQ host) — confirms external-tool detection and subprocess execution work, not just the builtins.
5. **Guardrail check** — try pointing a tool at a public IP you *don't* own (e.g. `8.8.8.8`) without checking "Authorized target." It should refuse with the public-IP error from `resolve_and_authorize`. This is the safety mechanism working as intended — confirm it actually blocks rather than silently scanning.
6. **Vulnerability import** — export a real scan (e.g. an Nmap XML or a Trivy/Grype JSON if you have a container to scan) and import it via the Vulnerabilities workspace. Confirms the import adapters parse real tool output, not just hand-crafted test JSON.
7. **Incident + notification loop** — from a critical finding, confirm a notification actually appears in the bell icon, and if you've set `SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL`, confirm the alert actually lands in the channel.
8. **Gap analysis / frameworks** — run a gap assessment against ISO 27001 or CIS and sanity-check the output makes sense given the VM's actual (lack of) hardening.
9. **Report export** — generate the executive PDF/DOCX and confirm it actually reflects the real findings from steps above, not placeholder data.

## 4. What this does *not* cover (be aware before you call it "done")

- **XDR/EDR connectors** (Sophos/CrowdStrike/SentinelOne/Defender) — these need real vendor tenant credentials to test at all; a lab VM alone won't exercise them. If you have a trial account for any of these, that's the next thing to validate — I have not been able to test any of the four against a live tenant.
- **Heavy/aggressive tools** (`sqlmap`, `ffuf`, `gobuster`, `masscan`) are opt-in (`include_heavy`) by design — don't run these against anything except a VM you fully control, and expect them to be noisy/slow.
- This guide validates *this session's* new work (`hardening_baseline`) and the pre-existing tool pipeline together — it's not a substitute for `scripts/smoke_test.py` / `scripts/check_openapi_gets.py` against a live server.

## 5. What "strong tool" should mean when you're done

Not "did it run without crashing" — check for:
- **Accuracy**: do the reported open ports/headers/TLS details match what you independently know is running on the VM (cross-check with `nmap -sV` run manually, or the VM's own service list)?
- **Correct refusals**: does it actually block the public-IP-without-authorization case, and does the "authorized lab only" framing in guardrails hold up if you ask it for something crimeware-flavored?
- **Honest findings**: does `hardening_baseline`'s score reflect reality — a deliberately unpatched box like Metasploitable2 should score badly, not get a misleadingly high grade.

Report back what breaks. That's more useful to me than "it worked" — I built the newest pieces (XDR connectors, hardening tool) without being able to execute them at all this session, so real findings against a real target are the highest-value thing you can hand back.
