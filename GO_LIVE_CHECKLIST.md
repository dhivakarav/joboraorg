# Jobora — Go-Live Checklist

Ordered, blocking items first. ☑ done · ☐ todo.

## 0. Integrity invariants (must stay true) — ☑ holding
- ☑ No fake jobs / companies / example.com / demo simulators (deleted).
- ☑ No fabricated applications or evidence.
- ☑ No hardcoded "Applied"; Verified Submitted requires id + confirmation + screenshot.
- ☑ Discovery from real providers only.

## 1. Infrastructure (BLOCKING)
- ☐ Provision managed **Postgres** (set `DATABASE_URL`); run `alembic upgrade head`
  (migrations incl. `a1b2c3d4e5f6`, `b2c3d4e5f6a7`).
- ☐ Provision **Redis** (`REDIS_URL`) for shared rate limiting + job cache + queue.
- ☐ Provision **object storage / S3** for submission evidence (set storage env).
- ☐ Set real **`JWT_SECRET`** + **`CREDENTIAL_KEY`** (app refuses to start in prod
  without them — verified).
- ☐ Run the submission worker as a **separate process** (RQ) in prod.

## 2. Payments (BLOCKING for paid)
- ☐ Add **Razorpay LIVE keys** (`RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`).
- ☐ Enable `/api/billing/checkout` + `/webhook` (signature-verified) → activate Pro.
- ☐ Test the upgrade → webhook → plan flip end-to-end with a real (small) charge.

## 3. Apply loop (BLOCKING for the core promise)
- ☐ Build the **Assisted-Apply front-end wizard** (prefill → review → record
  evidence) for Lever + Ashby (endpoints ready).
- ☐ Decide & gate **live Greenhouse submission** (`JOBORA_LIVE=1`) behind explicit
  per-application approval + truthful screening answers.
- ☐ First **real validated submission** (confirmation + id + screenshot) by a real
  user.

## 4. Trust, safety, ops
- ☐ Set **Sentry DSN**; verify error capture.
- ☐ Privacy Policy + ToS reviewed & linked; data-deletion path.
- ☐ Support channel (email/Intercom) + feedback capture.
- ☐ Backups for Postgres + evidence store.
- ☐ **Load test for 100 concurrent users** (search + apply paths).

## 5. Product polish
- ☑ Eligibility-first matching + reasons.
- ☑ Honest status everywhere (Dashboard / Activity / Job Cards / Evidence).
- ☐ Upgrade/pricing screen wired to `/api/billing/*`.
- ☐ Onboarding nudges premium-matching value.

## Launch gates
- **Free closed beta:** complete §0, §1, §4 → ship.
- **Paid public launch:** also complete §2, §3.
