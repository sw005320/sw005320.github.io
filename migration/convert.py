#!/usr/bin/env python3
"""One-off: turn data/*.json into hand-editable content/*.md.

The inline subset is deliberately tiny -- **bold**, *italic*, [text](url) --
so that entries stay readable and a typo can only break one line.

Every entry is converted back to HTML and compared against the original; the
script refuses to write anything if a single entry fails to round-trip.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONTENT = ROOT / "content"

A = re.compile(r'<a href="([^"]+)">(.*?)</a>', re.S)
STRONG = re.compile(r"<strong>(.*?)</strong>", re.S)
EM = re.compile(r"<em>(.*?)</em>", re.S)

BOTH = re.compile(r"<strong><em>(.*?)</em></strong>", re.S)

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
MD_BOTH = re.compile(r"\*\*\*(.+?)\*\*\*", re.S)
MD_STRONG = re.compile(r"\*\*(.+?)\*\*", re.S)
MD_EM = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)


ADJACENT = re.compile(r"</(strong|em)><\1>")
EM_OUTER = re.compile(r"<em><strong>(.*?)</strong></em>", re.S)


def normalise(s):
    """Tidy two harmless quirks of the Google Sites markup.

    1. Merge runs split across spans: `<em>Interspeech'2</em><em>5</em>` renders
       the same as `<em>Interspeech'25</em>` but would become the ambiguous
       `*Interspeech'2**5*`. Only directly adjacent tags merge, so a space
       between them survives.
    2. Settle bold+italic nesting on <strong><em>, which is what `***x***`
       round-trips to. Both orders render identically.
    """
    prev = None
    while prev != s:
        prev = s
        s = ADJACENT.sub("", s)
        s = EM_OUTER.sub(lambda m: f"<strong><em>{m.group(1)}</em></strong>", s)
    return s


def html_to_md(s):
    s = normalise(s)
    s = A.sub(lambda m: f"[{m.group(2)}]({m.group(1)})", s)
    s = BOTH.sub(lambda m: f"***{m.group(1)}***", s)
    s = STRONG.sub(lambda m: f"**{m.group(1)}**", s)
    s = EM.sub(lambda m: f"*{m.group(1)}*", s)
    return s


def md_to_html(s):
    s = MD_LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = MD_BOTH.sub(lambda m: f"<strong><em>{m.group(1)}</em></strong>", s)
    s = MD_STRONG.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = MD_EM.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    return s


def render(sections, title):
    out = [f"<!-- {title} -->", ""]
    for sec in sections:
        marker = "##" if sec["level"] == "h2" else "###"
        out.append(f"{marker} {sec['title']}")
        out.append("")
        for item in sec["items"]:
            out.append(html_to_md(item))
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def check(sections, label, problems):
    """Round-trip every entry: md_to_html(html_to_md(x)) must equal normalise(x)."""
    for sec in sections:
        for item in sec["items"]:
            if md_to_html(html_to_md(item)) != normalise(item):
                problems.append((label, sec["title"], item))


def main():
    problems = []
    loaded = {}
    for name in ("publications", "activities"):
        sections = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
        loaded[name] = sections
        check(sections, name, problems)

    home = json.loads((DATA / "home.json").read_text(encoding="utf-8"))
    for para in home["bio"]:
        if md_to_html(html_to_md(para)) != normalise(para):
            problems.append(("home", "bio", para))

    total = sum(len(s["items"]) for v in loaded.values() for s in v) + len(home["bio"])
    if problems:
        print(f"{len(problems)} of {total} entries do not round-trip; nothing written.\n")
        for label, sec, item in problems[:10]:
            print(f"  [{label} / {sec}] {item[:160]}")
        return 1

    CONTENT.mkdir(exist_ok=True)
    (CONTENT / "publications.md").write_text(
        render(loaded["publications"], "Publications"), encoding="utf-8")
    (CONTENT / "activities.md").write_text(
        render(loaded["activities"], "Activities"), encoding="utf-8")
    (CONTENT / "home.md").write_text(
        "<!-- Short bio -->\n\n" + "\n\n".join(html_to_md(p) for p in home["bio"]) + "\n",
        encoding="utf-8")

    print(f"all {total} entries round-trip cleanly")
    for f in sorted(CONTENT.iterdir()):
        print(f"  content/{f.name}  {f.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
