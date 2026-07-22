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

What this derives from the site every run, identically for every one of the
56 teams across both divisions — nobody's team gets richer data than anyone
else's:
    - team standings (rank, current total)
    - full round-by-round points history, straight from the league's own
      per-team history page (`team_standings/team_info`) — every round back
      to Round 2, not reconstructed by diffing successive totals
    - full per-round match detail from that same page: opponent, team
      us/them points, and both individual A-vs-A/B-vs-B player pairings
      (whoever actually played, subs included)
    - the full player roster's season hole-outcome totals (playerStats)
    - full round-by-round scorecards for every player on a team roster,
      plus anyone added via --add-player

Fetching all 112 teams' full history is expensive (one request per team,
same as the 112 player-detail fetches), so it's skipped unless something
actually changed: a team's current total differs from last save, a team
has no history on file yet, or --force. Otherwise only playerStats/
playerDetail refresh (the cheap, always-useful path).

What it CANNOT derive, because no page ggscrape reads exposes it, and
carries forward unchanged from the existing file instead:
    - meta.season config (scoringWeeks, dropCount, playoffSpots, ...) and
      meta.upcoming's schedule beyond what was already on file (future
      rounds haven't happened yet, so there's nothing to scrape)

Run this after each week's round, skim the printed warnings, then run
build_dashboard.py.
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
    from ggscrape.parsers.standings import (
        parse_standings, parse_division_options, fetch_division_standings, fetch_team_history,
    )
    from ggscrape.parsers.roster import parse_roster
    from ggscrape.parsers.player import parse_player
except ImportError:
    sys.path.insert(0, str(ROOT / "ggscrape"))
    from ggscrape.fetch import Client
    from ggscrape.discover import discover
    from ggscrape.parsers.standings import (
        parse_standings, parse_division_options, fetch_division_standings, fetch_team_history,
    )
    from ggscrape.parsers.roster import parse_roster
    from ggscrape.parsers.player import parse_player

