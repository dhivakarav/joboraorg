# Internshala — Lawful Data Acquisition Options

_Researched 2026-06-16. Compliant research only (robots-allowed fetches + prior
verified findings). **Specifics I could not verify are labelled `[ESTIMATE]` or
`[UNVERIFIED]` — do not treat them as confirmed.** No scraping. Goal: the fastest
legitimate path to activate the already-built, gated Internshala provider._

## Bottom line
**There is no self-serve or publicly-documented data-acquisition program** (no public
API, no feed, no `/partners` page, affiliate ≠ data). Every lawful path to *listings
data* runs through a **direct, negotiated business agreement** with Internshala.
**Fastest legitimate path = direct BD outreach via the employer/contact channel for a
licensed listings feed.** Meanwhile, **JSearch already surfaces some Internshala
listings via Google for Jobs at zero partnership cost** (but low Internshala
attribution — see Coverage Report).

## Evidence grounding (verified this session)
- `robots.txt`: `/api/`, `/internship/search/`, `/job/search/`, details, and `/*?*`
  all `Disallow:` for `User-Agent: *`; AI bots blocked site-wide. → no scraping.
- Page status (HEAD): `/hire-talent/` 200, `/contact` 200, **`/partners` 404**,
  `/developers` 200 (a *careers* page, not an API portal), `sitemap-employers.xml`
  exists (SEO only; points to disallowed pages).
- Prior verified: no `/api`, `/rss`, `/feed`; INRDeals "affiliate API" = promo links;
  Internshala Student Partner (ISP) = campus ambassador program.

---

## Path-by-path assessment

### 1. Partner / Syndication API — ❌ none public
| | |
|---|---|
| Exists? | **No public program** (`/partners` → 404; no developer docs). |
| Contact | Direct BD outreach: **`/contact` form** + **`/hire-talent/`** enquiry; LinkedIn outreach to Internshala/Scaler BD/partnerships staff. `[ESTIMATE]` a `partnerships@`/`business@` alias may exist — confirm via the contact form. |
| Approval | Business agreement; expect NDA + data-use/attribution terms. `[ESTIMATE]` |
| Cost | **Negotiated, likely paid.** `[UNVERIFIED]` — no public pricing. |
| Coverage | **Highest** — could be the full Internshala catalogue if the deal scopes listings data. |
| Time to integrate | **Code: ~1–2 days** once a feed spec exists. **Deal: weeks–months `[ESTIMATE]`.** |

### 2. Recruiter / Employer API — ⚠️ wrong direction
| | |
|---|---|
| Exists? | Internshala has an **employer/"Hire Talent"** product (`/hire-talent/` 200) for *posting* internships + managing applicants. |
| Why not a data path | An employer API serves an employer's **own** postings/applicants — it does **not** expose **cross-company listings** for an aggregator. `[ESTIMATE — standard for ATS/job-board employer APIs]` |
| Contact | `/hire-talent/` sales enquiry. |
| Approval | Employer account. | 
| Cost | Employer pricing (irrelevant — not a listings source). |
| Coverage | **N/A for discovery** (only your own posts). |
| Time to integrate | N/A — not usable for Jobora discovery. |

