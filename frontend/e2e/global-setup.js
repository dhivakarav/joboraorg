// Prepares deterministic state for the smoke run:
//  - waits for the backend to be healthy
//  - ensures an APPROVED smoke user exists (seeker_type=student) for auth flows
//  - writes a minimal resume PDF fixture
//  - clears stale artifacts (errors + screenshots) so the report is fresh
import fs from "fs";
import {
  API_URL, ADMIN_EMAIL, ADMIN_PASSWORD, SMOKE_EMAIL, SMOKE_PASSWORD,
  ORIGIN, SMOKE_STATE, ADMIN_STATE,
} from "./support.js";

// Write a Playwright storageState that seeds the JWT into localStorage, so tests
// reuse auth instead of logging in every time (avoids the login rate limit).
function writeState(path, token) {
  fs.writeFileSync(path, JSON.stringify({
    cookies: [],
    origins: [{ origin: ORIGIN, localStorage: [{ name: "jobora_token", value: token }] }],
  }, null, 2));
}

async function j(path, opts) {
  const r = await fetch(`${API_URL}${path}`, opts);
  let body = {};
  try { body = await r.json(); } catch { /* non-json */ }
  return { status: r.status, body };
}
const JSON_H = { "Content-Type": "application/json" };

function minimalPdf() {
  const txt = "Smoke Tester smoke@example.com Python Machine Learning React SQL";
  const stream = `BT /F1 11 Tf 50 760 Td (${txt}) Tj ET`;
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n"; const offs = [];
  objs.forEach((o, i) => { offs.push(pdf.length); pdf += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const x = pdf.length;
  pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  offs.forEach((o) => { pdf += `${String(o).padStart(10, "0")} 00000 n \n`; });
  pdf += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${x}\n%%EOF`;
  return Buffer.from(pdf, "latin1");
}

export default async function globalSetup() {
  // fresh artifacts
  fs.rmSync("e2e/.artifacts/errors.json", { force: true });
  fs.rmSync("e2e/screenshots", { recursive: true, force: true });
  fs.mkdirSync("e2e/screenshots", { recursive: true });
  fs.mkdirSync("e2e/fixtures", { recursive: true });
  fs.writeFileSync("e2e/fixtures/resume.pdf", minimalPdf());

  // wait for backend
  let up = false;
  for (let i = 0; i < 30; i++) {
    try { const r = await fetch(`${API_URL}/api/health`); if (r.ok) { up = true; break; } } catch { /* retry */ }
    await new Promise((s) => setTimeout(s, 1000));
  }
  if (!up) throw new Error(`Backend not reachable at ${API_URL}. Start it before the smoke run.`);

  // admin login
  const al = await j("/api/auth/login", { method: "POST", headers: JSON_H,
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }) });
  if (!al.body.access_token) {
    throw new Error(`Admin login failed (${al.status}). Set JOBORA_ADMIN_EMAIL / JOBORA_ADMIN_PASSWORD to the running backend's admin.`);
  }
  const ah = { ...JSON_H, Authorization: `Bearer ${al.body.access_token}` };

  // ensure smoke user exists + approved + student
  await j("/api/auth/register", { method: "POST", headers: JSON_H,
    body: JSON.stringify({ full_name: "Smoke Tester", email: SMOKE_EMAIL, password: SMOKE_PASSWORD, years_experience: 0 }) });
  const users = (await j("/api/admin/users", { headers: ah })).body || [];
  const u = Array.isArray(users) ? users.find((x) => x.email === SMOKE_EMAIL) : null;
  if (u) await j(`/api/admin/users/${u.id}/approve`, { method: "POST", headers: ah });

  const sl = await j("/api/auth/login", { method: "POST", headers: JSON_H,
    body: JSON.stringify({ email: SMOKE_EMAIL, password: SMOKE_PASSWORD }) });
  if (!sl.body.access_token) throw new Error(`Smoke user login failed (${sl.status}).`);
  await j("/api/profile/update", { method: "PUT",
    headers: { ...JSON_H, Authorization: `Bearer ${sl.body.access_token}` },
    body: JSON.stringify({ seeker_type: "student" }) });

  // Persist auth states for the tests to reuse (no per-test login → no rate limit).
  writeState(SMOKE_STATE, sl.body.access_token);
  writeState(ADMIN_STATE, al.body.access_token);
}
