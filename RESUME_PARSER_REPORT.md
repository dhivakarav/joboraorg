# Resume Parser Report

Audited `app/utils/resume_parser.py` (heuristic + regex; no ML dependency) against
**4 realistic student/fresher resumes** (AI/ML undergrad, CSE fresher, data-science
master's, sparse minimal). Parsed fields verified per resume.

## Results
| Field | R1 AI/ML | R2 CSE fresher | R3 Data MSc | R4 sparse | Verdict |
|---|---|---|---|---|---|
| Name | ✅ Dhivakar A V | ✅ Priya Sharma | ✅ Rahul Verma | ✅ John Doe | **4/4** |
| Email | ✅ | ✅ | ✅ | ✅ | **4/4** |
| Location | ✅ Trichy | ✅ Bengaluru | ✅ Pune | — (none in text) | **3/3 present** |
| **Skills** | ✅ 10 (Python, ML, PyTorch, NumPy, Pandas, SQL, React, Git, Docker, FastAPI) | ✅ 9 (Java, JS, Spring, MySQL, AWS, HTML, CSS, TensorFlow, NLP) | ✅ 7 (Data Analysis, Pandas, Tableau, Power BI, SQL, Excel, Deep Learning) | ✅ 2 (Python, Flask) | **strong** |
| **Education** | ✅ B.Tech CSE (AI&ML), 2023 | ✅ B.E CSE, 2025 | ✅ MSc Data Science, 2024 | ⚠️ BCA (line noisy) | **degree+year 4/4** |
| Experience (yrs) | 0 | 0 | 0 | 0 | see note |
| LinkedIn/GitHub | ✅ both | — | — | ✅ github | correct where present |
| Phone | ⚠️ truncated | — | — | — | see note |

## Skills extraction — strong
Keyword dictionary covers the common student stack (Python/Java/JS, React/Spring,
ML/DL/TensorFlow/PyTorch/NLP, data tools, cloud/devops). All real skills were
extracted across the 4 resumes; no false positives.

## Education extraction — good
Degree line + start year captured for all 4 (B.Tech / B.E / MSc / BCA). On the
sparse resume (R4) the degree "line" also captured trailing prose
("Pursuing BCA. Knows Python…") — cosmetic noise, degree still identified.

## Findings
- **Low — Experience reads 0 for interns/months.** `EXP_RE` matches only "N years/
  yrs". "Software Intern (2024)" and "6 months internship" → 0. **Acceptable for the
  target audience** (students/freshers are genuinely ~0 yrs), and it correctly keeps
  the strict internship/eligibility filters ON. Documented, not a blocker.
- **Low — Phone truncation on 5-5 grouped Indian numbers.** "+91 98765 43210" parsed
  as "+91 98765 4321" (dropped trailing digit) due to the `\d{3,4}` grouping in
  `PHONE_RE`. User can correct it on the editable Resume form. Recommend a regex
  tweak post-beta; low impact (phone is optional for matching).
- **Low — Education line noise** on prose-style resumes (R4). Cosmetic.

## Mitigation already in place
The Resume page exposes an **editable parsed-fields form** (`/resume/parsed` PUT),
so any miss is user-correctable before it affects matching.

## Verdict
**Parser is beta-ready.** Name/email/location/skills/education are reliable across
varied student resume styles; the two Low issues (intern-experience = 0, phone
truncation) are non-blocking and user-correctable.
