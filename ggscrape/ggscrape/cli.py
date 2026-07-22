from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from .fetch import Client
from .discover import discover
from .parsers.standings import parse_standings
from .parsers.roster import parse_roster
from .parsers.player import parse_player


def _to_jsonable(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def _client(args) -> Client:
    return Client(args.base_url, delay=args.delay, dump_dir=args.dump_html)


def cmd_discover(args):
    c = _client(args)
    site = discover(c)
    print(json.dumps({"league_id": site.league_id, "pages": site.pages}, indent=2))


def cmd_standings(args):
    c = _client(args)
    site = discover(c)
    page_id = args.page_id or site.page_id("standing")
    url = c.widget_url(site.league_id, "customized_team_standings", page_id)
    html = c.get(url, dump_name="standings")
    teams = parse_standings(html)
    print(json.dumps([_to_jsonable(t) for t in teams], indent=2))


def cmd_roster(args):
    c = _client(args)
    site = discover(c)
    page_id = args.page_id or site.page_id("player stat")
    url = c.widget_url(site.league_id, "player_stats", page_id)
    html = c.get(url, dump_name="roster")
    players = parse_roster(html)
    print(json.dumps([_to_jsonable(p) for p in players], indent=2))


def cmd_player(args):
    c = _client(args)
    site = discover(c)
    page_id = args.page_id or site.page_id("player stat")
    member_id = args.member_id
    if member_id is None:
        if not args.name:
            print("Need --member-id or --name", file=sys.stderr)
            sys.exit(1)
        url = c.widget_url(site.league_id, "player_stats", page_id)
        html = c.get(url, dump_name="roster")
        players = parse_roster(html)
        matches = [p for p in players if args.name.lower() in p.name.lower()]
        if not matches:
            print(f"No player matching {args.name!r}", file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            print("Multiple matches, pick one:", file=sys.stderr)
            for m in matches:
                print(f"  {m.name} (--member-id {m.member_id})", file=sys.stderr)
            sys.exit(1)
        member_id = matches[0].member_id

    url = c.widget_url(site.league_id, "player_stats/member_info", page_id, member_id=member_id)
    html = c.get(url, dump_name=f"player_{member_id}")
    detail = parse_player(html)
    print(json.dumps(_to_jsonable(detail), indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="ggscrape",
        description="Read standings/roster/player data from a Golf Genius league-portal site.",
    )
    ap.add_argument("base_url", help="Site root, e.g. https://mhgc-tuesdaynightleague.golfgenius.com")
    ap.add_argument("--delay", type=float, default=0.6, help="Seconds between requests (default 0.6)")
    ap.add_argument("--dump-html", metavar="DIR", default=None,
                     help="Save every fetched page's raw HTML to this directory (great for debugging)")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("discover", help="List the site's league_id and nav page_ids").set_defaults(func=cmd_discover)

    p_st = sub.add_parser("standings", help="Team standings (all divisions)")
    p_st.add_argument("--page-id", default=None, help="Override auto-discovered standings page_id")
    p_st.set_defaults(func=cmd_standings)

    p_ro = sub.add_parser("roster", help="Every player: member_id, division-relevant stats")
    p_ro.add_argument("--page-id", default=None)
    p_ro.set_defaults(func=cmd_roster)

    p_pl = sub.add_parser("player", help="One player's full detail")
    p_pl.add_argument("--page-id", default=None)
    p_pl.add_argument("--member-id", default=None)
    p_pl.add_argument("--name", default=None, help="Look up member_id by (partial) name via the roster page")
    p_pl.set_defaults(func=cmd_player)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
