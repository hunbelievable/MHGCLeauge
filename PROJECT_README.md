# Tuesday Night League Dashboard

A scraper + dashboard for Miracle Hill Golf Club's Tuesday Night League
(Golf Genius site: `mhgc-tuesdaynightleague.golfgenius.com`). Live at
https://hunbelievable.github.io/MHGCLeauge/.

## What this is

- **`ggscrape/`** — a pip-installable scraper/CLI for Golf Genius
  league-portal sites. Discovers pages by reading the site's own navigation
  (no hardcoded page IDs), and parses team standings, full round-by-round
  team history with per-match opponent/pairing detail, player rosters, and
  per-player scorecards into JSON. See `ggscrape/README.md`.
- **`scripts/scrape_to_league_data.py`** — pulls everything from the live
  site via ggscrape and reshapes it into `league-data.json`'s schema,
  merging into the existing file so whatever ggscrape can't derive (season
  config, future schedule) survives.
- **`league-data.json`** — the season data: standings, full weekly-points
  history and per-round match detail for every one of the 56 teams across
  both divisions, drop-2 shootout projections, and full scorecards for
  every team-roster player (112 of them).
- **`dashboard-template.html`** — the dashboard's HTML/CSS/JS, with
  `/*__DATA__*/` and `/*__CHARTJS__*/` placeholders.
- **`build_dashboard.py`** — fills the template's placeholders with the
  JSON data and an embedded copy of Chart.js, producing the standalone
  `Tuesday Night League Dashboard.html`.

## How team history actually works

Team weekly-points history and per-match detail (opponent, both individual
A-vs-A/B-vs-B pairings) come straight from the league's own per-team
history page (`team_standings/team_info` — a Golf Genius widget that took a
while to find) — every round back to Round 2, for any team in either
division. It is **not** reconstructed by diffing successive standings
snapshots; the site already has the real history, this just reads it.

That same page family carries the Callaway/Titleist division switch: the
plain standings list defaults to whichever division the site considers
"current" (Callaway here), and the other division lives behind a hidden
`teamset` + `sequence` parameter pair on a *different* widget path
(`team_standings`, not `customized_team_standings`) — internal numeric IDs,
not anything guessable. `fetch_division_standings` and `fetch_team_history`
in `ggscrape/ggscrape/parsers/standings.py` discover those IDs from the
page's own `<select>` options rather than hardcoding them, so this should
hold for any division on any club running the same template.

## Equal treatment by design

Every team gets the same full history, matchup detail, and shootout
projection — not just one. Every team-roster player gets the same full
scorecard treatment. There's no "my team" baked into `league-data.json` or
the dashboard.

Instead, the built HTML remembers each *viewer's* own team/player choice in
their browser's `localStorage`. Open it fresh and it defaults to the
current division leader and the alphabetically-first player; pick your own
team once and it's remembered on your device only, without changing what
anyone else sees when they open the same shared page.

## Refreshing the data

```bash
pip install -e ggscrape/
python3 scripts/scrape_to_league_data.py       # refresh league-data.json in place
python3 build_dashboard.py                     # rebuild the standalone HTML
git add -A && git commit -m "Weekly refresh" && git push
```

A full refresh fetches all 112 teams' history (one request per team) plus
all 112 tracked players' scorecards — expect several minutes, more if the
site rate-limits under the volume (the client backs off and retries
automatically, polite by default). It's skipped by default if nothing's
actually changed since the last save (pass `--force` to override anyway);
`playerStats`/`playerDetail` still refresh regardless since those are cheap.

Other flags: `--dry-run` (print, don't write), `--dump-html DIR` (save raw
HTML for debugging a parser), `--add-player "Last, First"` (track a
sub/fill-in's scorecard too, on top of every team-roster player already
tracked automatically).

## Deployment

Pushed to GitHub (`hunbelievable/MHGCLeauge`), served by GitHub Pages from
the repo root. `index.html` is a redirect to the built dashboard (whose
filename has spaces, which Pages' default-document lookup doesn't like).
Pages rebuilds automatically on push, usually within a minute.

## What's still manual / not automated

- **Season schedule** (`meta.season` config, `meta.upcoming` beyond what's
  already on file) — future rounds haven't happened yet, so there's nothing
  to scrape for them.
- **A scheduled/automated refresh** — right now someone runs the refresh
  commands above by hand each week. A GitHub Actions workflow (cron trigger
  → scrape → rebuild → commit → Pages redeploys on push) would remove that
  step, but hasn't been built — the season only has a few weeks left, and
  running it by hand weekly is low-cost at that cadence.
