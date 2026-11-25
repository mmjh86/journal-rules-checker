"""Crawl a journal website and check it against the Iraqi MoHESR journal controls
(circular 14838/4 of 23-12-2025, recommendations 9420 of 26-01-2026)."""

from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; JournalRulesChecker/1.0)"
MAX_PAGES = 45
TIMEOUT = 15

PASS, FAIL, WARN, MANUAL = "pass", "fail", "warn", "manual"

# Page types we look for, with keywords matched against link text and URL.
PAGE_HINTS = {
    "scope": ["aim", "scope", "about the journal", "about", "focus", "الأهداف", "اهداف", "نطاق", "عن المجلة"],
    "board": ["editorial board", "editorial team", "editorial.board", "editorial", "board", "هيئة التحرير", "هيئه التحرير"],
    "ethics": ["ethic", "publication ethics", "malpractice", "cope", "اخلاقيات", "أخلاقيات"],
    "authors": ["author guide", "guide for author", "authors.note", "instructions for author", "author guidelines",
                "submission", "guide for authors", "دليل الباحث", "تعليمات المؤلف", "تعليمات النشر", "دليل المؤلف"],
    "reviewers": ["reviewer", "referee", "دليل المقيم", "المحكمين", "المقيمين"],
    "indexing": ["index", "abstracting", "الفهرسة", "فهرسة"],
    "contact": ["contact", "اتصل", "تواصل"],
    "archive": ["archive", "all issues", "browse", "issue_", "issues", "الأرشيف", "الارشيف", "الأعداد", "الاعداد"],
    "fees": ["fee", "apc", "charge", "price", "payment", "أجور", "اجور", "رسوم"],
    "review": ["peer review", "review process", "process", "التحكيم"],
    "plagiarism": ["plagiarism", "similarity", "الاستلال"],
    "template": ["template", "قالب"],
    "arabic": ["العربية", "عربي", "/ar", "lang=ar", "locale=ar", "ar_iq", "ar_sa"],
    "current": ["current", "latest issue", "العدد الحالي"],
}

COUNTRIES = [
    "Iraq", "Afghanistan", "Albania", "Algeria", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan",
    "Bahrain", "Bangladesh", "Belarus", "Belgium", "Bosnia", "Brazil", "Brunei", "Bulgaria", "Cameroon", "Canada",
    "Chile", "China", "Colombia", "Croatia", "Cyprus", "Czech", "Denmark", "Egypt", "Estonia", "Ethiopia",
    "Finland", "France", "Georgia", "Germany", "Ghana", "Greece", "Hong Kong", "Hungary", "India", "Indonesia",
    "Iran", "Ireland", "Italy", "Japan", "Jordan", "Kazakhstan", "Kenya", "Korea", "Kuwait", "Latvia",
    "Lebanon", "Libya", "Lithuania", "Malaysia", "Malta", "Mexico", "Morocco", "Netherlands", "New Zealand",
    "Nigeria", "Norway", "Oman", "Pakistan", "Palestine", "Philippines", "Poland", "Portugal", "Qatar", "Romania",
    "Russia", "Saudi Arabia", "Serbia", "Singapore", "Slovakia", "Slovenia", "South Africa", "Spain", "Sri Lanka",
    "Sudan", "Sweden", "Switzerland", "Syria", "Taiwan", "Tanzania", "Thailand", "Tunisia", "Turkey", "Türkiye",
    "Ukraine", "United Arab Emirates", "UAE", "United Kingdom", "UK", "United States", "USA", "U.S.A",
    "Uzbekistan", "Vietnam", "Yemen", "Scotland", "England", "Wales",
]
COUNTRY_ALIASES = {"UAE": "United Arab Emirates", "UK": "United Kingdom", "England": "United Kingdom",
                   "Scotland": "United Kingdom", "Wales": "United Kingdom", "USA": "United States",
                   "U.S.A": "United States", "Türkiye": "Turkey"}
ARABIC_COUNTRIES = {"العراق": "Iraq", "مصر": "Egypt", "الأردن": "Jordan", "الاردن": "Jordan", "السعودية": "Saudi Arabia",
                    "ماليزيا": "Malaysia", "الإمارات": "United Arab Emirates", "الامارات": "United Arab Emirates",
                    "بريطانيا": "United Kingdom", "المملكة المتحدة": "United Kingdom", "امريكا": "United States",
                    "الولايات المتحدة": "United States", "تركيا": "Turkey", "إيران": "Iran", "ايران": "Iran",
                    "الجزائر": "Algeria", "تونس": "Tunisia", "المغرب": "Morocco", "لبنان": "Lebanon", "سوريا": "Syria",
                    "الكويت": "Kuwait", "قطر": "Qatar", "عمان": "Oman", "البحرين": "Bahrain", "اليمن": "Yemen",
                    "ليبيا": "Libya", "السودان": "Sudan", "فلسطين": "Palestine", "الهند": "India", "باكستان": "Pakistan",
                    "الصين": "China", "روسيا": "Russia", "ألمانيا": "Germany", "المانيا": "Germany", "فرنسا": "France",
                    "إيطاليا": "Italy", "ايطاليا": "Italy", "اسبانيا": "Spain", "كندا": "Canada", "استراليا": "Australia"}
