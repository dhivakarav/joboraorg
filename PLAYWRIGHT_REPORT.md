# Playwright Smoke Report (closes W1)

_Run: 2026-06-12T07:07:46.689Z. Backend: `http://localhost:8000`. Browser: Chromium (Playwright). Serialized (workers:1)._

## Summary
- Tests: **13 passed · 0 failed · 0 skipped** (of 13).
- **Console errors: 0** · **Failed API/network requests (5xx/connection): 0** · **Uncaught exceptions: 0**.
- Non-blocking 4xx (auth/validation, informational): 0.
- Screenshots: `frontend/e2e/screenshots/` · HTML report: `frontend/e2e/.artifacts/html`.

## Verdict
✅ **PASS — zero console errors, zero failed API requests, zero uncaught exceptions across all flows.**

## Per-test results
| Test | Status | Console err | Net fail | Exceptions |
|---|---|---|---|---|
| 1. Signup | ✅ | 0 | 0 | 0 |
| 2. Login | ✅ | 0 | 0 | 0 |
| 3+4. Resume upload & parsing | ✅ | 0 | 0 | 0 |
| 5+6. Find Jobs + internship filter | ✅ | 0 | 0 | 0 |
| 7. Dashboard statistics | ✅ | 0 | 0 | 0 |
| 8. Activity Log | ✅ | 0 | 0 | 0 |
| 9. Verification Center | ✅ | 0 | 0 | 0 |
| 10. Admin Operations | ✅ | 0 | 0 | 0 |
| 11. Greenhouse submit wizard | ✅ | 0 | 0 | 0 |
| 12. Lever Assisted Apply | ✅ | 0 | 0 | 0 |
| 13. Ashby Assisted Apply | ✅ | 0 | 0 | 0 |
| 14. Logout | ✅ | 0 | 0 | 0 |
| 15. Mobile responsiveness | ✅ | 0 | 0 | 0 |

## Captured issues
None. 🎉

## Coverage
Signup · Login · Resume upload · Resume parsing · Find Jobs · Internship filter · Dashboard · Activity Log · Verification Center · Admin Operations · Greenhouse Track & Apply · Lever Assisted Apply · Ashby Assisted Apply · Logout · Mobile drawer. Apply-flow tests interact with whatever real listings are live and otherwise screenshot the state (no fabricated data).
