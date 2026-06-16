# Jobara — Go-Live Plan (Product Launch)

Focus: **customer acquisition + retention**, not new engineering. Scope is honest
to what Jobara does today: AI job discovery + match scoring + application
tracking + INR salary intelligence + **Greenhouse auto-apply (with Manual Apply
Required fallback everywhere else)**. India-first (INR, Razorpay).

Guiding rule: every launch decision optimizes for **activation → first applied
job → weekly retention → conversion**. Don't promise auto-apply we can't deliver
— "Manual Apply" honesty is a trust asset, not a weakness.

---

## 1. Landing page optimization
**Goal:** visitor → signup. Single conversion action: "Upload your resume — find
matching jobs free."

- **Hero:** outcome promise + honesty. *"Find jobs that match your resume and
  apply faster. Auto-apply on supported boards; one-click assisted apply
  everywhere else."* Primary CTA: **Get started free**.
- **Proof of value above the fold:** screenshot of the match-scored job list with
  ₹ salaries + the Verified-Submitted evidence card (trust).
- **3 benefit blocks:** (1) Resume → matched jobs in seconds, (2) Salaries in INR
  (auto-converted), (3) Track every application + proof of submission.
- **"How it works" (3 steps):** Upload resume → Review matches → Apply & track.
- **Trust row:** "Your resume is encrypted. We only submit applications you
  approve. We never post fake applications." (all true today)
- **FAQ:** Which sites? (Greenhouse auto; others assisted/manual.) Is it safe?
  Do you apply without me? (No — explicit approval.) Pricing?
- **SEO/landing variants:** role/location landing pages ("AI job apply for
  software engineers in Bangalore") feeding the India market.
- **Instrumentation:** event on CTA click, signup start, signup complete (see §7).
- **Targets:** LP→signup ≥ 8–12%; measure per traffic source.

## 2. User onboarding (activation)
**Activation = uploaded resume + saw ≥1 matched job + applied/saved 1.** Drive to
this in the first session.

- **Post-signup wizard (3 steps):** (1) Upload resume (auto-parses profile), (2)
  confirm role + location + INR salary floor, (3) show top matches immediately.
- **Aha moment:** matched jobs with scores + ₹ salaries on screen within 60s of
  signup. Don't gate this behind admin approval friction for discovery — keep
  approval only for actions that need it.
- **Empty states → next action** (already partly built): no resume → "Upload to
  see matches"; no matches → broaden role.
- **First-apply nudge:** highlight one high-match Greenhouse job with "Apply"
  (review screen) to create the first tracked application.
- **Onboarding email series** (uses existing notifications): welcome → "here are
  your matches" → "complete your profile" → "you have N jobs waiting."
- **Targets:** signup→resume-uploaded ≥ 70%; signup→first-apply ≥ 35% in 48h.

## 3. Pricing strategy (freemium, INR)
Anchor on time saved + proof of submission. Keep Free genuinely useful (drives
acquisition); gate volume + automation + AI.

| Plan | Price (INR) | Includes |
|---|---|---|
| **Free** | ₹0 | Resume parsing, job discovery + match scores, INR salaries, application tracking, **manual/assisted apply**, up to **5 applies/day** |
| **Pro** | **₹499/mo** (or ₹3,999/yr) | Everything in Free + **Greenhouse auto-apply**, higher daily limit (e.g. 30/day), submission evidence, priority job refresh, email job alerts |
| **Pro+AI** | **₹899/mo** | Pro + AI resume/ATS analysis, AI cover letters, AI career coach (when the AI layer is enabled) |
| **Credits** | ₹149 / 5 | One-off: resume reviews / AI cover letters (for Free users) |

- Launch with **Free + Pro** only; add Pro+AI when the AI layer is enabled.
- **Beta offer:** first 100 users get Pro free for 60 days (founding-user pricing
  lock at ₹299/mo afterward).
- Annual discount ~33% to pull cash + improve retention.
- Trial: 7-day Pro trial on signup (card not required → reduce friction; convert
  via value, not lock-in).

## 4. Razorpay integration (plan — not yet built)
Razorpay fits India/INR. **Requires** a Razorpay account + KYC + API keys; do not
ship test keys to prod.

**Architecture (subscriptions):**
1. Create **Plans** in Razorpay dashboard (Pro monthly/annual, Pro+AI).
2. Backend: `POST /api/billing/subscribe` → create a Razorpay **Subscription**,
   return `subscription_id` + key to the frontend.
3. Frontend: **Razorpay Checkout** widget completes payment/mandate.
4. Backend **webhook** (`/api/billing/webhook`): **verify the
   `X-Razorpay-Signature` HMAC** (never trust client), then update the user's
   `plan` + `plan_status` + `current_period_end`.
5. Gate features on `plan` (e.g., auto-apply daily limit, AI features).
6. Handle `subscription.charged`, `subscription.cancelled`,
   `subscription.halted`; dunning emails on failed charges.

**New (small) backend work when you greenlight billing:** a `subscriptions`
table/columns (`plan`, `status`, `razorpay_subscription_id`, `period_end`),
the two endpoints, webhook signature verification, and feature-gating in the
apply/AI paths. Store `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` /
`RAZORPAY_WEBHOOK_SECRET` as env secrets (the B0 config pattern). **Compliance:**
show pricing, refund/cancellation policy, and GST handling; Razorpay needs a
public pricing + refund page live.

## 5. Privacy Policy
Draft provided: `legal/PRIVACY_POLICY.md`. **Must be reviewed by a lawyer** — this
is non-negotiable given Jobara processes **resumes (sensitive PII)** and
**submits applications on users' behalf**. Key clauses: what we collect (resume,
profile, application history), encryption at rest, third-party sharing (job
platforms we submit to, payment processor, email), retention + **delete-my-data**,
India **DPDP Act 2023** alignment, and that submissions are user-authorized.