DEFAULT_BASE_URL = "https://mhgc-tuesdaynightleague.golfgenius.com"
MONTH_FULL = {m[:3]: m for m in [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"]}


def short_date(date_str: str) -> str:
    """'May 05, 2026' -> 'May 5'"""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", date_str)
    return f"{m.group(1)[:3]} {int(m.group(2))}" if m else date_str


def full_date_with_weekday(date_str: str) -> str:
    """'May 05, 2026' -> 'Tue, May 5' (this league only ever plays Tuesdays)."""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", date_str)
    if not m:
        return date_str
    month = MONTH_FULL.get(m.group(1)[:3], m.group(1))
    return f"Tue, {month} {int(m.group(2))}"


def matchups_to_json(matchups) -> list:
    return [
        {"round": f"R{m.round_num}", "date": short_date(m.date), "opp": m.opponent,
         "us": m.us, "them": m.them,
         "pairings": [{"player": p.player, "opp": p.opponent, "us": p.us, "them": p.them} for p in m.pairings]}
        for m in matchups
    ]


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


def fetch_division_history(client, league_id, page_id, teams, teamset_id, sequence_id, warnings, label):
    """Fetch every team's ground-truth round history and full match detail —
    the same two requests-worth of data for every team, nobody privileged."""
    team_rows = []
    for t in teams:
        try:
            rounds, matchups = fetch_team_history(client, league_id, page_id, t.team_id, teamset_id, sequence_id)
        except Exception as e:
            warnings.append(f"Failed to fetch {label} team history for {t.name!r} ({e}) — skipping, weekly history for this team may go stale.")
            continue
        team_rows.append({"name": t.name, "rank": t.rank, "total": t.total_points,
                           "weekly": [r.points for r in rounds], "matchups": matchups_to_json(matchups),
                           "rounds": rounds})
    return team_rows


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
    ap.add_argument("--force", action="store_true",
                     help="Re-fetch every team's full history even if nothing looks changed")
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.outfile) if args.outfile else infile

    prev = json.loads(infile.read_text())
    data = copy.deepcopy(prev)
    data.pop("myTeam", None)  # replaced by a client-side preferred-team picker; every team's data is equal now
    warnings = []

    client = Client(args.base_url, delay=args.delay, dump_dir=args.dump_html)
    site = discover(client)
    pid = site.page_id("standing")

    # ---- both divisions' current standings (cheap: 2 requests) ----
    base_url = client.widget_url(site.league_id, "customized_team_standings", pid)
    opts = parse_division_options(client.get(base_url, dump_name="standings_form"))
    cal_teamset, tit_teamset = opts.teamset_id("callaway"), opts.teamset_id("titleist")
    seq = opts.default_sequence

    live_cal = parse_standings(client.get(client.widget_url(site.league_id, "customized_team_standings", pid),
                                           dump_name="standings_cal"))
    live_tit = fetch_division_standings(client, site.league_id, pid, "Titleist")

    prev_cal_by_name = {t["name"]: t for t in prev["teams"]}
    prev_tit_by_name = {t["name"]: t for t in prev.get("titleistTeams", [])}
    any_total_changed = any(
        round(t.total_points - prev_cal_by_name[t.name]["total"], 1) != 0
        for t in live_cal if t.name in prev_cal_by_name
    ) or any(
        round(t.total_points - prev_tit_by_name[t.name]["total"], 1) != 0
        for t in live_tit if t.name in prev_tit_by_name
    )
    missing_history = any(not prev_tit_by_name.get(t.name, {}).get("weekly") for t in live_tit) or \
        any(not prev_cal_by_name.get(t.name, {}).get("weekly") for t in live_cal) or \
        any("matchups" not in prev_tit_by_name.get(t.name, {}) for t in live_tit) or \
        any("matchups" not in prev_cal_by_name.get(t.name, {}) for t in live_cal)
    do_full_refresh = args.force or any_total_changed or missing_history

    if not do_full_refresh:
        warnings.append(
            "No team's point total changed and every team already has history on file — skipping the "
            "expensive full team-history refetch (pass --force to override). playerStats and tracked "
            "players' scorecards were still refreshed below."
        )
        data["standings"]["callaway"] = [[t.name, t.total_points] for t in live_cal]
        data["standings"]["titleist"] = [[t.name, t.total_points] for t in live_tit]
        for t in live_cal:
            if t.name in prev_cal_by_name:
                prev_cal_by_name[t.name]["rank"], prev_cal_by_name[t.name]["total"] = t.rank, t.total_points
        for t in live_tit:
            if t.name in prev_tit_by_name:
                prev_tit_by_name[t.name]["rank"], prev_tit_by_name[t.name]["total"] = t.rank, t.total_points
        data["teams"] = [prev_cal_by_name[t.name] for t in live_cal if t.name in prev_cal_by_name]
        data["titleistTeams"] = [prev_tit_by_name[t.name] for t in live_tit if t.name in prev_tit_by_name]
        data["callawayWeekly"] = {t["name"]: t["weekly"] for t in data["teams"]}
        data["titleistWeekly"] = {t["name"]: t["weekly"] for t in data["titleistTeams"]}
    else:
        cal_rows = fetch_division_history(client, site.league_id, pid, live_cal, cal_teamset, seq, warnings, "Callaway")
        tit_rows = fetch_division_history(client, site.league_id, pid, live_tit, tit_teamset, seq, warnings, "Titleist")

        # meta bookkeeping is derived from the real per-round dates we just fetched, not guessed.
        round_dates = {}
        for row in cal_rows + tit_rows:
            for r in row["rounds"]:
                round_dates.setdefault(r.round_num, r.date)
        latest_round_num = max(round_dates) if round_dates else None
        prev_last_label = prev["meta"]["roundLabels"][-1] if prev["meta"].get("roundLabels") else None
        prev_max_round = int(re.search(r"R(\d+)", prev_last_label).group(1)) if prev_last_label else 1

        if latest_round_num and latest_round_num > prev_max_round:
            meta = data["meta"]
            meta["roundLabels"] = [f"R{n}\n{short_date(round_dates[n])}" for n in sorted(round_dates)]
            meta["throughRound"] = f"Round {latest_round_num} ({full_date_with_weekday(round_dates[latest_round_num])})"
            meta["season"]["playedWeeks"] = len(meta["roundLabels"])
            upcoming = [u for u in prev["meta"].get("upcoming", [])
                        if not (re.search(r"Round\s*(\d+)", u["round"]) and
                                int(re.search(r"Round\s*(\d+)", u["round"]).group(1)) <= latest_round_num)]
            meta["upcoming"] = upcoming
            meta["nextMatch"] = (
                {**upcoming[0], "note": "Pairings not posted yet"} if upcoming else
                {"round": None, "date": None, "note": "No further scheduled rounds on file — add them to meta.upcoming"}
            )
        elif latest_round_num is None:
            warnings.append("Couldn't find any round data on the team history pages — meta left unchanged.")

        def strip(rows):
            return [{"name": r["name"], "rank": r["rank"], "total": r["total"],
                      "weekly": r["weekly"], "matchups": r["matchups"]} for r in rows]

        def latest_round_leaderboard(rows):
            board = []
            for r in rows:
                pts = next((x.points for x in r["rounds"] if x.round_num == latest_round_num), None)
                if pts is not None:
                    board.append([r["name"], pts])
            board.sort(key=lambda x: -x[1])
            return board

        data["teams"] = strip(cal_rows)
        data["callawayWeekly"] = {r["name"]: r["weekly"] for r in cal_rows}
        data["standings"]["callaway"] = [[r["name"], r["total"]] for r in cal_rows]
        data["titleistTeams"] = strip(tit_rows)
        data["titleistWeekly"] = {r["name"]: r["weekly"] for r in tit_rows}
        data["standings"]["titleist"] = [[r["name"], r["total"]] for r in tit_rows]

        if latest_round_num:
            data["latestRound"] = latest_round_leaderboard(cal_rows)
            data["latestRoundTitleist"] = latest_round_leaderboard(tit_rows)

    data.pop("round13", None)  # old per-round-number key name; dashboard now reads "latestRound"

    # ---- roster -> playerStats ----
    roster_url = client.widget_url(site.league_id, "player_stats", site.page_id("player stat"))
    roster = parse_roster(client.get(roster_url, dump_name="roster"))
    data["playerStats"] = sorted(
        ([p.name, p.eagles, p.birdies, p.pars, p.bogeys, p.doubles, p.triples_or_worse] for p in roster),
        key=lambda r: r[0],
    )

    # ---- playerDetail: every Callaway + Titleist team member, full parity ----
    all_team_members = {m for t in live_cal for m in t.members} | {m for t in live_tit for m in t.members}
    tracked = sorted(all_team_members | set(prev.get("playerDetail", {}).keys()) | set(args.add_player))
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

    # ---- meta housekeeping ----
    meta = data["meta"]
    meta["lastUpdated"] = dt.date.today().isoformat()
    extra = len(set(tracked) - all_team_members)
    meta["playerDetailNote"] = (
        f"Full round-by-round scorecards are available for all {len(all_team_members)} Callaway and "
        f"Titleist team-roster players." + (f" Plus {extra} sub/fill-in{'s' if extra != 1 else ''} tracked by request."
                                             if extra else " Subs/fill-ins show season HCP/scoring totals only.")
    )
    tit_lengths = [len(t["weekly"]) for t in data["titleistTeams"]]
    tit_weeks = max(set(tit_lengths), key=tit_lengths.count) if tit_lengths else 0  # mode, not min — a team or two
    short = sum(1 for n in tit_lengths if n < tit_weeks)                            # skipping rounds shouldn't understate everyone else's real history
    meta["titleistAsOf"] = (
        f"As of {meta['lastUpdated']} — full {tit_weeks}-week history, same as Callaway"
        + (f" ({short} team{'s' if short != 1 else ''} with fewer weeks played)" if short else "")
        if tit_weeks else
        f"As of {meta['lastUpdated']} — no weekly history yet"
    )

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
