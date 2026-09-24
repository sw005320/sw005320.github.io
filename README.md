# Homepage

Source for <https://sw005320.github.io>, a static rebuild of the old Google
Sites page at <https://sites.google.com/view/shinjiwatanabe>.

Edit `content/*.md`, commit and push. A workflow renders the site and the CV
PDF and deploys them; `docs/` is generated and is not in the repository.

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
| Something that belongs in the CV but not on the site | `content/cv-extra.md` |
| Colours, fonts, layout, print styles | `static/style.css` |
| Default palette | `static/app.js` (`recall(PALETTE_KEY) || "paper"`) |
| The photo, or any other asset | `static/` (copied verbatim into the build) |

Pushing is enough. To see it first:

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

The current CV runs to 49 pages / 1137 entries.

Sections that belong in the CV but not on the website live in
`content/cv-extra.md`; `CV_LAYOUT` refers to them as `("cv", "<name>")`.

Checked against the previous [CV on Drive](https://drive.google.com/file/d/1fQw_dsvdNRMuqv2YnG6ip0YmANEFyX2v/view)
(50 pages) on 2026-09-16: the only sections it had that the website did not were
Programming Skills and Language Skills, now in `content/cv-extra.md`. It has no
separate grants, funding or patents sections.

## Keeping the list up to date

`find_new.py` asks OpenAlex what it has that `content/publications.md` does not,
and writes the candidates out in house style:

```sh
python3 find_new.py --fetch
```

A weekly workflow runs the same thing and opens an issue when there is anything
to add. It never commits: the list is the record, and the drafts need checking.
OpenAlex leaves the venue empty on most conference papers (Crossref fills it in),
truncates author lists, and sometimes files another Shinji Watanabe's work under
this author id -- a 2025 depth-camera paper on elderly action recognition arrived
that way. Candidates whose titles carry no vocabulary from this field are flagged.

`verify.py` is the other half: it cross-checks what is already listed. See
`verify-report.md`.

## Theme

Newsreader (display) + Inter (UI), from Google Fonts.

Three palettes ship as CSS custom-property sets, switchable from the header
swatches: **paper** (warm white / garnet, default), **slate** (cool grey /
indigo), **forest** (cream / deep green). Each has light and dark variants; with
no explicit choice the page follows the OS setting. Both preferences live in
`localStorage`, so they are per-visitor and never baked into the published page.

## Photo

`static/assets/shinji.jpg` comes from <https://www.wavlab.org/assets/img/shinji_20210605.jpg>,
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

## Deployment

Live since 2026-09-16 at <https://sw005320.github.io>, from the public repo
`sw005320/sw005320.github.io`. A user site must be public unless the account has
a paid plan.

`.github/workflows/deploy.yml` builds and deploys on every push to `main`, so
`docs/` is generated and deliberately untracked -- a committed copy could only
drift from what is published. The workflow refuses to deploy a build that looks
wrong: too few publication entries, no italic venue names, unrendered markdown
in the HTML, a missing stylesheet, script or portrait, or a tiny `cv.pdf`.

Two things that cost time before, in case Pages is ever reconfigured:

- Serving from a branch folder requires that folder to hold an `index.html`;
  picking `/ (root)` 404s everything.
- **Changing the Pages source does not trigger a rebuild.** The previous build
  keeps serving while the API reports the new setting. Force one with
  `gh api -X POST repos/sw005320/sw005320.github.io/pages/builds`.

A custom domain can be attached later from Settings -> Pages without touching
the repo; the `.github.io` URL keeps working. The lab site is the same
arrangement -- `wavlab.org` is served by the repo
`wavlab-speech/shinjiwlab.github.io` (the DNS CNAME still names a
`shinjiwlab` account that no longer exists; it resolves through the apex A
records instead).

The Google Sites page has to stay up as a pointer -- it cannot redirect.
