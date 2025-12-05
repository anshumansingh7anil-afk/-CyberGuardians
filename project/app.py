#!/usr/bin/env python3
"""
Enhanced Password Generator Web App (single-file)

- Requires qrcode[pil] and reportlab for QR / PDF endpoints (you installed them).
- Run: python app.py
- Visit: http://127.0.0.1:8000/
"""

import http.server
import secrets
import string
import json
from urllib.parse import parse_qs, urlparse, parse_qsl
from datetime import datetime, timedelta
from pathlib import Path
import html
import hashlib
import getpass
import sys
import http.cookies
import csv
import io

# External libs (installed)
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HOST = "127.0.0.1"
PORT = 8000
LOG_FILE = Path("passwords.log")
LAST_FILE = Path("last_generation.json")
ADMIN_STORE = Path("admin.json")
SESS_FILE = Path("sessions.json")

# Ensure files exist
if not LOG_FILE.exists():
    LOG_FILE.write_text("", encoding="utf-8")
if not SESS_FILE.exists():
    SESS_FILE.write_text("{}", encoding="utf-8")


# ---------- Utilities ----------
def rand_bg():
    r = secrets.randbelow(156) + 100
    g = secrets.randbelow(156) + 100
    b = secrets.randbelow(156) + 100
    return f"rgb({r},{g},{b})"


def generate_password(length, include_symbols=True):
    chars = string.ascii_letters + string.digits
    if include_symbols:
        chars += string.punctuation
    return "".join(secrets.choice(chars) for _ in range(length))


def save_log(entry: dict):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_logs():
    out = []
    try:
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            out.append(json.loads(line))
    except Exception:
        pass
    return out


def save_last(entry: dict):
    LAST_FILE.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")


