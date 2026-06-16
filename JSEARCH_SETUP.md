# JSearch Setup & Verification

How to enable the JSearch (Google-for-Jobs) provider in Jobora. Verification only —
no deploy, no pipeline changes.

## 1. Exact RapidAPI subscription required
- Provider: **JSearch** by **OpenWeb Ninja** (publisher id `letscrape-6bRBa3QguO5`)
  on the RapidAPI marketplace.
- API host: **`jsearch.p.rapidapi.com`**.
- Plan: **Basic (Free)** — sufficient for verification and light beta use.
- Subscribe page: `https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/pricing`
- (Alternative: the same API is available directly via OpenWeb Ninja's portal at
  `openwebninja.com/api/jsearch`, which avoids RapidAPI's data-transfer limits. The
  endpoint/params/response are identical; just point `JSEARCH_HOST` at the portal
  host and use that key.)

## 2. Exact environment variables required
| Var | Required | Default | Purpose |
|---|---|---|---|
| `JSEARCH_API_KEY` | ✅ **Yes** | — | Your RapidAPI key. Without it the provider is inert (`available()=False`). |
| `JSEARCH_HOST` | optional | `jsearch.p.rapidapi.com` | RapidAPI host header (change only for the OpenWeb Ninja portal). |
| `JSEARCH_COUNTRY` | optional | `in` | ISO-2 country hint when the search has no explicit location (India). |
| `JSEARCH_DEFAULT_QUERY` | optional | `software developer intern` | Fallback query when none is provided. |

Set them in `.env` (or the process env). With only `JSEARCH_API_KEY` set, JSearch
works; the rest are tuning.

## 3. Where to obtain the API key
1. Create a free account at **rapidapi.com** (no credit card for Basic).
2. Open the **JSearch** API: `https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch`.
3. Click **Subscribe to Test** → choose the **Basic (Free)** plan.
4. On any endpoint (e.g. **Search**), the right-hand **Code Snippets** panel shows
   the header `X-RapidAPI-Key: <YOUR_KEY>`. Copy that value → that's `JSEARCH_API_KEY`.

## 4. Free-tier limits
- **200 requests / month** on the Basic plan — **hard-capped**, **no credit card**.
- Free tier effectively returns **1 page** per call (`num_pages=1`, ~10 results);
  Jobora already requests `num_pages=1`.
- **Budget the 200/month deliberately.** Jobora's provider-level + aggregate caching
  (15-min TTL, query-keyed) means repeated/identical searches do **not** spend
  quota. For heavier beta traffic, upgrade the RapidAPI plan or use the OpenWeb
  Ninja portal route.

## 5. Sample API response (representative documented schema — not a live fetch)
`GET https://jsearch.p.rapidapi.com/search?query=internship%20in%20India&page=1&num_pages=1`
with headers `X-RapidAPI-Key`, `X-RapidAPI-Host`:
```json
{
  "status": "OK",
  "request_id": "…",
  "parameters": { "query": "internship in India", "page": 1, "num_pages": 1 },
  "data": [
    {
      "job_id": "abcd1234…",
      "job_title": "Software Engineer Intern",
      "employer_name": "Example Tech Pvt Ltd",
      "job_publisher": "LinkedIn",
      "job_employment_type": "INTERN",
      "job_apply_link": "https://…/apply",
      "job_is_remote": false,
      "job_city": "Bengaluru",
      "job_state": "Karnataka",
      "job_country": "IN",
      "job_posted_at_datetime_utc": "2026-06-01T00:00:00.000Z",
      "job_min_salary": 20000,
      "job_max_salary": 40000,
      "job_salary_currency": "INR",
      "job_salary_period": "MONTH",
      "job_description": "…"
    }
  ]
}
```
Jobora maps each `data[]` item → `RawJob` (title, company, `job_apply_link`→apply
URL, city/state/country→location, `INTERN`→`internship`, `job_is_remote`→remote,
salary→INR display, `jsearch-{job_id}`).

## 6. Verification procedure
1. Set the key: `export JSEARCH_API_KEY=<your-key>`.
2. Run the temporary probe (read-only, fetches 10 India internships):
   ```bash
   cd backend
   JSEARCH_API_KEY=$JSEARCH_API_KEY .venv/bin/python -m scripts.jsearch_probe
   ```
   Expect a table of up to 10 rows: **title · company · location · apply URL**.
3. In the app: restart the backend with the key set, open **Find Jobs**, and the
   **Sources** row flips `JSearch` from `○` (Source Pending) to `●` (active);
   India/remote/intern results appear, ranked by eligibility.
4. Confirm quota: each manual search spends ≤1 request (cached for 15 min).

> The probe is **temporary** (`backend/scripts/jsearch_probe.py`) — delete it after
> verifying. It only reads via the existing provider; it changes nothing.
