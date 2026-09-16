#!/usr/bin/env python3
"""Build the static site from content/*.md into docs/.

Plain HTML/CSS/JS -- no build toolchain, no Jekyll. The output directory can be
served by GitHub Pages straight from the docs/ folder on main.

Content lives in content/*.md and is the single source of truth. The CV page is
generated from exactly the same entries as the rest of the site, so it can never
drift out of date.
"""
import re
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "docs"

YEAR = re.compile(r"\((19|20)(\d{2})\)")
TAG = re.compile(r"<[^>]+>")

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
MD_BOTH = re.compile(r"\*\*\*(.+?)\*\*\*", re.S)
MD_STRONG = re.compile(r"\*\*(.+?)\*\*", re.S)
MD_EM = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)

# ---------------------------------------------------------------- identity
NAME = "Shinji Watanabe"
ROLE = "Associate Professor"
AFFIL = "Carnegie Mellon University"
DEPT = "Language Technologies Institute"
EMAIL = "shinjiw_at_ieee.org or swatanab_at_andrew.cmu.edu"

PROFILE_LINKS = [
    ("Google Scholar", "https://scholar.google.com/citations?user=U5xRA6QAAAAJ"),
    ("GitHub", "https://github.com/sw005320"),
    ("WAVLab", "https://www.wavlab.org/"),
    ("CMU LTI", "https://lti.cmu.edu/people/faculty/watanabe-shinji.html"),
    ("Curriculum Vitae", "cv.html"),
]

# Each project lists its own links: the project page first, then the published
# paper, then the preprint. Unlike the per-entry links dropped from the
# publication list, these are fixed per project and do not need upkeep.
SOFTWARE = [
    {
        "name": "ESPnet",
        "tagline": "End-to-End Speech Processing Toolkit",
        "url": "https://github.com/espnet/espnet",
        "links": [
            ("Documentation", "https://espnet.github.io/espnet/"),
            ("Paper (Interspeech'18)", "https://doi.org/10.21437/Interspeech.2018-1456"),
            ("arXiv", "https://arxiv.org/abs/1804.00015"),
        ],
        "body": "An open-source toolkit for speech recognition, text-to-speech, "
                "speech enhancement, speech translation, and spoken language "
                "understanding. It provides reproducible recipes and a complete "
                "setup for speech foundation model research.",
    },
    {
        "name": "VERSA",
        "tagline": "Versatile Evaluation of Speech and Audio",
        "url": "https://github.com/wavlab-speech/versa",
        "links": [
            ("Paper (NAACL'25)", "https://aclanthology.org/2025.naacl-demo.19/"),
            ("arXiv", "https://arxiv.org/abs/2412.17667"),
        ],
        "body": "A toolkit for evaluating speech and audio quality. It provides "
                "seamless access to over 90 evaluation and profiling metrics with "
                "10x variants, assessing audio through multiple dimensions.",
    },
    {
        "name": "OWSM",
        "tagline": "Open Whisper-style Speech Models",
        "url": "https://www.wavlab.org/activities/2024/owsm/",
        "links": [
            ("Paper (ASRU'23)", "https://doi.org/10.1109/ASRU57964.2023.10389676"),
            ("arXiv", "https://arxiv.org/abs/2309.13876"),
        ],
        "body": "Reproduces Whisper-style training using publicly available data "
                "and ESPnet. Data preparation scripts, training and inference code, "
                "pre-trained model weights, and training logs are all publicly released.",
    },
]

PAGES = [("index.html", "Home"), ("publications.html", "Publications"),
         ("activities.html", "Activities"), ("software.html", "Software"),
         ("cv.html", "CV")]

