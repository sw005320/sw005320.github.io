#!/usr/bin/env python3
"""Cross-check content/publications.md against OpenAlex.

Reports author-list and title differences, and proposes venue/year/page details
for entries that still say "(accepted)". Writes a report; never edits content.

    python3 verify.py --fetch     # refresh .cache/openalex_works.json
    python3 verify.py             # report only
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache" / "openalex_works.json"
AUTHOR_ID = "A5001291873"          # Shinji Watanabe, Carnegie Mellon University
MAIL = "swatanab@andrew.cmu.edu"

QUOTES = '"“”‘’„‟〝〞'
TAGS = re.compile(r"\*{1,3}|\[|\]\([^)]*\)")


# ---------------------------------------------------------------- fetch
def fetch_works():
    fields = ("id,doi,title,display_name,publication_year,authorships,"
              "primary_location,biblio,type,ids")
    cursor, works = "*", []
    while cursor:
        q = urllib.parse.urlencode({
            "filter": f"author.id:{AUTHOR_ID}", "per-page": 200,
            "cursor": cursor, "select": fields, "mailto": MAIL,
        })
        with urllib.request.urlopen(f"https://api.openalex.org/works?{q}", timeout=60) as r:
            d = json.loads(r.read())
        works.extend(d["results"])
        cursor = d["meta"].get("next_cursor")
        if not d["results"]:
            break
        time.sleep(0.3)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(works), encoding="utf-8")
    return works


# ---------------------------------------------------------------- parsing
def strip_markup(s):
    return TAGS.sub("", s)


def norm_title(s):
    """Aggressive normalisation: case, accents, punctuation and spacing."""
    s = unicodedata.normalize("NFKD", strip_markup(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


# Words that turn up inside author lists but are not people.
NOT_A_NAME = {"member", "fellow", "senior", "student", "life", "ieee", "et", "al",
              "and", "the", "jr", "ii", "iii"}


def norm_name(s):
    """A person as (surname tokens, given initials).

    Surnames here are messy -- Garcia-Perera, Haeb-Umbach, Le Roux, Fosler-Lussier
    -- and each source splits them differently, so keep every surname token and
    compare loosely in `same_person`.
    """
    s = unicodedata.normalize("NFKD", strip_markup(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z\s.'-]", " ", s)
    parts = [p.strip(".'-").lower() for p in re.split(r"[\s]+", s)]
    parts = [p for p in parts if p and p not in NOT_A_NAME]
    if not parts:
        return None
    surname = set(re.split(r"-", parts[-1])) | {parts[-1]}
    initials = {p[0] for p in parts[:-1] if p}
    allwords = set()
    for p in parts:
        allwords |= set(re.split(r"-", p)) | {p}
    return (frozenset(x for x in surname if x), frozenset(initials),
            frozenset(x for x in allwords if x))


def same_person(a, b):
    """True if two parsed names could be the same person.

    Sources disagree constantly about which token is the surname -- "Muhammad
    Shakeel", "Wei Ping", "Takashi Maekaku" all come back from OpenAlex with the
    parts swapped. So accept a match when the full token sets share a real word,
    and fall back to surname-overlap plus compatible initials.
    """
    if not a or not b:
        return False
    shared = {t for t in (a[2] & b[2]) if len(t) >= 3}
    if shared:
        return True
    if not (a[0] & b[0]):
        return False
    return not a[1] or not b[1] or bool(a[1] & b[1])


def split_authors(chunk):
    """Parsed names, plus any comma-separated word that is not a name at all."""
    chunk = strip_markup(chunk)
    chunk = re.sub(r"\band\b", ",", chunk, flags=re.I)
    out, junk = [], []
    for p in chunk.split(","):
        raw = p.strip()
        if not raw:
            continue
        n = norm_name(p)
        if n:
            out.append(n)
        elif re.search(r"[A-Za-z]", raw):
            junk.append(raw)
    return out, junk


def parse_entries(md_path):
    """Yield {section, raw, authors, title, tail} for each entry."""
    text = md_path.read_text(encoding="utf-8")
    entries, section, buf = [], None, []

    def flush():
        if section and buf:
            entries.append((section, " ".join(buf).strip()))
        buf.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("<!--"):
            continue
        if s.startswith("## ") or s.startswith("### "):
            flush()
            section = s.lstrip("#").strip()
            continue
        if not s:
            flush()
            continue
        buf.append(s)
    flush()

    # A closing quote is any of the quote characters, or two apostrophes -- the
    # list inherits several styles from years of hand editing.
    qpat = re.compile(f"''|[{QUOTES}]")
    out = []
    for section, raw in entries:
        marks = [(m.start(), m.end()) for m in qpat.finditer(raw)]
        title = authors = tail = None
        if len(marks) >= 2:
            # first quoted span only: a book chapter quotes the chapter *and*
            # the book, and taking first-to-last would swallow both.
            (o_s, o_e), (c_s, c_e) = marks[0], marks[1]
            title = raw[o_e:c_s].strip().rstrip(",").strip()
            authors, junk = split_authors(raw[:o_s])
            tail = raw[c_e:].strip(" ,")
        out.append({"section": section, "raw": raw, "authors": authors,
                    "title": title, "tail": tail, "junk": junk if title else []})
    return out


# ---------------------------------------------------------------- matching
def work_key(w):
    return norm_title(w.get("display_name") or w.get("title") or "")


def build_index(works):
    idx = {}
    for w in works:
        k = work_key(w)
        if not k:
            continue
        idx.setdefault(k, []).append(w)
    return idx


def pick(cands):
    """Prefer a published record over a preprint."""
    if not cands:
        return None
    ranked = sorted(cands, key=lambda w: (w.get("type") == "preprint",
                                          -(w.get("publication_year") or 0)))
    return ranked[0]


def venue_of(w):
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    return src.get("display_name")


def pages_of(w):
    b = w.get("biblio") or {}
    first, last = b.get("first_page"), b.get("last_page")
    if first and last and first != last:
        return f"pp. {first}--{last}"
    if first:
        return f"p. {first}"
    return None


def authors_of(w):
    got = (norm_name(a["author"]["display_name"]) for a in w.get("authorships", []))
    return [g for g in got if g]


def show(n):
    """Render a parsed name back to something readable."""
    if not n:
        return "?"
    sur = "-".join(sorted(n[0], key=len, reverse=True)[:1])
    ini = "".join(sorted(n[1]))
    return f"{sur} {ini}".strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="refresh the OpenAlex cache")
    ap.add_argument("--out", default="verify-report.md")
    args = ap.parse_args()

    works = fetch_works() if args.fetch else json.loads(CACHE.read_text(encoding="utf-8"))
    idx = build_index(works)
    keys = list(idx)

    entries = parse_entries(ROOT / "content" / "publications.md")
    print(f"entries parsed : {len(entries)}")
    print(f"  with a title : {sum(1 for e in entries if e['title'])}")
    print(f"openalex works : {len(works)}  ({len(idx)} distinct titles)")

    exact = fuzzy = unmatched = 0
    for e in entries:
        e["match"] = e["score"] = None
        if not e["title"]:
            continue
        k = norm_title(e["title"])
        if k in idx:
            e["match"], e["score"] = pick(idx[k]), 1.0
            exact += 1
            continue
        best, bs = None, 0.0
        for ck in keys:
            if abs(len(ck) - len(k)) > 25:
                continue
            r = SequenceMatcher(None, k, ck).ratio()
            if r > bs:
                best, bs = ck, r
        if bs >= 0.90:
            e["match"], e["score"] = pick(idx[best]), bs
            fuzzy += 1
        else:
            unmatched += 1
    print(f"\nmatched exact  : {exact}")
    print(f"matched fuzzy  : {fuzzy}   (>=0.90 title similarity)")
    print(f"unmatched      : {unmatched}")
    json.dump(
        [{k: v for k, v in e.items() if k != "match"} | {"oa": e["match"]} for e in entries],
        open(ROOT / ".cache" / "matched.json", "w"), default=str)


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------- report
def venue_year_pages(w):
    """The bits needed to finish an entry that still says (accepted)."""
    return {"venue": venue_of(w), "year": w.get("publication_year"),
            "pages": pages_of(w), "doi": w.get("doi"),
            "volume": (w.get("biblio") or {}).get("volume"),
            "issue": (w.get("biblio") or {}).get("issue")}


def report(entries, path):
    TALKS = {"Keynote talk", "Tutorial/Overview/Invited talk"}
    accepted = re.compile(r"\(accepted\)", re.I)

    author_diffs, title_diffs, fills, unmatched = [], [], [], []
    junk_authors = [e for e in entries if e.get("junk")]
    for e in entries:
        w = e.get("oa") if isinstance(e.get("oa"), dict) else e.get("match")
        if not e["title"]:
            continue
        if not w:
            if e["section"] not in TALKS:
                unmatched.append(e)
            continue

        ours, theirs = e["authors"] or [], authors_of(w)
        if ours and theirs:
            missing = [a for a in theirs if not any(same_person(a, o) for o in ours)]
            extra = [a for a in ours if not any(same_person(a, t) for t in theirs)]
            if missing or extra:
                author_diffs.append((e, w, missing, extra))

        if e["score"] and e["score"] < 1.0:
            title_diffs.append((e, w))

        if accepted.search(e["raw"]):
            fills.append((e, w, venue_year_pages(w)))

    with open(path, "w", encoding="utf-8") as f:
        w_ = f.write
        w_("# Publication cross-check against OpenAlex\n\n")
        w_(f"- entries: {len(entries)}\n")
        w_(f"- author-list differences: {len(author_diffs)}\n")
        w_(f"- title differences: {len(title_diffs)}\n")
        w_(f"- `(accepted)` entries with details available: {len(fills)}\n")
        w_(f"- unmatched (excluding talks): {len(unmatched)}\n")
        w_(f"- author lists containing a non-name word: {len(junk_authors)}\n\n")

        w_("## Non-name words inside author lists\n\n")
        for e in junk_authors:
            w_(f"- `{', '.join(e['junk'])}` in: {e['raw'][:120]}\n")
        w_("\n")

        w_("## Author-list differences\n\n")
        for e, wk, missing, extra in author_diffs:
            w_(f"### {e['title'][:95]}\n\n")
            if missing:
                w_(f"- only in OpenAlex: {', '.join(show(x) for x in missing)}\n")
            if extra:
                w_(f"- only on the site: {', '.join(show(x) for x in extra)}\n")
            w_(f"- site: `{e['raw'][:180]}`\n\n")

        w_("## Title differences\n\n")
        for e, wk in title_diffs:
            w_(f"- site: {e['title'][:95]}\n")
            w_(f"  OpenAlex: {(wk.get('display_name') or '')[:95]}\n\n")

        w_("## `(accepted)` entries that can be completed\n\n")
        for e, wk, d in fills:
            bits = [b for b in (d["venue"], str(d["year"]) if d["year"] else None,
                                d["pages"]) if b]
            w_(f"- {e['title'][:85]}\n  -> {' | '.join(bits)}\n")

        w_("\n## Unmatched (need a look by hand)\n\n")
        for e in unmatched:
            w_(f"- [{e['section'][:24]}] {e['title'][:95]}\n")

    return dict(author_diffs=len(author_diffs), title_diffs=len(title_diffs),
                fills=len(fills), unmatched=len(unmatched),
                junk_authors=len(junk_authors))
