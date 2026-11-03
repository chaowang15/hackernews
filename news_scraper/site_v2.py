"""Render the Neon Glass site (home, daily/weekly/monthly readers, trends, favorites, search) from JSON backups.

Runs at the end of `update_hackernews_index()`, so every scheduled job (top / weekly / monthly) refreshes it.
Pages keep their existing URLs; each is a Jekyll page using `_layouts/hn2.html` with raw HTML content.

    python news_scraper/site_v2.py                 # write pages into hackernews/
    python news_scraper/site_v2.py --preview DIR   # standalone .html preview (serve DIR with any static server)
"""
import argparse
import glob
import html
import json
import os
import re
import urllib.parse
import zlib
from collections import Counter, defaultdict
from datetime import date, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(ROOT_DIR, "hackernews")
WD_ZH = "一二三四五六日"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

TAG_COLORS = {
    "AI": "#8b5cf6", "Programming": "#3b82f6", "Security": "#ef4444", "Science": "#10b981",
    "Hardware": "#f59e0b", "Privacy": "#ec4899", "Open Source": "#22c55e", "Politics": "#f97316",
    "Business": "#0ea5e9", "Web": "#06b6d4", "Culture": "#d946ef", "Show HN": "#ff6600",
    "Legal": "#64748b", "Design": "#f472b6", "DevOps": "#14b8a6", "Data": "#6366f1",
    "Health": "#4ade80", "Energy": "#eab308", "Gaming": "#a855f7", "Education": "#60a5fa",
    "Finance": "#84cc16", "Startups": "#fb7185", "Entertainment": "#c084fc", "Career": "#2dd4bf", "Space": "#818cf8",
}


class Out:
    """URL and file-path policy for production (Jekyll .md) or preview (.html)."""

    def __init__(self, preview_dir=None):
        self.preview = preview_dir
        self.base = "/" if preview_dir else "/hackernews/"
        self.dir = preview_dir or SITE

    def url(self, p):
        if not self.preview:
            return self.base + p
        return self.base + (p + "index.html" if p == "" or p.endswith("/") else p + ".html")

    def file(self, p):
        rel = p + "index" if p == "" or p.endswith("/") else p
        return os.path.join(self.dir, rel + (".html" if self.preview else ".md"))


O = Out()


def day_path(d):
    return f"{d:%Y/%m/%d}/top_stories_{d:%m%d%Y}"


# ------------------------------------------------------------------ text helpers
def e(s):
    return html.escape(str(s or ""), quote=True)


def first_sentence(s, zh=False, min_len=30):
    """Leading sentence(s) of a summary, long enough to survive abbreviations like "W." or "U.S."."""
    s = (s or "").strip()
    pat = r"(.+?[。！？])" if zh else r"(.+?[.!?])(?=\s|$)"
    out, pos = "", 0
    for m in re.finditer(pat, s):
        out = s[:m.end()]
        pos = m.end()
        if len(out) >= (min_len // 2 if zh else min_len):
            return out.strip()
    return s


def domain(url):
    return re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0]


def tcolor(t):
    return TAG_COLORS.get(t, "#94a3b8")


def tag(t, count=None, href=None):
    n = f"<b>{count}</b>" if count is not None else ""
    el = "a" if href else "span"
    h = f" href='{href}'" if href else ""
    return f"<{el} class='tag'{h} data-t='{e(t)}' style='--c:{tcolor(t)}'>{e(t)}{n}</{el}>"


def bil(en, zh):
    return f"<span class='en'>{e(en)}</span><span class='zh'>{e(zh)}</span>"


def B(en, zh):
    return f"<span class='en'>{en}</span><span class='zh'>{zh}</span>"


def d_en(d, wd=True):
    return (f"{d:%A}, " if wd else "") + f"{d:%B} {d.day}, {d.year}"


def d_zh(d, wd=True):
    return f"{d.year}年{d.month}月{d.day}日" + (f" · 星期{WD_ZH[d.weekday()]}" if wd else "")


def d_short(d):
    return B(f"{d:%b} {d.day}", f"{d.month}月{d.day}日")


def updated(run_local):
    m = re.match(r"(\d{1,2}):(\d{2}), (\w+) (\d{1,2}), (\d{4}) \((\w+)\)", run_local or "")
    if not m or m.group(3) not in MONTHS:
        return B(e(run_local), e(run_local))
    hh, mm, mon, dd, yy, tz = m.groups()
    h = int(hh)
    return B(f"Updated {mon[:3]} {int(dd)}, {yy} · {h % 12 or 12}:{mm} {'PM' if h >= 12 else 'AM'} {tz}",
             f"更新于 {yy}年{MONTHS.index(mon) + 1}月{int(dd)}日 {hh}:{mm}（{tz}）")


def fallback(url, tags, cls):
    """Image placeholder: tag-coloured gradient, site favicon and domain."""
    d = domain(url)
    t = tags[0] if tags else ""
    return (f"<div class='{cls} fb' style='--c:{tcolor(t)}' data-tag='{e(t)}'>"
            f"<img class='fbi' src='https://www.google.com/s2/favicons?domain={e(d)}&amp;sz=64' alt='' loading='lazy'>"
            f"<span class='fbd'>{e(d)}</span></div>")


GENERIC_HOSTS = ("opengraph.githubassets.com", "gravatar.com", "avatars.githubusercontent.com", "pbs.twimg.com/profile_images")
GENERIC_WORD = re.compile(r"logo|favicon|icon|avatar|blank|og-default|default-og|share-thumbnail", re.I)
GENERIC_DIR = re.compile(r"/(?:logos?|icons?|favicons?|avatars?|branding)/", re.I)
SHARED_IMAGES = set()  # image URLs used by 3+ different stories: site-wide defaults, filled by load()