# Which website sections go into the CV, in order. Each CV heading pulls one or
# more sections; when it pulls more than one, their names become sub-headings.
CV_LAYOUT = [
    ("Education", [("activities", "Education")]),
    ("Appointments", [("activities", "Work Experience")]),
    ("Awards and Honours", [("activities", "Award and Notable Achievement")]),
    ("Teaching", [("activities", "Teaching")]),
    ("Skills", [("cv", "Programming Skills"), ("cv", "Language Skills")]),
    ("Invited Talks", [
        ("publications", "Keynote talk"),
        ("publications", "Tutorial/Overview/Invited talk"),
        ("activities", "Seminar"),
    ]),
    ("Professional Service", [
        ("activities", "Membership"),
        ("activities", "Organizer/Committee Member"),
        ("activities", "Editor"),
        ("activities", "Session Chair"),
        ("activities", "Conference Review"),
        ("activities", "Journal/Transaction Review"),
        ("activities", "External PhD Thesis Review/Committee"),
    ]),
    ("Research Projects", [("activities", "Joint Research Projects")]),
    ("Advising and Collaboration", [
        ("activities", "At CMU"),
        ("activities", "At JHU"),
        ("activities", "At MERL"),
        ("activities", "At NTT"),
    ]),
    ("Publications", [
        ("publications", "Book"),
        ("publications", "Book chapter"),
        ("publications", "PhD thesis"),
        ("publications", "Review and overview paper"),
        ("publications", "Journal (refereed)"),
        ("publications", "International Conference and Workshop (refereed)"),
    ]),
]


# ---------------------------------------------------------------- content
def md_inline(s):
    s = escape(s, quote=False)
    s = MD_LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = MD_BOTH.sub(lambda m: f"<strong><em>{m.group(1)}</em></strong>", s)
    s = MD_STRONG.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = MD_EM.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    return s


def read_sections(name):
    """Parse content/<name>.md into [{level, title, items}]."""
    text = (CONTENT / f"{name}.md").read_text(encoding="utf-8")
    sections, current, buf = [], None, []

    def flush():
        if current is not None and buf:
            current["items"].append(md_inline(" ".join(buf).strip()))
        buf.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!--"):
            continue
        if stripped.startswith("## ") or stripped.startswith("### "):
            flush()
            level = "h2" if stripped.startswith("## ") else "h3"
            current = {"level": level, "title": stripped.lstrip("#").strip(), "items": []}
            sections.append(current)
            continue
        if not stripped:
            flush()
            continue
        buf.append(stripped)
    flush()
    return sections


def read_bio():
    text = (CONTENT / "home.md").read_text(encoding="utf-8")
    paras, buf = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!--"):
            continue
        if not stripped:
            if buf:
                paras.append(md_inline(" ".join(buf)))
                buf = []
            continue
        buf.append(stripped)
    if buf:
        paras.append(md_inline(" ".join(buf)))
    return paras


def find(sections, title):
    for s in sections:
        if s["title"] == title:
            return s
    raise KeyError(f"section not found: {title!r}")


# ---------------------------------------------------------------- helpers
def year_of(entry_html):
    hits = YEAR.findall(TAG.sub("", entry_html))
    return hits[-1][0] + hits[-1][1] if hits else ""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def shell(active, title, body, extra_js=""):
    nav = "\n".join(
        f'      <a href="{href}"{" class=\"on\"" if label == active else ""}>{label}</a>'
        for href, label in PAGES
    )
    js = f'\n  <script src="{extra_js}"></script>' if extra_js else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="topbar">
  <a class="brand" href="index.html">{NAME}</a>
  <nav>
{nav}
  </nav>
  <div class="controls">
    <div class="swatches" role="group" aria-label="Colour palette">
      <button class="swatch paper" type="button" data-palette="paper" aria-label="Paper palette"></button>
      <button class="swatch slate" type="button" data-palette="slate" aria-label="Slate palette"></button>
      <button class="swatch forest" type="button" data-palette="forest" aria-label="Forest palette"></button>
    </div>
    <button id="theme" class="theme" type="button" aria-label="Toggle light or dark">&#9681;</button>
  </div>
