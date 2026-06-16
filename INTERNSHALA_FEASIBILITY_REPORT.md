# Internshala Integration — Feasibility Report

_Research only. No scraping, no submissions, no captcha/anti-bot evasion, no ToS
violation. Greenhouse/Lever/Ashby flows untouched. **Re-verified 2026-06-16**
(supersedes the 2026-06-12 draft); grounded in the live robots.txt + code checks._

## TL;DR
**Internshala has no public jobs API, no RSS/data feed, and its `robots.txt`
disallows every job search/detail/API path for all agents — and blocks AI/LLM
crawlers (GPTBot, ClaudeBot, Anthropic-AI, …) from the whole site.** Compliant
in-app discovery is therefore **impossible without a licensed/partner data feed**.
Internshala is the **highest-value India internship source** (it would be a Tier-1
provider *by data value*), but it is **currently not a viable engineering
integration** — it is blocked on a **business partnership**, not code.
**Recommendation: keep the existing gated seam, pursue a licensed feed as a
business track, and rely on JSearch as the interim India-internship engine.**

---

## 1. Verified evidence

### 1a. robots.txt — fetched 2026-06-16 (`https://internshala.com/robots.txt`)
```
User-Agent: *
Disallow: /*,*
Disallow: /*?*              # ANY URL with a query string
Disallow: /api/
Disallow: /student
Disallow: /internship/details/
Disallow: /job/details/
Disallow: /internship/search/
Disallow: /job/search/
...
# AI/LLM bots — GPTBot, OAI-SearchBot, Google-Extended, Amazonbot,
#               Anthropic-AI, Claude-Web, ClaudeBot, Claude-SearchBot,
#               PerplexityBot, Cohere, Applebot-Extended, …:
Disallow: /
Allow: /about_us
Allow: /blog/
Allow: /competitions/
# User-initiated assistant agents (ChatGPT-User, Perplexity-User, Claude-User): Allow: /
Sitemap: https://internshala.com/sitemap.xml (+ sitemap-main, sitemap-employers)
```
**Findings (verified):**
- **Every discovery surface** — `/internship/search/`, `/job/search/`,
  `/internship/details/`, `/job/details/`, `/api/`, and **any `?query` URL** — is
  `Disallow:` for `User-Agent: *`.
- **Bulk AI/LLM crawlers are blocked site-wide** (incl. ClaudeBot/Anthropic-AI),
  except `/about_us`, `/blog/`, `/competitions/`.
- The **sitemaps exist for SEO**, but the URLs they point to (search/detail) are
  themselves `Disallow:`-ed → harvesting URLs from them and fetching them would
  breach robots.txt.

### 1b. No public API / feed (verified, consistent with robots)
- `/api/`, `/api/v1` → 404 **and** `Disallow: /api/`. `/rss`, `/feed`, `/jobs.rss` → 404.
- No developer/OAuth program. The only "Internshala API" results are **third-party
  scrapers** (e.g. Apify) — non-official, inheriting the same robots/ToS breach.
- The **INRDeals "Internshala affiliate API"** generates **promo/tracking links**
  (marketing), **not** listing data. Affiliate ≠ data feed.

### 1c. ⚠️ Jobora's own robots gate FAILS OPEN here (new finding, verified)
`app/jobs/robots.can_fetch()` (uses Python `urllib.robotparser`) returns **`True`**
for `/internship/search/`, `/internship/detail/…`, and `/api/` — paths the file
clearly disallows:
```
can_fetch('https://internshala.com/internship/search/') = True   # WRONG — should be False
can_fetch('https://internshala.com/api/')               = True   # WRONG
```
Cause: `urllib.robotparser` mis-parses this wildcard-heavy file (leading
`Disallow: /*,*` / `/*?*` + multi-group AI-bot blocks) and defaults to *allow*.
**Implication:** the seam is described as "robots-gated", but the gate does **not**
actually block Internshala. This is a **defect to fix** (see Implementation Plan)
— and a reason **never to rely on the automated gate alone** for this site; the
human-read robots.txt is authoritative and it disallows scraping.

### 1d. Apply workflow (product-level, not probed)
Applying on Internshala **requires a logged-in student account**; applications are
submitted through their portal (profile/resume + per-internship questions / cover
note), protected by **session auth + anti-automation**. There is **no public apply
API**. We did **not** probe authenticated/apply endpoints (out of scope + ToS).

---

## 2 & 3. Capability matrix — what's possible, with risk

