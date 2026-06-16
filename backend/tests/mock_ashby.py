"""A controlled mock that mirrors an Ashby **React-SPA** apply form + in-app
confirmation, so the G3 submit pipeline can be tested WITHOUT filing a fabricated
application into a real company's ATS.

The crucial property: on submit the page mutates its DOM **in place, with NO
navigation** (the URL never changes) — exactly how real Ashby shows its success
state. This proves the pipeline detects an SPA confirmation by DOM state, not by
a URL change (requirement #7).

DOM mirrors real Ashby: `#_systemfield_name`, `#_systemfield_email`,
`input[type=tel]`, `#_systemfield_resume`, a UUID-named required textarea, a
Yes/No button pair, a `g-recaptcha-response` field, and a "Submit Application"
button. The submit handler branches on ?mode=:

  ok          -> in-app success panel + reference "ASH-XXXX"     (no navigation)
  captcha      -> in-app reCAPTCHA challenge message              (no navigation)
  validation   -> in-app "This field is required" error           (no navigation)

Run: python -m tests.mock_ashby   (serves on 127.0.0.1:8096)
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8096

PAGE = """<!doctype html><html><head><title>{title} @ MockCo</title></head>
<body><div class="ashby-job-posting-right-pane-application-tab">
<div id="app" class="ashby-application-form">
  <input id="_systemfield_name" name="_systemfield_name" type="text" placeholder="Name" required>
  <input id="_systemfield_email" name="_systemfield_email" type="email" placeholder="Email" required>
  <input id="phone" name="ad-hoc-phone" type="tel" placeholder="Phone" required>
  <input id="_systemfield_resume" type="file" required>
  <textarea name="0086e069-bc0c-467b-8d38-c3f023146e79" placeholder="Why this role? *" required></textarea>
  <div class="ashby-yesno">
    <span>Authorized to work? *</span>
    <button type="button" class="yesno" onclick="this.classList.add('selected')">Yes</button>
    <button type="button" class="yesno" onclick="this.classList.add('selected')">No</button>
  </div>
  <textarea name="g-recaptcha-response" id="g-recaptcha-response-100000" style="display:none"></textarea>
  <button type="button" id="submit-app" onclick="submitApp()">Submit Application</button>
</div></div>
<script>
function ref(){{var s='';var c='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  for(var i=0;i<10;i++) s+=c[Math.floor(Math.random()*c.length)]; return 'ASH-'+s;}}
function submitApp(){{
  var mode=(new URLSearchParams(location.search).get('mode'))||'ok';
  var app=document.getElementById('app');
  if(mode==='captcha'){{ app.innerHTML='<div class="recaptcha-challenge">Please verify you are human — complete the reCAPTCHA challenge to submit your application.</div>'; return; }}
  if(mode==='validation'){{ app.innerHTML='<div class="form-error">There were errors with your submission. This field is required.</div>'; return; }}
  app.innerHTML='<div class="ashby-application-form-success application-success">'
    +'<h2>Application submitted</h2>'
    +'<p>Thank you for applying. Your application has been submitted. '
    +'Reference number: <strong>'+ref()+'</strong>.</p></div>';
}}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 3 and parts[2] == "application":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE.format(title="Mock Engineer").encode())
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b"not found")


if __name__ == "__main__":
    print(f"Mock Ashby (SPA, in-place success) on http://127.0.0.1:{PORT}"
          f"  (/<Board>/<id>/application?mode=ok|captcha|validation)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