</header>
<main>
{body}
</main>
<footer>
  <p>Built from content/*.md &mdash; prototype.</p>
</footer>
<script src="app.js"></script>{js}
</body>
</html>
"""


# ---------------------------------------------------------------- pages
def home_page(bio):
    paras = "\n".join(f"    <p>{p}</p>" for p in bio)
    links = "\n".join(
        f'      <a class="pill" href="{u}">{escape(t)}</a>' for t, u in PROFILE_LINKS
    )
    cards = "\n".join(
        f"""      <a class="card" href="{s['url']}">
        <h3>{escape(s['name'])}</h3>
        <p>{escape(s['tagline'])}</p>
      </a>"""
        for s in SOFTWARE
    )
    return shell("Home", NAME, f"""  <section class="hero">
    <img class="portrait" src="assets/shinji.jpg" width="168" height="168"
         alt="Portrait of {NAME}">
    <div class="who">
      <h1>{NAME}</h1>
      <p class="role">{ROLE} &middot; <span>{AFFIL}</span></p>
      <p class="email">{escape(EMAIL)}</p>
      <div class="pills">
{links}
      </div>
    </div>
  </section>

  <section>
    <h2>Short bio</h2>
{paras}
  </section>

  <section>
    <h2>Software</h2>
    <div class="cards">
{cards}
    </div>
  </section>
""")


def publications_page(sections):
    total = sum(len(s["items"]) for s in sections)
    years = sorted(
        {year_of(i) for s in sections for i in s["items"] if year_of(i)}, reverse=True
    )
    opts = "\n".join(f'      <option value="{y}">{y}</option>' for y in years)

    blocks = []
    for s in sections:
        items = "\n".join(
            f'        <li data-year="{year_of(i)}">{i}</li>' for i in s["items"]
        )
        blocks.append(f"""  <details class="sec" open id="{slug(s['title'])}">
    <summary><span class="t">{escape(s['title'])}</span>
      <span class="count"><span class="shown">{len(s['items'])}</span> / {len(s['items'])}</span>
    </summary>
    <ol class="entries">
{items}
    </ol>
  </details>""")

    body = f"""  <h1>Publications</h1>
  <p class="lede">{total} entries across {len(sections)} categories.</p>

  <div class="toolbar">
    <input id="q" type="search" placeholder="Search titles, authors, venues&hellip;"
           autocomplete="off" aria-label="Search publications">
    <select id="year" aria-label="Filter by year">
      <option value="">All years</option>
{opts}
    </select>
    <button type="button" data-all="open">Expand all</button>
    <button type="button" data-all="close">Collapse all</button>
  </div>
  <p id="status" class="status" role="status"></p>

{chr(10).join(blocks)}
"""
    return shell("Publications", f"Publications — {NAME}", body, "filter.js")


def activities_page(sections):
    blocks = []
    for s in sections:
        if not s["items"]:
            blocks.append(f'  <p class="group">{escape(s["title"])}</p>')
            continue
        items = "\n".join(f"        <li>{i}</li>" for i in s["items"])
        cls = "sec sub" if s["level"] == "h3" else "sec"
        blocks.append(f"""  <details class="{cls}" id="{slug(s['title'])}">
    <summary><span class="t">{escape(s['title'])}</span>
      <span class="count">{len(s['items'])}</span>
    </summary>
    <ul class="entries">
{items}
    </ul>
  </details>""")
    total = sum(len(s["items"]) for s in sections)
    body = f"""  <h1>Activities</h1>
  <p class="lede">{total} entries. Sections are collapsed &mdash; click to open.</p>
  <div class="toolbar">
    <button type="button" data-all="open">Expand all</button>
    <button type="button" data-all="close">Collapse all</button>
  </div>

{chr(10).join(blocks)}
"""
    return shell("Activities", f"Activities — {NAME}", body)


def software_page():
    blocks = []
    for s in SOFTWARE:
        pills = [("Project page", s["url"])] + list(s.get("links") or [])
        rendered = "\n".join(
            f'      <a class="pill" href="{url}">{escape(label)}</a>'
            for label, url in pills
        )
        blocks.append(f"""  <section class="proj">
    <h2><a href="{s['url']}">{escape(s['name'])}</a></h2>
    <p class="tagline">{escape(s['tagline'])}</p>
    <p>{escape(s['body'])}</p>
    <div class="pills">
{rendered}
    </div>
  </section>""")
    body = "  <h1>Software</h1>\n" + "\n".join(blocks) + "\n"
    return shell("Software", f"Software — {NAME}", body)


def cv_page(sources):
    """The CV, assembled from the same sections the rest of the site uses."""
    blocks, counted = [], 0
    for heading, refs in CV_LAYOUT:
        parts = []
        for source, title in refs:
            sec = find(sources[source], title)
            if not sec["items"]:
                continue
            counted += len(sec["items"])
            label = ""
            if len(refs) > 1:
                label = f'      <h3 class="cv-sub">{escape(title)}</h3>\n'
            items = "\n".join(f"        <li>{i}</li>" for i in sec["items"])
            parts.append(f"{label}      <ol class=\"cv-list\">\n{items}\n      </ol>")
        if parts:
            blocks.append(
                f'  <section class="cv-block">\n'
                f"    <h2>{escape(heading)}</h2>\n"
                + "\n".join(parts)
                + "\n  </section>"
            )

    links = " &middot; ".join(
        f'<a href="{u}">{escape(t)}</a>' for t, u in PROFILE_LINKS
        if not u.endswith("cv.html")
    )
    today = date.today().strftime("%d %B %Y")

    body = f"""  <div class="cv-actions">
    <button type="button" onclick="window.print()">Print / Save as PDF</button>
    <span class="cv-note">{counted} entries &middot; generated {today}</span>
  </div>

  <article class="cv">
    <header class="cv-head">
      <h1>{NAME}</h1>
      <p class="cv-role">{ROLE}, {DEPT}, {AFFIL}</p>
      <p class="cv-contact">{escape(EMAIL)}</p>
      <p class="cv-contact">{links}</p>
    </header>

{chr(10).join(blocks)}
  </article>
"""
    return shell("CV", f"Curriculum Vitae — {NAME}", body)


def main():
    SITE.mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)

    pubs = read_sections("publications")
    acts = read_sections("activities")
    bio = read_bio()
    sources = {"publications": pubs, "activities": acts,
               "cv": read_sections("cv-extra")}

    (SITE / "index.html").write_text(home_page(bio), encoding="utf-8")
    (SITE / "publications.html").write_text(publications_page(pubs), encoding="utf-8")
    (SITE / "activities.html").write_text(activities_page(acts), encoding="utf-8")
    (SITE / "software.html").write_text(software_page(), encoding="utf-8")
    (SITE / "cv.html").write_text(cv_page(sources), encoding="utf-8")

    n_pub = sum(len(s["items"]) for s in pubs)
    n_act = sum(len(s["items"]) for s in acts)
    print(f"index.html          {len(bio)} bio paragraph(s)")
    print(f"publications.html   {n_pub} entries")
    print(f"activities.html     {n_act} entries")
    print(f"software.html       {len(SOFTWARE)} projects")

    used = {(src, t) for _, refs in CV_LAYOUT for src, t in refs}
    allsec = {("publications", s["title"]) for s in pubs if s["items"]} | \
             {("activities", s["title"]) for s in acts if s["items"]}
    missing = sorted(allsec - used)
    print(f"cv.html             {len(CV_LAYOUT)} headings")
    if missing:
        print("  not in the CV:", ", ".join(f"{a}/{b}" for a, b in missing))


if __name__ == "__main__":
    main()