IRAQI_CITIES = ["Baghdad", "Basra", "Basrah", "Mosul", "Erbil", "Kirkuk", "Najaf", "Karbala", "Kerbala", "Babylon",
                "Babil", "Hilla", "Diyala", "Anbar", "Ramadi", "Tikrit", "Duhok", "Sulaimani", "Sulaymaniyah",
                "Kufa", "Wasit", "Kut", "Nasiriyah", "Thi-Qar", "Thi Qar", "Dhi Qar", "Maysan", "Misan", "Samarra",
                "Diwaniyah", "Qadisiyah", "Al-Qadisiyah", "Muthanna", "Fallujah", "Zakho", "Halabja", "Mustansiriyah"]

RANKS = [  # order matters: most specific first
    ("Associate Professor", "Associate Professor"), ("Assoc. Prof", "Associate Professor"),
    ("Assist. Prof", "Assistant Professor"), ("Asst. Prof", "Assistant Professor"),
    ("Assistant Professor", "Assistant Professor"), ("Asst Prof", "Assistant Professor"), ("Ass. Prof", "Assistant Professor"),
    ("Professor", "Professor"), ("Prof.", "Professor"), ("Prof ", "Professor"),
    ("Assistant Lecturer", "Assistant Lecturer"), ("Asst. Lect", "Assistant Lecturer"), ("Lecturer", "Lecturer"),
    ("Lect.", "Lecturer"), ("Dr.", "Doctor (rank not stated)"),
    ("أ.م.د", "Assistant Professor"), ("أ.م", "Assistant Professor"), ("أ.د", "Professor"),
    ("م.م", "Assistant Lecturer"), ("م.د", "Lecturer"),
]
QUALIFIED_MEMBER = {"Professor", "Associate Professor", "Assistant Professor", "Lecturer"}


@dataclass
class Page:
    url: str
    title: str
    text: str
    soup: BeautifulSoup
    links: list  # (abs_url, text)


@dataclass
class Result:
    section: str
    rid: str
    rule: str
    status: str
    detail: str
    evidence: list = field(default_factory=list)  # list of (url, label)


class Crawler:
    def __init__(self, start_url: str):
        if not re.match(r"^https?://", start_url):
            start_url = "https://" + start_url
        self.start = start_url
        self.host = urlparse(start_url).netloc.lower()
        self.base_host = self.host[4:] if self.host.startswith("www.") else self.host
        self.pages: dict[str, Page] = {}
        self.errors: list[str] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "en,ar;q=0.8"})
        self.files: list[tuple[str, str]] = []  # document links (url, text)

    def same_site(self, url: str) -> bool:
        h = urlparse(url).netloc.lower()
        h = h[4:] if h.startswith("www.") else h
        return h == self.base_host or h.endswith("." + self.base_host) or self.base_host.endswith("." + h)

    def fetch(self, url: str) -> Page | None:
        if url in self.pages:
            return self.pages[url]
        try:
            r = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException as e:
            self.errors.append(f"{url}: {e.__class__.__name__}")
            return None
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
            if r.status_code >= 400:
                self.errors.append(f"{url}: HTTP {r.status_code}")
            return None
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "javascript:", "tel:")):
                links.append((href, a.get_text(" ", strip=True)))
                continue
            absu = urldefrag(urljoin(r.url, href))[0]
            links.append((absu, a.get_text(" ", strip=True) or a.get("title", "")))
            if re.search(r"\.(docx?|dotx?|pdf)(\?|$)", absu, re.I):
                self.files.append((absu, a.get_text(" ", strip=True)))
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = re.sub(r"[ \t\r\f\v]+", " ", soup.get_text("\n", strip=True))
        title = soup.title.get_text(strip=True) if soup.title else url
        page = Page(r.url, title, text, soup, links)
        self.pages[url] = page
        self.pages[r.url] = page
        return page

    def crawl(self) -> None:
        home = self.fetch(self.start)
        if not home:
            return
        self.home = home
        seen = {self.start, home.url}
        queue: deque[tuple[int, str]] = deque()

        def score(url: str, text: str) -> int:
            s = (url + " " + text).lower()
            hits = sum(1 for kws in PAGE_HINTS.values() for k in kws if k.lower() in s)
            return hits

        def enqueue(page: Page) -> None:
            cands = []
            for u, t in page.links:
                if not u.startswith("http") or u in seen or not self.same_site(u):
                    continue
                if re.search(r"\.(pdf|docx?|jpe?g|png|gif|zip|rar|xml|css|js)(\?|$)", u, re.I):
                    continue
                if re.search(r"(login|register|logout|signin|signup|download|lostPassword)", u, re.I):
                    continue
                sc = score(u, t)
                if sc:
                    cands.append((sc, u))
                    seen.add(u)
            for sc, u in sorted(cands, reverse=True):
                queue.append((sc, u))

        enqueue(home)
        while queue and len({p.url for p in self.pages.values()}) < MAX_PAGES:
            _, u = queue.popleft()
            p = self.fetch(u)
            if p and len(self.pages) < MAX_PAGES // 2:
                enqueue(p)

    # helpers ------------------------------------------------------------
    def all_pages(self) -> list[Page]:
        out, seen = [], set()
        for p in self.pages.values():
            if p.url not in seen:
                seen.add(p.url)
                out.append(p)
        return out

    def find_pages(self, kind: str) -> list[Page]:
        """Pages whose URL or title match the hint list for `kind`."""
        kws = [k.lower() for k in PAGE_HINTS[kind]]
        res = []
        for p in self.all_pages():
            s = (p.url + " " + p.title).lower()
            if any(k in s for k in kws):
                res.append(p)
        return res

    def find_links(self, kind: str) -> list[tuple[str, str]]:
        kws = [k.lower() for k in PAGE_HINTS[kind]]
        out, seen = [], set()
        for p in self.all_pages():
            for u, t in p.links:
                s = (u + " " + t).lower()
                if any(k in s for k in kws) and u not in seen:
                    seen.add(u)
                    out.append((u, t))
        return out

    def search(self, pattern: str, flags=re.I) -> list[tuple[Page, str]]:
        out = []
        rx = re.compile(pattern, flags)
        for p in self.all_pages():
            m = rx.search(p.text)
            if m:
                a, b = max(0, m.start() - 70), min(len(p.text), m.end() + 90)
                out.append((p, p.text[a:b].replace("\n", " ")))
        return out


