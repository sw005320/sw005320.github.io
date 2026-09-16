#!/usr/bin/env python3
"""Extract content from the published Google Sites pages into structured JSON.

Reads raw/*.html (fetched with curl) and writes data/*.json.
Inline formatting (bold / italic / links) is preserved as a small, clean
subset of HTML: <strong>, <em>, <a href>.
"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT = ROOT / "data"

BOLD = re.compile(r"font-weight:\s*(bold|[6-9]00)")
ITALIC = re.compile(r"font-style:\s*italic")


def soup_for(name):
    return BeautifulSoup((RAW / f"{name}.html").read_text(encoding="utf-8"), "lxml")


def _render(node):
    """Render a node's children as a minimal HTML subset.

    Whitespace is preserved here on purpose: stripping each nested fragment
    would swallow the single spaces that separate adjacent styled runs
    (e.g. "<strong>Shinji Watanabe</strong> and Jen-Tzung Chien").
    """
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child).replace("\xa0", " "))
            continue
        if not isinstance(child, Tag):
            continue
        if child.name == "br":
            out.append(" ")
            continue
        inner = _render(child)
        if not inner.strip():
            continue
        if child.name == "a" and child.get("href"):
            out.append(f'<a href="{child["href"]}">{inner.strip()}</a>')
            continue
        style = child.get("style", "") or ""
        lead = " " if inner[:1].isspace() else ""
        trail = " " if inner[-1:].isspace() else ""
        core = inner.strip()
        if child.name in ("b", "strong") or BOLD.search(style):
            core = f"<strong>{core}</strong>"
        if child.name in ("i", "em") or ITALIC.search(style):
            core = f"<em>{core}</em>"
        out.append(lead + core + trail)
    return "".join(out)


def inline_html(node):
    """Rendered inline HTML with runs of whitespace collapsed."""
    return re.sub(r"\s{2,}", " ", _render(node)).strip()


def leaf_items(container, stop_at):
    """Collect leaf <li> entries that appear after `container` and before `stop_at`."""
    items = []
    for el in container.find_all_next():
        if el is stop_at:
            break
        if el.name == "li" and not el.find("li"):
            html = inline_html(el)
            if html:
                items.append(html)
    return items


def content_root(soup, first_heading):
    """Smallest ancestor of the first section heading that holds the whole body."""
    head = next(
        h for h in soup.find_all(["h2", "h3"]) if h.get_text(strip=True) == first_heading
    )
    node = head.parent
    while node is not None and node.name != "body":
        if len(node.get_text(strip=True)) > 5000:
            return node, head
        node = node.parent
    return head.parent, head


def sectioned(name, first_heading, level="h2"):
    """Split a page into sections keyed by its headings."""
    soup = soup_for(name)
    root, _ = content_root(soup, first_heading)
    heads = [h for h in root.find_all(["h2", "h3"]) if h.get_text(strip=True)]
    sections = []
    for idx, h in enumerate(heads):
        nxt = heads[idx + 1] if idx + 1 < len(heads) else None
        sections.append(
            {
                "level": h.name,
                "title": h.get_text(strip=True).rstrip(":"),
                "items": leaf_items(h, nxt),
            }
        )
    return sections


def main():
    OUT.mkdir(exist_ok=True)

    pubs = sectioned("publications", "Book")
    (OUT / "publications.json").write_text(
        json.dumps(pubs, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    acts = sectioned("activities", "Education:")
    (OUT / "activities.json").write_text(
        json.dumps(acts, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    # Home: bio paragraphs.
    soup = soup_for("home")
    bio_head = next(
        h for h in soup.find_all(["h2", "h3"]) if h.get_text(strip=True) == "Short bio"
    )
    paras = []
    for el in bio_head.find_all_next():
        if el.name in ("h2", "h3") and el is not bio_head:
            break
        if el.name == "p":
            t = inline_html(el)
            if t:
                paras.append(t)
    (OUT / "home.json").write_text(
        json.dumps({"bio": paras}, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    for label, data in (("publications", pubs), ("activities", acts)):
        total = sum(len(s["items"]) for s in data)
        print(f"{label}: {len(data)} sections, {total} items")
        for s in data:
            print(f"  {s['level']} {s['title']}: {len(s['items'])}")
    print(f"home: {len(paras)} bio paragraph(s)")


if __name__ == "__main__":
    main()
