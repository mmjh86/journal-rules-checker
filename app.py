"""مدقق ضوابط المجلات العلمية - واجهة الويب.  التشغيل:  python app.py  ثم افتح http://127.0.0.1:5000"""

import os
import re

from flask import Flask, render_template_string, request

from checker import ar, run_checks

app = Flask(__name__)

# نص الضوابط كما ورد في التعاميم
SECTIONS = [
    ("General controls (14838, Part 1)", "أولاً: ضوابط عامة", "ضوابط استحداث وإصدار المجلات العلمية الرصينة المحكمة، التعميم ب ت 14838/4 في 2025/12/23"),
    ("Editorial board (14838, Part 2)", "ثانياً: ضوابط هيئة التحرير", "التعميم ب ت 14838/4 في 2025/12/23"),
    ("Website (14838, Part 3)", "ثالثاً: الموقع", "التعميم ب ت 14838/4 في 2025/12/23"),
    ("Recommendations (9420)", "توصيات المؤتمر الأول لهيئات تحرير المجلات العراقية", "التعميم 9420-1410 في 2026/1/26"),
]

RULES_AR = {
    "A1": "يحق لأي جهة حكومية، مؤسسة علمية، مراكز الدراسات المؤسسة وفق القانون أو جمعية علمية تعنى بالبحث العلمي أو النشر الأكاديمي التقدم بطلب إلى دائرة البحث والتطوير لاستحداث مجلة علمية محكمة.",
    "A2": "تتعهد جهة الإصدار بتوفير التخصيص المالي لاستحداث وديمومة إصدار أعداد المجلة ويثبت ذلك بكتاب رسمي.",
    "A3": "تلتزم جهة الإصدار بفهرسة ورفع البحوث التي تنشر في المجلة في موقع المجلات الأكاديمية العراقية.",
    "A4": "تعتمد المجلات المفهرسة في قواعد بيانات سكوبس وكلاريفيت مع الطلب من ناشر المجلة إجراء التعديلات المطلوبة على المجلة وفق تعليمات دائرة البحث والتطوير.",
    "A5": "يجب أن يكون للمجلة رقم معياري دولي إلكتروني أو مطبوع أو كليهما على أن يكون مسجلاً باسم العراق.",
    "A6": "أن تكون المجلة حاصلة على رقم إيداع من دار الكتب والوثائق في بغداد ويكون مثبتاً على الغلاف الخارجي لها.",
    "A7": "يتم تدقيق المجلة إلكترونياً (من خلال موقع المجلة) مع تقديم نسخة ورقية وإلكترونية بصيغة PDF للعدد الأول.",
    "A9": "يجب أن تكون المجلة بتخصص واحد فقط (مثال: علوم الحاسبات، اللغة العربية، الهندسة المدنية).",
    "A10": "لا يتجاوز نشر المجلة 60 بحثاً سنوياً قبل الفهرسة في إحدى المستودعات (سكوبس أو كلاريفيت).",
    "A11": "تنشر المجلة على الأقل عدداً واحداً سنوياً.",
    "A12": "لا يتجاوز نشر أعضاء هيئة التحرير نسبة 10% من العدد الكلي لبحوث العدد الواحد.",
    "A13": "أن يتلاءم اسم المجلة لغوياً مع تخصصها العام أو الدقيق ويكون فريداً (لا يتطابق مع مجلات أخرى).",
    "A14": "أن تعتمد المجلة أحد برامج فحص الاستلال المعتمدة لفحص البحوث المقدمة للنشر أو حسب توجيهات دائرة البحث والتطوير.",
    "A15": "أن تمتلك المجلة قالباً للبحوث خاصاً بها متوفراً على موقعها الإلكتروني مثبتاً فيه شعار المجلة وشعار الناشر، ومثبتاً فيه نوع تنسيق المصادر المعتمد (IEEE, APA, ...).",
    "A16": "للمجلات التي تنشر باللغة العربية، يجب ترجمة أسماء الباحثين، مكان عملهم، الكلمات المفتاحية، عنوان البحث، والخلاصة للغة الإنكليزية.",
    "A17": "أن تحتوي المجلة على سياسة نشر واضحة وتفصيلية تبين التزامها بتطبيق أخلاقيات البحث العلمي وبنود لجنة أخلاقيات النشر (Committee On Publication Ethics).",
    "A18": "ضرورة التزام المجلة بعملية التحكيم الشفاف والمراجعة العلمية المتخصصة (Peer-Reviewed Process).",
    "A19": "يلتزم كل من الناشر للمجلة وإدارة المجلة بكافة تعاميم وتعليمات دائرة البحث والتطوير الخاصة بالمجلات والبحث العلمي وكذلك التعليمات الخاصة بالمصادقة على رئيس التحرير ومدير التحرير وأعضاء التحرير.",
    "B1": "يجب أن لا يقل عدد الأعضاء عن 20 عضواً في تخصص المجلة وبنسبة 75% من خارج العراق و25% من داخل العراق ومن بلدان وقارات مختلفة (الحد الأعلى 10% من كل بلد خارج العراق).",
    "B2": "لا يقل معامل H-index (في سكوبس) للتخصصات العلمية عن 5 والإنسانية عن 2، وفي حال تعذر ذلك في التخصصات الإنسانية بالإمكان الاستعانة بأساتذة دوليين في هيئة التحرير.",
    "B3": "لا يقل معامل H-index (في سكوبس) لرئيس ومدير التحرير عن 6 للتخصصات العلمية و2 للتخصصات الإنسانية، أما في حالة تعذر الاختيار بناءً على H-index يصار إلى اختيار التدريسي ذي السمعة العلمية المتميزة والنتاج العلمي الأعلى.",
    "B4": "يكون اللقب العلمي لأعضاء هيئة التحرير مدرس صعوداً، وفي حال وجدت ألقاب علمية أعلى من مدرس لا ضير في اعتمادها.",
    "B5": "يكون اللقب العلمي لرئيس ومدير التحرير أستاذ مساعد صعوداً.",
    "B6": "يفضل أن تكون هناك نسبة بين المدرس والأستاذ المساعد (30% - 40%) لأعضاء هيئة التحرير.",
    "C1": "يجب أن يكون الموقع باللغتين العربية والإنكليزية.",
    "C2": "يجب أن يكون للمجلة موقع إلكتروني مستقل عن موقع المجلات في دائرة البحث والتطوير.",
    "C3": "يجب أن يكون للمجلة DOI.",
    "C4a": "يجب أن يحتوي الموقع على: نطاق المجلة.",
    "C4b": "يجب أن يحتوي الموقع على: هيئة التحرير.",
    "C4c": "يجب أن يحتوي الموقع على: أخلاقيات النشر.",
    "C4d": "يجب أن يحتوي الموقع على: دليل الباحثين.",
    "C4e": "يجب أن يحتوي الموقع على: دليل المقيمين.",
    "C4f": "يجب أن يحتوي الموقع على: الفهارس التي فهرست فيها المجلة.",
    "C4g": "يجب أن يحتوي الموقع على: التواصل.",
    "C4h": "يجب أن يحتوي الموقع على: الأرشفة (archiving).",
    "C4i": "يجب أن يحتوي الموقع على: أسعار النشر في المجلة وهل يوجد تخفيض لفئة معينة.",
    "D1": "منع الجمع بين المناصب الإدارية (رئيس جامعة، عميد، رئيس قسم) وعضوية رئاسة التحرير أو مدير التحرير لتفادي تضارب المصالح.",
    "D4": "تقليل نشر أبحاث أعضاء هيئة التحرير في مجلتهم ومنع الاستشهاد الذاتي القسري.",
    "D6": "خطة زمنية (3 – 5 سنوات) لدخول (Scopus / Clarivate) مع لجنة متابعة.",
    "D10": "التوصية بإدخال تقنيات وبرامج حديثة في التعامل مع النشر ومن ضمنها خدمات الـ(AI).",
}
LETTERS = {"a": "أ", "b": "ب", "c": "ج", "d": "د", "e": "هـ", "f": "و", "g": "ز", "h": "ح", "i": "ط"}
LABELS = {"pass": "مستوفى", "fail": "غير مستوفى", "warn": "يحتاج مراجعة", "manual": "يُتحقق يدوياً"}


