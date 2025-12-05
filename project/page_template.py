def page_template(bg_color, extra_html=""):
    # Improved typography and a beautiful animated background.
    # This is a plain triple-quoted string (not an f-string) to avoid JS/template interpolation issues.
    template = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Password Generator</title>
<meta name="viewport" content="width=device-width,initial-scale=1">

<!-- Try to load a nice web font; browser will fallback if offline -->
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">

<style>
:root{
  --bg: BG;
  --card: rgba(255,255,255,0.92);
  --card-dark: rgba(12,18,28,0.75);
  --muted: #6b7280;
  --accent: #6366f1;
  --glass-border: rgba(255,255,255,0.14);
}

/* Reset / base */
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family: "Poppins", Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  color:#0f172a;
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  background: linear-gradient(180deg, rgba(10,16,30,0.02), rgba(230,238,252,0.02));
  overflow:auto;
}

/* big scenic background with soft moving gradient blobs */
.background {
  position:fixed;
  inset:0;
  z-index:0;
  pointer-events:none;
  background: radial-gradient(800px 600px at 10% 20%, rgba(99,102,241,0.12), transparent 12%),
              radial-gradient(700px 500px at 85% 80%, rgba(6,182,212,0.09), transparent 12%),
              linear-gradient(120deg, rgba(99,102,241,0.06), rgba(6,182,212,0.04));
  filter: blur(22px) saturate(115%);
  transform: translateZ(0);
  animation: floatBg 14s ease-in-out infinite;
}
@keyframes floatBg {
  0% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-16px) scale(1.02); }
  100% { transform: translateY(0) scale(1); }
}

/* container */
.wrap{width:100%;max-width:980px;padding:28px;z-index:2}
.card{
  background: var(--card);
  border-radius:18px;
  padding:26px;
  box-shadow: 0 18px 50px rgba(2,6,23,0.12);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(6px) saturate(120%);
}

/* header */
.header-row{display:flex;align-items:center;gap:16px;justify-content:space-between;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}
.logo{
  width:48px;height:48px;border-radius:12px;
  background: linear-gradient(135deg,var(--accent),#06b6d4);
  display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:20px;
  box-shadow: 0 6px 18px rgba(99,102,241,0.18);
}
h1{margin:0;font-size:20px}
.lead{margin:6px 0 18px 0;color:var(--muted)}

/* form layout */
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.controls{margin-top:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
label{display:block;font-weight:600;color:#111827;margin-bottom:6px;font-size:13px}
input[type=number], select, input[type=password]{
  padding:10px;border-radius:10px;border:1px solid #e6e9ee;min-width:120px;font-size:14px;
}
button{
  padding:10px 14px;border-radius:10px;border:none;background:var(--accent);color:white;font-weight:700;cursor:pointer;
  box-shadow: 0 8px 22px rgba(99,102,241,0.14);
}
button.ghost{background:transparent;color:var(--accent);border:1px solid rgba(99,102,241,0.12);box-shadow:none}

/* results */
.results{margin-top:18px}
.pwd-item{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px;border-radius:12px;
  background: linear-gradient(90deg, rgba(99,102,241,0.06), rgba(6,182,212,0.04));
}
code.pwd{font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace; font-size:14px; background:transparent; padding:6px 8px; border-radius:8px; max-width:78%; overflow-wrap:anywhere}
.meta{color:var(--muted);font-size:13px;margin-top:12px}
.footer{text-align:center;color:var(--muted);margin-top:18px;font-size:13px}

/* strength meter and small touches */
.strength-bar{height:10px;background:#f3f4f6;border-radius:8px;overflow:hidden;width:220px}
.strength-fill{height:100%;width:0;background:linear-gradient(90deg,#ef4444,#f59e0b,#10b981);transition:width 360ms}

/* small responsive */
@media (max-width:720px){
  .row{flex-direction:column;align-items:stretch}
  .brand h1{font-size:18px}
}

/* dark mode adjustments (JS toggles .dark on body) */
body.dark { background: linear-gradient(180deg, #071028, #071428); color: #e6eefc; }
body.dark .card { background: var(--card-dark); border: 1px solid rgba(255,255,255,0.04) }
body.dark .meta, body.dark .footer, body.dark .lead { color: #cbd5e1 }
body.dark .logo { filter: drop-shadow(0 8px 24px rgba(2,6,23,0.4)); }

/* subtle glass highlight at top */
.card:before { content:""; position:absolute; left:50%; transform:translateX(-50%); top:20px; width:220px; height:110px; border-radius:50%; filter: blur(46px); opacity:0.03; pointer-events:none; }
</style>
</head>
<body>
<div class="background" aria-hidden="true"></div>

<div class="wrap">
  <div class="card" id="card">
    <div class="header-row">
      <div class="brand">
        <div class="logo">PW</div>
        <div>
          <h1>Secure Password Studio</h1>
          <div class="lead">Generate, copy, export and save passwords — locally on your machine.</div>
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="ghost" id="randomizeBtn">Randomize background</button>
        <button class="ghost" id="toggleDark">Toggle dark</button>
      </div>
    </div>

    <form id="genForm" method="POST" action="/generate" style="margin-top:14px">
      <div class="row">
        <div>
          <label>How many characters?</label>
          <input type="number" name="length" min="4" max="256" value="12" required>
        </div>

        <div>
          <label>How many passwords?</label>
          <input type="number" name="count" min="1" max="50" value="1" required>
        </div>

        <div style="min-width:180px">
          <label>Symbols</label>
          <select name="symbols">
            <option value="yes" selected>Include symbols</option>
            <option value="no">Exclude symbols</option>
          </select>
        </div>

        <div style="flex:1"></div>

        <div style="align-self:end">
          <div class="controls">
            <button type="submit">Generate</button>
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

    <div class="meta">Passwords logged to <code>passwords.log</code>. Last generation saved to <code>last_generation.json</code>.</div>
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

// randomize: reload root to generate a new bg color from server
document.getElementById('randomizeBtn').addEventListener('click', function(){ location.href = '/'; });

// dark toggle
const toggle = document.getElementById('toggleDark');
toggle.addEventListener('click', function(){
  document.body.classList.toggle('dark');
  document.getElementById('card').classList.toggle('dark');
});

// Copy helper used in server-generated result blocks
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
    # replace placeholders safely
    return template.replace("BG", bg_color).replace("EXTRA_CONTENT", extra_html)
