# Internships & New Grad — Hard Filter Report

**Scope:** recommendation quality only. **No application-integrity logic touched;
no Greenhouse/Lever/Ashby pipeline touched.** Pure visibility/ranking layer over
real listings.

## 1. The toggle
```
[ ] Show all eligible jobs
[✓] Internships & New Grad only
```
Rendered on **Find Jobs**. State persists per request; the user can switch it off
anytime (`?internships_only=false`).

## 2. Default ON for
- `seeker_type = student`
- `seeker_type = fresher`
- `graduation_year >= current year` (when provided)

Your profile (`student`, grad 2027) → **default ON**. Experienced users → default OFF.

## 3. Shows ONLY jobs carrying an explicit early-career signal
`Intern · Internship · New Grad · Graduate Program · University Graduate ·
Campus · Fresher · Entry Level · Associate Engineer` (+ Trainee/Apprentice/Junior).
Everything else is hidden while the toggle is on.

## 4. Hidden while ON (unless toggled off)
- **Generic "Software Engineer"** (no early-career signal)
- Senior · Staff · Principal · Lead · Manager · Director · Architect
- (these were already eligibility-hidden; the hard filter additionally drops
  generic mid-level titles that carry no intern/new-grad signal)

## 5. Visible badges
- Tier: **Excellent Match** · **Good Match** (· Possible Match)
- Type: **Internship** · **New Grad** · **Fresher Friendly**
  (derived from the title/snippet signal; shown on every card)

## 6. Dashboard
Recent-activity now uses the **same filtered dataset** — for students/freshers it
shows only eligible *intern/new-grad-signal* roles, so generic/senior titles no
longer appear there.

---

## Before / After (real Greenhouse data, your profile)
| Stage | Count |
|---|---|
| **Before** — all real jobs fetched | **2,267** |
| After eligibility (senior/PhD/Master's/3+ yrs removed) | 698 |
| **After hard filter** — internships & new grad only | **9** |
| **Hidden** by the hard filter (generic + senior) | **2,258** |

Signal breakdown of the shown set: **5 Internship · 4 New Grad.**

> Note: this is the **Greenhouse-only** slice (big-tech boards have few open
> intern reqs at any moment). The live app aggregates all real providers
> (Remotive, Arbeitnow, Adzuna, Jooble, Lever, Ashby…), so the user sees more.
> The filter behavior — keep only explicit early-career signals — is identical.

### Sample top matches (filter ON)
| Type | Role |
|---|---|
| Internship | Stripe — Software Engineer, Intern |
| New Grad | Stripe — Software Engineering, New Grad |
| New Grad | Stripe — SWE New Grad, Developer Experience |
| Internship | Airbnb — Communications Intern, LATAM |
| Internship | Airbnb — Sales Operations Intern, Italy |

## Verification
- Generic "Software Engineer" / "Senior Software Engineer" / "Backend Developer"
  → **no signal → hidden** when ON. ✅
- All spec signals (Intern…Associate Engineer) → detected & shown with a type
  badge. ✅
- Default ON for student/fresher, OFF for experienced. ✅
- 21/21 backend tests pass; frontend builds clean; backend restarted healthy.
- Integrity & ATS pipelines untouched.