def read_last():
    try:
        return json.loads(LAST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------- Admin helpers (very simple) ----------
def init_admin_interactive():
    print("Create admin user (interactive).")
    uname = input("Username: ").strip()
    pw = getpass.getpass("Password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw != pw2:
        print("Passwords do not match. Exiting.")
        return
    salt = secrets.token_hex(16)
    phash = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    ADMIN_STORE.write_text(json.dumps({"username": uname, "salt": salt, "password_hash": phash}), encoding="utf-8")
    print("Admin created.")


def verify_admin(username, password):
    if not ADMIN_STORE.exists():
        return False
    data = json.loads(ADMIN_STORE.read_text(encoding="utf-8"))
    if data.get("username") != username:
        return False
    salt = data.get("salt", "")
    stored = data.get("password_hash", "")
    calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return calc == stored


def load_sessions():
    try:
        return json.loads(SESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_sessions(sessions):
    SESS_FILE.write_text(json.dumps(sessions), encoding="utf-8")


def create_session():
    token = secrets.token_urlsafe(24)
    expiry = (datetime.utcnow() + timedelta(hours=3)).isoformat()
    s = load_sessions()
    s[token] = expiry
    save_sessions(s)
    return token


def is_authenticated(cookie_header):
    if not cookie_header:
        return False
    cookie = http.cookies.SimpleCookie()
    cookie.load(cookie_header)
    if "MYSITE_ADMIN" not in cookie:
        return False
    token = cookie["MYSITE_ADMIN"].value
    s = load_sessions()
    expiry = s.get(token)
    if not expiry:
        return False
    if datetime.fromisoformat(expiry) < datetime.utcnow():
        # expired
        del s[token]
        save_sessions(s)
        return False
    return True


def clear_session(token):
    s = load_sessions()
    if token in s:
        del s[token]
        save_sessions(s)


# ---------- QR and PDF helpers ----------
def make_qr_png_bytes(text: str) -> bytes:
    """
    Return PNG bytes for a QR code encoding `text`.
    """
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def make_pdf_bytes(entry: dict) -> bytes:
    """
    Build a simple PDF listing the generated passwords and parameters.
    """
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    width, height = A4
    margin = 40
    y = height - margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "Generated Passwords")
    c.setFont("Helvetica", 10)
    y -= 24
    info = f"Timestamp: {entry.get('timestamp','')}, length: {entry.get('length')}, count: {entry.get('count')}, symbols: {entry.get('include_symbols')}"
    for line in split_text(info, 92):
        c.drawString(margin, y, line)
        y -= 12
    y -= 8
    c.setFont("Helvetica", 11)
    c.drawString(margin, y, "Passwords:")
    y -= 18
    for p in entry.get("passwords", []):
        # wrap if too long
        for part in split_text(p, 90):
            if y < margin + 40:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 11)
            c.drawString(margin + 8, y, part)
            y -= 12
        y -= 6
    c.showPage()
    c.save()
    bio.seek(0)
    return bio.getvalue()


def split_text(s, width_chars=80):
    """Naive splitter for PDF line wrapping."""
    out = []
    while s:
        out.append(s[:width_chars])
        s = s[width_chars:]
    return out


# ---------- Templates (avoid f-strings inside JS) ----------
def page_template(bg_color, extra_html=""):
    template = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Password Generator</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{ --bg: BG; --card:#ffffff; --muted:#6b7280; --accent:#6366f1; }
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,Segoe UI,Roboto,Arial;background:linear-gradient(180deg,var(--bg),#e6eefc);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.wrap{width:100%;max-width:920px}
.card{background:var(--card);padding:22px;border-radius:16px;box-shadow:0 12px 40px rgba(2,6,23,0.12)}
h1{margin:0 0 6px 0}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.controls{margin-top:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
input[type=number], select, input[type=password]{padding:10px;border-radius:8px;border:1px solid #e6e9ee}
button{background:var(--accent);color:white;padding:10px 14px;border-radius:10px;border:none;cursor:pointer;font-weight:700}
button.ghost{background:transparent;color:var(--accent);border:2px solid rgba(99,102,241,0.12)}
.results{margin-top:18px}
.pwd-item{display:flex;gap:8px;align-items:center;justify-content:space-between;padding:12px;border-radius:10px;background:linear-gradient(90deg,rgba(99,102,241,0.06),rgba(6,182,212,0.04));margin-bottom:8px}
code.pwd{font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;background:transparent;padding:6px 8px;border-radius:6px;max-width:78%;overflow-wrap:anywhere;word-break:break-all}
.meta{color:var(--muted);font-size:13px;margin-top:8px}
.footer{text-align:center;color:var(--muted);margin-top:16px;font-size:13px}
.switch{display:flex;align-items:center;gap:8px}
.strength-bar{height:10px;background:#eee;border-radius:6px;overflow:hidden;width:220px}
.strength-fill{height:100%;width:0;background:linear-gradient(90deg,#ef4444,#f59e0b,#10b981);transition:width 300ms}
.darkmode{background:#0b1220;color:#e6eefc}
</style>
</head>
<body>
<div class="wrap">
  <div class="card" id="card">
    <h1>🔐 Modern Password Generator</h1>
    <p class="lead">Generate strong passwords locally. QR & PDF available for the last generation.</p>

    <form id="genForm" method="POST" action="/generate">
      <div class="row">
        <div>
          <label>How many characters?</label><br>
          <input type="number" name="length" min="4" max="256" value="12" required>
        </div>

        <div>
          <label>How many passwords?</label><br>
          <input type="number" name="count" min="1" max="50" value="1" required>
        </div>

        <div style="min-width:160px">
          <label>Symbols</label><br>
          <select name="symbols">
            <option value="yes" selected>Include symbols</option>
            <option value="no">Exclude symbols</option>
          </select>
        </div>

        <div style="flex:1"></div>

        <div style="align-self:end">
          <div class="controls">
            <button type="submit">Generate</button>
            <button type="button" class="ghost" id="randomizeBtn">Randomize background</button>
            <button type="button" class="ghost" id="toggleDark">Dark mode</button>
          </div>
        </div>
      </div>
    </form>

    <div style="margin-top:12px">
      <div style="display:flex;align-items:center;gap:8px">
        <div class="strength-bar"><div id="strengthFill" class="strength-fill"></div></div>
        <div id="strengthText" style="color:var(--muted);font-size:13px">Strength</div>
      </div>
    </div>

    <div style="margin-top:12px">
      <a href="/download_txt"><button class="ghost" style="background:#f3f4f6;color:#111;border:none">Download all as TXT</button></a>
      <a href="/admin_login"><button class="ghost">Admin</button></a>
    </div>

    <div id="results" class="results">EXTRA_CONTENT</div>

    <div class="meta">Passwords logged to <code>passwords.log</code> (JSON lines). Last generation saved to <code>last_generation.json</code>.</div>
    <div class="footer">Made with Python • Local-only</div>
  </div>
</div>

<script>
// strength meter (client-side)
const lengthInput = document.querySelector('input[name="length"]');
const symSelect = document.querySelector('select[name="symbols"]');
const strengthFill = document.getElementById('strengthFill');
const strengthText = document.getElementById('strengthText');

function calcStrength(len, includeSymbols) {
  let score = 0;
  if (len >= 8) score += 1;
  if (len >= 12) score += 1;
  if (len >= 16) score += 1;
  if (includeSymbols) score += 1;
  return score; // 0-4
}
function updateStrength() {
  const len = parseInt(lengthInput.value || 0);
  const inc = symSelect.value === 'yes';
  const s = calcStrength(len, inc);
  const pct = (s / 4) * 100;
  strengthFill.style.width = pct + '%';
  if (s <= 1) {
    strengthText.textContent = 'Weak';
  } else if (s === 2) {
    strengthText.textContent = 'Fair';
  } else if (s === 3) {
    strengthText.textContent = 'Good';
  } else {
    strengthText.textContent = 'Strong';
  }
}
lengthInput.addEventListener('input', updateStrength);
symSelect.addEventListener('change', updateStrength);
updateStrength();

// randomize
document.getElementById('randomizeBtn').addEventListener('click', function(){ location.href = '/'; });

// dark toggle (simple)
const toggle = document.getElementById('toggleDark');
const card = document.getElementById('card');
toggle.addEventListener('click', function(){
  document.body.classList.toggle('darkmode');
  card.classList.toggle('darkmode');
});

// Copy utility used for generated results (server injects copy handlers)
function copyText(txt, btn) {
  navigator.clipboard.writeText(txt).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(()=> btn.textContent = orig, 1200);
  }, ()=> alert('Copy failed.'));
}
</script>

</body>
</html>
"""
    return template.replace("BG", bg_color).replace("EXTRA_CONTENT", extra_html)


# ---------- HTTP handler ----------
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "":
            page = page_template(rand_bg(), "")
            self._send_html(page)
            return
        if path == "/download_txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            txt = LOG_FILE.read_text(encoding="utf-8")
            self.send_header("Content-Length", str(len(txt.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(txt.encode("utf-8"))
            return
        if path == "/admin_login":
            htmlp = """<!doctype html><html><head><meta charset='utf-8'><title>Admin Login</title></head><body>
            <h2>Admin Login</h2>
            <form method="POST" action="/admin_login">
              <label>Username</label><input name="username"><br>
              <label>Password</label><input name="password" type="password"><br>
              <button type="submit">Login</button>
            </form>
            <p><a href="/">Back</a></p>
            </body></html>"""
            self._send_html(htmlp)
            return
        if path == "/admin":
            cookie_hdr = self.headers.get("Cookie", "")
            if not is_authenticated(cookie_hdr):
                self.send_response(303)
                self.send_header("Location", "/admin_login")
                self.end_headers()
                return
            logs = read_logs()
            rows_html = "<h2>Logs</h2>"
            rows_html += "<form method='POST' action='/admin'><button name='action' value='export_csv'>Export CSV</button> <button name='action' value='logout'>Logout</button></form>"
            rows_html += "<div style='margin-top:12px'>"
            for entry in reversed(logs[-200:]):
                ts = html.escape(entry.get("timestamp",""))
                length = entry.get("length")
                count = entry.get("count")
                include_symbols = entry.get("include_symbols")
                pwds = entry.get("passwords", [])
                rows_html += f"<div style='padding:8px;border-bottom:1px solid #eee'><strong>{ts}</strong> — len:{length} count:{count} symbols:{include_symbols}<br>"
                rows_html += "<ul>"
                for p in pwds:
                    rows_html += f"<li><code>{html.escape(p)}</code></li>"
                rows_html += "</ul></div>"
            rows_html += "</div><p><a href='/'>Back</a></p>"
            page = page_template(rand_bg(), rows_html)
            self._send_html(page)
            return
        if path == "/qr":
            # expects query param i (index), 0-based
            q = dict(parse_qsl(parsed.query))
            try:
                idx = int(q.get("i", "0"))
            except Exception:
                idx = 0
            last = read_last()
            if not last:
                self.send_error(404, "No last generation found.")
                return
            pwds = last.get("passwords", [])
            if idx < 0 or idx >= len(pwds):
                self.send_error(404, "Index out of range.")
                return
            png = make_qr_png_bytes(pwds[idx])
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)
            return
        if path == "/export_pdf":
            last = read_last()
            if not last:
                self.send_error(404, "No last generation found.")
                return
            pdf_bytes = make_pdf_bytes(last)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=generated_passwords.pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
        # fallback to static or 404
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/generate":
            try:
                cl = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(cl).decode("utf-8")
                params = parse_qs(raw)
                length = int(params.get("length", ["12"])[0])
                count = int(params.get("count", ["1"])[0])
                symbols_param = params.get("symbols", ["yes"])[0].lower()
                include_symbols = symbols_param != "no"
            except Exception:
                length, count, include_symbols = 12, 1, True

            length = max(4, min(256, length))
            count = max(1, min(50, count))

            pwds = [generate_password(length, include_symbols) for _ in range(count)]
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "length": length,
                "count": count,
                "include_symbols": include_symbols,
                "passwords": pwds
            }
            try:
                save_log(entry)
                save_last(entry)
            except Exception as e:
                print("Log error:", e)

            # build result HTML with links to QR and PDF
            extra = "<h2>Generated</h2>"
            extra += "<button onclick=\"(function(){navigator.clipboard.writeText(Array.from(document.querySelectorAll('code.pwd')).map(e=>e.textContent).join('\\n'))})()\">Copy All</button>"
            for i, p in enumerate(pwds):
                safe = html.escape(p)
                # URL for QR (index)
                qr_url = f"/qr?i={i}"
                extra += f"""<div class='pwd-item'><code class='pwd'>{safe}</code>
                <div style="display:flex;gap:8px;align-items:center">
                  <button onclick="(function(t,b){{navigator.clipboard.writeText(t).then(()=>{{b.textContent='Copied!';setTimeout(()=>b.textContent='Copy',1200);}},()=>alert('Copy failed'))}})('{safe}', this)">Copy</button>
                  <a href="{qr_url}" download="qr_{i}.png"><button class="ghost" type="button">QR</button></a>
                </div></div>"""

            # PDF link for the whole generation
            extra += "<div style='margin-top:10px'><a href='/export_pdf'><button class='ghost' type='button'>Download PDF</button></a></div>"

            # Show a hint about admin/export
            extra += "<div style='margin-top:10px'><em>QR and PDF are generated server-side using qrcode & reportlab.</em></div>"

            page = page_template(rand_bg(), extra)
            self._send_html(page)
            return

        if path == "/admin_login":
            cl = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(cl).decode("utf-8")
            params = parse_qs(raw)
            user = params.get("username", [""])[0]
            pwd = params.get("password", [""])[0]
            if verify_admin(user, pwd):
                token = create_session()
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.send_header("Set-Cookie", f"MYSITE_ADMIN={token}; Path=/; HttpOnly")
                self.end_headers()
            else:
                self.send_response(303)
                self.send_header("Location", "/admin_login")
                self.end_headers()
            return

        if path == "/admin":
            cl = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(cl).decode("utf-8")
            params = parse_qs(raw)
            action = params.get("action", [""])[0]
            cookie_hdr = self.headers.get("Cookie", "")
            if not is_authenticated(cookie_hdr):
                self.send_response(303)
                self.send_header("Location", "/admin_login")
                self.end_headers()
                return
            if action == "export_csv":
                logs = read_logs()
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow(["timestamp","length","count","include_symbols","passwords_joined"])
                for e in logs:
                    writer.writerow([e.get("timestamp",""), e.get("length",""), e.get("count",""), e.get("include_symbols",""), " | ".join(e.get("passwords",[]))])
                csv_text = out.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", "attachment; filename=logs.csv")
                self.send_header("Content-Length", str(len(csv_text.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(csv_text.encode("utf-8"))
                return
            if action == "logout":
                cookie = http.cookies.SimpleCookie()
                cookie.load(cookie_hdr)
                token = cookie["MYSITE_ADMIN"].value if cookie.get("MYSITE_ADMIN") else None
                if token:
                    clear_session(token)
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", "MYSITE_ADMIN=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
                self.end_headers()
                return

        # fallback
        self.send_response(404)
        self.end_headers()

    def _send_html(self, content):
        b = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "initadmin":
        init_admin_interactive()
        return
    print(f"Serving at http://{HOST}:{PORT}")
    server = http.server.HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    main()
