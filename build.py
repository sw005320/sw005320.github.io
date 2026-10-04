#!/usr/bin/env python3
"""Build the static site from content/*.md into docs/.

Plain HTML/CSS/JS -- no build toolchain, no Jekyll. The output directory can be
served by GitHub Pages straight from the docs/ folder on main.

Content lives in content/*.md and is the single source of truth. The CV page is
generated from exactly the same entries as the rest of the site, so it can never
drift out of date.
"""
import re
import shutil
from difflib import get_close_matches
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"       # css, js, images -- copied verbatim into the build
SITE = ROOT / "docs"
NOTES = CONTENT / "notes"   # one Markdown file per note, named YYYY-MM-DD-slug.md

YEAR = re.compile(r"\((19|20)(\d{2})\)")
TAG = re.compile(r"<[^>]+>")

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
MD_BOTH = re.compile(r"\*\*\*(.+?)\*\*\*", re.S)
MD_STRONG = re.compile(r"\*\*(.+?)\*\*", re.S)
MD_EM = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)
NOTE_FILE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-([a-z0-9-]+)\.md$")
MD_HEADING = re.compile(r"^(#{1,3})\s+(.*)")
MD_ITEM = re.compile(r"^(\d+\.|[-*])\s+(.*)")

# ---------------------------------------------------------------- identity
NAME = "Shinji Watanabe"
ROLE = "Associate Professor"
AFFIL = "Carnegie Mellon University"
DEPT = "Language Technologies Institute"
EMAIL = "shinjiw_at_ieee.org or swatanab_at_andrew.cmu.edu"

PROFILE_LINKS = [
    ("Google Scholar", "https://scholar.google.com/citations?user=U5xRA6QAAAAJ"),
    ("GitHub", "https://github.com/sw005320"),
    ("X", "https://x.com/shinjiw_at_cmu"),
    ("LinkedIn", "https://www.linkedin.com/in/shinji-watanabe-82533520/"),
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
         ("notes.html", "Notes"), ("cv.html", "CV")]

