# Job Sources — Capability Matrix

Generated from the live code (`app/jobs/providers` + `app/adapters`). "Discovery"
reflects the current runtime status; "Apply / Auto Apply / API Access" are static
capabilities.

| Source              | Discovery        | Apply          | Auto Apply               | API Access |
|---------------------|------------------|----------------|--------------------------|------------|
| Remotive            | Connected        | Yes (generic)  | No                       | Yes        |
| Arbeitnow           | Connected        | Yes (generic)  | No                       | Yes        |
| Greenhouse          | Connected        | Yes            | Yes (live, JOBORA_LIVE)  | Yes        |
| Lever               | Connected        | Yes            | No (assisted)            | Yes        |
| Ashby               | Connected        | Yes            | No (assisted)            | Yes        |
| Workable            | Disabled (no key)| Yes            | No (assisted)            | Yes        |
| Adzuna              | Disabled (no key)| Yes (generic)  | No                       | Yes        |
| Jooble              | Disabled (no key)| Yes (generic)  | No                       | Yes        |
| JSearch             | Connected¹       | Yes (generic)  | No                       | Yes        |
| Internshala         | **Mock Mode²**   | Yes            | Yes (credential, opt-in) | **No**     |
| Wellfound           | Disabled (no key)| Yes            | No (assisted)            | No         |
| Workday             | — (apply only)   | Yes            | No (manual)              | n/a        |
| LinkedIn            | — (apply only)   | Yes            | No (manual)              | n/a        |
| Company Career Page | — (apply only)   | Yes (generic)  | No (manual)              | n/a        |

## Legend

- **Discovery** — can Jobora *fetch listings* from this source.
  - `Connected` — live and returning jobs.
  - `Disabled (no key)` — provider exists but needs an API key/token (set the env var to enable).
  - `Mock Mode` / `Authorized Feed Available` / `Disabled` — Internshala's four-state lifecycle (see below).
  - `— (apply only)` — not a discovery provider; only an apply adapter (jobs arrive via other sources/links).
- **Apply** — can a user apply through Jobora.
  - `Yes` — a dedicated platform adapter (prefill / form handling).
  - `Yes (generic)` — "Track & Apply": Jobora opens the real application page and records it; no platform form integration.
- **Auto Apply** — can Jobora *submit* the application (not just open it).
  - `Yes (live, JOBORA_LIVE)` — real browser submission when `JOBORA_LIVE=1` (Greenhouse).
  - `Yes (credential, opt-in)` — real submission under the user's own stored credentials, gated by `JOBORA_LIVE=1` + an **authorized feed** + explicit per-application approval (Internshala).
  - `No (assisted)` — captcha-gated: Jobora prefills, the user finishes + submits on the portal (Lever/Ashby/Workable/Wellfound).
  - `No (manual)` — automation not possible/permitted; manual apply (Workday/LinkedIn/career pages).
- **API Access** — is the source an official, documented API (`official_api`)? `No` means it has no public API (discovery requires a licensed/partner feed).

## Notes

1. **JSearch** shows `Connected` only because the dev `.env` points `JSEARCH_HOST` at the
   local mock (`localhost:8001`) with a test key. In production it needs a real RapidAPI key.
2. **Internshala** is the focus of this change. It has **no public API** and its
   `robots.txt` disallows the discovery/detail/login paths (and explicitly blocks
   Anthropic/Claude agents site-wide). Its discovery status is one of:

   | Status | Meaning | Search | Auto-Apply |
   |--------|---------|--------|-----------|
   | `Disabled` | No `INTERNSHALA_FEED_URL` set | off | off |
   | `Mock Mode` | Feed points at a local/mock host (sample data) | **excluded from results** | **403 (gated)** |
   | `Authorized Feed Available` | A real licensed feed configured, not yet fetched | on | on (once live) |
   | `Connected` | Authorized feed configured and returning records | on | on |

   `authorized()` is `True` only for a genuine, non-mock feed with
   `INTERNSHALA_FEED_AUTHORIZED=1`. Until then, Internshala results are excluded from
   search and Auto-Apply returns HTTP 403 — sample data never masquerades as real.

## Related fix

`app/jobs/robots.py` was rewritten: the stdlib `urllib.robotparser` **failed open** on
Internshala's wildcard-led robots.txt (it returned `allowed=True` for explicitly
disallowed paths). The new wildcard-aware matcher honors `*`/`$`, longest-match-wins,
and **fails closed** on any fetch/parse error.
