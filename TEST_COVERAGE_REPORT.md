# Test Coverage Report

Backend suite grew from **21 → 33 passing tests** (new `tests/test_medium.py`,
12 tests). No matching/integrity logic changed; one real bug was fixed (below).

## New coverage (`tests/test_medium.py`)
| Area | Tests | What's asserted |
|---|---|---|
| **Status transitions** | 4 | Verified Submitted needs id + URL + screenshot; missing any → downgrades to Submitted; legacy "Applied" → Tracked (never surfaces); Manual/Tracked/Draft mapping |
| **Search caching** | 3 | `query_agnostic` providers (Greenhouse) produce a query-independent cache key; query-specific (Remotive) varies by query; `clear_provider_cache()` works |
| **Greenhouse Track & Apply** | 2 | `/jobs/apply` records **Tracked**; legacy `status:"Applied"` is coerced to **Tracked** |
| **Assisted Apply + Verification** | 1 | prepare returns platform + prefilled required fields; record **without** screenshot → Submitted (verified=false, missing=[screenshot]); **with** all three → Verified Submitted; evidence endpoint returns reference id + confirmation URL |
| **Assisted guardrail** | 1 | non-assisted platform (Greenhouse) rejected from the assisted endpoint (400) |
| **Dead-code removal** | 1 | `/api/portals` and `/api/billing/plans` return 404 |

## Bug found & fixed by the new tests
`app/status.py::display_status` recognized only `"Manual Apply Required"`, not the
canonical `"Manual Apply"` value — a row with `submission_status="Manual Apply"`
and `manual_required=False` wrongly displayed as **Draft**. Fixed to accept both.
(In practice such rows also carried `manual_required=True`, so the bug was masked;
the test caught the latent gap.)

## Test infrastructure note
The new user fixture creates an approved user **directly in the DB** and issues a
token via `security.issue_tokens`, deliberately avoiding the `/auth/login`
endpoint so it never collides with the per-IP login rate limit that
`test_b2::test_login_rate_limit` intentionally exhausts.

## Full run
```
33 passed, 3 warnings
```

## Gaps still open (Low)
- No browser/E2E tests for the React UI (wizard, drawer) — verified via build +
  manual reasoning.
- Live ATS submission paths (real Greenhouse/Lever/Ashby) remain validated by the
  G0–G3 scripts + mocks, not unit tests (by design — they need a browser).