def ev(hits, n=3):
    return [(p.url, snip) for p, snip in hits[:n]]


# --------------------------------------------------------------------------
# Editorial board parsing
# --------------------------------------------------------------------------

def country_of(chunk: str) -> str | None:
    found = None
    last_pos = -1
    for c in COUNTRIES:
        for m in re.finditer(r"(?<![A-Za-z])" + re.escape(c) + r"(?![A-Za-z])", chunk):
            if m.start() > last_pos:
                last_pos, found = m.start(), COUNTRY_ALIASES.get(c, c)
    for ar, en in ARABIC_COUNTRIES.items():
        i = chunk.rfind(ar)
        if i > last_pos:
            last_pos, found = i, en
    if not found:
        for city in IRAQI_CITIES:
            if re.search(r"(?<![A-Za-z])" + re.escape(city) + r"(?![A-Za-z])", chunk, re.I):
                return "Iraq"
        if re.search(r"\.edu\.iq|University of (Baghdad|Technology|Basrah|Mosul|Kufa|Babylon)|جامعة بغداد", chunk, re.I):
            return "Iraq"
    return found


def rank_of(chunk: str) -> str | None:
    for key, val in RANKS:
        if key in chunk:
            return val
    return None


def parse_board(page: Page) -> list[dict]:
    """Split an editorial board page into member records (best effort)."""
    soup = page.soup
    blocks: list[str] = []
    # Common containers: OJS (.editorial_team, #content), Sinaweb/Sprint (.ed_board, table rows), cards.
    main = (soup.select_one(".page_editorial_team, #editorial-team, .editorial_board, .ed_board, main, #content, .content")
            or soup.body or soup)
    # Prefer repeated structures
    for sel in ["tr", "li", ".card", ".member", ".editor", "p", "div"]:
        items = [el.get_text(" ", strip=True) for el in main.select(sel)]
        items = [t for t in items if 15 < len(t) < 600 and (rank_of(t) or country_of(t))]
        if len(items) >= 5:
            blocks = items
            break
    if not blocks:
        blocks = [ln for ln in page.text.split("\n") if 15 < len(ln) < 600 and (rank_of(ln) or country_of(ln))]
    # Deduplicate nested repeats
    uniq, seen = [], set()
    for b in blocks:
        k = b[:80]
        if k not in seen:
            seen.add(k)
            uniq.append(b)
    members = []
    role_rx = re.compile(r"(editor[- ]in[- ]chief|chief editor|managing editor|رئيس التحرير|مدير التحرير)", re.I)
    for b in uniq:
        name_m = re.search(r"((?:Prof\.?|Dr\.?|Assist\.?|Asst\.?|Assoc\.?|Lect\.?|Professor|Lecturer|أ\.م\.د|أ\.د|م\.د)[^,|\n]{3,60})", b)
        members.append({
            "text": b[:220],
            "name": (name_m.group(1) if name_m else b.split(",")[0])[:70].strip(),
            "country": country_of(b),
            "rank": rank_of(b),
            "role": (role_rx.search(b).group(1) if role_rx.search(b) else ""),
        })
    return members


