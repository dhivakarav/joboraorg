"""A controlled mock that mirrors a Greenhouse application form + confirmation
flow, so the G3 submit pipeline can be tested WITHOUT filing a fabricated
application into a real company's ATS.

Routes:
  GET  /job/ok          -> form that submits successfully
  GET  /job/captcha     -> form whose submit returns a CAPTCHA challenge
  GET  /job/validation  -> form whose submit returns a validation error
  POST /submit?mode=...  -> ok: 303 -> /confirmation?ref=GH-XXXX
                            captcha/validation: 200 error page (no ref)
  GET  /confirmation     -> success page with the confirmation number

Field ids mirror real Greenhouse (#first_name, #resume, #submit_app, question_*).
Run: python -m tests.mock_greenhouse  (serves on 127.0.0.1:8099)
"""
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8099

FORM = """<!doctype html><html><head><title>Apply — Mock Co</title></head><body>
<h1>Apply for Mock Engineer</h1>
<form id="application_form" action="/submit?mode={mode}" method="post" enctype="multipart/form-data">
  <label for="first_name">First Name *</label><input id="first_name" name="first_name" required>
  <label for="last_name">Last Name *</label><input id="last_name" name="last_name" required>
  <label for="email">Email *</label><input id="email" name="email" type="email" required>
  <label for="phone">Phone</label><input id="phone" name="phone">
  <label for="resume">Resume/CV *</label><input id="resume" name="resume" type="file" required>
  <label for="question_900001">Are you authorized to work?</label>
  <select id="question_900001" name="question_900001">
    <option value="">--</option><option>Yes</option><option>No</option>
  </select>
  <button id="submit_app" type="submit">Submit Application</button>
</form></body></html>"""

CAPTCHA_PAGE = """<!doctype html><html><head><title>Verify</title></head><body>
<h1>Security check</h1>
<div class="g-recaptcha">Please complete the reCAPTCHA challenge to continue.</div>
</body></html>"""

VALIDATION_PAGE = """<!doctype html><html><head><title>Apply — error</title></head><body>
<div class="error">There were errors with your submission. This field is required.</div>
</body></html>"""

CONFIRM_PAGE = """<!doctype html><html><head><title>Application submitted</title></head><body>
<h1>Your application has been submitted!</h1>
<p>Thank you for applying. Your confirmation number is <strong>{ref}</strong>.</p>
</body></html>"""


def ref_id():
    return "GH-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if body is not None:
            self.send_header("Content-Type", "text/html")
        self.end_headers()
        if body is not None:
            self.wfile.write(body.encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/job/"):
            mode = u.path.split("/job/", 1)[1] or "ok"
            self._send(200, FORM.format(mode=mode))
        elif u.path == "/confirmation":
            ref = parse_qs(u.query).get("ref", ["GH-UNKNOWN"])[0]
            self._send(200, CONFIRM_PAGE.format(ref=ref))
        else:
            self._send(404, "<h1>not found</h1>")

    def do_POST(self):
        u = urlparse(self.path)
        # drain the body (file upload) without parsing
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        mode = parse_qs(u.query).get("mode", ["ok"])[0]
        if mode == "captcha":
            self._send(200, CAPTCHA_PAGE)
        elif mode == "validation":
            self._send(200, VALIDATION_PAGE)
        else:
            self._send(303, None, {"Location": f"/confirmation?ref={ref_id()}"})


if __name__ == "__main__":
    print(f"Mock Greenhouse on http://127.0.0.1:{PORT}  (/job/ok, /job/captcha, /job/validation)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