def image_of(x):
    """Article image URL, or "" when the image is missing, expired or only a site-wide logo/default.

    Rules are URL-only (no download, no LLM): expired signed URLs; GitHub repo cards and avatars;
    short file names containing logo/favicon/icon/avatar; logo/icon directories; any SVG; and images
    shared by three or more different stories.
    """
    u = x.get("image_url") or ""
    if not u or "X-Amz-Signature=" in u or "X-Amz-Credential=" in u or u in SHARED_IMAGES:
        return ""
    for cand in [u] + re.findall(r"url=([^&]+)", u):  # Next.js /_next/image?url=... wraps the real file
        path = re.sub(r"[?#].*$", "", urllib.parse.unquote(cand))
        name = path.rstrip("/").rsplit("/", 1)[-1]
        if (any(h in path for h in GENERIC_HOSTS) or path.lower().endswith(".svg") or "/static/og-image" in path
                or GENERIC_DIR.search(path) or (len(name) <= 48 and GENERIC_WORD.search(name))):
            return ""
    return u


def picture(x, cls):
    url = x.get("url")
    if image_of(x):
        return (f"<img class='{cls}' src='{e(image_of(x))}' alt='' loading='lazy' referrerpolicy='no-referrer' "
                f"data-d='{e(domain(url))}' data-c='{tcolor((x.get('tags') or [''])[0])}' data-tag='{e((x.get('tags') or [''])[0])}'>")
    return fallback(url, x.get("tags"), cls)


I = {
    "up": "<svg class='ico' viewBox='0 0 24 24'><path d='M12 19V5M5 12l7-7 7 7'/></svg>",
    "chat": "<svg class='ico' viewBox='0 0 24 24'><path d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/></svg>",
    "fire": "<svg class='ico' viewBox='0 0 24 24'><path d='M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14 0-5.5 3-7 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z'/></svg>",
    "search": "<svg class='ico' viewBox='0 0 24 24'><circle cx='11' cy='11' r='7'/><path d='m21 21-4.3-4.3'/></svg>",
    "sun": "<svg class='ico' viewBox='0 0 24 24'><circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></svg>",
    "cal": "<svg class='ico' viewBox='0 0 24 24'><rect x='3' y='4' width='18' height='18' rx='2'/><path d='M16 2v4M8 2v4M3 10h18'/></svg>",
    "star": "<svg class='ico' viewBox='0 0 24 24'><path d='m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z'/></svg>",
    "home": "<svg class='ico' viewBox='0 0 24 24'><path d='M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z'/></svg>",
    "chart": "<svg class='ico' viewBox='0 0 24 24'><path d='M3 3v18h18'/><path d='m7 15 4-4 3 3 6-7'/></svg>",
    "rss": "<svg class='ico' viewBox='0 0 24 24'><path d='M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16'/><circle cx='5' cy='19' r='1'/></svg>",
    "left": "<svg class='ico' viewBox='0 0 24 24'><path d='m15 18-6-6 6-6'/></svg>",
    "right": "<svg class='ico' viewBox='0 0 24 24'><path d='m9 18 6-6-6-6'/></svg>",
}


def meta(it, link=True):
    hn = it.get("hn", {})
    c = (f"<a class='m ic-chat' href='{e(hn.get('comments_url'))}' target='_blank' rel='noopener'>{hn.get('descendants', 0)}</a>"
         if link else f"<span class='m ic-chat'>{hn.get('descendants', 0)}</span>")
    return (f"<span class='metas'><span class='m hot ic-fire'>{(it.get('hot_score') or 0):.1f}</span>"
            f"<span class='m ic-up'>{hn.get('score', 0)}</span>{c}</span>")