### 3. Campus / College API — ⚠️ conditional, narrow
| | |
|---|---|
| Programs | **ISP** (Internshala Student Partner) = campus *ambassador* (marketing), **not data**. Internshala also runs **college/placement-cell** offerings `[UNVERIFIED scope]`. |
| Possible data angle | A **college placement partnership** *might* share listings/opportunities **for that college's students** — narrow, institution-scoped, not a general feed. `[ESTIMATE]` |
| Contact | College/placement partnerships via `/contact` or their training/placement team. |
| Approval | Institutional agreement (Jobora would need a college relationship). |
| Cost | `[UNVERIFIED]`. |
| Coverage | **Low/narrow** (one institution's scope), not catalogue-wide. |
| Time to integrate | Code ~1–2 d if it yields a JSON feed; deal effort high relative to coverage. |

### 4. Affiliate program — ❌ not a data path
| | |
|---|---|
| Exists? | **Yes — via INRDeals** (and similar): generates **promo/tracking links** to *drive signups*. |
| Why not | It licenses **marketing links, not listings data.** Repurposing it as a data source is neither its purpose nor permitted. |
| Contact | INRDeals campaign page. |
| Cost | Free to join (you *earn* commission). |
| Coverage | **None (no listing data).** |
| Time to integrate | N/A for discovery. |

### 5. XML / JSON feeds (RSS, jobs feed) — ❌ none public
| | |
|---|---|
| Exists? | **No** — `/rss`, `/feed` → 404; `/api/` disallowed. Sitemaps exist (SEO) but enumerate `Disallow:`-ed pages, so harvesting them breaches robots. |
| Contact | Only via a negotiated feed (Path 1). |
| Cost / Coverage / Time | Same as Path 1 (a feed only exists if licensed). |

### 6. ATS integration — ❌ not applicable
| | |
|---|---|
| Reality | Internshala **is** the job board/ATS-like platform; it is **not** a company *using* Greenhouse/Lever/Ashby whose board Jobora could read. Standard ATS connectors don't include Internshala. |
| Data path | None via ATS. |

### 7. Official syndication program — ❌ none documented
| | |
|---|---|
| Exists? | **No public syndication/distribution program** (`/partners` 404). |
| Note | Internshala **already syndicates to Google for Jobs** (which is why **JSearch surfaces some Internshala listings today**) — but that is Google's index, not a feed Jobora can license from Internshala directly. |
| Contact / Cost / Time | A direct feed = Path 1 (negotiated). |

---

## Ranked by "fastest legitimate path to activate the provider"

| Rank | Path | Lawful | Coverage | Effort to activate | Verdict |
|---|---|:--:|:--:|---|---|
| **1** | **JSearch (Google for Jobs), already live** | ✅ | Internshala-attributable **Low**; India-internship **High** | **0 — already shipped** | **Use now.** Zero partnership; surfaces some Internshala + lots of other India internships. |
| **2** | **Direct BD → licensed listings feed** (Path 1) | ✅ | **Highest (distinct)** | Code ~1–2 d **after** a signed feed; deal = weeks–months `[ESTIMATE]` | **Pursue in parallel.** The only path to full, attributed Internshala data. |
| 3 | College/placement partnership (Path 3) | ✅ | Low/narrow | Code ~1–2 d if JSON; deal effort high | Only if a college relationship already exists. |
| — | Recruiter/Employer API, Affiliate, ATS, public feed | n/a | None (not listings data) | — | **Not data-acquisition paths.** |

## Recommendation (fastest legitimate activation)
1. **Now (0 effort):** rely on **JSearch** — it's live and lawfully surfaces a slice of
   Internshala plus broad India internships. The provider's analytics already count
   Internshala-hosted listings arriving this way.
2. **Parallel business track:** send a **partnerships enquiry via `/contact` +
   `/hire-talent/`** (and LinkedIn BD outreach) requesting a **licensed JSON listings
   feed** — scope: fields, refresh cadence, attribution, allowed use, rate limits,
   takedown. **Confirm the real partnerships contact** (don't assume an email).
3. **On signature:** set `INTERNSHALA_FEED_URL` (+ `INTERNSHALA_FEED_TRUSTED=1`) — the
   **already-built, tested provider activates immediately** (~1–2 d to validate/map),
   tiers India-first, dedupes vs JSearch, and emits coverage analytics.

> **Honesty note:** I could not verify exact contacts, pricing, or whether any
> private partner/syndication program exists — those require direct confirmation with
> Internshala. Everything labelled `[ESTIMATE]`/`[UNVERIFIED]` should be validated in
> outreach. What **is** verified: no public API/feed/affiliate-data path, and that
> JSearch is the only live, lawful source of any Internshala listings today.

_Companions: `INTERNSHALA_FEASIBILITY_REPORT.md`, `INTERNSHALA_PROVIDER.md`,
`INTERNSHALA_COVERAGE_REPORT.md`._
