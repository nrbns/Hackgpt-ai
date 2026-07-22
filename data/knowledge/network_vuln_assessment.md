# Network vulnerability assessment (authorized / lab)

Use HackGPT **Vuln Assessment** mode with a **Target IP** on networks you own or have written permission to test (home lab, HTB/THM VPN, VulnHub, company engagement scope).

## Supported targets
- Private ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Loopback / link-local
- Public IP only if you check **I own / authorized this target**

## What HackGPT probes
1. Common TCP ports (FTP/SSH/HTTP/SMB/RDP/DB/…)
2. Light banners + HTTP/TLS fingerprints
3. Optional `nmap` top-ports if installed on the host running HackGPT

## Suggested workflow
1. Put the host IP in **Target IP** (e.g. `192.168.56.101` or HTB `10.10.10.x`)
2. Enable **Probe target** (+ authorized checkbox for owned public hosts)
3. Ask: “Assess this host, map open services to likely CVEs, give verify commands and fixes”
4. Follow up with service-specific deep dives (smb, web, etc.)

## Manual follow-ups (lab)
```bash
nmap -sC -sV -oA nmap/initial <ip>
nmap -p- --min-rate 2000 -oA nmap/allports <ip>
nuclei -u http://<ip> -severity critical,high
```

## Detection / remediation
Always document: what an IDS would see, patch priority, and network segmentation for exposed services.
