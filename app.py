"""Journal Rules Checker - web UI.  Run:  python app.py  then open http://127.0.0.1:5000"""

import os
import re
from itertools import groupby

from flask import Flask, render_template_string, request

from checker import run_checks

app = Flask(__name__)

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Journal Rules Checker</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b1f24;--mute:#5b6470;--line:#e2e5ea;--pass:#1a7f37;--fail:#c62828;--warn:#b26a00;--man:#3d5a99;--accent:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1b1e23;--ink:#e8eaed;--mute:#9aa3ad;--line:#2c3138;--pass:#4cc26b;--fail:#ff6b6b;--warn:#f0a73a;--man:#8aa8ef;--accent:#6aa9ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 20px}
form{display:flex;gap:8px;flex-wrap:wrap}input[type=url],input[type=text]{flex:1;min-width:220px;padding:11px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font-size:15px}
button{padding:11px 18px;border:0;border-radius:8px;background:var(--accent);color:#fff;font-weight:600;cursor:pointer}
button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
.summary{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.pill{padding:4px 10px;border-radius:99px;font-weight:600;font-size:13px;border:1px solid currentColor}
.pass{color:var(--pass)}.fail{color:var(--fail)}.warn{color:var(--warn)}.manual{color:var(--man)}
.score{font-size:34px;font-weight:700}
h2{font-size:17px;margin:26px 0 8px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
td{padding:10px;border-top:1px solid var(--line);vertical-align:top}tr:first-child td{border-top:0}
td.id{width:52px;color:var(--mute);font-weight:600}td.st{width:110px}
.rule{font-weight:600}.detail{color:var(--mute);margin-top:3px;word-break:break-word}
.ev a{color:var(--accent);font-size:13px;margin-right:10px;word-break:break-all}
.err{color:var(--fail)}details{margin-top:10px;color:var(--mute)}
.loading{display:none;color:var(--mute);margin-top:10px}
.legend{color:var(--mute);font-size:13px;margin-top:8px}
@media print{form,.noprint{display:none}body{background:#fff}}
@media (max-width:600px){td.id{display:none}td.st{width:80px}}
</style></head><body><div class="wrap">
<h1>Journal Rules Checker</h1>
<p class="sub">Checks a journal website against the Ministry of Higher Education and Scientific Research controls for reputable peer-reviewed journals (circular 14838/4, 23-12-2025) and the editorial boards conference recommendations (9420, 26-01-2026).</p>
<form method="post" onsubmit="document.getElementById('ld').style.display='block'">
 <input type="text" name="url" placeholder="Paste the journal website link, e.g. https://journal.uobaghdad.edu.iq" value="{{ url or '' }}" required>
 <button type="submit">Check journal</button>
</form>
<div class="loading" id="ld">Reading the journal website. This takes 20 to 60 seconds...</div>
{% if report %}
 {% if report.error %}<div class="card err">{{ report.error }}</div>{% else %}
 <div class="card">
  <div class="summary">
   <div><div class="score">{{ report.score }}%</div><div class="legend">of automatic checks passed</div></div>
   <span class="pill pass">{{ report.counts.get('pass',0) }} pass</span>
   <span class="pill fail">{{ report.counts.get('fail',0) }} fail</span>
   <span class="pill warn">{{ report.counts.get('warn',0) }} check</span>
   <span class="pill manual">{{ report.counts.get('manual',0) }} confirm by hand</span>
   <button class="ghost noprint" onclick="window.print()">Print / save PDF</button>
  </div>
  <p style="margin:10px 0 0"><b>{{ report.title }}</b><br><a href="{{ report.url }}" target="_blank" rel="noopener">{{ report.url }}</a> · {{ report.pages_read }} pages read</p>
  <div class="legend">Pass: rule met. Fail: not found or not met. Check: partly found, look again. Confirm by hand: can't be verified from the website.</div>
 </div>
 {% for section, rows in groups %}
  <h2>{{ section }}</h2>
  <table>{% for r in rows %}
   <tr><td class="id">{{ r.rid }}</td><td class="st"><span class="pill {{ r.status }}">{{ labels[r.status] }}</span></td>
   <td><div class="rule">{{ r.rule }}</div><div class="detail">{{ r.detail }}</div>
   {% if r.evidence %}<div class="ev">{% for u, t in r.evidence %}{% if u and u.startswith('http') %}<a href="{{ u }}" target="_blank" rel="noopener" title="{{ t }}">{{ (t or u)[:70] }}</a>{% endif %}{% endfor %}</div>{% endif %}</td></tr>
  {% endfor %}</table>
 {% endfor %}
 {% if report.board.members %}
 <details><summary>Editorial board as read ({{ report.board.members|length }} members)</summary>
 <table>{% for m in report.board.members %}<tr><td>{{ m.text }}</td><td class="st">{{ m.country or '?' }}</td><td class="st">{{ m.rank or '?' }}</td></tr>{% endfor %}</table></details>
 {% endif %}
 <details><summary>Pages read ({{ report.pages|length }})</summary><ul>{% for u, t in report.pages %}<li><a href="{{ u }}" target="_blank" rel="noopener">{{ t }}</a></li>{% endfor %}</ul>
 {% if report.errors %}<p>Could not open: {{ report.errors|join('; ') }}</p>{% endif %}</details>
 {% endif %}
{% endif %}
</div></body></html>"""

LABELS = {"pass": "Pass", "fail": "Fail", "warn": "Check", "manual": "By hand"}


@app.route("/", methods=["GET", "POST"])
def index():
    url = request.form.get("url", "").strip() if request.method == "POST" else request.args.get("url", "").strip()
    report, groups = None, []
    if url:
        report = run_checks(url)
        order = ["General controls (14838, Part 1)", "Editorial board (14838, Part 2)", "Website (14838, Part 3)", "Recommendations (9420)"]
        rows = sorted(report["results"], key=lambda r: (order.index(r["section"]), r["rid"][0], int(re.sub(r"\D", "", r["rid"]) or 0), r["rid"]))
        groups = [(k, list(g)) for k, g in groupby(rows, key=lambda r: r["section"])]
    return render_template_string(PAGE, url=url, report=report, groups=groups, labels=LABELS)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