def board_results(c: Crawler) -> tuple[list[Result], dict]:
    res: list[Result] = []
    pages = c.find_pages("board")
    info = {"members": [], "page": None}
    if not pages:
        links = c.find_links("board")
        for u, _ in links[:3]:
            p = c.fetch(u)
            if p:
                pages = [p]
                break
    best, members = None, []
    for p in pages:
        m = parse_board(p)
        if len(m) > len(members):
            best, members = p, m
    info["members"], info["page"] = members, best.url if best else None
    sec = "Editorial board (14838, Part 2)"
    if not best or len(members) < 3:
        msg = "Could not find or read an editorial board page." if not best else \
            "Found the board page but could not split it into members (it may be an image or load by script)."
        for rid, rule in [("B1", "At least 20 members; 75% from outside Iraq; max 10% from any one foreign country"),
                          ("B4", "All members are Lecturer or higher"),
                          ("B5", "Editor-in-chief and managing editor are Assistant Professor or higher"),
                          ("B6", "Preferably 30%-40% of members are Lecturers or Assistant Professors")]:
            res.append(Result(sec, rid, rule, MANUAL, msg, [(best.url, "Board page")] if best else []))
    else:
        n = len(members)
        countries = Counter(m["country"] for m in members if m["country"])
        known = sum(countries.values())
        iraq = countries.get("Iraq", 0)
        foreign = known - iraq
        foreign_pct = 100 * foreign / known if known else 0
        foreign_counts = {k: v for k, v in countries.items() if k != "Iraq"}
        top_foreign = max(foreign_counts.items(), key=lambda kv: kv[1]) if foreign_counts else None
        top_pct = 100 * top_foreign[1] / n if top_foreign else 0
        problems = []
        if n < 20:
            problems.append(f"only {n} members found (need 20 or more)")
        if known and foreign_pct < 75:
            problems.append(f"{foreign_pct:.0f}% from outside Iraq (need 75%)")
        if top_foreign and top_pct > 10:
            problems.append(f"{top_pct:.0f}% from {top_foreign[0]} (max 10% per foreign country)")
        detail = (f"{n} members found; country identified for {known}. Iraq: {iraq}, outside Iraq: {foreign} "
                  f"({foreign_pct:.0f}%). Countries: " + ", ".join(f"{k} {v}" for k, v in countries.most_common()) + ".")
        if problems:
            detail += " Problems: " + "; ".join(problems) + "."
        status = PASS if not problems and known >= n * 0.8 else (FAIL if problems else WARN)
        res.append(Result(sec, "B1", "At least 20 members; 75% from outside Iraq; max 10% from any one foreign country",
                          status, detail, [(best.url, "Board page")]))

        ranks = Counter(m["rank"] or "Not stated" for m in members)
        low = [m for m in members if m["rank"] == "Assistant Lecturer"]
        unknown = ranks.get("Not stated", 0) + ranks.get("Doctor (rank not stated)", 0)
        st = FAIL if low else (WARN if unknown else PASS)
        res.append(Result(sec, "B4", "All members are Lecturer or higher", st,
                          "Titles found: " + ", ".join(f"{k} {v}" for k, v in ranks.most_common()) + "." +
                          (f" {len(low)} Assistant Lecturer(s) listed." if low else "") +
                          (f" {unknown} member(s) have no clear title; confirm by hand." if unknown else ""),
                          [(best.url, "Board page")]))

        heads = [m for m in members if m["role"]]
        if heads:
            bad = [h for h in heads if h["rank"] not in ("Professor", "Associate Professor", "Assistant Professor")]
            res.append(Result(sec, "B5", "Editor-in-chief and managing editor are Assistant Professor or higher",
                              FAIL if bad and all(b["rank"] for b in bad) else (WARN if bad else PASS),
                              "; ".join(f"{h['role']}: {h['name']} ({h['rank'] or 'title not stated'})" for h in heads),
                              [(best.url, "Board page")]))
        else:
            res.append(Result(sec, "B5", "Editor-in-chief and managing editor are Assistant Professor or higher", MANUAL,
                              "Could not identify the editor-in-chief / managing editor on the board page.",
                              [(best.url, "Board page")]))
        mid = ranks.get("Lecturer", 0) + ranks.get("Assistant Professor", 0)
        pct = 100 * mid / n
        res.append(Result(sec, "B6", "Preferably 30%-40% of members are Lecturers or Assistant Professors (advisory)",
                          PASS if 30 <= pct <= 40 else WARN, f"{pct:.0f}% are Lecturers or Assistant Professors.",
                          [(best.url, "Board page")]))
    res.append(Result(sec, "B2", "Each member's Scopus h-index is at least 5 (sciences) or 2 (humanities)", MANUAL,
                      "h-index is not on journal websites. Check each member in Scopus author search.",
                      [("https://www.scopus.com/freelookup/form/author.uri", "Scopus author lookup")]))
    res.append(Result(sec, "B3", "Editor-in-chief and managing editor h-index at least 6 (sciences) or 2 (humanities)",
                      MANUAL, "Check in Scopus author search.",
                      [("https://www.scopus.com/freelookup/form/author.uri", "Scopus author lookup")]))
    return res, info


