#!/usr/bin/env python3
"""Refresh league-data.json from the live Golf Genius site, using ggscrape.

This is the missing piece flagged in PROJECT_README.md: it calls ggscrape's
parsers directly (as a library, not the CLI) and reshapes their dataclass
output into league-data.json's schema, then merges that into the existing
file so hand-curated content that has no scrape source survives.

Usage:
    pip install -e ggscrape/
    python3 scripts/scrape_to_league_data.py
    python3 scripts/scrape_to_league_data.py --dry-run          # print, don't write
    python3 scripts/scrape_to_league_data.py --dump-html ./dump # save raw HTML too
    python3 scripts/scrape_to_league_data.py --add-player "Doe, Jane"

What this CAN derive from the site every run:
    - Callaway team standings, rank, and this round's points (by diffing
      each team's new total against its previous stored total)
    - the full player roster's season hole-outcome totals (playerStats)
    - full round-by-round scorecards for whichever players are already
      being tracked in playerDetail (or newly added via --add-player)

What it CANNOT derive, because no page ggscrape reads exposes it, and
carries forward unchanged from the existing file instead:
    - myTeam.matchups' per-round opponent/result narrative (needs pairing
      and opponent-scorecard data no discovered page has)
    - Titleist division standings and its week-by-week history (Titleist
      isn't exposed the way Callaway is — see dashboard-template.html's
      own note on the Playoffs tab)
    - meta.season config (scoringWeeks, dropCount, playoffSpots, ...) and
      meta.upcoming's schedule beyond what was already on file

Run this after each week's round, skim the printed warnings, fill in the
new myTeam.matchups entry by hand, then run build_dashboard.py.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from ggscrape.fetch import Client
    from ggscrape.discover import discover
    from ggscrape.parsers.standings import parse_standings
    from ggscrape.parsers.roster import parse_roster
    from ggscrape.parsers.player import parse_player
except ImportError:
    sys.path.insert(0, str(ROOT / "ggscrape"))
    from ggscrape.fetch import Client
    from ggscrape.discover import discover
    from ggscrape.parsers.standings import parse_standings
    from ggscrape.parsers.roster import parse_roster
    from ggscrape.parsers.player import parse_player

DEFAULT_BASE_URL = "https://mhgc-tuesdaynightleague.golfgenius.com"


def short_date(date_str: str) -> str:
    """'Tue, July 28' -> 'Jul 28'"""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", date_str)
    if not m:
        return date_str
    return f"{m.group(1)[:3]} {int(m.group(2))}"


def round_num_from_label(label: str):
    m = re.search(r"Round\s*(\d+)", label)
    return int(m.group(1)) if m else None


def build_player_detail(gg) -> dict:
    hole_by_round = {h.round_num: h for h in gg.hole_rounds}
    rounds = []
    for s in gg.scoring:
        h = hole_by_round.get(s.round_num)
        if h is None:
            continue  # scoring row with no matching hole-by-hole grid (e.g. not posted yet)
        rounds.append({
            "round": f"Round {s.round_num}",
            "date": s.date,
            "nine": h.nine,
            "holes": h.holes,
            "dist": s.dist,
        })
    course = {
        nine: {"par": nd.par, "leagueAvg": nd.league_avg, "myAvg": nd.my_avg}
        for nine, nd in gg.course.items()
    }
    par9 = sum(course["front"]["par"]) if "front" in course else (
        sum(course["back"]["par"]) if "back" in course else None)
    return {
        "name": gg.name,
        "hcpIndex": gg.hcp_index,
        "lowGross": gg.low_gross,
        "lowNet": gg.low_net,
        "roundsPlayed": gg.rounds_played,
        "par9": par9,
        "course": course,
        "rounds": rounds,
    }


def find_member(roster, name: str):
    """Exact match first (roster names are canonical 'Last, First'), then a
    unique case-insensitive substring match like ggscrape's CLI --name does."""
    for p in roster:
        if p.name == name:
            return p
    matches = [p for p in roster if name.lower() in p.name.lower()]
    return matches[0] if len(matches) == 1 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--in", dest="infile", default=str(ROOT / "league-data.json"))
    ap.add_argument("--out", dest="outfile", default=None, help="defaults to --in (in-place refresh)")
    ap.add_argument("--dump-html", metavar="DIR", default=None)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--add-player", action="append", default=[], metavar="NAME",
                     help="Roster name (e.g. 'Doe, Jane') to start tracking full scorecards for")
    ap.add_argument("--dry-run", action="store_true", help="Print the result instead of writing it")
    ap.add_argument("--force-round", action="store_true",
                     help="Advance meta/roundLabels/weekly history even if no team's points changed "
                          "since the last save (by default this is treated as 'this week hasn't posted "
                          "yet' and standings/meta are left alone, to avoid recording a phantom zero-point week)")
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.outfile) if args.outfile else infile

    prev = json.loads(infile.read_text())
    data = copy.deepcopy(prev)
    warnings = []

    client = Client(args.base_url, delay=args.delay, dump_dir=args.dump_html)
    site = discover(client)

    # ---- Callaway standings ----
    standings_url = client.widget_url(site.league_id, "customized_team_standings", site.page_id("standing"))
    live_teams = parse_standings(client.get(standings_url, dump_name="standings"))

    prev_teams_by_name = {t["name"]: t for t in prev["teams"]}
    matched_diffs = [
        round(t.total_points - prev_teams_by_name[t.name]["total"], 1)
        for t in live_teams if t.name in prev_teams_by_name
    ]
    new_round_posted = args.force_round or any(d != 0 for d in matched_diffs)

    if not new_round_posted:
        warnings.append(
            "No team's point total changed since the last save — this week's round doesn't look "
            "posted yet. Standings/weekly history/meta left unchanged (pass --force-round to override). "
            "playerStats and tracked players' scorecards were still refreshed below."
        )
        # Still refresh rank/total in case of a correction, but don't touch weekly history.
        data["teams"] = [
            {**prev_teams_by_name.get(t.name, {"weekly": [t.total_points]}), "rank": t.rank, "total": t.total_points}
            for t in live_teams
        ]
        data["callawayWeekly"] = {t["name"]: t["weekly"] for t in data["teams"]}
        data["standings"]["callaway"] = [[t.name, t.total_points] for t in live_teams]
    else:
        new_teams = []
        round_diffs = []
        for t in live_teams:
            prev_t = prev_teams_by_name.get(t.name)
            if prev_t is None:
                warnings.append(f"New team not in previous file: {t.name!r} — starting its weekly history from this round only.")
                weekly = [t.total_points]
            else:
                diff = round(t.total_points - prev_t["total"], 1)
                weekly = prev_t["weekly"] + [diff]
                round_diffs.append([t.name, diff])
            new_teams.append({"name": t.name, "rank": t.rank, "total": t.total_points, "weekly": weekly})
        round_diffs.sort(key=lambda r: -r[1])

        data["teams"] = new_teams
        data["callawayWeekly"] = {t["name"]: t["weekly"] for t in new_teams}
        data["standings"]["callaway"] = [[t["name"], t["total"]] for t in new_teams]
        data["latestRound"] = round_diffs
    data.pop("round13", None)  # old per-round-number key name; dashboard now reads "latestRound"

    if "titleist" not in data.get("standings", {}):
        data.setdefault("standings", {})["titleist"] = prev.get("standings", {}).get("titleist", [])
    warnings.append("standings.titleist NOT refreshed — Titleist isn't exposed the way Callaway is (see dashboard-template.html's Playoffs-tab note). Carried forward unchanged.")

    # ---- myTeam ----
    my_name = prev["myTeam"]["name"]
    my_team = next((t for t in data["teams"] if t["name"] == my_name), None)
    if my_team is None:
        warnings.append(f"Your team {my_name!r} not found in live standings — myTeam left unchanged.")
    else:
        data["myTeam"]["rank"] = my_team["rank"]
        data["myTeam"]["points"] = my_team["total"]
        data["myTeam"]["weekly"] = my_team["weekly"]
    if new_round_posted:
        warnings.append("myTeam.matchups NOT updated — opponent/result narrative isn't on any page ggscrape reads. Add this round's entry by hand.")

    # ---- roster -> playerStats ----
    roster_url = client.widget_url(site.league_id, "player_stats", site.page_id("player stat"))
    roster = parse_roster(client.get(roster_url, dump_name="roster"))
    data["playerStats"] = sorted(
        ([p.name, p.eagles, p.birdies, p.pars, p.bogeys, p.doubles, p.triples_or_worse] for p in roster),
        key=lambda r: r[0],
    )

    # ---- playerDetail for tracked (+ newly added) players ----
    tracked = sorted(set(prev.get("playerDetail", {}).keys()) | set(args.add_player))
    new_player_detail = {}
    for name in tracked:
        member = find_member(roster, name)
        if member is None or member.member_id is None:
            warnings.append(f"Could not resolve a member_id for tracked player {name!r} on the roster — keeping their previous scorecard data as-is.")
            if name in prev.get("playerDetail", {}):
                new_player_detail[name] = prev["playerDetail"][name]
            continue
        pd_url = client.widget_url(site.league_id, "player_stats/member_info", site.page_id("player stat"),
                                    member_id=member.member_id)
        try:
            gg_detail = parse_player(client.get(pd_url, dump_name=f"player_{member.member_id}"))
            new_player_detail[name] = build_player_detail(gg_detail)
        except Exception as e:
            warnings.append(f"Failed to fetch/parse {name!r} ({e}) — keeping their previous scorecard data as-is.")
            if name in prev.get("playerDetail", {}):
                new_player_detail[name] = prev["playerDetail"][name]
    data["playerDetail"] = new_player_detail

    # ---- meta bookkeeping ----
    meta = data["meta"]
    if new_round_posted:
        upcoming = list(prev["meta"].get("upcoming", []))
        if upcoming:
            played = upcoming.pop(0)
            meta["throughRound"] = f"{played['round']} ({played['date']})"
            rnum = round_num_from_label(played["round"])
            label = f"R{rnum}\n{short_date(played['date'])}" if rnum else played["round"]
            meta["roundLabels"] = prev["meta"]["roundLabels"] + [label]
            meta["season"]["playedWeeks"] = prev["meta"]["season"]["playedWeeks"] + 1
        else:
            warnings.append("meta.upcoming was empty — couldn't tell which round just completed. "
                             "throughRound/roundLabels/playedWeeks left unchanged; add the season's remaining schedule to meta.upcoming by hand.")
        meta["upcoming"] = upcoming
        meta["nextMatch"] = (
            {**upcoming[0], "note": "Pairings not posted yet"} if upcoming else
            {"round": None, "date": None, "note": "No further scheduled rounds on file — add them to meta.upcoming"}
        )
    meta["lastUpdated"] = dt.date.today().isoformat()

    out_text = json.dumps(data, indent=2) + "\n"
    if args.dry_run:
        print(out_text)
    else:
        outfile.write_text(out_text)
        print(f"Wrote {outfile}")

    if warnings:
        print("\nRefresh completed with notes:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
