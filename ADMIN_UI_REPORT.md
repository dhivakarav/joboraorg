# Admin Operations UI — Report (closes Warning W2)

Built the missing admin UI that surfaces the existing (but previously unsurfaced)
`/api/admin/{metrics,feedback,invites}` endpoints. No payments, no new boards, no
deploy; Greenhouse/Lever/Ashby pipelines untouched (no backend logic changed —
the endpoints already existed and are now wired to a UI).

## 1. Menu item
Added **"◆ Operations"** to the admin sidebar (`Layout.jsx` `ADMIN_NAV`) →
route `/admin/operations` (`App.jsx`, `RequireAdmin`).

## 2. Endpoints surfaced
New page `pages/admin/Operations.jsx` with three tabs:

| Tab | Endpoint(s) | What it shows |
|---|---|---|
| **Metrics** | `GET /api/admin/metrics` | Users (total/pending/approved/new-this-week), Funnel (signed up → uploaded resume → tracked a job), Applications by canonical status (Verified Submitted / Submitted / Manual Apply / Tracked / Failed / Total), Feedback (open / open-bugs) + Invites (used/total) |
| **Feedback & Bugs** | `GET /api/admin/feedback` (+ `?kind=`) | Table of feedback/bug reports — type, message, page, rating, severity, contact, date; filter All / 💡 Feedback / 🐞 Bugs |
| **Invites** | `GET /api/admin/invites`, `POST /api/admin/invites?count=&note=` | Generate N codes with an optional note; table of codes with **Available/Used** status, redeemer email, note, date; click-to-copy |

## 3. Responsive UI
- Tab chips wrap; stat grids `grid-cols-2 md:grid-cols-4`; all tables in
  `overflow-x-auto` (horizontal scroll on phones). Consistent with the existing
  admin pages + the mobile shell (drawer + scrollable modals).

## 4. Tests
`tests/test_admin_ops.py` (4 tests, all passing):
- `metrics` returns the expected sections + keys.
- invites: `POST ?count=3` creates 3 codes; `GET` lists them (unused).
- feedback: a seeded bug appears in the list and the `?kind=bug` filter works.
- the endpoints reject unauthenticated access (401/403).

Admin token is minted directly from a DB-created admin (no `/auth/login`), so it
never collides with the login rate-limit test.

## 5. Build / suite
- Frontend **build passes** (clean).
- Backend suite: **40 passed** (36 → 40; +4 admin-ops). No regressions.

## Verification of W2 closure
The audit's W2 was: *"admin metrics/feedback/invites endpoints exist but aren't
surfaced in the admin UI."* They are now reachable from **Admin → Operations**,
responsive, and test-covered. Beta feedback/bug triage + invite-code issuing +
the funnel are all usable from the dashboard.

## Notes
- No new backend endpoints were created; this is purely UI + tests over existing
  APIs. `/admin/invites` honors `BETA_INVITE_REQUIRED` at registration (unchanged).
- Remaining audit items (live-browser smoke W1, device mobile test) are unaffected
  and still recommended pre-invite.