# --------------------------------------------------------------------------
# Issues and articles (best effort)
# --------------------------------------------------------------------------

ARTICLE_URL = re.compile(r"(/article/view/\d+|/article_\d+\.html|/index\.php/[^/]+/article/view/|/articles?/\d+)", re.I)
ISSUE_URL = re.compile(r"(/issue/view/\d+|/issue_\d+_\d+\.html|/issue/\d+|/volume_\d+)", re.I)


def issue_results(c: Crawler, board_members: list[dict], indexed: bool = False) -> list[Result]:
    res: list[Result] = []
    sec = "General controls (14838, Part 1)"
    issue_links = []
    for p in c.all_pages():
        for u, t in p.links:
            if ISSUE_URL.search(u) and c.same_site(u):
                issue_links.append((u, t))
    seen, issues = set(), []
    for u, t in issue_links:
        if u not in seen:
            seen.add(u)
            issues.append((u, t))
    # Find years mentioned with issues
    years = Counter()
    for _, t in issues:
        for y in re.findall(r"\b(20\d\d)\b", t):
            years[int(y)] += 1
    latest = None
    for u, _ in issues[:3]:
        p = c.fetch(u)
        if p:
            arts = {x for x, _ in p.links if ARTICLE_URL.search(x)}
            if arts:
                latest = (p, arts)
                break
    if years:
        y = max(years)
        last_full = y - 1 if (y - 1) in years else y
        res.append(Result(sec, "A11", "At least one issue per year", PASS if years.get(last_full) else WARN,
                          "Issues found by year: " + ", ".join(f"{k}: {years[k]}" for k in sorted(years, reverse=True)[:6]) + ".",
                          [(issues[0][0], "Issue")] if issues else []))
    else:
        freq = c.search(r"(quarterly|bi-?annual|semi-?annual|monthly|annually|issues? (per|a|each) year|twice a year|نصف سنوية|فصلية|سنوية)")
        res.append(Result(sec, "A11", "At least one issue per year", WARN if freq else MANUAL,
                          ("Publication frequency stated: \"" + freq[0][1] + "\"") if freq else
                          "Could not read issue dates from the archive. Check the archive page.", ev(freq)))
    if latest:
        p, arts = latest
        n = len(arts)
        per_year = max(years.values()) if years else 1
        est = n * per_year
        if indexed:
            st, why = PASS, "The journal says it is indexed in Scopus/Clarivate, so the 60-paper limit no longer applies. Confirm the indexing."
        else:
            st = FAIL if est > 60 else PASS if years else WARN
            why = f"Latest issue read has about {n} papers; with about {per_year} issue(s) a year that is roughly {est} papers a year (limit 60)."
        res.append(Result(sec, "A10", "No more than 60 papers a year before Scopus/Clarivate indexing", st, why,
                          [(p.url, p.title[:60])]))
        # Board members' share of papers in the issue
        surnames = set()
        for m in board_members:
            nm = re.sub(r"^(Prof\.?|Dr\.?|Assist\.?|Asst\.?|Assoc\.?|Lect\.?|Professor|Lecturer)\s*", "", m["name"], flags=re.I)
            parts = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", nm) if w.lower() not in
                     {"prof", "professor", "assistant", "associate", "lecturer", "dr", "editor", "chief", "university", "college", "department"}]
            if len(parts) >= 2:
                surnames.add((parts[0].lower(), parts[-1].lower()))
        if surnames:
            text = p.text.lower()
            hits = [f"{a} {b}" for a, b in surnames if a in text and b in text and re.search(re.escape(a) + r".{0,40}" + re.escape(b), text)]
            share = 100 * len(hits) / n if n else 0
            res.append(Result(sec, "A12", "Board members' papers are at most 10% of an issue",
                              FAIL if share > 10 else PASS if n >= 5 else WARN,
                              f"Board names found among authors of the latest issue: {len(hits)} of {n} papers ({share:.0f}%)."
                              + (" Names: " + ", ".join(h.title() for h in hits[:8]) + "." if hits else "")
                              + " Name matching is approximate; confirm by hand.",
                              [(p.url, p.title[:60])]))
        else:
            res.append(Result(sec, "A12", "Board members' papers are at most 10% of an issue", MANUAL,
                              "Board names could not be read, so authors were not compared.", [(p.url, p.title[:60])]))
    else:
        res.append(Result(sec, "A10", "No more than 60 papers a year before Scopus/Clarivate indexing", MANUAL,
                          "Could not open an issue's table of contents to count papers.",
                          [(issues[0][0], "Issue")] if issues else []))
        res.append(Result(sec, "A12", "Board members' papers are at most 10% of an issue", MANUAL,
                          "Could not open an issue's table of contents to compare authors with the board.", []))
    return res