| Capability | Feasibility | Eng. effort | Maintenance | Legal/Compliance | Failure modes |
|---|:--:|---|---|---|---|
| **Discovery — scraping** | **None (forbidden)** | — | — | ⛔ robots `Disallow` for all agents + AI-bot site-wide block; ToS breach | N/A — will not do |
| **Discovery — licensed/partner feed** | **High** *(once feed exists)* | Low (~1–2 d: feed→`RawJob`) | Low–Med (schema drift, refresh) | ✅ Clean under written agreement | Feed outage; schema change; attribution terms |
| **Discovery — via JSearch (Google for Jobs)** | **High (live today)** | None (built) | Low | ✅ Lawful (Google-indexed) | Quota (200/mo); not all listings indexed |
| **Job tracking** (Jobora-side) | **High** | Low | Low | ✅ | Needs discovery to have a job to track |
| **Resume matching** | **High** | None (existing engine) | Low | ✅ | Needs job data (feed/JSearch) |
| **Application status tracking** | **Low** | High | High | ⚠️ reading status needs auth/API (none) | Only user-asserted status; no source of truth |
| **User-assisted apply (deep-link)** | **Medium** | Low | Low | ✅ a user clicking a public link is fine (robots governs *crawling*, not users) | Can't pre-fill login-gated form; user does it on Internshala |
| **Pre-fill resume/profile into their form** | **Low/None** | — | — | ⛔ requires driving an authenticated session = ToS/anti-bot breach | Forbidden |
| **Fully automated apply** | **None (forbidden)** | — | — | ⛔ login-gated + anti-bot + ToS; policy forbids | N/A |

**Net:** the only *compliant* capabilities are (a) **discovery via a licensed feed**
(doesn't exist yet) or **via JSearch** (already live), (b) **Jobora-side tracking/
matching** on lawfully-held data, and (c) a **manual deep-link hand-off**. **No
automated or assisted apply, and no scraping.**

---

## 4. Provider comparison (India internship lens)

| Provider | Data access | India internship coverage | Internship density | Apply automation | Lawful today | Status |
|---|---|:--:|:--:|---|:--:|---|
| **Internshala** | ❌ no API/feed (needs partnership) | **Very High** (dominant India intern platform) | **Very High** | ❌ login-gated | ⛔ scraping; ✅ only via licensed feed | Gated seam (inactive) |
| **JSearch** (Google for Jobs) | ✅ keyed API | **High** (indexes Internshala/LinkedIn/Indeed/company posts) | High | Track & Apply | ✅ | **Active** |
| **Adzuna** | ✅ keyed API | **Medium** | Low–Med (jobs-skewed) | Track & Apply | ✅ | Built, needs key |
| **Greenhouse** | ✅ read API | Low–Med (India offices of global cos) | Med | ✅ gated auto-submit | ✅ | Active |
| **Ashby** | ✅ read API | Low | Med | Assisted Apply | ✅ | Active |
| **Lever** | ✅ read API | Low | Med | Assisted Apply | ✅ | Active |
| **Workable** | ✅ keyed API | Low | Low–Med | Track & Apply | ✅ | Built, needs token |

**Key contrast:** Internshala has the **best India-internship data** but the **worst
data access** (none, lawfully). JSearch has **good access and good coverage** — and
critically **already surfaces many Internshala listings** because Google for Jobs
indexes Internshala internship pages. A large slice of Internshala's value is
**already reachable today via JSearch**, without any partnership.

---

## 5. Goal: should Internshala be a Tier-1 provider? + coverage estimate

**By data value: yes — it is the #1 India internship source.**
**By current feasibility: no — there is no lawful data path.** It cannot be wired as
an engineering integration today; it is a **business/partnership track**.

### Estimated India *internship* coverage (relative, qualitative — not live counts)
| Source | Est. India internship coverage | Notes |
|---|:--:|---|
| Internshala (with licensed feed) | **100% (baseline)** | Reference set — its own catalogue |
| **JSearch (live today)** | **~50–70% of that set** *(estimate)* | Google indexes a large share of Internshala + LinkedIn/Indeed internships; misses login-only/non-indexed |
| Adzuna (with key) | ~20–35% | Broader jobs, fewer pure internships; complements JSearch |
| Greenhouse/Ashby/Lever/Workable | <10% combined | US-centric ATS; few India internships |

> Estimates are directional (no live Internshala counts are obtainable without a
> feed). Actionable point: **JSearch already covers the majority of the
> India-internship value Internshala would add** — so the marginal gain from an
> Internshala feed is real but **incremental**, not foundational.

### Verdict
- **Do not** scrape or build assisted/auto apply (forbidden + non-compliant).
- **Keep** the gated seam; **fix** the robots-gate defect (§1c) so it can never
  silently scrape.
- **Treat Internshala as a partnership track** (request a licensed listings feed);
  if signed, activation is ~1–2 days (feed→`RawJob`).
- **Until then, JSearch is the India-internship engine** (active), Adzuna = cheap
  incremental breadth.

## Sources
- `https://internshala.com/robots.txt` (fetched 2026-06-16, compliance review)
- Code: `app/jobs/robots.py` (`can_fetch` defect), `app/jobs/providers/internshala.py` (seam)
- Prior endpoint checks: `/api/`, `/rss`, `/feed`, `/sitemap.xml`, `/developers`
- Companion docs: `INTERNSHALA_PROVIDER_DESIGN.md`, `INTERNSHALA_IMPLEMENTATION_PLAN.md`
