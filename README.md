# مدقق ضوابط المجلات العلمية

أدخل رابط موقع المجلة لتحصل على تقرير باللغة العربية يبين مدى استيفائها لضوابط استحداث وإصدار المجلات العلمية الرصينة المحكمة (التعميم ب ت 14838/4 في 2025/12/23) وتوصيات المؤتمر الأول لهيئات تحرير المجلات العراقية (التعميم 9420 في 2026/1/26). الموقع المنشور: https://journal-rules-checker.onrender.com

# Journal Rules Checker

Paste a journal's website link and get a report on how it meets the Iraqi Ministry of Higher Education
and Scientific Research controls for reputable peer-reviewed journals (circular 14838/4, 23-12-2025)
and the editorial boards conference recommendations (circular 9420, 26-01-2026).

## Run it

You need Python 3.10 or newer (python.org).

- **Windows:** double-click `run-windows.bat`.
- **Mac / Linux:** run `./run-mac-linux.sh` in a terminal.

Your browser opens http://127.0.0.1:5000. Paste the journal link and press **Check journal**.
A check takes 20 to 60 seconds. Use **Print / save PDF** to keep the report.

## What it checks

The app reads up to 45 pages of the journal website (home, scope, board, ethics, guides, indexing,
contact, archive, fees, and the latest issue) and marks each rule:

- **Pass**: the rule is met on the website.
- **Fail**: the item was not found, or the numbers break the rule.
- **Check**: partly found; look again.
- **By hand**: can't be verified from a website (Scopus h-index, funding letter, ministry approvals).

Automatic checks include: ISSN, DOI, IASJ link, Scopus/Clarivate mention, deposit number, plagiarism
tool, template and citation style, COPE ethics, peer-review type, Arabic + English site, independent
site, the nine required website sections, issues per year, papers per year (60 limit), editorial board
size, share of members from outside Iraq (75%), max 10% per foreign country, members' titles,
editor-in-chief/managing editor titles, and board members' share of papers in the latest issue (10%).

Board and author matching read names from web pages, so results are approximate. Always open the
evidence links before relying on a Fail.

## Files

- `checker.py`: crawling and all rule checks (`python checker.py <url>` prints JSON).
- `app.py`: the web page.
- `rules-summary.md`: English summary of the three circulars.

## Put it online (Render, free plan)

1. Sign in at https://render.com with GitHub.
2. New > Blueprint, pick this repository, then Apply. Render reads `render.yaml`.
3. After the build, open the `onrender.com` link it gives you.
