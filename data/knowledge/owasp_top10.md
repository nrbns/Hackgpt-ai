# OWASP Top 10 (2021) — Summary for RAG

## A01 Broken Access Control
Test horizontal/vertical privilege escalation, IDOR, forced browsing, and missing function-level access control.
Mitigation: deny by default, server-side checks, rate limiting, log access control failures.

## A02 Cryptographic Failures
Look for weak TLS, hardcoded keys, plaintext storage of passwords/PII, weak hashing (MD5/SHA1).
Mitigation: TLS 1.2+, bcrypt/argon2, envelope encryption, key rotation.

## A03 Injection
SQLi, NoSQLi, OS command injection, LDAP injection. Test with parameterized queries as the fix baseline.
Mitigation: prepared statements, input validation, least privilege DB accounts.

## A04 Insecure Design
Threat modeling gaps, missing security requirements. Review business logic flaws (coupon abuse, race conditions).

## A05 Security Misconfiguration
Default creds, verbose errors, open cloud storage, unnecessary features enabled.
Mitigation: hardened baselines, automated config scanning, minimal attack surface.

## A06 Vulnerable Components
Outdated libraries with known CVEs. Use dependency scanners (npm audit, pip-audit, OWASP Dependency-Check).

## A07 Identification and Authentication Failures
Weak passwords, no MFA, session fixation, credential stuffing.
Mitigation: MFA, secure session management, breach-resistant password policies.

## A08 Software and Data Integrity Failures
Unsigned updates, insecure CI/CD, deserialization attacks.
Mitigation: code signing, SBOM, integrity checks on pipelines.

## A09 Security Logging and Monitoring Failures
Missing audit logs, no alerting on brute force or privilege changes.
Mitigation: centralized logging, SIEM rules, incident response playbooks.

## A10 Server-Side Request Forgery (SSRF)
Abuse server to fetch internal URLs, metadata endpoints (169.254.169.254).
Mitigation: allowlists, network segmentation, disable unnecessary URL fetchers.