# --------------------------------------------------------------------------
# All checks
# --------------------------------------------------------------------------

def presence(c: Crawler, kind: str, text_rx: str | None = None):
    pages = c.find_pages(kind)
    links = c.find_links(kind)
    hits = c.search(text_rx) if text_rx else []
    evidence = [(p.url, p.title[:70]) for p in pages[:2]] or [(u, t[:60] or u) for u, t in links[:2]]
    evidence += ev(hits, 2)
    return bool(pages or links), bool(hits), evidence


def _is_private(url: str) -> bool:
    """Refuse links to the server's own network when hosted online (set ALLOW_LOCAL=1 to allow)."""
    import ipaddress, os, socket
    if os.environ.get("ALLOW_LOCAL"):
        return False
    host = urlparse(url if re.match(r"^https?://", url) else "https://" + url).hostname or ""
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except (socket.gaierror, ValueError):
        return False
    return False


def run_checks(url: str) -> dict:
    if _is_private(url):
        return {"url": url, "error": "That address points to a private or local network. Enter the journal's public website link.", "results": []}
    c = Crawler(url)
    c.crawl()
    if not c.pages:
        return {"url": url, "error": "Could not open the website. " + "; ".join(c.errors[:3]), "results": []}
    R: list[Result] = []
    home = c.home
    G, W, Rec = "General controls (14838, Part 1)", "Website (14838, Part 3)", "Recommendations (9420)"

    # ---- General controls
    R.append(Result(G, "A1", "Issued by a government body, scientific institution, legal study centre or scientific society",
                    MANUAL if not re.search(r"\.(edu|gov)\.iq$", c.base_host) else PASS,
                    f"Website domain is {c.host}." + (" A .edu.iq / .gov.iq domain suggests a university or government issuer."
                                                     if re.search(r"\.(edu|gov)\.iq$", c.base_host) else " Confirm the issuer by hand."),
                    [(home.url, "Home page")]))
    R.append(Result(G, "A2", "Issuer commits in writing to fund the journal", MANUAL,
                    "This is an official letter and is not on the website.", []))
    iasj = [(p.url, u) for p in c.all_pages() for u, _ in p.links if "iasj" in u.lower()]
    R.append(Result(G, "A3", "Papers indexed on the Iraqi Academic Scientific Journals (IASJ) site", PASS if iasj else WARN,
                    "Link to IASJ found." if iasj else "No link to IASJ found on the pages read. Search the journal on iasj.rdd.edu.iq.",
                    [(iasj[0][1], "IASJ link")] if iasj else [("https://iasj.rdd.edu.iq", "IASJ")]))
    scop = c.search(r"((?i:Scopus|Clarivate|Web of Science|Emerging Sources Citation)|\bESCI\b|\bSCIE\b)", 0)
    R.append(Result(G, "A4", "Indexed in Scopus / Clarivate (accepted subject to R&D changes)", PASS if scop else WARN,
                    "Scopus/Clarivate mentioned: \"" + scop[0][1] + "\"" if scop else "No mention of Scopus or Clarivate found. Not required, but needed for the 3-5 year plan (9420 #6).",
                    ev(scop, 2)))
    issn = c.search(r"(e-?ISSN|p-?ISSN|Print ISSN|Online ISSN|ISSN)\s*[:\-]?\s*\d{4}\s*-\s*\d{3}[\dXx]")
    ids = sorted({m for p in c.all_pages() for m in re.findall(r"\b\d{4}-\d{3}[\dXx]\b", p.text)
                  if re.search(r"ISSN[^\n]{0,30}" + re.escape(m), p.text)})
    R.append(Result(G, "A5", "Has an electronic and/or print ISSN, registered under Iraq", PASS if ids else FAIL,
                    ("ISSN found: " + ", ".join(ids[:4]) + ". Confirm the country of registration (Iraq) at portal.issn.org.") if ids
                    else "No ISSN found on the pages read.",
                    ev(issn, 1) + [(f"https://portal.issn.org/resource/ISSN/{ids[0].upper()}", "ISSN portal record")] if ids else ev(issn, 1)))
    dep = c.search(r"(Deposit|Legal deposit|رقم الإيداع|رقم الايداع|الإيداع|National Library)")
    R.append(Result(G, "A6", "Legal deposit number from the National Library and Archives, Baghdad, on the cover",
                    PASS if dep else MANUAL, ("Deposit number mentioned: \"" + dep[0][1] + "\"") if dep else
                    "No deposit number found on the website. Check the printed or PDF cover.", ev(dep, 1)))
    R.append(Result(G, "A7", "Can be audited online through the journal website", PASS,
                    f"Website opened and {len(c.all_pages())} pages were read.", [(home.url, "Home page")]))
    scope_pages = c.find_pages("scope")
    scope_txt = ""
    for p in scope_pages:
        paras = [ln for ln in p.text.split("\n") if len(ln) > 80 and re.search(r"(aims?|scope|publish|focus|covers?|topics)", ln, re.I)]
        if paras:
            scope_txt = paras[0][:400]
            break
    R.append(Result(G, "A9", "Single specialty only", MANUAL,
                    ("Scope text: \"" + scope_txt + "\". Decide whether this is one specialty.") if scope_txt
                    else "Read the journal's scope and decide whether it covers one specialty.",
                    [(p.url, p.title[:60]) for p in scope_pages[:1]]))
    R.append(Result(G, "A13", "Name fits its specialty and is unique", MANUAL,
                    f"Journal title on the site: \"{home.title[:120]}\". Compare with the scope and search IASJ for duplicates.",
                    [(home.url, "Home page")]))
    plag = c.search(r"(plagiarism|iThenticate|Turnitin|Similarity Check|Crossref Similarity|الاستلال)")
    tools = sorted({t for t in ["iThenticate", "Turnitin", "Similarity Check", "Plagiarism X", "Grammarly"]
                    if any(t.lower() in p.text.lower() for p in c.all_pages())})
    R.append(Result(G, "A14", "Uses an approved plagiarism-checking tool",
                    PASS if tools else (WARN if plag else FAIL),
                    ("Tool named: " + ", ".join(tools) + ".") if tools else
                    ("Plagiarism is mentioned but no tool is named." if plag else "No plagiarism policy found."), ev(plag, 2)))
    tmpl = [(u, t) for u, t in c.files if re.search(r"template|قالب|format", u + " " + t, re.I)]
    tmpl += [(u, t) for u, t in c.find_links("template") if (u, t) not in tmpl]
    style = sorted({s for s in ["IEEE", "APA", "Harvard", "Vancouver", "Chicago", "MLA", "AMA"]
                    if re.search(r"\b" + s + r"\b", " ".join(p.text for p in c.find_pages("authors")) or "")})
    if not style:
        style = sorted({s for s in ["IEEE", "APA", "Harvard", "Vancouver", "Chicago", "MLA"]
                        if c.search(r"\b" + s + r"\b(?=[^\n]{0,40}(style|format|reference|citation))", 0)})
    R.append(Result(G, "A15", "Own paper template on the website with journal and publisher logos and the citation style",
                    PASS if tmpl and style else (WARN if tmpl or style else FAIL),
                    ("Template file found. " if tmpl else "No template file found. ") +
                    (("Citation style: " + ", ".join(style) + ".") if style else "Citation style not found.") +
                    (" Open the template to confirm both logos." if tmpl else ""),
                    [(u, t[:60] or "Template") for u, t in tmpl[:2]]))
    arabic_chars = sum(len(re.findall(r"[؀-ۿ]", p.text)) for p in c.all_pages())
    R.append(Result(G, "A16", "Arabic-language journals give names, affiliations, keywords, title and abstract in English",
                    MANUAL, "Open one Arabic paper and check for the English title, abstract, keywords, author names and affiliations."
                    if arabic_chars > 500 else "Only applies if the journal publishes in Arabic.", []))
    eth_link, cope_hit, eth_ev = presence(c, "ethics", r"(COPE|Committee on Publication Ethics)")
    R.append(Result(G, "A17", "Clear publication ethics policy following COPE",
                    PASS if eth_link and cope_hit else (WARN if eth_link or cope_hit else FAIL),
                    ("Ethics page found" if eth_link else "No ethics page found") + "; " +
                    ("COPE is referenced." if cope_hit else "COPE is not mentioned."), eth_ev))
    pr = c.search(r"(double[- ]blind|single[- ]blind|peer[- ]review|تحكيم)")
    blind = c.search(r"(double[- ]blind|single[- ]blind|open peer review)")
    R.append(Result(G, "A18", "Transparent, specialised peer-review process", PASS if blind else (WARN if pr else FAIL),
                    ("Review type stated: \"" + blind[0][1] + "\"") if blind else
                    ("Peer review is mentioned but the process is not described." if pr else "No peer-review description found."),
                    ev(blind or pr, 2)))
    R.append(Result(G, "A19", "Follows R&D Department circulars, including approval of the editor-in-chief and board", MANUAL,
                    "Administrative: check the ministry approval letters.", []))

    # ---- Board + issues
    br, binfo = board_results(c)
    R += br
    R += issue_results(c, binfo["members"], indexed=bool(scop))

    # ---- Website
    ar_links = c.find_links("arabic")
    en_ok = sum(len(re.findall(r"[A-Za-z]", p.text)) for p in c.all_pages()) > 2000
    ar_ok = bool(ar_links) or arabic_chars > 1500
    R.append(Result(W, "C1", "Website in both Arabic and English", PASS if ar_ok and en_ok else FAIL,
                    ("Arabic version link found. " if ar_links else ("Arabic text found. " if arabic_chars > 1500 else "No Arabic version found. ")) +
                    ("English content found." if en_ok else "Little English content found."),
                    [(u, t[:40] or "Arabic") for u, t in ar_links[:1]]))
    indep = not re.search(r"(iasj\.net|iasj\.rdd\.edu\.iq|rdd\.edu\.iq)", c.host)
    R.append(Result(W, "C2", "Independent website, separate from the R&D Department's journals site", PASS if indep else FAIL,
                    f"Website host: {c.host}.", [(home.url, "Home page")]))
    dois = sorted({m for p in c.all_pages() for m in re.findall(r"\b10\.\d{4,9}/[^\s\"<>]+", p.text + " ".join(u for u, _ in p.links))})
    prefixes = sorted({d.split("/")[0] for d in dois})
    R.append(Result(W, "C3", "Journal has DOI", PASS if dois else FAIL,
                    ("DOI prefix found: " + ", ".join(prefixes[:3]) + f" ({len(dois)} DOIs seen).") if dois else "No DOIs found on the pages read.",
                    [("https://doi.org/" + dois[0], dois[0][:60])] if dois else []))
    for rid, kind, label, rx in [
        ("C4a", "scope", "Aims and scope page", None),
        ("C4b", "board", "Editorial board page", None),
        ("C4c", "ethics", "Publication ethics page", None),
        ("C4d", "authors", "Author guidelines page", None),
        ("C4e", "reviewers", "Reviewer guidelines page", None),
        ("C4f", "indexing", "Indexing / abstracting page", None),
        ("C4g", "contact", "Contact page", r"(@[a-z0-9.-]+\.[a-z]{2,}|Tel|Phone|هاتف)"),
        ("C4h", "archive", "Archive of issues", None),
        ("C4i", "fees", "Publication fees (and any discounts)", r"(publication fee|article processing charge|APC|free of charge|no fees?|IQD|USD|\$\s?\d+|دينار|أجور النشر|اجور النشر)"),
    ]:
        has, hit, evd = presence(c, kind, rx)
        ok = has or hit
        st = PASS if ok else FAIL
        if rid == "C4e" and not has:
            hit2 = c.search(r"(reviewer guidelines|guide for reviewers|instructions for reviewers)")
            if hit2:
                st, evd = PASS, ev(hit2, 1)
        R.append(Result(W, rid, "Website has: " + label, st, "Found." if st == PASS else "Not found on the pages read.", evd))

    # ---- Recommendations 9420
    heads = [m for m in binfo["members"] if m["role"]]
    admin = [h for h in heads if re.search(r"(Dean|President of the University|University President|Head of (the )?Department|عميد|رئيس الجامعة|رئيس قسم)", h["text"], re.I)]
    R.append(Result(Rec, "D1", "Editor-in-chief / managing editor do not also hold an administrative post (president, dean, head of department)",
                    FAIL if admin else MANUAL,
                    ("Possible administrative post: " + "; ".join(a["text"][:120] for a in admin)) if admin else
                    "No administrative title seen next to the editor-in-chief; confirm by hand.",
                    [(binfo["page"], "Board page")] if binfo["page"] else []))
    coerce = c.search(r"(self-citation|coercive citation|citation manipulation)")
    R.append(Result(Rec, "D4", "Policy against coercive self-citation", PASS if coerce else WARN,
                    "Citation manipulation is addressed." if coerce else "No statement on coercive or excessive self-citation found.",
                    ev(coerce, 1)))
    ai = c.search(r"(generative AI|AI[- ]generated|AI tools|use of AI|artificial intelligence tools|use of artificial intelligence|ChatGPT|large language model|الذكاء الاصطناعي)")
    R.append(Result(Rec, "D10", "Uses modern tools and has a position on AI in publishing", PASS if ai else WARN,
                    "AI is addressed on the website." if ai else "No AI policy or AI tools mentioned.", ev(ai, 1)))
    R.append(Result(Rec, "D6", "3-5 year plan to enter Scopus / Clarivate with a follow-up committee", MANUAL,
                    "Internal plan; not usually on the website.", []))

    counts = Counter(r.status for r in R)
    auto = [r for r in R if r.status != MANUAL]
    score = round(100 * sum(1 for r in auto if r.status == PASS) / len(auto)) if auto else 0
    return {
        "url": c.start, "host": c.host, "title": home.title, "pages_read": len(c.all_pages()),
        "errors": c.errors[:8], "counts": dict(counts), "score": score,
        "board": binfo,
        "results": [r.__dict__ for r in R],
        "pages": [(p.url, p.title[:80]) for p in c.all_pages()],
    }


if __name__ == "__main__":
    import json, sys
    print(json.dumps(run_checks(sys.argv[1]), indent=1, ensure_ascii=False, default=str)[:6000])