# Which website sections go into the CV, in order. Each CV heading pulls one or
# more sections; when it pulls more than one, their names become sub-headings.
CV_LAYOUT = [
    ("Education", [("activities", "Education")]),
    ("Appointments", [("activities", "Work Experience")]),
    ("Awards and Honours", [("activities", "Awards and Notable Achievements")]),
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
    """Parse content/<name>.md into [{level, title, items, groups}].

    `####` is a label *inside* a section, not a section of its own -- the
    collaborator lists are grouped into Post-doc, CMU student and so on. Keeping
    them inside means `items` still holds everything and CV_LAYOUT, which refers
    to sections by name, is unaffected. `groups` is [(label or None, [items])].
    """
    text = (CONTENT / f"{name}.md").read_text(encoding="utf-8")
    sections, current, buf = [], None, []

    def flush():
        if current is not None and buf:
            item = md_inline(" ".join(buf).strip())
            current["items"].append(item)
            current["groups"][-1][1].append(item)
        buf.clear()

    def new_group(label):
        if current is not None:
            current["groups"].append((label, []))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!--"):
            continue
        if stripped.startswith("#### "):
            flush()
            new_group(stripped[5:].strip())
            continue
        if stripped.startswith("## ") or stripped.startswith("### "):
            flush()
            level = "h2" if stripped.startswith("## ") else "h3"
            current = {"level": level, "title": stripped.lstrip("#").strip(),
                       "items": [], "groups": [(None, [])]}
            sections.append(current)
            continue
        if not stripped:
            flush()
            continue
        buf.append(stripped)
    flush()
    for sec in sections:
        sec["groups"] = [g for g in sec["groups"] if g[1]]
    return sections


def grouped_list(section, tag="ul", cls="entries"):
    """Render a section's entries, with a label above each group that has one."""
    out = []
    for label, items in section["groups"]:
        if label:
            out.append(f'      <p class="sublabel">{escape(label)}</p>')
        rows = "\n".join(f"        <li>{i}</li>" for i in items)
        out.append(f'      <{tag} class="{cls}">\n{rows}\n      </{tag}>')
    return "\n".join(out)


AUTHORS_END = re.compile(r'["\u201c\u201d]')


def shorten_authors(entry, keep=3):
    """`A, B, ..., and T, "Title," ...` -> `A et al., "Title," ...`

    The selected block sits above the list and some of these papers carry
    twenty authors; spelling them all out costs more space than the block is
    worth. Shortening happens here rather than in content/highlights.md so that
    file stays a verbatim copy of the list and can still be diffed against it.
    """
    m = AUTHORS_END.search(entry)
    if not m:
        return entry
    head, rest = entry[:m.start()], entry[m.start():]
    people = [p for p in re.split(r",|\band\b", head) if p.strip(" *")]
    if len(people) <= keep:
        return entry
    first = people[0].strip().rstrip(",")
    return f"{first} et al., {rest}"


def read_highlights():
    """(entries, caption) for the selected-publications block.

    The file is hand-maintained; a leading `caption:` line, if present, becomes
    the line under the heading. Everything else is one entry per paragraph.
    """
    f = CONTENT / "highlights.md"
    if not f.is_file():
        return [], ""
    out, buf, in_comment = [], [], False
    for line in f.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if in_comment:
            in_comment = not s.endswith("-->")
            continue
        if s.startswith("<!--"):
            in_comment = not s.endswith("-->")
            continue
        if not s:
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        buf.append(s)
    if buf:
        out.append(" ".join(buf))

    caption = ""
    if out and out[0].startswith("caption:"):
        caption = md_inline(out.pop(0)[len("caption:"):].strip())
    return [md_inline(shorten_authors(o)) for o in out], caption


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


def md_blocks(text):
    """Block-level Markdown for notes: headings, paragraphs, quotes and lists.

    Deliberately small. Notes are prose, so this is all they need, and it keeps
    the build free of dependencies. Inline markup goes through md_inline().
    """
    html, para = [], []

    def flush():
        if para:
            html.append(f"<p>{md_inline(' '.join(para))}</p>")
            para.clear()

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith("<!--"):
            flush()
            i += 1
            continue
        m = MD_HEADING.match(s)
        if m:
            flush()
            level = len(m.group(1))
            html.append(f"<h{level}>{md_inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            html.append(f"<blockquote><p>{md_inline(' '.join(quote))}</p></blockquote>")
            continue
        if MD_ITEM.match(s):
            flush()
            tag = "ol" if s[0].isdigit() else "ul"
            items = []
            while i < len(lines) and lines[i].strip():
                m = MD_ITEM.match(lines[i].strip())
                if m:
                    items.append(m.group(2))
                else:
                    items[-1] += " " + lines[i].strip()   # wrapped continuation
                i += 1
            lis = "".join(f"<li>{md_inline(x)}</li>" for x in items)
            html.append(f"<{tag}>{lis}</{tag}>")
            continue
        para.append(s)
        i += 1
    flush()
    return html


def read_notes():
    """Parse content/notes/YYYY-MM-DD-slug.md into [{date, slug, title, lede, body}].

    The file name carries the date and the URL; the first "# " heading is the
    title; the first paragraph doubles as the summary on the index page.
    """
    notes = []
    if not NOTES.is_dir():
        return notes
    for path in sorted(NOTES.glob("*.md"), reverse=True):
        m = NOTE_FILE.match(path.name)
        if not m:
            raise SystemExit(f"{path}: notes are named YYYY-MM-DD-slug.md")
        when = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        blocks = md_blocks(path.read_text(encoding="utf-8"))
        if not blocks or not blocks[0].startswith("<h1>"):
            raise SystemExit(f"{path}: a note starts with a '# Title' line")
        title = TAG.sub("", blocks[0])
        first = next((b for b in blocks[1:] if b.startswith("<p>")), "")
        # the index shows the first two sentences of the opening paragraph
        sentences = re.split(r"(?<=[.!?])\s+", TAG.sub("", first))
        notes.append({
            "date": when, "slug": m.group(4), "title": title,
            "lede": " ".join(sentences[:2]), "body": blocks[1:],
        })
    return notes


def find(sections, title):
    for s in sections:
        if s["title"] == title:
            return s
    raise KeyError(f"section not found: {title!r}")


def check_cv_layout(sources):
    """Fail early, and usefully, when CV_LAYOUT and the content disagree.

    Renaming a heading in content/*.md is an ordinary edit, but CV_LAYOUT refers
    to headings by name -- so without this the build dies on a bare KeyError
    several hundred lines later, saying nothing about what to do next.
    """
    problems = []
    for heading, refs in CV_LAYOUT:
        for source, title in refs:
            have = [s["title"] for s in sources[source]]
            if title in have:
                continue
            near = get_close_matches(title, have, n=1, cutoff=0.6)
            hint = f" Did you mean {near[0]!r}?" if near else ""
            problems.append(
                f"CV_LAYOUT ({heading}) wants {title!r} from {source}, "
                f"which is not a heading there.{hint}"
            )
    if problems:
        raise SystemExit(
            "\n".join(["build.py and content/ disagree:", *("  - " + p for p in problems),
                        "", "Fix the heading in content/, or CV_LAYOUT in build.py."])
        )

    used = {(src, t) for _, refs in CV_LAYOUT for src, t in refs}
    for source, sections in sources.items():
        for s in sections:
            if s["items"] and (source, s["title"]) not in used:
                print(f"  note: {source}/{s['title']!r} is not in the CV")


# ---------------------------------------------------------------- helpers
def year_of(entry_html):
    hits = YEAR.findall(TAG.sub("", entry_html))
    return hits[-1][0] + hits[-1][1] if hits else ""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def shell(active, title, body, extra_js="", prefix=""):
    """Wrap a page body in the site chrome. `prefix` is the relative path back
    to the site root ("../" for a page in a sub-directory)."""
    nav = "\n".join(
        f'      <a href="{prefix}{href}"{" class=\"on\"" if label == active else ""}>{label}</a>'
        for href, label in PAGES
    )
    js = f'\n  <script src="{prefix}{extra_js}"></script>' if extra_js else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="{prefix}style.css">
</head>
<body>
<header class="topbar">
  <a class="brand" href="{prefix}index.html">{NAME}</a>
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
<script src="{prefix}app.js"></script>{js}
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


def publications_page(sections, highlights=(), caption=""):
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
        # starts collapsed: 698 entries open at once is a wall of text, and
        # the search in filter.js opens whichever sections match
        blocks.append(f"""  <details class="sec" id="{slug(s['title'])}">
    <summary><span class="t">{escape(s['title'])}</span>
      <span class="count"><span class="shown">{len(s['items'])}</span> / {len(s['items'])}</span>
    </summary>
    <ol class="entries">
{items}
    </ol>
  </details>""")

    selected = ""
    if highlights:
        rows = "\n".join(f"      <li>{h}</li>" for h in highlights)
        selected = f"""
  <section class="selected-block">
    <h2>Selected publications</h2>
    <p class="caption">{caption}</p>
    <ol class="entries selected">
{rows}
    </ol>
  </section>
"""

    body = f"""  <h1>Publications</h1>
  <p class="lede">{total} entries across {len(sections)} categories.</p>
{selected}
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
        cls = "sec sub" if s["level"] == "h3" else "sec"
        blocks.append(f"""  <details class="{cls}" id="{slug(s['title'])}">
    <summary><span class="t">{escape(s['title'])}</span>
      <span class="count">{len(s['items'])}</span>
    </summary>
{grouped_list(s)}
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


def long_date(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def notes_page(notes):
    items = "\n".join(f"""    <li>
      <time datetime="{n['date'].isoformat()}">{long_date(n['date'])}</time>
      <a href="notes/{n['slug']}.html">{escape(n['title'])}</a>
      <p>{escape(n['lede'])}</p>
    </li>""" for n in notes)
    body = f"""  <h1>Notes</h1>
  <p class="lede">Occasional longer pieces: where things came from, and what was
  learned along the way.</p>
  <ul class="notes">
{items}
  </ul>
"""
    return shell("Notes", f"Notes — {NAME}", body)


def note_page(note):
    body = "\n".join(f"    {b}" for b in note["body"])
    article = f"""  <article class="note">
    <p class="note-meta"><a href="../notes.html">Notes</a> &middot;
      <time datetime="{note['date'].isoformat()}">{long_date(note['date'])}</time></p>
    <h1>{escape(note['title'])}</h1>
{body}
  </article>
"""
    return shell("Notes", f"{note['title']} — {NAME}", article, prefix="../")


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
            parts.append(label + grouped_list(sec, tag="ol", cls="cv-list"))
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


def copy_static():
    """Mirror static/ into the build. These are sources, not build output --
    docs/ is regenerated from scratch by CI, so anything only kept there would
    simply vanish from the published site."""
    shutil.copytree(STATIC, SITE, dirs_exist_ok=True)
    return sorted(p.relative_to(STATIC).as_posix() for p in STATIC.rglob("*") if p.is_file())


def main():
    SITE.mkdir(exist_ok=True)
    copied = copy_static()

    pubs = read_sections("publications")
    acts = read_sections("activities")
    bio = read_bio()
    sources = {"publications": pubs, "activities": acts,
               "cv": read_sections("cv-extra")}
    check_cv_layout(sources)

    (SITE / "index.html").write_text(home_page(bio), encoding="utf-8")
    highlights, caption = read_highlights()
    (SITE / "publications.html").write_text(
        publications_page(pubs, highlights, caption), encoding="utf-8")
    (SITE / "activities.html").write_text(activities_page(acts), encoding="utf-8")
    (SITE / "software.html").write_text(software_page(), encoding="utf-8")
    (SITE / "cv.html").write_text(cv_page(sources), encoding="utf-8")

    notes = read_notes()
    (SITE / "notes").mkdir(exist_ok=True)
    (SITE / "notes.html").write_text(notes_page(notes), encoding="utf-8")
    for n in notes:
        (SITE / "notes" / f"{n['slug']}.html").write_text(note_page(n), encoding="utf-8")

    n_pub = sum(len(s["items"]) for s in pubs)
    n_act = sum(len(s["items"]) for s in acts)
    print(f"index.html          {len(bio)} bio paragraph(s)")
    print(f"publications.html   {n_pub} entries, {len(highlights)} highlight(s)")
    print(f"activities.html     {n_act} entries")
    print(f"software.html       {len(SOFTWARE)} projects")
    print(f"notes.html          {len(notes)} note(s)")
    print(f"static              {len(copied)} files: {', '.join(copied)}")

    print(f"cv.html             {len(CV_LAYOUT)} headings")


if __name__ == "__main__":
    main()
