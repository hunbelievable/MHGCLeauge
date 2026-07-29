"""Parser for the `next_round` (Tee Sheet) widget — who's playing whom for a
round that hasn't happened yet, so there's no team_info page for it.

Each hole's players column lists four names as two consecutive pairs; the
page never labels which pair is which team, but the site always lists a
team's two players next to each other, so cells [0:2] and [2:4] are the two
opposing teams. The page renders every hole twice — once in a desktop row
(class `search_rows hidden-xs`) and again in a mobile-only duplicate row
(class `search_rows visible-xs ...`) with identical content — only the
desktop rows are parsed, or every match would be double-counted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup

_WS_RE = re.compile(r"\s+")
_ROUND_OPTION_RE = re.compile(r"Round\s*(\d+)\s*\(([^)]+)\)")
_ROUND_ID_RE = re.compile(r"[?&]round_id=(\d+)")


@dataclass
class TeeSheetMatch:
    hole: str
    team_a: List[str]
    team_b: List[str]


@dataclass
class TeeSheetRoundOption:
    round_num: int
    date: str
    round_id: str
    selected: bool


def parse_round_panel_options(html: str) -> List[TeeSheetRoundOption]:
    """Parse the round-picker <select> on the Tee Sheet (`next_round`) widget
    into every round it knows about, with the internal round_id each needs
    for a direct fetch (see `fetch_tee_sheet_html`)."""
    soup = BeautifulSoup(html, "lxml")
    select = soup.find("select", attrs={"name": "widget_round_panel_selector"})
    out = []
    if select is None:
        return out
    for opt in select.find_all("option"):
        value = opt.get("value") or ""
        text = opt.get_text(strip=True)
        m = _ROUND_OPTION_RE.search(text)
        rid = _ROUND_ID_RE.search(value)
        if not m or not rid:
            continue
        out.append(TeeSheetRoundOption(
            round_num=int(m.group(1)), date=_WS_RE.sub(" ", m.group(2)).strip(),
            round_id=rid.group(1), selected=opt.has_attr("selected"),
        ))
    return out


def fetch_tee_sheet_html(client, league_id: str, page_id: str, round_id: Optional[str] = None) -> str:
    params = {"round_id": round_id} if round_id else {}
    url = client.widget_url(league_id, "next_round", page_id, **params)
    return client.get(url, dump_name=f"tee_sheet_{round_id or 'default'}")


def parse_tee_sheet(html: str) -> List[TeeSheetMatch]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen_holes = set()
    for tr in soup.find_all("tr", class_="search_rows"):
        classes = tr.get("class") or []
        if "visible-xs" in classes:
            continue  # mobile duplicate of the same holes — skip to avoid double-counting
        tds = tr.find_all("td", recursive=False)
        for i in range(0, len(tds) - 2, 3):
            hole = tds[i + 1].get_text(strip=True)
            if not hole or hole in seen_holes:
                continue
            names = [
                _WS_RE.sub(" ", d.get_text(" ", strip=True)).strip()
                for d in tds[i + 2].find_all("div", class_="players_portrait")
            ]
            names = [n for n in names if n]
            if len(names) >= 4:
                seen_holes.add(hole)
                out.append(TeeSheetMatch(hole=hole, team_a=names[0:2], team_b=names[2:4]))
    return out


def match_teams_to_opponents(matches: List[TeeSheetMatch], team_members: dict) -> dict:
    """Given tee-sheet matches and a {team_name: frozenset(members)} lookup
    (built from the site's own current rosters, both divisions), return
    {team_name: opponent_team_name} for every team that could be matched.
    Skips any hole where a player pair isn't a full exact match for a known
    team's two-person roster (e.g. a sub who isn't reflected in the roster
    snapshot yet) rather than guessing."""
    by_members = {frozenset(v): k for k, v in team_members.items()}
    out = {}
    for m in matches:
        team_a = by_members.get(frozenset(m.team_a))
        team_b = by_members.get(frozenset(m.team_b))
        if team_a and team_b:
            out[team_a] = team_b
            out[team_b] = team_a
    return out