# ------------------------------------------------------------------ data
def load():
    raw = defaultdict(dict)
    for f in glob.glob(os.path.join(SITE, "20[0-9][0-9]/*/*/*_stories_*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            y, m, dd = map(int, d["meta"]["date_dir"].split("/"))
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
        kind = "best" if os.path.basename(f).startswith("best") else "top"
        raw[date(y, m, dd)][kind] = d
    days = {}
    for d, parts in raw.items():
        best = parts.get("best", {}).get("items", [])
        both = best + parts.get("top", {}).get("items", [])
        for x in both:
            x["_best"] = x in best
            if "hn" not in x:
                x["hn"] = {"id": zlib.crc32((x.get("url") or x.get("title_en", "")).encode()), "score": 0, "descendants": 0, "comments_url": x.get("url")}
            x.setdefault("tags", [])
            x.setdefault("title_zh", x.get("title_en", ""))
            x.setdefault("summary_en", "")
            x.setdefault("summary_zh", "")
        items, seen = [], set()
        for x in both:
            if x["hn"]["id"] not in seen:
                seen.add(x["hn"]["id"])
                items.append(x)
        if not items:
            continue
        mt = (parts.get("top") or parts.get("best"))["meta"]
        days[d] = {"meta": mt, "items": items, "best_n": len(best), "top_n": len(items) - len(best),
                   "files": sorted(parts)}
    first_seen = {}
    for d in sorted(days):
        for x in days[d]["items"]:
            first_seen.setdefault(x["hn"]["id"], d)
    weeks, months = {}, {}
    for f in glob.glob(os.path.join(SITE, "weekly/*.json")):
        w = json.load(open(f, encoding="utf-8"))
        w["items"] = sorted(w["items"], key=lambda i: -(i.get("hn", {}).get("score") or 0))[:100]
        weeks[w["meta"]["iso_week"]] = w
    for f in glob.glob(os.path.join(SITE, "monthly/*.json")):
        m = json.load(open(f, encoding="utf-8"))
        m["items"] = sorted(m["items"], key=lambda i: -(i.get("hn", {}).get("score") or 0))
        months[m["meta"]["month"]] = m
    use = defaultdict(set)
    for d in days:
        for x in days[d]["items"]:
            if x.get("image_url"):
                use[x["image_url"]].add(x["hn"]["id"])
    SHARED_IMAGES.clear()
    SHARED_IMAGES.update(u for u, ids in use.items() if len(ids) >= 3)
    for coll in (weeks, months):
        for v in coll.values():
            for x in v["items"]:
                x.setdefault("tags", [])
                x.setdefault("hn", {"id": zlib.crc32((x.get("url") or "").encode()), "score": 0, "descendants": 0})
    return days, weeks, months, first_seen


def headline(days, first_seen, d):
    """The day's biggest story that first appeared that day, so consecutive days don't repeat."""
    new = [x for x in days[d]["items"] if first_seen[x["hn"]["id"]] == d]
    return max(new or days[d]["items"], key=lambda x: x["hn"].get("score", 0))


# Home / top-page windows in days before the latest day; the latest (still-growing) day is left out.
WINDOWS = {7: (1, 7), 30: (1, 30)}


def recent(days, first_seen, n, k=100):
    """Top-k stories from the n days before the latest day, ranked like the weekly/monthly digests.

    Each story counts once with its highest HN score in the window; its date is the day it first appeared.
    """
    last = max(days)
    lo, hi = WINDOWS[n]
    start, end = last - timedelta(days=hi), last - timedelta(days=lo)
    best = {}
    for d in days:
        if not start <= d <= end:
            continue
        for x in days[d]["items"]:
            i = x["hn"]["id"]
            if i not in best or x["hn"].get("score", 0) > best[i][1]["hn"].get("score", 0):
                best[i] = (first_seen[i], x)
    return sorted(best.values(), key=lambda v: -v[1]["hn"].get("score", 0))[:k]


def window_range(days, n):
    last = max(days)
    lo, hi = WINDOWS[n]
    return last - timedelta(days=hi), last - timedelta(days=lo)


# ------------------------------------------------------------------ page chrome
def chrome(body, nav_on):
    u = O.url
    links = [("", B("Today", "今日"), "today", ""), ("weekly/", B("Weekly", "周榜"), "week", ""),
             ("monthly/", B("Monthly", "月榜"), "month", ""), ("#archive", B("Archive", "往期"), "archive", ""),
             ("trends/", B("Trends", "趋势"), "trends", I["chart"]),
             ("favorites/", B("Favorites", "收藏") + "<b class='favn' hidden></b>", "fav", I["star"])]
    nav = "".join(f"<a class='{'on' if k == nav_on else ''}' href='{u('') + h if h.startswith('#') else u(h)}'>{ic}{t}</a>"
                  for h, t, k, ic in links)
    top = f"""<header class="topbar"><div class="wrap tb"><a class='logo' href='{u('')}'><b>Y</b><span>HN Daily</span></a><nav class="links">{nav}</nav>
<a class="searchbox" href="{u('search/')}">{I['search']}{B('Search all stories', '搜索全部新闻')}<kbd>/</kbd></a>
<a class="iconbtn msearch" href="{u('search/')}" title="Search">{I['search']}</a>
<button class="iconbtn" onclick="setScheme()" title="Light / dark">{I['sun']}</button>
<div class="seg lang"><button data-set='lang:zh'>中</button><button data-set='lang:en'>EN</button></div></div></header>"""
    tabs = [("", I["home"], B("Today", "今日"), ("today",)), ("#archive", I["cal"], B("Archive", "往期"), ("archive", "day", "week", "month")),
            ("trends/", I["chart"], B("Trends", "趋势"), ("trends",)), ("favorites/", I["star"], B("Saved", "收藏"), ("fav",))]
    tab = "<nav class='tabbar'>" + "".join(
        f"<a class='{'on' if nav_on in k else ''}' href='{u('') + h if h.startswith('#') else u(h)}'>{ic}<span>{t}</span></a>" for h, ic, t, k in tabs) + "</nav>"
    foot = (f"<footer class='foot wrap'>Hacker News Daily · {B('Source', '来源')}: <a href='https://news.ycombinator.com/' target='_blank' rel='noopener'>news.ycombinator.com</a>"
            f" · <a href='{O.base}feed.xml'>{I['rss']} RSS</a></footer>")
    return top + body + foot + tab


LAYOUT_HEAD = None


def write(p, title, body, nav_on, extra_js="", bare=False):
    content = "\n".join(line for line in ((body if bare else chrome(body, nav_on)) + extra_js).split("\n") if line.strip())
    path = O.file(p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if O.preview:
        doc = LAYOUT_HEAD.replace("{{ page.title }}", e(title)).replace("{{ content }}", content)
    else:
        doc = f'---\nlayout: hn2\ntitle: "{title.replace(chr(34), chr(39))}"\n---\n{{% raw %}}\n{content}\n{{% endraw %}}\n'
    if os.path.exists(path) and open(path, encoding="utf-8").read() == doc:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


# ------------------------------------------------------------------ reader pages
def story(it, i, top, day=None):
    hn = it.get("hn", {})
    url = it.get("url") or hn.get("comments_url")
    tags = "".join(tag(t) for t in it.get("tags", []))
    best = "<span class='bestb'>Best</span>" if it.get("_best") else ""
    sday = f"<a class='sday' href='{O.url(day_path(day))}'>{d_short(day)}</a>" if day else ""
    return f"""<article class="story{' top' if i < top else ''}" id="story-{hn.get('id')}" data-id="{hn.get('id')}" data-tags="{e('|'.join(it.get('tags', [])))}" data-score="{hn.get('score', 0)}" data-comments="{hn.get('descendants', 0)}" data-hn="{e(hn.get('comments_url'))}" data-time="{hn.get('time', 0)}">
<a class="thumb" href="{e(url)}" target="_blank" rel="noopener">{picture(it, 'th')}</a><button class="fav" aria-label="favorite">☆</button>
<div class="sbody"><div class="rk">{i + 1:02d}</div>
<h3 class="st"><a href="{e(url)}" target="_blank" rel="noopener">{bil(it.get('title_en'), it.get('title_zh'))}</a>{best}<span class="dom">{e(domain(url))}</span></h3>
<p class="sum one">{bil(first_sentence(it.get('summary_en')), first_sentence(it.get('summary_zh'), True))}</p>
<p class="sum full">{bil(it.get('summary_en'), it.get('summary_zh'))}</p>
<div class="sfoot"><span class="tags">{tags}</span>{sday}{meta(it)}</div></div></article>"""


VIEWS = "".join(f"<button data-set='view:{v}'>{t}</button>" for v, t in
                (("title", B("Titles", "仅标题")), ("one", B("One line", "一句话")), ("full", B("Full", "完整")), ("cards", B("Cards", "卡片"))))


def toolbar(chips):
    return f"""<div class="toolbar"><div class="wrap tbin"><div class="seg">{VIEWS}</div>
<span class="fhint">{B('Click a tag to filter', '点标签筛选')}</span><div class="filters">{chips}</div></div></div>"""


def reader(p, title_txt, kind, title_html, sub_html, items, prev_, next_, nav_on, extra="", dates=None):
    tc = Counter(t for it in items for t in it.get("tags", []))
    chips = "".join(tag(t, n, "#") for t, n in tc.most_common())
    pn = (f"<a class='pn' href='{prev_}' title='Previous'>{I['left']}</a>" if prev_ else f"<span class='pn off'>{I['left']}</span>")
    pn += (f"<a class='pn' href='{next_}' title='Next'>{I['right']}</a>" if next_ else f"<span class='pn off'>{I['right']}</span>")
    body = f"""<div class="rhead"><div class="wrap">
<div class="crumb"><span class="kind">{kind}</span>{pn}</div>
<h1 class="rtitle">{title_html}</h1><div class="rsub">{sub_html} · <b id="count">{len(items)}</b> {B('stories', '条')}</div>{extra}
</div></div>{toolbar(chips)}
<main class="wrap stories">{''.join(story(it, i, 10, dates[i] if dates else None) for i, it in enumerate(items))}</main>"""
    write(p, title_txt, body, nav_on)


def list_page(p, title_txt, kind, title_html, sub_html, rows, nav_on):
    body = f"""<div class="rhead"><div class="wrap"><div class="crumb"><span class="kind">{kind}</span></div>
<h1 class="rtitle">{title_html}</h1><div class="rsub">{sub_html}</div></div></div><main class="wrap dlist">{rows}</main>"""
    write(p, title_txt, body, nav_on)


# ------------------------------------------------------------------ home
def archive(days, weeks, months, first_seen):
    by_month = defaultdict(list)
    for d in sorted(days):
        by_month[d.strftime("%Y-%m")].append(d)
    ms = sorted(by_month, reverse=True)
    sel = next((i for i, m in enumerate(ms) if len(by_month[m]) >= 7), 0)
    heads = {d: headline(days, first_seen, d) for d in days}
    mx = max(h["hn"].get("score", 0) for h in heads.values()) or 1
    today_wk = max(days).isocalendar()[:2]

    def mlabel(m):
        f0 = date.fromisoformat(m + "-01")
        return B(f"{f0:%b %Y}", f"{f0.year}年{f0.month}月")

    chips = "".join(f"<button class='mchip{' on' if i == sel else ''}' data-m='{m}'>{mlabel(m)}</button>" for i, m in enumerate(ms))
    panels = []
    for i, m in enumerate(ms):
        ds = by_month[m]
        first = date.fromisoformat(m + "-01")
        present = set(ds)
        cells = "<i></i>" * first.weekday()
        d = first
        while d.month == first.month:
            if d in present:
                h = heads[d]
                cells += (f"<a class='hc' href='{O.url(day_path(d))}' title='{d:%b %d} · {e(h.get('title_zh'))}' "
                          f"style='--a:{0.18 + 0.82 * h['hn'].get('score', 0) / mx:.2f}'>{d.day}</a>")
            else:
                cells += f"<span class='hc off'>{d.day}</span>"
            d += timedelta(days=1)
        if m in months:
            mi = months[m]["items"]
            dig = "".join(f"<li><a href='{e(x.get('url'))}' target='_blank' rel='noopener'>{bil(x.get('title_en'), x.get('title_zh'))}</a></li>" for x in mi[:5])
            mlink = f"<a class='more' href='{O.url('monthly/' + m)}'>{B(f'Read the monthly digest · Top {len(mi)} →', f'阅读月榜 · Top {len(mi)} →')}</a>"
            mt = B("Monthly digest", "月榜")
        else:
            seen, tops = set(), []
            for x in sorted((x for dd in ds for x in days[dd]["items"]), key=lambda x: -x["hn"].get("score", 0)):
                if x["hn"]["id"] not in seen and len(tops) < 5:
                    seen.add(x["hn"]["id"])
                    tops.append(x)
            dig = "".join(f"<li><a href='{e(x.get('url'))}' target='_blank' rel='noopener'>{bil(x.get('title_en'), x.get('title_zh'))}</a></li>" for x in tops)
            mlink = f"<span class='more mute'>{B('The monthly digest publishes at month end', '月榜在月底发布')}</span>"
            mt = B("So far this month", "本月至今")
        wk = defaultdict(list)
        for dd in ds:
            wk[dd.isocalendar()[:2]].append(dd)
        strips = ""
        for (y, w) in sorted(wk, reverse=True):
            iso = f"{y}-W{w:02d}"
            cards = ""
            for dd in sorted(wk[(y, w)], reverse=True):
                h = heads[dd]
                tg = h["tags"][0] if h["tags"] else ""
                cards += (f"<a class='dc' href='{O.url(day_path(dd))}'><div class='dd'><b>{B(f'{dd:%a}', '周' + WD_ZH[dd.weekday()])}</b> {d_short(dd)}</div>"
                          f"<div class='dt'>{bil(h.get('title_en'), h.get('title_zh'))}</div>"
                          f"<div class='dm'><span>{len(days[dd]['items'])} {B('stories', '条')}</span>{tag(tg) if tg else ''}</div></a>")
            if iso in weeks:
                wl = f"<a href='{O.url('weekly/' + iso)}'>{B('Weekly digest →', '周榜 →')}</a>"
            elif (y, w) == today_wk:
                wl = f"<span class='mute'>{B('In progress', '本周进行中')}</span>"
            else:
                wl = f"<span class='mute'>{B('Digest pending', '周榜待生成')}</span>"
            strips += f"<div class='wk'><div class='wh'><b>{B(f'Week {w}', f'第 {w} 周')}</b><span>{wl}</span></div><div class='strip'>{cards}</div></div>"
        panels.append(f"""<div class='mpanel{' on' if i == sel else ''}' data-m='{m}'><div class='mtop'>
<div class='panel mdig'><div class='eyebrow'>{mt} · {B(f'{first:%B %Y}', f'{first.year}年{first.month}月')}</div><ol>{dig}</ol>{mlink}</div>
<div class='panel heat'><div class='hgrid'>{''.join(f'<span>{x}</span>' for x in 'MTWTFSS')}{cells}</div>
<small>{B('Darker = bigger top story that day · click a day to open it', '颜色越深 = 当天头条分数越高 · 点击进入当天')}</small></div></div>{strips}</div>""")
    return (f"<section id='archive' class='archive'><div class='sech'><h2>{B('Browse by month', '按月浏览')} <span class='hsub'>{B('every day, week and month', '往期每日 · 周榜 · 月榜')}</span></h2>"
            f"<div class='mchips'>{''.join(chips)}</div></div>{''.join(panels)}</section>")


def source_band(x):
    """Coloured strip with the site's favicon and domain, used where a story has no real image."""
    d = domain(x.get("url"))
    return (f"<div class='band'><img class='fbi' src='https://www.google.com/s2/favicons?domain={e(d)}&amp;sz=64' alt='' loading='lazy'>"
            f"<span>{e(d)}</span></div>")


def top_block(mode, pairs, label, all_href, on):
    """Lead + four cards + list (ranks 1, 2-5, 6-15). Stories without a real image use text layouts."""
    url = lambda x: e(x.get("url") or x["hn"].get("comments_url"))
    when = (lambda d: "") if mode == "today" else (lambda d: f" · {d_short(d)}")
    (d0, lead), sub4, more = pairs[0], pairs[1:5], pairs[5:15]

    def shell(x, cls):
        has = bool(image_of(x))
        c = tcolor((x.get("tags") or [""])[0])
        return has, f"class='{cls} panel{'' if has else ' noimg'}' style='--c:{c}'"

    has, attrs = shell(lead, "lead")
    leadh = f"""<a {attrs} href="{url(lead)}" target="_blank" rel="noopener">{picture(lead, 'limg') if has else ''}<div class="ltxt">{'' if has else source_band(lead)}
<div class="eyebrow">#01 · {label}{when(d0)}</div><h2>{bil(lead.get('title_en'), lead.get('title_zh'))}</h2>
<div class="alt">{bil(lead.get('title_zh'), lead.get('title_en'))}</div><p>{bil(lead.get('summary_en'), lead.get('summary_zh'))}</p>
<div class="sfoot"><span class="tags">{''.join(tag(t) for t in lead['tags'])}</span>{meta(lead, link=False)}</div></div></a>"""
    cards = ""
    for i, (d, x) in enumerate(sub4):
        has, attrs = shell(x, "card")
        summary = (bil(first_sentence(x.get('summary_en')), first_sentence(x.get('summary_zh'), True)) if has
                   else bil(x.get('summary_en'), x.get('summary_zh')))
        cards += f"""<a {attrs} href="{url(x)}" target="_blank" rel="noopener">{picture(x, 'cimg') if has else source_band(x)}<div class="ctxt"><div class="n">{i + 2:02d}<small>{when(d)}</small></div>
<h3>{bil(x.get('title_en'), x.get('title_zh'))}</h3><p>{summary}</p>
<div class="sfoot"><span class="tags">{''.join(tag(t) for t in x['tags'][:2])}</span>{meta(x, link=False)}</div></div></a>"""
    rows = "".join(f"""<a class="row" href="{url(x)}" target="_blank" rel="noopener"><div class="n">{i + 6:02d}</div><div><h4>{bil(x.get('title_en'), x.get('title_zh'))}</h4>
<p>{bil(first_sentence(x.get('summary_en')), first_sentence(x.get('summary_zh'), True))}</p>{f"<span class='rd'>{d_short(d)}</span>" if mode != 'today' else ''}</div></a>""" for i, (d, x) in enumerate(more))
    return f"""<div class="tblock{' on' if on else ''}" data-mode="{mode}">{leadh}<div class="cards">{cards}</div>
<div class="rows">{rows}</div><a class="readall" href="{all_href}">{B('Read all stories →', '阅读全部 →')}</a></div>"""


def home(days, weeks, months, first_seen):
    last = max(days)
    d = days[last]
    items = sorted(d["items"], key=lambda x: -(x.get("hot_score") or 0))
    tc = Counter(t for dd in days for x in days[dd]["items"] for t in x["tags"])
    stats = f"""<div class="kpis"><div><b>{len(items)}</b><small>{B('stories today', '今日新闻')}</small></div>
<div><b>{items[0]['hn'].get('score', 0):,}</b><small>{B('top score today', '今日最高分')}</small></div>
<div><b>{len(first_seen):,}</b><small>{B(f'stories · {len(days)} days', f'条新闻 · {len(days)} 天')}</small></div>
<div><b>{tc.most_common(1)[0][0] if tc else '—'}</b><small>{B('hottest topic', '最热话题')}</small></div></div>"""
    intro = f"""<section class="hero"><div class="eyebrow"><span class="live"></span>{updated(d['meta'].get('run_time_local') or d['meta'].get('scrape_time_display'))}</div>
<h1>The best of Hacker News, <em>distilled daily.</em></h1><p class="lede">{B('AI-curated tech news, bilingual summaries and topic tags, updated twice a day.', '每天两次，AI 精选、双语摘要、自动分类的技术新闻。')}</p>{stats}</section>"""
    blocks = (top_block("today", [(last, x) for x in items], B("Today's top story", "今日头条"), O.url(day_path(last)), True)
              + top_block("7d", recent(days, first_seen, 7), B("Top of the past 7 days", "过去 7 天最热"), O.url("top/7d"), False)
              + top_block("30d", recent(days, first_seen, 30), B("Top of the past 30 days", "过去 30 天最热"), O.url("top/30d"), False))
    switch = (f"<div class='seg modes'><button class='on' data-mode='today'>{B('Today', '今天')}</button>"
              f"<button data-mode='7d'>{B('Past 7 days', '过去 7 天')}</button><button data-mode='30d'>{B('Past 30 days', '过去 30 天')}</button></div>")
    body = f"""<main class="wrap home">{intro}
<div class="sech top"><h2>{B('Top stories', '热门新闻')} <span class='hsub'>{B(d_en(last), d_zh(last))}</span></h2>{switch}</div>{blocks}
{archive(days, weeks, months, first_seen)}</main>"""
    write("", "Hacker News Daily", body, "today")


# ------------------------------------------------------------------ trends
def spark(vals, color, w=260, h=56):
    mx = max(vals or [0]) or 1
    pts = " ".join(f"{i * w / max(len(vals) - 1, 1):.1f},{h - 4 - (v / mx) * (h - 8):.1f}" for i, v in enumerate(vals))
    return (f"<svg class='spark' viewBox='0 0 {w} {h}' preserveAspectRatio='none'><polygon points='0,{h} {pts} {w},{h}' fill='{color}' opacity='.14'/>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2' vector-effect='non-scaling-stroke'/></svg>")


def trends(days):
    last = max(days)
    seen = {}
    for d in sorted(days):
        for x in days[d]["items"]:
            seen.setdefault(x["hn"]["id"], (d, x))
    weeks = sorted({d.isocalendar()[:2] for d, _ in seen.values()})
    wi = {w: i for i, w in enumerate(weeks)}
    series = defaultdict(lambda: [0] * len(weeks))
    total, n30, p30 = Counter(), Counter(), Counter()
    stories30 = defaultdict(list)
    for d, x in seen.values():
        for t in x["tags"]:
            series[t][wi[d.isocalendar()[:2]]] += 1
            total[t] += 1
            if d > last - timedelta(days=30):
                n30[t] += 1
                stories30[t].append((d, x))
            elif d > last - timedelta(days=60):
                p30[t] += 1
    partial = last.isocalendar()[2] < 7
    cards = ""
    for t, _ in sorted(total.items(), key=lambda kv: (-n30[kv[0]], -kv[1])):
        c = tcolor(t)
        ch = (n30[t] - p30[t]) / p30[t] * 100 if p30[t] else 0
        top3 = sorted(stories30[t], key=lambda v: -v[1]["hn"].get("score", 0))[:3]
        li = "".join(f"<li><a href='{e(x.get('url'))}' target='_blank' rel='noopener'>{bil(x.get('title_en'), x.get('title_zh'))}</a>"
                     f"<div class='tmeta'>{I['up']}{x['hn'].get('score', 0):,} · <a href='{O.url(day_path(d))}'>{d_short(d)}</a></div></li>" for d, x in top3)
        cards += f"""<div class="panel tcard" style="--c:{c}"><div class="tch"><a class="tname" href="{O.url('search/')}?tag={e(t)}">{tag(t)}</a>
<span class="tdelta {'up' if ch >= 0 else 'down'}">{'▲' if ch >= 0 else '▼'} {abs(ch):.0f}%</span></div>
<div class="tnum"><b>{n30[t]}</b><small>{B('stories · last 30 days', '条 · 近 30 天')}</small><small class="tall">{B(f'{total[t]:,} all time', f'累计 {total[t]:,}')}</small></div>
{spark(series[t][:-1] if partial and len(series[t]) > 1 else series[t], c)}<ol class="tlist">{li}</ol></div>"""
    rising = sorted((t for t in total if p30[t] >= 10), key=lambda t: -(n30[t] - p30[t]) / p30[t])[:5]
    rise = "".join(f"<a class='rise' href='{O.url('search/')}?tag={e(t)}' style='--c:{tcolor(t)}'>{e(t)}<b>{(n30[t] - p30[t]) / p30[t] * 100:+.0f}%</b></a>" for t in rising)
    body = f"""<div class="rhead"><div class="wrap"><div class="crumb"><span class="kind">{B('Trends', '趋势')}</span></div>
<h1 class="rtitle">{B('Topic trends', '话题趋势')}</h1>
<div class="rsub">{B(f'{len(seen):,} unique stories · {d_en(min(days), False)} — {d_en(last, False)} · weekly counts per tag',
                     f'{len(seen):,} 条不重复新闻 · {d_zh(min(days), False)} — {d_zh(last, False)} · 每个标签按周统计')}</div>
<div class="risers"><span>{B('Rising vs previous 30 days', '比前 30 天上升最快')}</span>{rise}</div></div></div>
<main class="wrap tgrid">{cards}</main>"""
    write("trends/", "Trends · Hacker News Daily", body, "trends")


# ------------------------------------------------------------------ favorites & search
def favorites_page():
    body = f"""<div class="rhead"><div class="wrap"><div class="crumb"><span class="kind">{B('Favorites', '收藏')}</span></div>
<h1 class="rtitle">{B('Saved stories', '我的收藏')}</h1>
<div class="rsub">{B('Stored only in this browser — no account needed', '只保存在本浏览器，不需要账号')} · <b id="count">0</b> {B('stories', '条')}</div>
<div class="favbar"><div class="seg"><button data-sort="added">{B('Recently saved', '最近收藏')}</button><button data-sort="score">{B('Score', '分数')}</button></div>
<button class="ghost" id="clear">{B('Clear all', '清空')}</button></div></div></div>{toolbar('')}
<div class="wrap"><p id="empty" class="empty" hidden>{B('No favorites yet. Tap ☆ on any story to save it here.', '还没有收藏。点任意新闻右上角的 ☆ 即可收藏。')}</p></div>
<main class="wrap stories"></main>"""
    write("favorites/", "Favorites · Hacker News Daily", body, "fav", "<script>window.addEventListener('DOMContentLoaded',()=>HN2.favoritesPage())</script>")


def search_page():
    body = f"""<div class="rhead"><div class="wrap"><div class="crumb"><span class="kind">{B('Search', '搜索')}</span></div>
<div class="sbox">{I['search']}<input id="q" type="search" autocomplete="off" placeholder="Search titles, 中文标题, tags, domains…"></div>
<div class="rsub"><b id="count">…</b> {B('results of', '条结果，共')} <span id="total">…</span> {B('stories', '条')}
<span class="seg sm sortseg"><button data-sort="relevance">{B('Relevance', '相关')}</button><button data-sort="date">{B('Newest', '最新')}</button><button data-sort="score">{B('Score', '分数')}</button></span></div></div></div>
{toolbar(''.join(tag(t, None, '#') for t in TAG_COLORS))}<main class="wrap stories"></main><div class="wrap"><button id="more" class="readall" hidden>{B('Show more', '显示更多')}</button></div>"""
    write("search/", "Search · Hacker News Daily", body, "search", "<script>window.addEventListener('DOMContentLoaded',()=>HN2.searchPage())</script>")


def search_index(days):
    """One JSON shard per month so a scheduled run only rewrites the current month."""
    seen = {}
    for d in sorted(days, reverse=True):
        for x in days[d]["items"]:
            i = x["hn"]["id"]
            if i not in seen:
                seen[i] = [i, x.get("title_en"), x.get("title_zh"), x.get("url") or "", x["tags"], x["hn"].get("score", 0), str(d),
                           first_sentence(x.get("summary_en")), first_sentence(x.get("summary_zh"), True), x["hn"].get("descendants", 0), image_of(x)]
            else:
                seen[i][5] = max(seen[i][5], x["hn"].get("score", 0))
    shards = defaultdict(list)
    for row in seen.values():
        shards[row[6][:7]].append(row)
    out = os.path.join(O.dir, "search")
    os.makedirs(out, exist_ok=True)
    for m, rows in shards.items():
        s = json.dumps(sorted(rows, key=lambda r: r[6]), ensure_ascii=False, separators=(",", ":"))
        p = os.path.join(out, f"{m}.json")
        if not (os.path.exists(p) and open(p, encoding="utf-8").read() == s):
            open(p, "w", encoding="utf-8").write(s)
    man = json.dumps({"shards": sorted(shards, reverse=True), "total": len(seen)}, separators=(",", ":"))
    open(os.path.join(out, "manifest.json"), "w").write(man)


# ------------------------------------------------------------------ build
def build(preview_dir=None):
    global O, LAYOUT_HEAD
    O = Out(preview_dir)
    days, weeks, months, first_seen = load()
    if not days:
        return
    if preview_dir:
        lay = open(os.path.join(ROOT_DIR, "_layouts", "hn2.html"), encoding="utf-8").read()
        LAYOUT_HEAD = (lay.replace("/hackernews/", "/").replace("{{ site.time | date: '%s' }}", "preview")
                       .replace("ext:''", "ext:'.html'"))
        os.makedirs(os.path.join(preview_dir, "assets/hn/v2"), exist_ok=True)
        for f in glob.glob(os.path.join(ROOT_DIR, "assets/hn/v2/*")):
            open(os.path.join(preview_dir, "assets/hn/v2", os.path.basename(f)), "w").write(open(f).read())
    search_index(days)
    home(days, weeks, months, first_seen)
    trends(days)
    favorites_page()
    search_page()
    ds = sorted(days)
    for i, d in enumerate(ds):
        dm, dd = days[d]["meta"], days[d]
        p = O.url(day_path(ds[i - 1])) if i else None
        n = O.url(day_path(ds[i + 1])) if i + 1 < len(ds) else None
        iso = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        extra = (f"<div class='rlinks'><a href='{O.url('weekly/' + iso)}'>{B(f'Week {d.isocalendar()[1]} digest →', f'第 {d.isocalendar()[1]} 周周榜 →')}</a></div>" if iso in weeks else "")
        parts = (B(f"Daily Best {dd['best_n']} + Trending {dd['top_n']}", f"每日最佳 {dd['best_n']} + 热门 {dd['top_n']}") if dd["best_n"] and dd["top_n"]
                 else e(dm.get("edition_label") or ("Daily Best" if dd["best_n"] else "")))
        sub = f"{parts} · {updated(dm.get('run_time_local') or dm.get('scrape_time_display'))}"
        args = (B("Daily", "每日"), B(d_en(d), d_zh(d)), sub, dd["items"], p, n, "day", extra)
        reader(day_path(d), f"Hacker News Daily — {d}", *args)
        if "best" in dd["files"]:
            target = O.url(day_path(d))
            write(f"{d:%Y/%m/%d}/best_stories_{d:%m%d%Y}", f"Hacker News Daily — {d}",
                  f"<p class='wrap'><a href='{target}'>{d_en(d)} →</a></p><script>location.replace('{target}'+location.hash)</script>", "day", bare=True)
    wl = sorted(weeks)
    for i, k in enumerate(wl):
        m = weeks[k]["meta"]
        a, b = date.fromisoformat(m["date_start"]), date.fromisoformat(m["date_end"])
        title = B(f"Week {int(k[-2:])} · {a:%b} {a.day} – {b:%b} {b.day}, {b.year}", f"第 {int(k[-2:])} 周 · {a.month}月{a.day}日 – {b.month}月{b.day}日")
        sub = B(f"Top {len(weeks[k]['items'])} of {m['total_pool']} stories", f"{m['total_pool']} 条中的 Top {len(weeks[k]['items'])}")
        reader("weekly/" + k, f"Weekly Digest {k} — Hacker News Daily", B("Weekly", "周榜"), title, sub, weeks[k]["items"],
               O.url("weekly/" + wl[i - 1]) if i else None, O.url("weekly/" + wl[i + 1]) if i + 1 < len(wl) else None, "week")
    rows = "".join(f"<a class='panel drow' href='{O.url('weekly/' + k)}'><b>{B(f'Week {int(k[-2:])}', f'第 {int(k[-2:])} 周')}</b>"
                   f"<span>{B(weeks[k]['meta']['date_start'] + ' – ' + weeks[k]['meta']['date_end'], weeks[k]['meta']['date_start'] + ' – ' + weeks[k]['meta']['date_end'])}</span>"
                   f"<em>{bil(weeks[k]['items'][0].get('title_en'), weeks[k]['items'][0].get('title_zh'))}</em></a>" for k in reversed(wl) if weeks[k]["items"])
    list_page("weekly/", "Weekly Digests — Hacker News Daily", B("Weekly", "周榜"), B("Weekly digests", "每周周榜"),
              B(f"{len(wl)} weeks · Top 100 per week", f"共 {len(wl)} 周 · 每周 Top 100"), rows, "week")
    ml = sorted(months)
    for i, k in enumerate(ml):
        m = months[k]["meta"]
        f0 = date.fromisoformat(k + "-01")
        sub = B(f"Top {len(months[k]['items'])} of {m['total_pool']} stories", f"{m['total_pool']} 条中的 Top {len(months[k]['items'])}")
        reader("monthly/" + k, f"Monthly Digest {k} — Hacker News Daily", B("Monthly", "月榜"), B(f"{f0:%B %Y}", f"{f0.year}年{f0.month}月"), sub,
               months[k]["items"], O.url("monthly/" + ml[i - 1]) if i else None, O.url("monthly/" + ml[i + 1]) if i + 1 < len(ml) else None, "month")
    def month_row(k):
        f0, mi = date.fromisoformat(k + "-01"), months[k]["items"]
        return (f"<a class='panel drow' href='{O.url('monthly/' + k)}'><b>{B(f'{f0:%B %Y}', f'{f0.year}年{f0.month}月')}</b>"
                f"<span>Top {len(mi)}</span><em>{bil(mi[0].get('title_en'), mi[0].get('title_zh'))}</em></a>")
    rows = "".join(month_row(k) for k in reversed(ml) if months[k]["items"])
    list_page("monthly/", "Monthly Digests — Hacker News Daily", B("Monthly", "月榜"), B("Monthly digests", "每月月榜"),
              B(f"{len(ml)} months", f"共 {len(ml)} 个月"), rows, "month")
    for n, en, zh in ((7, "Past 7 days", "过去 7 天"), (30, "Past 30 days", "过去 30 天")):
        pairs = recent(days, first_seen, n)
        a, b = window_range(days, n)
        sub = B(f"{a:%b} {a.day} – {b:%b} {b.day} · excluding today · ranked by highest HN score, each story once",
                f"{a.month}月{a.day}日 – {b.month}月{b.day}日 · 不含今天 · 按最高 HN 分数排序，同一新闻只出现一次")
        reader(f"top/{n}d", f"{en} — Hacker News Daily", B("Trending", "热门"), B(en, zh), sub,
               [x for _, x in pairs], None, None, "today", dates=[d for d, _ in pairs])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="write a standalone .html preview into this directory")
    args = ap.parse_args()
    build(os.path.abspath(args.preview) if args.preview else None)
