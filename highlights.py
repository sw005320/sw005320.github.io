#!/usr/bin/env python3
"""Pick the most-cited recent papers and write them to content/highlights.md.

Citation counts come from OpenAlex and decide only *which* papers are listed --
the text written out is the entry already in content/publications.md, so the
highlight and the list can never word things differently.

    python3 highlights.py --fetch        # refresh counts, then rewrite
    python3 highlights.py --years 5 -n 5
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "content" / "highlights.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("-n", type=int, default=5)
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

    lines = [
        # build.py reads this line for the caption, so the page can never
        # describe a different cut than the one that produced the list
        f"<!-- highlights: n={len(chosen)} since={cutoff} "
        f"generated={date.today():%Y-%m-%d} -->",
        "<!-- Text copied from content/publications.md so the two always agree.",
        "     Edit freely -- regenerating overwrites, so keep a note if you do. -->",
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
