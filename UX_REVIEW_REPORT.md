# Jobara — UX Review Report (Internship UI Enhancements)

Scope: the UI work requested — internship/fresher/remote filter tabs, the
Internshala "Source Pending" badge + tooltip, the Jobs-page tabs, and onboarding
that personalizes recommendations by seeker type. Captured against the running
app with real backend data.

## Screenshots (in `/tmp/jobara_ui_shots/`)
| File | Shows |
|---|---|
| `01_onboarding.png` | Welcome modal — Student / Fresher / Experienced |
| `02_findjobs_tabs.png` | Find Jobs: 5 tabs, "Recommended for you", Source Pending badge, honest empty state |
| `03_tooltip.png` | Source Pending tooltip text on hover |
| `04_internship_tab.png` | Internship tab selected |

---

## What was delivered (and verified on screen)

### 1–3. Filter chips / tabs — Internship, Fresher, Remote (+ All, Full-time) ✅
The Jobs page now leads with a tab row: **All · Internship · Fresher · Full-time
· Remote**. Each maps to a real backend filter (`employment_type` and, for
Remote, `location=Remote`) on `GET /api/jobs`. Active tab is white-on-black per
the design system; switching tabs re-queries.

### 4. "Source Pending" badge for Internshala ✅
In the Sources row, Internshala renders as a yellow **"⏳ Internshala · Source
Pending"** badge (distinct from green available / grey unavailable sources),
reflecting the honest backend state (`available:false`).

### 5. Tooltip ✅
Hovering the badge shows: **"Internshala integration is awaiting an authorized
data source."** — exact requested copy, in an on-brand glossy tooltip.

### 6. Jobs page tabs ✅
Internship / Fresher / Full-time / Remote all present and functional (Remote uses
the location filter; the others use employment type).

### 7. Onboarding — Student / Fresher / Experienced ✅
A one-time welcome modal (shown to approved users with no seeker type set) asks
the user's stage with clear iconography and descriptions, plus "Skip for now".
Selection persists via `PUT /api/profile/update { seeker_type }`.

### 8. Personalized recommendations ✅
Seeker type sets the **default Jobs tab** — Student → Internship, Fresher →
Fresher, Experienced → Full-time — and shows a **"★ Recommended for you"** chip on
that tab. Verified: choosing **Student** in onboarding landed the user on the
**Internship** tab with the Recommended chip (visible in `02_findjobs_tabs.png`).

---

## UX assessment

### Strengths
- **Consistent design language** — chips, badges, modal, and tooltip all reuse
  the glossy black/white system; nothing looks bolted on.
- **Honesty as UX** — the empty internship state explains *why* there are no
  listings ("arrive once an authorized India source is connected. Try the
  Full-time or Remote tab.") and routes the user to value instead of a dead end.
  Same for the Source Pending badge + tooltip. This builds trust rather than
  faking content.
- **Personalization is immediate and low-friction** — one tap in onboarding
  changes the default view; "Recommended for you" makes the personalization
  legible to the user.
- **Reversible** — "Skip for now" and free tab switching mean the preference
  never traps the user.

### Issues & recommendations (prioritized)
1. **[Medium] Internship/Fresher tabs are empty today** — because the only
   internship source (Internshala) is pending. The empty-state copy is good, but
   consider **disabling/greying the Internship & Fresher tabs** (with the same
   tooltip) until a source is connected, so users don't tap into empty views.
   Alternatively, surface any internships that appear via other sources
   (Greenhouse interns) so the tab isn't always empty.
2. **[Medium] Onboarding can be skipped and never returns** — add a way to set
   seeker type later (Settings) so "Skip" isn't permanent; also re-prompt gently
   if still unset after a few sessions.
3. **[Low] Personalization is currently tab-default only** — to deepen it, bias
   match scoring or the default query by seeker type (e.g., students → entry
   keywords), not just the active tab.
4. **[Low] Location vs Remote tab interaction** — the Remote tab and the Location
   dropdown can both set location; make the Remote tab visibly sync the Location
   control (or hide the dropdown on the Remote tab) to avoid a confusing dual
   control.
5. **[Low] Tooltip on touch devices** — hover tooltips don't trigger on mobile;
   add tap-to-reveal (or an inline "ⓘ") for the Source Pending explanation.
6. **[Low] Mobile layout** — the tab row + filter card should be verified at
   narrow widths (wrap is handled, but tab overflow on small phones may need a
   horizontal scroll).

### Accessibility notes
- Tabs are `<button>`s (keyboard-focusable) ✅; consider adding
  `role="tablist"/"tab"` + `aria-selected` for screen readers.
- Tooltip has `role="tooltip"` ✅ but is hover-only — pair with focus/tap.
- Colour-only status (green/yellow/grey badges) — add the text label (already
  present for Source Pending) to all states for colour-blind users.

---

## Verdict
All eight requested items are implemented, on-brand, and **verified on screen**.
The standout is that the UI stays **honest** about Internshala (Source Pending +
explanatory tooltip + helpful empty state) rather than faking listings — fully
consistent with the product's integrity stance. The top follow-up is handling the
empty Internship/Fresher tabs gracefully until an authorized source is connected.

_No new automated UI tests were added; backend remains 21/21 green and the
frontend builds clean._
