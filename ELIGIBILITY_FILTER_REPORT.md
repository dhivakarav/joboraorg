# Eligibility Filter Report

**Profile:** B.Tech CSE (AI/ML), graduating 2027, internship seeker / fresher /
entry-level (`seeker_type=student`, `experience=0`).
**Mode:** **Strict eligibility filtering — ON by default for everyone.**

## Root cause of the bug you saw
Eligibility *hiding* had been gated behind the **Pro plan** (`premium_matching`).
Your account is on **Free**, so senior/staff/principal roles were no longer being
hidden. Filtering is now a **baseline feature for all users** — never paywalled.

## 1. Default-hidden (Not Recommended)
Hidden by default for early-career profiles, each with a reason:
`Senior · Sr · Staff · Principal · Lead · Manager · Director · Architect`
(also Head/VP/Distinguished/Fellow) · **3+ years experience** · **PhD required** ·
**Master's required**. (Degree requirements are ignored when the posting also
welcomes Bachelor's/B.Tech/"or equivalent".)

## 2. Boosted
`Internship · Intern · Student · New Grad · Graduate Program · Fresher ·
Entry Level · Associate Engineer` (+ Junior/Trainee/Apprentice/Co-op/Campus),
with an extra boost for AI/ML & software roles.

## 3. Eligibility Score → tier
| Score | Tier | Shown? |
|---|---|---|
| ≥ 80 | **Excellent Match** | ✅ |
| 60–79 | **Good Match** | ✅ |
| 40–59 | **Possible Match** | ✅ |
| < 40 or any disqualifier | **Not Recommended** | ❌ hidden by default |

A "show anyway" toggle reveals hidden roles on demand; experienced users (non-early
profiles) are never penalized by these filters.

## 4. "Why matched?" on every job card
Each card now shows a **Why matched?** panel listing the eligibility reasons
(e.g. "Early-career role (internship / new grad / entry-level)", "Matches your
AI/ML & software focus") plus skill/role match reasons.

## 5. Dashboard
The Dashboard **recent-activity** feed now also hides Not-Recommended roles by
default, so senior/staff/principal titles no longer surface there.

---

## Before / After (real Greenhouse data, your profile)
| Metric | Count |
|---|---|
| **Before** — all real jobs fetched | **2,267** |
| **After** — shown (eligible) | **698** |
| **Hidden** — Not Recommended | **1,569** |
| Excellent Match | 10 |
| Good Match | 688 |

### Roles hidden — reason breakdown
| Reason | Count |
|---|---|
| Senior-level | 421 |
| Manager-level | 366 |
| Staff-level | 223 |
| Architect-level | 179 |
| Sr-level | 161 |
| Lead-level | 86 |
| Director-level | 68 |
| Principal-level | 26 |
| **Total hidden** | **1,569** |

(PhD-required / Master's-required / 3+ years are also hidden when stated in the
title or snippet; counts above reflect title-level signals in this fetch.)

### Roles promoted — sample top recommendations
| Score | Tier | Role |
|---|---|---|
| 98 | Excellent Match | Stripe — Software Engineering, New Grad |
| 98 | Excellent Match | Stripe — Software Engineer, Intern |
| 98 | Excellent Match | Stripe — SWE New Grad, Developer Experience |
| 90 | Excellent Match | Airbnb — Communications Intern, LATAM |
| 90 | Excellent Match | Stripe — Operations Associate, New Grad |

## Verification
- All disqualifiers (Senior/Staff/Principal/Lead/Manager/Director/Architect,
  3+ yrs, PhD-required, Master's-required) → **Not Recommended + hidden**. ✅
- All boost terms (Internship…Associate Engineer) → **Excellent Match, shown**. ✅
- Filtering applies on **Free and Pro** (ungated). ✅
- 21/21 backend tests pass; frontend builds clean; backend restarted healthy.

## Integrity
Real providers + real data only; no fake jobs, no fabricated evidence. Eligibility
is a pure, deterministic ranking/visibility layer over genuine listings.