## 6. Terms of Service
Draft provided: `legal/TERMS_OF_SERVICE.md`. **Lawyer review required.** Key
clauses: user authorizes Jobara to submit **their own genuine applications**;
user warrants information is truthful; we do not guarantee interviews/offers; we
respect target platforms' terms and fall back to manual where automation isn't
permitted; acceptable use (no spam/fake applications); liability limits;
subscription/refund terms; governing law (India).

## 7. Analytics
Instrument the **activation + retention funnel**, not vanity metrics.

- **Tool:** PostHog (self-host or cloud — generous free tier, product analytics +
  funnels + session replay) or Plausible (privacy-friendly web) + PostHog for
  product. Recommend **PostHog**.
- **Core events:** `signup_started/completed`, `resume_uploaded`,
  `jobs_viewed`, `job_apply_clicked`, `application_submitted`,
  `submission_verified`, `manual_apply_opened`, `subscription_started`,
  `subscription_paid`, `churned`.
- **Funnels:** LP→signup→resume→first-apply→repeat-apply→paid.
- **Server-side** events for submission outcomes (truth source is the backend),
  client-side for UI funnel.
- Respect consent (cookie banner) per the privacy policy.

## 8. Email notifications (mostly built — extend for lifecycle)
The notification provider exists (SMTP↔console, B0). Add **lifecycle + retention**
emails (use a real ESP: Resend/SendGrid/SES via the existing SMTP/provider hook):

- **Transactional (have/extend):** verify email, account approved, application
  submitted/verified, password reset.
- **Lifecycle (add):** welcome + onboarding series, "N new matches this week"
  (weekly digest — strong retention driver), "your application moved to
  Interview", trial-ending, payment-failed dunning, win-back for churned.
- Deliverability: SPF/DKIM/DMARC on the sending domain; `EXPOSE_RESET_TOKEN=0`.

## 9. Customer support flow
Lean but responsive (founder-led support is fine for the first 100).

- **Channels:** in-app "Help" → email (`support@`), a help widget (Crisp/Intercom
  free tier), and a public FAQ/help center.
- **Tiers:** self-serve FAQ → email (24h SLA in beta) → founder escalation.
- **Top expected tickets + canned answers:** "did it actually apply?" (point to
  the Evidence view), "why Manual Apply?", "resume parsed wrong" (editable
  fields), "billing/cancel", "delete my data".
- **Status/incident:** a simple status page; surface `/api/ready` health.

## 10. Beta user feedback collection
- **In-app:** a one-click feedback button + a 1-question micro-survey after first
  apply ("Did this save you time? 👍/👎 + optional note").
- **NPS** at day 14.
- **5–8 user interviews** in the first two weeks (founder calls) — highest signal.
- **Public changelog** + a "request a platform" vote (Lever/Ashby/Workable/
  Internshala demand signal informs the roadmap).
- Route all feedback to one board (Linear/Notion) tagged acquisition vs retention.

---

# Generated artifacts

## A) Public Beta Checklist
**Legal/compliance**
- [ ] Privacy Policy + ToS reviewed by a lawyer and published (`/privacy`, `/terms`)
- [ ] Cookie/consent banner wired to analytics
- [ ] Delete-my-data + data-export path working (DPDP)
- [ ] Refund/cancellation + pricing page public (Razorpay requirement)

