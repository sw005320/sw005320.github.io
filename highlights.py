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
import pathlib
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


def current_entries():
    """The entries listed in content/highlights.md right now."""
    if not OUT.is_file():
        return []
    out, buf, in_comment = [], [], False
    for line in OUT.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if in_comment:                       # a comment block spans lines, and
            in_comment = not t.endswith("-->")   # stripping hides its indent
            continue
        if t.startswith("<!--"):
            in_comment = not t.endswith("-->")
            continue
        if t.startswith("caption:"):
            continue
        if not t:
            if buf:
                out.append(" ".join(buf)); buf = []
            continue
        buf.append(t)
    if buf:
        out.append(" ".join(buf))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("-n", type=int, default=15)
    ap.add_argument("--write", action="store_true",
                    help="replace content/highlights.md with the top --n")
    ap.add_argument("--check", metavar="FILE",
                    help="write a report of how the ranking has moved since "
                         "content/highlights.md was last set, for CI")
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

    if args.check:
        listed = current_entries()
        picked = [e["raw"] for _, e in chosen]
        gone = [r for r in listed if r not in picked]
        risen = [(w, e) for w, e in chosen if e["raw"] not in listed]
        lines = []
        if gone or risen:
            lines = [
                "## Selected publications",
                "",
                f"The top {args.n} by citation since {cutoff} no longer matches "
                "`content/highlights.md`.",
                "",
                "`highlights.md` is maintained by hand, so nothing was changed. "
                "Run `python3 highlights.py --write -n "
                f"{args.n}` to take the ranking as it stands, or edit the file.",
                "",
            ]
            if risen:
                lines.append("**Now in the top, not listed:**")
                lines.append("")
                for w, e in risen:
                    lines.append(f"- {w.get('cited_by_count')} citations &mdash; "
                                 f"{(w.get('display_name') or '')[:90]}")
                lines.append("")
            if gone:
                lines.append("**Listed, no longer in the top:**")
                lines.append("")
                for r in gone:
                    t = re.split(r'["\u201c\u201d]', r)
                    lines.append(f"- {(t[1] if len(t) > 1 else r)[:90]}")
                lines.append("")
        pathlib.Path(args.check).write_text("\n".join(lines), encoding="utf-8")
        print(f"{len(risen)} risen, {len(gone)} dropped -> {args.check}")
        return 0

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