def rule_no(rid: str) -> str:
    """رقم الفقرة كما في التعميم، مثل 4 أو 4/أ."""
    m = re.match(r"[A-D](\d+)([a-i]?)$", rid)
    if not m:
        return rid
    return m.group(1) + ("/" + LETTERS[m.group(2)] if m.group(2) else "")


PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدقق ضوابط المجلات العلمية</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">
<style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#16202b;--mute:#5a6676;--line:#dde3ea;--accent:#14598f;--accent-ink:#fff;
--pass:#17763a;--pass-bg:#e7f4ec;--fail:#b3261e;--fail-bg:#fbeae9;--warn:#9a5b00;--warn-bg:#fdf2e1;--man:#3b5596;--man-bg:#eaeef9}
@media (prefers-color-scheme:dark){:root{--bg:#11161c;--card:#19202a;--ink:#e6ebf1;--mute:#97a3b2;--line:#2a3441;--accent:#6eb0ec;--accent-ink:#0d1620;
--pass:#5fcf87;--pass-bg:#15301f;--fail:#ff8a80;--fail-bg:#3a1a19;--warn:#f2b35a;--warn-bg:#352812;--man:#9db4f2;--man-bg:#1c2540;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 "IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 16px 60px}
.ministry{color:var(--mute);font-size:14px;margin:0}
h1{font-size:28px;margin:2px 0 6px}
.sub{color:var(--mute);margin:0 0 20px}
form{display:flex;gap:8px;flex-wrap:wrap}
input[type=text]{flex:1;min-width:220px;padding:11px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit;direction:ltr;text-align:left}
button{padding:11px 20px;border:0;border-radius:8px;background:var(--accent);color:var(--accent-ink);font:600 16px inherit;font-family:inherit;cursor:pointer}
button.ghost{background:transparent;color:var(--accent);border:1px solid var(--line)}
input:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin:18px 0}
.summary{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.pill{padding:3px 11px;border-radius:99px;font-weight:600;font-size:13px;white-space:nowrap}
.pass{color:var(--pass);background:var(--pass-bg)}.fail{color:var(--fail);background:var(--fail-bg)}
.warn{color:var(--warn);background:var(--warn-bg)}.manual{color:var(--man);background:var(--man-bg)}
.score{font-size:38px;font-weight:700;line-height:1}
.legend{color:var(--mute);font-size:13px;margin-top:6px}
h2{font-size:18px;margin:28px 0 2px}.src{color:var(--mute);font-size:13px;margin:0 0 8px}
.rules{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.rule{display:grid;grid-template-columns:52px 120px minmax(0,1fr);gap:12px;padding:12px 14px;border-top:1px solid var(--line)}
.rule:first-child{border-top:0}
.no{color:var(--mute);font-weight:600}
.st{justify-self:start;align-self:start}
.rt{font-weight:600}.rd{color:var(--mute);margin-top:4px;overflow-wrap:anywhere}
.ev{margin-top:4px;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px}
.ev a{color:var(--accent);overflow-wrap:anywhere}
.err{color:var(--fail)}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:14px}
summary{cursor:pointer;font-weight:600}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin-top:8px}
td,th{padding:7px 8px;border-top:1px solid var(--line);text-align:right;vertical-align:top}th{color:var(--mute);border-top:0}
td.en{direction:ltr;text-align:left}
.loading{display:none;color:var(--mute);margin-top:10px}
@media print{form,.noprint{display:none}body{background:#fff}}
@media (max-width:640px){.rule{grid-template-columns:auto minmax(0,1fr)}.no{grid-column:1/-1}}
</style></head><body><div class="wrap">
<p class="ministry">وزارة التعليم العالي والبحث العلمي، دائرة البحث والتطوير</p>
<h1>مدقق ضوابط المجلات العلمية</h1>
<p class="sub">يفحص موقع المجلة وفق ضوابط استحداث وإصدار المجلات العلمية الرصينة المحكمة (التعميم ب ت 14838/4 في 2025/12/23) وتوصيات المؤتمر الأول لهيئات تحرير المجلات العراقية (التعميم 9420 في 2026/1/26).</p>
<form method="post" onsubmit="document.getElementById('ld').style.display='block'">
 <input type="text" name="url" placeholder="https://journal.uobaghdad.edu.iq" value="{{ url or '' }}" required aria-label="رابط موقع المجلة">
 <button type="submit">افحص المجلة</button>
</form>
<div class="loading" id="ld">جارٍ قراءة موقع المجلة. يستغرق الفحص من 20 إلى 60 ثانية...</div>
{% if report %}
 {% if report.error %}<div class="card err">{{ report.error }}</div>{% else %}
 <div class="card">
  <div class="summary">
   <div><div class="score">{{ report.score }}%</div><div class="legend">من الفحوص التلقائية مستوفاة</div></div>
   <span class="pill pass">{{ report.counts.get('pass',0) }} مستوفى</span>
   <span class="pill fail">{{ report.counts.get('fail',0) }} غير مستوفى</span>
   <span class="pill warn">{{ report.counts.get('warn',0) }} يحتاج مراجعة</span>
   <span class="pill manual">{{ report.counts.get('manual',0) }} يُتحقق يدوياً</span>
   <button class="ghost noprint" onclick="window.print()">طباعة / حفظ PDF</button>
  </div>
  <p style="margin:12px 0 0"><b dir="auto">{{ report.title }}</b><br><a href="{{ report.url }}" target="_blank" rel="noopener" dir="ltr">{{ report.url }}</a> · قُرئت {{ report.pages_read }} صفحة</p>
  <div class="legend">مستوفى: الضابط متحقق في الموقع. غير مستوفى: غير موجود أو مخالف. يحتاج مراجعة: موجود جزئياً. يُتحقق يدوياً: لا يمكن التحقق منه من الموقع.</div>
 </div>
 {% for title, src, rows in groups %}
  <h2>{{ title }}</h2><p class="src">{{ src }}</p>
  <div class="rules">{% for r in rows %}
   <div class="rule"><div class="no">{{ r.no }}</div><div class="st"><span class="pill {{ r.status }}">{{ labels[r.status] }}</span></div>
   <div><div class="rt">{{ r.rule_ar }}</div><div class="rd" dir="auto">{{ r.detail }}</div>
   {% if r.evidence %}<div class="ev">{% for u, t in r.evidence %}{% if u and u.startswith('http') %}<a href="{{ u }}" target="_blank" rel="noopener" dir="auto" title="{{ t }}">{{ (t or u)[:70] }}</a>{% endif %}{% endfor %}</div>{% endif %}</div></div>
  {% endfor %}</div>
 {% endfor %}
 {% if report.board.members %}
 <details><summary>هيئة التحرير كما قُرئت من الموقع ({{ report.board.members|length }} عضواً)</summary>
 <div class="tbl"><table><tr><th>العضو</th><th>البلد</th><th>اللقب العلمي</th></tr>
 {% for m in report.board.members %}<tr><td class="en">{{ m.text }}</td><td>{{ ar(m.country) or '؟' }}</td><td>{{ ar(m.rank) or '؟' }}</td></tr>{% endfor %}</table></div></details>
 {% endif %}
 <details><summary>الصفحات التي قُرئت ({{ report.pages|length }})</summary><ul>{% for u, t in report.pages %}<li><a href="{{ u }}" target="_blank" rel="noopener" dir="auto">{{ t }}</a></li>{% endfor %}</ul>
 {% if report.errors %}<p dir="ltr">{{ report.errors|join('; ') }}</p>{% endif %}</details>
 {% endif %}
{% endif %}
</div></body></html>"""


@app.route("/", methods=["GET", "POST"])
def index():
    url = request.form.get("url", "").strip() if request.method == "POST" else request.args.get("url", "").strip()
    report, groups = None, []
    if url:
        report = run_checks(url)
        for key, title, src in SECTIONS:
            rows = [dict(r, rule_ar=RULES_AR.get(r["rid"], r["rule"]), no=rule_no(r["rid"]))
                    for r in report.get("results", []) if r["section"] == key]
            rows.sort(key=lambda r: (int(re.sub(r"\D", "", r["rid"]) or 0), r["rid"]))
            if rows:
                groups.append((title, src, rows))
    return render_template_string(PAGE, url=url, report=report, groups=groups, labels=LABELS, ar=ar)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
