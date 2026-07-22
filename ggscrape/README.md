# ggscrape

A CLI + Python library that reads standings, rosters, and player scorecards
off a Golf Genius **league portal** site (the public, no-login-required kind
— `https://<something>.golfgenius.com`) and returns clean JSON instead of a
web page built for a browser.

Written against `mhgc-tuesdaynightleague.golfgenius.com`, but everything
about *how* it finds pages (see `ggscrape/discover.py`) reads the site's own
navigation instead of hardcoding one club's page IDs, so it should work
against any club running the same Golf Genius template. It hasn't been
tried against a second club's site yet — if you point it at one and
something breaks, that's expected on the first try, see "Verification
status" below.

## Install

```bash
pip install -e .
```

Needs Python 3.9+. Pulls in `requests`, `beautifulsoup4`, `lxml`.

## Usage

```bash
# What pages/sections does this site have?
ggscrape https://mhgc-tuesdaynightleague.golfgenius.com discover

# Full team standings (all divisions)
ggscrape https://mhgc-tuesdaynightleague.golfgenius.com standings

# Every player + their member_id + season hole-outcome totals
ggscrape https://mhgc-tuesdaynightleague.golfgenius.com roster

# One player, by name (looked up via the roster) or by member_id directly
ggscrape https://mhgc-tuesdaynightleague.golfgenius.com player --name "Holiday, Rusty"
ggscrape https://mhgc-tuesdaynightleague.golfgenius.com player --member-id 12541418705654939173
```

Add `--dump-html ./dump` to any command to save the raw HTML of every page
it fetches into that folder. Do this the first time you run it — if a
parser gets something wrong, the saved HTML is what lets it get fixed
against ground truth instead of another guess.

Everything is polite by default: one request at a time, ~0.6s between
requests (`--delay` to change it). This is someone's small club's server,
not a CDN.

## Verification status — read this before trusting the output blindly

This tool was built inside a sandbox that could only ever see a
**pre-rendered text view** of these pages (tables converted to markdown,
links converted to `[text](url)`), never the actual HTML. That text view was
used to hand-verify the *data* extensively — every player's low-gross round,
every round's scoring-mix counts, and full season totals were cross-checked
against the site's own reported numbers and matched exactly, for 9 players
and all 28 Callaway teams.

But this package talks to the site with plain `requests`, which returns raw
HTML, not that pre-rendered text. The parsers were rewritten to read real
HTML via BeautifulSoup, using structural heuristics (find the table whose
header row contains "Rank" and "Team Points"; figure out whether holes 1-9
or 10-18 are the real ones by checking which half of the row has non-blank
values) rather than guessed CSS class names, specifically so they'd survive
not knowing the exact markup. That's a reasonable bet, but it's a bet, it
has only been checked against hand-built fixture HTML that matches the
*documented* structure (see `tests/fixtures_note.md`), not the real site.

Practical upshot:
- `discover` and `standings` are lower-risk — simple, regular tables.
- `roster` is similar.
- `player` (the hole-by-hole scorecard grid) is the most structurally
  complex page and the one most likely to need a follow-up patch.

Run it once for real, skim the output, and if anything looks wrong (or the
tool errors out with a "couldn't find table" message), send the
`--dump-html` output back and it's a quick fix against real markup rather
than more guessing.

## What's not built yet

Round-by-round **team** history (a team's week-by-week points, as opposed to
a single player's), the tee sheet, and individual match/round results pages
are not implemented. The dashboard this was built for currently gets team
weekly history by diffing team season totals week over week rather than
reading a dedicated widget for it — `ggscrape` doesn't do that diffing, it
only reads pages directly.

## Layout

```
ggscrape/
  fetch.py       — HTTP client (requests session, rate limiting, --dump-html)
  discover.py    — resolve a site's league_id + nav page_ids from its homepage
  parsers/
    standings.py — customized_team_standings widget
    roster.py    — player_stats list widget
    player.py    — player_stats/member_info widget (per-player detail)
  cli.py         — the `ggscrape` command
tests/
  test_parsers.py — structural smoke tests against hand-built fixture HTML
```
