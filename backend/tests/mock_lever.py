"""A controlled mock that mirrors a Lever apply form + confirmation flow, so the
G3 submit pipeline can be tested WITHOUT filing a fabricated application into a
real company's ATS.

DOM mirrors real Lever: single `name`, `email`, `phone`, `org`, `resume` file,
custom `cards[<uuid>][...]` (textarea + radio), and a "Submit Application"
button. Three submit outcomes:

  GET  /<co>/<pid>/apply?mode=ok|captcha|validation -> the form
  POST /<co>/<pid>/apply?mode=ok          -> 303 -> /<co>/thanks?ref=LVR-XXXX
  POST /<co>/<pid>/apply?mode=captcha      -> 200 hCaptcha challenge (no ref)
  POST /<co>/<pid>/apply?mode=validation   -> 200 validation error (no ref)
  GET  /<co>/thanks                        -> Lever-style confirmation page

The `captcha` mode reproduces what real public Lever forms do (every one ships an
hCaptcha): it lets us prove the pipeline records CAPTCHA as a FAILURE, never a
false success.

Run: python -m tests.mock_lever   (serves on 127.0.0.1:8097)
"""
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8097
CARD1 = "06e54799-8fbd-41b0-b37d-da1d3014c432"
CARD2 = "c8cb8fa2-2145-4df9-9df1-eacae11a8ffd"

FORM = """<!doctype html><html><head><title>Apply | Mock Co</title></head>
<body><div class="content"><form id="application-form" method="post"
   action="/{co}/{pid}/apply?mode={mode}" enctype="multipart/form-data">
  <input name="name" type="text" placeholder="Full name" required>
  <input name="email" type="email" placeholder="Email" required>
  <input name="phone" type="text" placeholder="Phone" required>
  <input name="org" type="text" placeholder="Current company" required>
  <input name="urls[LinkedIn]" type="text" placeholder="LinkedIn URL">
  <input name="resume" type="file" required>
  <div class="application-question">
    <label>Why do you want this role? *</label>
    <textarea name="cards[{c1}][0]" required></textarea>
  </div>
  <div class="application-question">
    <label>Are you authorized to work? *</label>
    <input name="cards[{c2}][0]" type="radio" value="Yes" required> Yes
    <input name="cards[{c2}][0]" type="radio" value="No"> No
  </div>
  <button class="template-btn-submit" type="submit">Submit Application</button>
</form></div></body></html>"""

CAPTCHA_PAGE = """<!doctype html><html><head><title>Verify</title></head><body>
<h1>Please verify you are human</h1>
<div class="h-captcha" data-sitekey="mock">Complete the hCaptcha challenge to submit your application.</div>
</body></html>"""

VALIDATION_PAGE = """<!doctype html><html><head><title>Apply | error</title></head><body>
<div class="form-error">There were errors with your submission. This field is required.</div>
</body></html>"""

CONFIRM_PAGE = """<!doctype html><html><head><title>Thank you for applying</title></head><body>
<h1>Thank you for applying</h1>
<p>Your application has been submitted. Reference number: <strong>{ref}</strong>.</p>
</body></html>"""


def ref_id():
    return "LVR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
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
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 3 and parts[2] == "apply":
            mode = parse_qs(u.query).get("mode", ["ok"])[0]
            self._send(200, FORM.format(co=parts[0], pid=parts[1], mode=mode,
                                        c1=CARD1, c2=CARD2))
        elif len(parts) >= 2 and parts[1] == "thanks":
            ref = parse_qs(u.query).get("ref", ["LVR-UNKNOWN"])[0]
            self._send(200, CONFIRM_PAGE.format(ref=ref))
        else:
            self._send(404, "<h1>Not found</h1>")

    def do_POST(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        mode = parse_qs(u.query).get("mode", ["ok"])[0]
        if mode == "captcha":
            self._send(200, CAPTCHA_PAGE)
        elif mode == "validation":
            self._send(200, VALIDATION_PAGE)
        else:
            co = parts[0] if parts else "mockco"
            self._send(303, None, {"Location": f"/{co}/thanks?ref={ref_id()}"})


if __name__ == "__main__":
    print(f"Mock Lever on http://127.0.0.1:{PORT}  (/<co>/<pid>/apply?mode=ok|captcha|validation)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
