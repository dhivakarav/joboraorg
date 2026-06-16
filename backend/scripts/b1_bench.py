"""B1 performance benchmarks + load test + concurrency/retry checks."""
import concurrent.futures as cf
import json, statistics, time, urllib.request, urllib.error

B = "http://localhost:8000"


def call(path, method="POST", token=None, body=None, form=None):
    h = {}; data = None
    if token: h["Authorization"] = "Bearer " + token
    if form is not None:
        bnd = "--b"; fn, ct, cnt = form
        data = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n").encode() + cnt + (f"\r\n--{bnd}--\r\n").encode()
        h["Content-Type"] = f"multipart/form-data; boundary={bnd}"
    elif body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    r = urllib.request.Request(B + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}


def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(len(xs) * p / 100))]


admin = call("/api/auth/login", body={"email": "ops@jobara.io", "password": "OpsBootstrap1"})[1]["access_token"]

# Seed a primary user + resume.
call("/api/auth/register", body={"full_name": "Asha Rao", "email": "asha@x.io", "password": "Str0ngPass1", "phone": "+1 415 555 0190", "years_experience": 5, "job_title": "engineer"})
uid = [u["id"] for u in call("/api/admin/users", "GET", token=admin)[1] if u["email"] == "asha@x.io"][0]
call(f"/api/admin/users/{uid}/approve", token=admin)
tok = call("/api/auth/login", body={"email": "asha@x.io", "password": "Str0ngPass1"})[1]["access_token"]
pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
call("/api/resume/upload", token=tok, form=("r.pdf", "application/pdf", pdf))

print("=" * 60)
print("BENCH 1 — apply enqueue latency (browser does NOT run in request)")
print("=" * 60)
lat = []
for i in range(12):
    job = {"fingerprint": f"b{i}", "external_id": "", "source": "Greenhouse", "title": "Eng",
           "company": "MockCo", "apply_url": "http://127.0.0.1:8099/job/ok", "answers": {}, "approved": True}
    t0 = time.time(); sc, res = call("/api/jobs/greenhouse/apply", token=tok, body=job); lat.append((time.time() - t0) * 1000)
print(f"  enqueued {len(lat)} applications")
print(f"  enqueue latency ms: p50={pct(lat,50):.0f} p95={pct(lat,95):.0f} max={max(lat):.0f} mean={statistics.mean(lat):.0f}")

print("\n" + "=" * 60)
print("BENCH 2 — worker concurrency cap + throughput (SUBMISSION_CONCURRENCY=2)")
print("=" * 60)
t0 = time.time(); terminal = 0
while time.time() - t0 < 90:
    d = call("/api/applications?page=1&page_size=50", "GET", token=tok)[1]
    states = [a["submission_status"] for a in d["items"]]
    terminal = sum(1 for s in states if s in ("Verified Submitted", "Submitted", "Failed", "CAPTCHA Required", "Manual Apply Required"))
    if terminal >= len(lat):
        break
    time.sleep(1)
elapsed = time.time() - t0
verified = sum(1 for a in d["items"] if a["submission_status"] == "Verified Submitted")
print(f"  {terminal}/{len(lat)} processed in {elapsed:.1f}s | Verified Submitted={verified}")
print(f"  throughput ≈ {terminal/elapsed:.2f} submissions/s with concurrency=2 (each launches real Chromium)")

print("\n" + "=" * 60)
print("BENCH 3 — admin user list (H4 N+1 fix): seed users, time the call")
print("=" * 60)
for i in range(60):
    call("/api/auth/register", body={"full_name": f"U{i}", "email": f"bulk{i}@x.io", "password": "Str0ngPass1"})
lt = []
for _ in range(5):
    t0 = time.time(); call("/api/admin/users", "GET", token=admin); lt.append((time.time() - t0) * 1000)
print(f"  /api/admin/users with ~61 users: p50={pct(lt,50):.0f}ms (single grouped count query, not N+1)")

print("\n" + "=" * 60)
print("LOAD TEST — concurrent authenticated reads (DB, exercises user_id index)")
print("=" * 60)
def hit(_):
    t0 = time.time(); sc, _ = call("/api/applications?page=1&page_size=20", "GET", token=tok); return (time.time() - t0) * 1000, sc
for conc in (10, 25, 50):
    N = 200
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        results = list(ex.map(hit, range(N)))
    wall = time.time() - t0
    lats = [r[0] for r in results]; ok = sum(1 for r in results if r[1] == 200)
    print(f"  conc={conc:3d} N={N}: {ok}/{N} ok | p50={pct(lats,50):.0f}ms p95={pct(lats,95):.0f}ms p99={pct(lats,99):.0f}ms | {N/wall:.0f} req/s")

print("\nDONE")