**Product/infra (gates from B0–B2)**
- [ ] Managed Postgres + Redis + S3 provisioned; secrets set (fail-closed config enforces)
- [ ] Separate RQ worker running (`JOBORA_LIVE=1`, browsers installed)
- [ ] `REQUIRE_EMAIL_VERIFICATION=1`, `EXPOSE_RESET_TOKEN=0`, `SENTRY_DSN` set
- [ ] **Greenhouse auto-apply validated on ≥5 real postings** (else keep auto-apply off, ship Manual Apply)
- [ ] One real-stack load test (≥100 users / ~10 concurrent applies)
- [ ] Backups on + a restore drill done
- [ ] CI green; staging environment live

**Acquisition/retention**
- [ ] Landing page live with analytics events
- [ ] Onboarding wizard + first-apply nudge
- [ ] Onboarding + weekly-digest emails scheduled
- [ ] Support email + FAQ + feedback widget live
- [ ] Metrics dashboard (below) populated

## B) First 100 users strategy
Channel order (cheapest, highest-intent first):
1. **Founder network + warm DMs** — 20–30 users; direct onboarding + interviews.
2. **India job-seeker communities** — relevant subreddits (r/developersIndia,
   r/jobs), Telegram/WhatsApp job groups, college placement groups, LinkedIn.
   Lead with the honest hook ("auto-apply on Greenhouse + assisted everywhere,
   salaries in ₹"). Give the **founding-user free Pro 60 days** offer.
3. **Content + SEO** — 5 launch posts: "How I applied to 50 jobs in a week
   (honestly)", role/city landing pages, a salary-in-INR explainer. Targets
   long-tail intent.
4. **Product Hunt / r/SideProject / Showwcase** launch once onboarding is smooth.
5. **Micro-influencers** — 2–3 India career/tech creators for walkthroughs.
- **Loop:** every activated user prompted to share + a referral ("give a friend
  Pro for a month, get one").
- **Target:** 100 signups in 3–4 weeks; ≥40 activated (resume + first apply);
  10–15 weekly-active by week 4.

## C) First paying customer strategy
- **Convert from value, in-product:** when a Free user hits the 5/day apply cap
  or clicks Greenhouse "Auto-Apply", show an upgrade modal ("Auto-apply + 30/day
  for ₹499/mo — founding price ₹299").
- **Trigger paywall at proven value moments:** after a Verified-Submitted, after
  3 applies in a day, on the weekly-digest ("12 new matches — upgrade to
  auto-apply").
- **Founder-led close for the first 10:** personally reach out to the most
  active beta users with the founding offer; ask for the sale.
- **Reduce risk:** 7-day Pro trial, transparent cancel-anytime, refund policy.
- **Target:** first paying customer within 2 weeks of enabling billing; 5–10
  paid in the first month; aim Free→Pro ≥ 3–5%.

## D) Metrics dashboard
Track weekly; **North-Star = Weekly Applied Users** (users who submitted ≥1
application in the week — captures real value delivered).

**Acquisition**
- Signups (by source), LP→signup %, CAC (if paid).

**Activation**
- Signup→resume-uploaded %, signup→first-apply % (48h), time-to-first-match.

**Engagement / Retention (priority)**
- **North Star: Weekly Applied Users**
- WAU/MAU, week-1 / week-4 retention curves, applies per active user/week,
  Verified-Submitted rate, Manual-vs-Auto apply mix.

**Monetization**
- Trial starts, Free→Pro conversion %, MRR, ARPU, churn %, LTV.

**Reliability/trust (from existing telemetry)**
- Submission success rate, CAPTCHA/manual fallback rate, p95 API latency,
  error rate (Sentry), queue depth.

**Build it as:** PostHog dashboards (funnel + retention) + a small internal
"ops" view backed by the `applications` table (submission outcomes) and
`/api/ready`. Don't build a bespoke analytics product — wire events to PostHog.

---

## Sequencing (acquisition/retention first)
```
Week 0: legal review + publish, analytics events, onboarding wizard, support+FAQ,
        provision prod infra + worker, real-posting Greenhouse validation
Week 1: soft launch to founder network (20–30), interviews, fix activation leaks
Week 2: enable Razorpay billing + paywall triggers; community launch
Week 3–4: content/SEO + Product Hunt; push to 100 signups; first paying customers
```
Engineering is **frozen to launch-blockers only** (billing + the validation gate);
everything else is acquisition, retention, and content.
