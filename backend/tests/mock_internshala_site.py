"""Local MOCK of Internshala's login + application pages — TEST ONLY.

This exists so the live auto-submit harness (app/adapters/internshala_submit.py)
can be verified end-to-end WITHOUT touching real internshala.com (whose ToS
disallows automation). The DOM ids/classes here mirror the submitter's default
selectors so no selector override is needed.

Run:  python tests/mock_internshala_site.py 8011
Pages:
  GET /login/student            → login form (#email/#password/#login_submit)
  GET /internship/detail/<...>  → listing with #easy_apply_button → #cover_letter + #submit
"""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOGIN_PAGE = """<!doctype html><html><head><title>Login - Internshala (mock)</title></head>
<body><div id="content">
  <h1>Student Login</h1>
  <input id="email" name="email" placeholder="Email"/>
  <input id="password" name="password" type="password" placeholder="Password"/>
  <button id="login_submit" type="button" onclick="doLogin()">Login</button>
</div>
<script>
function doLogin(){
  var e=document.getElementById('email').value, p=document.getElementById('password').value;
  if(e && p){ document.getElementById('content').innerHTML =
      '<div id="user_dropdown">Hi, '+e+'</div><p>Signed in.</p>'; }
  else { document.getElementById('content').innerHTML +=
      '<div class="error_message">Invalid credentials</div>'; }
}
</script></body></html>"""

DETAIL_PAGE = """<!doctype html><html><head><title>Internship - Internshala (mock)</title></head>
<body><div id="content">
  <h1>Software Engineering Intern — TechCorp India (mock)</h1>
  <button id="easy_apply_button" type="button" onclick="showForm()">Apply now</button>
  <div id="apply_form" style="display:none">
    <textarea id="cover_letter" name="cover_letter" placeholder="Cover letter"></textarea>
    <button id="submit" type="button" onclick="doSubmit()">Submit application</button>
  </div>
</div>
<script>
function showForm(){ document.getElementById('apply_form').style.display='block'; }
function doSubmit(){
  var cl=(document.getElementById('cover_letter').value||'').trim();
  if(!cl){ alert('cover letter required'); return; }
  document.getElementById('content').innerHTML =
    '<div class="application_success">Application submitted successfully! '+
    'Application ID: ISH-MOCK-77421</div>';
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        if self.path.startswith("/login"):
            self._send(LOGIN_PAGE)
        elif "/internship/detail" in self.path or "/job/detail" in self.path:
            self._send(DETAIL_PAGE)
        else:
            self._send("<html><body>mock internshala</body></html>")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8011
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
