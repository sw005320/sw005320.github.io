#!/usr/bin/env python3
"""Find publications that OpenAlex knows about and content/publications.md does not.

Writes a Markdown report and, with --emit, the entries themselves in house style
so they can be pasted (or committed by CI) into content/publications.md.

Nothing here decides anything: the output is a draft for a person to check. Venue
abbreviations, section choice and author order all need a human eye, and OpenAlex
occasionally carries truncated author lists or a preprint in place of the paper.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify  # noqa: E402  (same directory, shares the matching logic)

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "publications.md"

# How Shinji writes the venues he publishes in most. Anything not here falls back
# to the name OpenAlex gives, which is usually right but rarely in his style.
VENUES = {
    "interspeech": "Interspeech",
    "icassp": "ICASSP",
    "ieee international conference on acoustics speech and signal processing": "ICASSP",
    "automatic speech recognition and understanding": "ASRU",
    "spoken language technology": "SLT",
    "annual meeting of the association for computational linguistics": "ACL",
    "empirical methods in natural language processing": "EMNLP",
    "north american chapter of the association for computational linguistics": "NAACL",
    "neural information processing systems": "NeurIPS",
    "international conference on machine learning": "ICML",
    "international conference on learning representations": "ICLR",
    "workshop on applications of signal processing to audio and acoustics": "WASPAA",
    "asia-pacific signal and information processing association": "APSIPA ASC",
}

JOURNAL_TYPES = {"article", "review"}

# Four other researchers share the name, and OpenAlex occasionally files one of
# their papers under this author id -- a 2025 depth-camera paper on elderly
# action recognition turned up this way. Pinning the id is not enough, so flag
# anything with no vocabulary from this field in its title.
FIELD_WORDS = (
    "speech", "audio", "asr", "spoken", "voice", "acoustic", "language model",
    "tts", "text-to-speech", "music", "diariz", "codec", "espnet", "whisper",
    "multimodal", "translation", "phonem", "speaker", "sound",
)


def looks_like_this_field(work):
    title = (work.get("display_name") or "").lower()
    return any(w in title for w in FIELD_WORDS)


def house_venue(name, year):
    """'Interspeech 2025' -> "Proc. Interspeech'25", when we recognise it."""
    if not name:
        return None
    low = re.sub(r"[^a-z ]+", " ", name.lower())
    low = " ".join(low.split())
    for needle, short in VENUES.items():
        if needle in low:
            yy = f"'{str(year)[-2:]}" if year else ""
            return f"Proc. {short}{yy}"
    return name


def authors_line(work):
    names = [a["author"]["display_name"] for a in work.get("authorships", [])]
    out = []
    for n in names:
        out.append(f"**{n}**" if n.strip().lower() == "shinji watanabe" else n)
    if len(out) > 1:
        return ", ".join(out[:-1]) + ", and " + out[-1]
    return out[0] if out else ""


def crossref_venue(doi):
    """OpenAlex leaves the venue empty for most conference papers; Crossref,
    where the publisher registered the DOI, almost always has it."""
    if not doi:
        return None
    doi = doi.replace("https://doi.org/", "")
    try:
        url = f"https://api.crossref.org/works/{doi}?mailto={verify.MAIL}"
        with urllib.request.urlopen(url, timeout=25) as r:
            m = json.loads(r.read())["message"]
    except Exception:
        return None
    finally:
        time.sleep(0.15)
    titles = m.get("container-title") or m.get("event", {}).get("name")
    if isinstance(titles, list):
        titles = titles[0] if titles else None
    return titles


def work_authors(work):
    return [a["author"]["display_name"] for a in work.get("authorships", [])]


def is_accepted(entry):
    """An entry still waiting for its published details."""
    return "(accepted)" in (entry.get("tail") or "").lower()


def title_overlap(work, entry):
    """How much of the two titles is the same, 0..1."""
    return SequenceMatcher(
        None,
        verify.norm_title(work.get("display_name") or ""),
        verify.norm_title(entry.get("title") or ""),
    ).ratio()


def same_paper(work, entry, venue):
    """Is this record the published version of an entry still "(accepted)"?

    Titles are not stable across acceptance: five 2025 papers were renamed
    between the two, and every one of them came back here as a brand new
    publication. At acceptance there is no DOI to compare either, so match on
    the two things that do not move -- who wrote it and where it appeared.
    """
    tail = (entry.get("tail") or "").lower()
    if not venue or venue.lower() not in tail:
        return False
    a = [n for n in (verify.norm_name(x) for x in work_authors(work)) if n]
    b = [n for n in (entry.get("authors") or []) if n]   # already parsed names
    if not a or not b:
        return False
    if not verify.same_person(a[0], b[0]):      # a renamed paper keeps its lead
        return False
    hits = sum(any(verify.same_person(x, y) for y in b) for x in a)
    return hits >= max(2, (min(len(a), len(b)) + 1) // 2)


def entry_for(work):
    """One publication in the list's house style."""
    title = (work.get("display_name") or "").strip().rstrip(".")
    year = work.get("publication_year")
    venue = verify.venue_of(work) or crossref_venue(work.get("doi"))
    venue = house_venue(venue, year)
    pages = verify.pages_of(work)
    tail = ", ".join(x for x in (f"*{venue}*" if venue else None, pages) if x)
    return f'{authors_line(work)}, "{title}," {tail} ({year})'.replace(" ,", ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="refresh the OpenAlex cache")
    ap.add_argument("--emit", action="store_true", help="print the entries themselves")
    ap.add_argument("--out", default="new-publications.md")
    args = ap.parse_args()

    works = (
        verify.fetch_works()
        if args.fetch
        else json.loads(verify.CACHE.read_text(encoding="utf-8"))
    )
    entries = verify.parse_entries(CONTENT)
    known = {verify.norm_title(e["title"]) for e in entries if e["title"]}

    pending = [e for e in entries if is_accepted(e)]

    fresh, updates = [], []
    for w in works:
        key = verify.work_key(w)
        if not key or key in known:
            continue
        if w.get("type") == "preprint":
            continue  # wait for the published version
        if not w.get("publication_year"):
            continue
        venue = house_venue(verify.venue_of(w) or crossref_venue(w.get("doi")),
                            w.get("publication_year"))
        # several accepted papers can share a first author and a venue -- Jiatong
        # Shi had two at ASRU'25 -- so take the closest title among the matches
        # rather than the first, or the report names the wrong entry to edit.
        cands = [e for e in pending if same_paper(w, e, venue)]
        hit = max(cands, key=lambda e: title_overlap(w, e), default=None)
        if hit:
            updates.append((w, hit))      # a listed paper, now published
        else:
            fresh.append(w)

    # newest first, and only ever a handful: anything older is already a decision
    # someone made not to list it.
    fresh.sort(key=lambda w: -(w.get("publication_year") or 0))
    fresh = [
        w for w in fresh if (w.get("publication_year") or 0) >= date.today().year - 1
    ]

    lines = [f"# Candidate publications ({date.today():%Y-%m-%d})", ""]

    if updates:
        lines += [
            f"## {len(updates)} listed paper(s) now published",
            "",
            "These are already in `content/publications.md` under the title they",
            "were accepted under, and are still marked `(accepted)`. OpenAlex now",
            "has the published version. Replace the title and add the pages --",
            "do not add a second entry.",
            "",
        ]
        for w, e in updates:
            lines += [
                "**listed:**", "", "```", e["raw"], "```", "",
                "**published:**", "", "```", entry_for(w), "```", "",
            ]
            if w.get("doi"):
                lines += [f"{w['doi']}", ""]

    if not fresh and not updates:
        lines += [
            "Nothing new. Every OpenAlex record from this year and last is "
            "already in `content/publications.md`.",
            "",
        ]
    elif fresh:
        lines += [
            f"## {len(fresh)} record(s) not in `content/publications.md`",
            "",
            "",
            "These are **drafts**. Check the author order, the venue abbreviation and",
            "the section before committing -- OpenAlex sometimes truncates author lists,",
            "and the venue name is only rewritten into house style for venues it knows.",
            "",
        ]
        suspect = [w for w in fresh if not looks_like_this_field(w)]
        if suspect:
            lines += [
                f"**{len(suspect)} of these may belong to a different Shinji Watanabe.**",
                "Four other researchers share the name and OpenAlex sometimes files",
                "their work under this author id. Each is marked below.",
                "",
            ]
        for w in fresh:
            section = (
                "Journal (refereed)"
                if w.get("type") in JOURNAL_TYPES
                else "International Conference and Workshop (refereed)"
            )
            warn = "" if looks_like_this_field(w) else "  :warning: **probably not yours**"
            lines += [
                f"## {w.get('publication_year')} &mdash; {section}{warn}",
                "",
                "```",
                entry_for(w),
                "```",
                "",
            ]
            if not looks_like_this_field(w):
                names = ", ".join(a["author"]["display_name"]
                                  for a in w.get("authorships", []))
                lines += [f"Co-authors: {names}", ""]
            if w.get("doi"):
                lines += [f"{w['doi']}", ""]

    (ROOT / args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(fresh)} candidate(s), {len(updates)} update(s) -> {args.out}")
    if args.emit:
        for w in fresh:
            print(entry_for(w))
    return 0


if __name__ == "__main__":
    sys.exit(main())
