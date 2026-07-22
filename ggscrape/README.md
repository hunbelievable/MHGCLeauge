# ggscrape

A CLI + Python library that reads standings, rosters, player scorecards,
and full team round-by-round history (points, opponent, and per-match
A-vs-A/B-vs-B pairing detail) off a Golf Genius **league portal** site (the
public, no-login-required kind — `https://<something>.golfgenius.com`) and
returns clean JSON instead of a web page built for a browser.

Written against `mhgc-tuesdaynightleague.golfgenius.com`, but everything
about *how* it finds pages (see `ggscrape/discover.py`) reads the site's own
navigation instead of hardcoding one club's page IDs, and division/teamset
IDs are discovered from the standings page's own `<select>` options (see
`parsers/standings.py`) rather than hardcoded, so it should work against
any club running the same Golf Genius template. It hasn't been tried
against a second club's site yet — if you point it at one and something
breaks, that's expected on the first try, see "Verification status" below.

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

## Verification status

Everything below has been run for real against the live site (not just
hand-built fixtures) and cross-checked against the site's own reported
numbers: standings and roster totals matched to the penny for all 28
Callaway + 28 Titleist teams and 199 players; a team's full round-by-round
history (`fetch_team_history`) matched its real cumulative total exactly
for every team checked, including edge cases like a team that stopped
playing mid-season (short history, not a parser bug) and rounds where a
substitute played (correctly attributed via majority-vote teammate
detection, not assumed). `player.py`'s hole-by-hole scorecard grid — the
most structurally complex page — was the one that needed the most
follow-up patching (a real HTML page packs two nine-blocks into a single
`<table>`, which naive label-keyed parsing silently corrupts); it's now
solid too.

The parsers use structural heuristics (find the table whose header row
contains "Round Date" and "Points"; figure out whether holes 1-9 or 10-18
are the real ones by checking which half of the row has non-blank values)
rather than guessed CSS class names, so they should survive markup that
differs slightly from Miracle Hill's. `tests/test_parsers.py` now uses
fixtures built from real captured structure (see `tests/fixtures_note.md`),
not just documented/inferred structure.

If you point this at a different club's site and something breaks, that's
still expected on the first try — rerun with `--dump-html` and compare.

## Layout

```
ggscrape/
  fetch.py       — HTTP client (requests session, rate limiting w/ 429 backoff, --dump-html)
  discover.py    — resolve a site's league_id + nav page_ids from its homepage
  parsers/
    standings.py — team standings (both the "current" division and any other,
                   discovered via the page's own <select> options), plus full
                   per-team round-by-round history + match/pairing detail
                   (customized_team_standings / team_standings widgets)
    roster.py    — player_stats list widget
    player.py    — player_stats/member_info widget (per-player detail)
  cli.py         — the `ggscrape` command (discover/standings/roster/player —
                   team history and other-division standings are library-only
                   so far, used directly by scripts/scrape_to_league_data.py;
                   no CLI subcommand for them yet)
tests/
  test_parsers.py — structural smoke tests, fixtures built from real captured markup
```
