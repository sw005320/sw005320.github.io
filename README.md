# Homepage

A static rebuild of <https://sites.google.com/view/shinjiwatanabe>, as a proof of
concept for moving to GitHub Pages. Nothing here is published anywhere yet.

## Where to edit what

`content/*.md` is the single source of truth for everything that changes often.

| To change | Edit |
| --- | --- |
| A publication | `content/publications.md` |
| Education, appointments, awards, teaching, service, collaborators | `content/activities.md` |
| Short bio | `content/home.md` |
| Name, title, affiliation, e-mail | `NAME` / `ROLE` / `AFFIL` / `DEPT` / `EMAIL` in `build.py` |
| Profile links (Scholar, GitHub, ...) | `PROFILE_LINKS` in `build.py` |
| Software projects | `SOFTWARE` in `build.py` |
| Which sections go in the CV, and their order | `CV_LAYOUT` in `build.py` |
| Colours, fonts, layout, print styles | `docs/style.css` |
| Default palette | `docs/app.js` (`recall(PALETTE_KEY) || "paper"`) |

Then:

```sh
python3 build.py                                  # regenerate docs/
python3 -m http.server 8787 --directory docs      # preview
```

## Content format

One entry per paragraph, blank line between entries. `##` starts a section and
`###` a subsection; the names must match what `CV_LAYOUT` refers to.

```
## Journal (refereed)

**Shinji Watanabe** and Jen-Tzung Chien, "[Bayesian Speech and Language
Processing](http://www.cambridge.org/...)," *Cambridge University Press* (2015)
```

The whole inline vocabulary is `**bold**`, `*italic*`, `***bold italic***` and
`[text](url)`. No escaping, no commas to balance; a typo can only break the one
entry it is in. An entry may wrap across lines -- the blank line is what
separates entries.

## The CV

`docs/cv.html` is generated from the same entries as the rest of the site, so it
cannot drift out of date. `CV_LAYOUT` in `build.py` decides which website
sections appear, in what order, and under which CV heading.

For a PDF, either press **Print / Save as PDF** on the page, or:

```sh
./makepdf.sh        # needs the preview server running; writes docs/cv.pdf
```

The current CV runs to 48 pages / 1131 entries.

**It only contains what is on the website.** Compare it against the existing
[CV on Drive](https://drive.google.com/file/d/1fQw_dsvdNRMuqv2YnG6ip0YmANEFyX2v/view)
before using it anywhere -- funding, grants, patents and students are the usual
things a website leaves out.

## Theme

Newsreader (display) + Inter (UI), from Google Fonts.

Three palettes ship as CSS custom-property sets, switchable from the header
swatches: **paper** (warm white / garnet, default), **slate** (cool grey /
indigo), **forest** (cream / deep green). Each has light and dark variants; with
no explicit choice the page follows the OS setting. Both preferences live in
`localStorage`, so they are per-visitor and never baked into the published page.

## Photo

`docs/assets/shinji.jpg` comes from <https://www.wavlab.org/assets/img/shinji_20210605.jpg>,
centre-cropped square, resized to 640x640, re-encoded (1.3 MB -> 134 KB). The
original carries EXIF including GPS coordinates and the capture device; the copy
here is written without any metadata.

## migration/

The one-off Google Sites import, kept for reference and no longer part of the
build:

```
migration/raw/         the four Sites pages, fetched with curl
migration/extract.py   raw/*.html  -> data/*.json
migration/convert.py   data/*.json -> content/*.md, with round-trip verification
migration/data/        the intermediate JSON
```

All 1132 entries converted with a verified round-trip (`md_to_html(html_to_md(x))`
equal to the original for every entry). Counts match the live site exactly,
including the subsection splits: Academic Activity 96 = 4 + 73 + 13 + 6,
Reviewer 68 = 28 + 18 + 22, Collaborators 103 = 61 + 17 + 11 + 14.

Do not re-run `extract.py` -- `content/` is now ahead of it.

## Known gaps

- **Publication years** are scraped from the trailing `(YYYY)` in each entry and
  drive the year filter. Entries without a parseable year are still listed but
  are not reachable from the dropdown.
- **No BibTeX yet.** Entries are single strings, as on the current site.
  Splitting them into structured fields (authors / title / venue / year / links)
  is the step that would enable per-entry BibTeX export and sorting by venue.
- The Google Sites page cannot redirect automatically; it would have to stay up
  as a pointer to the new address.

## If this becomes the real site

`docs/` is plain HTML/CSS/JS with no build step. GitHub Pages serves it
directly: Settings -> Pages -> Source = `main` branch, folder `/docs`.

Intended home: a public repo named exactly **`sw005320.github.io`**, which
publishes at <https://sw005320.github.io>. That name is free as of 2026-09-16
and the account already exists. A user site must be public unless the account
has a paid plan.

A custom domain can be attached later from Settings -> Pages without touching
the repo; the `.github.io` URL keeps working. The lab site is the same
arrangement -- `wavlab.org` is served by the repo
`wavlab-speech/shinjiwlab.github.io` (the DNS CNAME still names a
`shinjiwlab` account that no longer exists; it resolves through the apex A
records instead).

The Google Sites page has to stay up as a pointer -- it cannot redirect.
