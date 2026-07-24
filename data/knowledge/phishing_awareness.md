# Phishing awareness & authorized simulations

## Goal
Reduce human-risk: teach recognition, reporting, and technical controls — not real attacks on unwilling people.

## Red flags (train users)
- Urgency / fear / prize pressure
- Display-name spoof vs real domain
- Lookalike domains (`rnicrosoft`, extra TLDs)
- Unexpected MFA / “re-authenticate” prompts
- Links to raw IPs or odd redirects
- Attachments + macros from unknown senders

## Authorized simulation program
1. Written approval + scoped employee list
2. Platform: GoPhish / commercial awareness suite
3. Banner or landing page: **This was a training simulation**
4. Metrics: click rate, **report rate**, time-to-report
5. Coaching, not public shaming

## Technical controls (blue team)
- SPF + DKIM + DMARC (`p=quarantine` → `reject`)
- Secure email gateway / URL rewrite
- MFA everywhere; number-matching / phishing-resistant MFA where possible
- Conditional access / device trust
- SOC playbook: phish reported → hunt similar subjects/URLs → block IOC

## SecuraIQ
- Mode **Awareness / Phishing**
- Tools: `phishing_url`, `email_auth` (SPF/DMARC), `suite_guide`
- Example: `Review this lure URL for awareness training: https://…`
