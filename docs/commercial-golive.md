# SecuraIQ — Commercial go-live checklist

Billing **code** exists (`app/billing*.py`). Live payments need this end-to-end path.

## Stripe path

```text
Stripe account
 → Products + Prices (Pro / Business)
 → Checkout Session
 → Webhook (invoice.paid / customer.subscription.*)
 → Subscription row
 → Entitlements
 → Usage metering limits
 → Invoice / customer portal
```

### Env

```env
BILLING_ENFORCEMENT_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...   # use sk_test_ first
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_TEAM=price_...
```

### Verify before charging money

- [ ] Test-mode checkout completes
- [ ] Webhook updates org plan
- [ ] Feature gate blocks over-limit assets/users when enforcement on
- [ ] Cancel / downgrade restores free entitlements
- [ ] Live mode keys only after counsel + Terms/Privacy signed off

## Partner onboarding (minimal)

1. Create org + invite admin  
2. Enforce MFA  
3. Set engagement `scope_json` before tools  
4. Point them at Mission Control → Investigate → Findings → Report  

## Public support layer (still open)

- [ ] Invitations UX  
- [ ] Support channel  
- [ ] Status page  
- [ ] Changelog  
- [ ] Public docs site  

Do **not** block closed beta on these; block **public paid** launch until Stripe + counsel are done.
