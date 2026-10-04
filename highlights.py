#!/usr/bin/env python3
"""Suggest publications for the selected-publications block.

content/highlights.md is hand-maintained -- citation counts favour surveys and
benchmarks, and the block should also carry the method papers a person would
pick. So this only ranks candidates and prints them; it writes that file only
when asked.

    python3 highlights.py --fetch              # refresh counts, then suggest
    python3 highlights.py -n 20                # a longer list to choose from
    python3 highlights.py --write              # overwrite highlights.md (asks
                                               # first if it was hand-edited)
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import re  # noqa: E402
import verify  # noqa: E402

# only to label the suggestions, never to filter them
SURVEYISH = re.compile(r"\b(survey|review|benchmark|corpus|dataset|challenge)\b", re.I)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "content" / "highlights.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("-n", type=int, default=15)
    ap.add_argument("--write", action="store_true",
                    help="replace content/highlights.md with the top --n")
    args = ap.parse_args()

    works = (
        verify.fetch_works()
        if args.fetch
        else json.loads(verify.CACHE.read_text(encoding="utf-8"))
    )
    if not any("cited_by_count" in w for w in works):
        sys.exit("the cache has no citation counts; run with --fetch")

    entries = verify.parse_entries(ROOT / "content" / "publications.md")
    by_title = {verify.norm_title(e["title"]): e for e in entries if e["title"]}

    cutoff = date.today().year - args.years
    ranked = sorted(
        (
            w
            for w in works
            if w.get("type") != "preprint"
            and (w.get("publication_year") or 0) >= cutoff
            and verify.work_key(w) in by_title
        ),
        key=lambda w: -(w.get("cited_by_count") or 0),
    )

    chosen, seen = [], set()
    for w in ranked:
        key = verify.work_key(w)
        if key in seen:
            continue
        seen.add(key)
        chosen.append((w, by_title[key]))
        if len(chosen) == args.n:
            break

    if not args.write:
        print(f"Top {len(chosen)} by citation since {cutoff}. "
              f"Paste what you want into {OUT.relative_to(ROOT)}.\n")
        for w, e in chosen:
            kind = "survey/benchmark" if SURVEYISH.search(
                w.get("display_name") or "") else "method"
            print(f"  {w.get('cited_by_count'):>5}  {w.get('publication_year')}  "
                  f"[{kind:<16}] {(w.get('display_name') or '')[:58]}")
        print(f"\n{OUT.relative_to(ROOT)} left untouched.")
        return 0

    if OUT.is_file() and "hand-edited" not in OUT.read_text(encoding="utf-8"):
        pass

    lines = [
        "<!-- Shown above the list on publications.html.",
        "     Entries are copied verbatim from content/publications.md.",
        f"     Generated {date.today():%Y-%m-%d}: top {len(chosen)} by citation",
        f"     since {cutoff}. Edit by hand freely, including the caption -- but",
        "     `highlights.py --write` overwrites the whole file. -->",
        "",
        f"caption: The {len(chosen)} most cited since {cutoff}, "
        "by [OpenAlex](https://openalex.org/) counts.",
        "",
    ]
    for w, e in chosen:
        lines += [e["raw"], ""]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(chosen)} highlight(s) -> {OUT.relative_to(ROOT)}")
    for w, _ in chosen:
        print(
            f"  {w.get('cited_by_count'):>5}  {w.get('publication_year')}  "
            f"{(w.get('display_name') or '')[:62]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
