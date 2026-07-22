# Tuesday Night League Dashboard — handoff notes

Everything needed to turn this into a real repo is in this folder. Ignore
`_scratch_*.txt` and `ziF6aAh5` — leftover scratch files from the Cowork
session, not part of the project.

## What exists and works right now

- **`dashboard-template.html`** — the dashboard's HTML/CSS/JS, with
  `/*__DATA__*/` and `/*__CHARTJS__*/` placeholders. This is what you edit
  when you want to change the dashboard's look or add a feature.
- **`league-data.json`** — the actual season data (standings, playoff
  projections, 8 players' full scorecards, 190 players' season stats).
  Currently built/updated by hand each week.
- **`build_dashboard.py`** — fills the template's placeholders with the JSON
  data and an embedded copy of Chart.js, producing the standalone
  `Tuesday Night League Dashboard.html` you can open in a browser or deploy
  as-is. Run `python3 build_dashboard.py` after changing either the template
  or the data.
- **`ggscrape/`** — a pip-installable scraper/CLI for Golf Genius
  league-portal sites (see `ggscrape/README.md`). Discovers pages, and
  parses standings, roster, and per-player scorecards into JSON. **Not yet
  verified against the live site** — nothing in this sandbox could execute
  its HTTP calls (see below). Run it for real once you're set up locally.

## What's NOT built yet — the actual gap before this is automated

`ggscrape`'s output is shaped as its own dataclasses (`TeamStanding`,
`RosterEntry`, `PlayerDetail`), not the `league-data.json` schema the
dashboard template expects (`meta`, `teams`, `playerDetail`, `standings`,
playoff-projection config, etc — see the existing `league-data.json` for the
full shape). There's no script that turns ggscrape's output into that
schema. That's the real next piece of work: a `scripts/scrape_to_league_data.py`
that calls `ggscrape`'s parsers and reshapes the result. `.github/workflows/refresh.yml`
has a TODO exactly where this plugs in.

## Why this needs to leave the chat session

Two separate things blocked finishing this inside Cowork:

1. **I can't execute live HTTP requests.** I'm restricted to a sanctioned
   fetch tool that pre-renders pages to text, not raw HTML — that's why
   `ggscrape` (which uses plain `requests` + BeautifulSoup on real HTML) has
   never actually been run. It needs to run somewhere without that
   restriction: your machine, or a GitHub Actions runner.
2. **A scheduled/automated refresh needs a process that outlives this
   conversation.** GitHub Actions (see `.github/workflows/refresh.yml`) is
   built for exactly this — cron trigger, scrape, rebuild, commit, and
   Cloudflare Pages or GitHub Pages redeploys on the push.

## Suggested order of operations in Claude Code

1. `git init`, commit everything in this folder.
2. Run `ggscrape` for real against
   `https://mhgc-tuesdaynightleague.golfgenius.com` with `--dump-html`, fix
   whatever the raw HTML reveals is wrong in `ggscrape/ggscrape/parsers/`
   (the README there flags `player.py` as the riskiest one).
3. Write `scripts/scrape_to_league_data.py` (the missing transform step
   above), test it produces a `league-data.json` that matches the existing
   file's shape.
4. Fill in the `.github/workflows/refresh.yml` scrape step to call it.
5. Push to GitHub, connect the repo to Cloudflare Pages (or enable GitHub
   Pages), point it at `Tuesday Night League Dashboard.html` — or better,
   have Pages' build command literally run `python3 build_dashboard.py` so
   the committed HTML is always freshly built from `league-data.json`.
