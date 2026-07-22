"""Parser for the `customized_team_standings` widget — team rank, points,
and roster, plus the team_info link/id needed to pull a team's round-by-round
history later.

Verified against the Tuesday Night League Callaway standings page (28 teams,
computed total matched the site's own grand total to the penny). The same
column layout (Number, Rank, Teams, Team Points, Team Participation Points,
Total Points, Team Members) is a Golf Genius template default, not something
Miracle Hill customized, so this should hold for other clubs on the same
template.

By default, this widget only renders whichever division/teamset the site
considers "current" (Callaway for this league) — other divisions (e.g.
Titleist) live behind a "Divisions/Teams" <select> on the SAME page, which
submits to a *different* widget path (`team_standings`, not
`customized_team_standings`) with `teamset` + `sequence` params holding
internal numeric IDs, not anything guessable. `fetch_division_standings`
discovers those IDs from the page's own <select> options (see
`parse_division_options`) rather than hardcoding them, so it should work for
any division on any club running this template.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from . import find_table_by_headers, row_cells, cell_text, cell_link, to_float

TEAM_ID_RE = re.compile(r"[?&]team=(\d+)")


@dataclass
class TeamStanding:
    rank: int
    name: str
    team_points: float
    total_points: float
    members: List[str]
    team_id: Optional[str]


def parse_standings(html: str) -> List[TeamStanding]:
    soup = BeautifulSoup(html, "lxml")
    table = find_table_by_headers(soup, ["rank", "team points"])
    if table is None:
        raise RuntimeError(
            "Couldn't find the standings table (looked for a header row "
            "containing 'Rank' and 'Team Points'). The page layout may have "
            "changed — rerun with --dump-html and compare."
        )

    rows = table.find_all("tr")
    out: List[TeamStanding] = []
    for tr in rows:
        cells = row_cells(tr)
        if len(cells) < 6:
            continue
        texts = [cell_text(c) for c in cells]
        if texts[0].lower() in ("number", "") and texts[1].lower() == "rank":
            continue  # header row
        if texts[0].lower().startswith("total"):
            continue  # footer totals row
        rank = None
        for t in texts[:2]:
            try:
                rank = int(t)
                break
            except ValueError:
                continue
        if rank is None:
            continue

        team_cell = cells[2]
        name = cell_text(team_cell)
        href = cell_link(team_cell)
        team_id_match = TEAM_ID_RE.search(href) if href else None

        team_points = to_float(texts[3], default=0.0)
        total_points = to_float(texts[5], default=team_points)
        members_raw = texts[6] if len(texts) > 6 else name
        members = [m.strip() for m in re.split(r"\s*\|\s*", members_raw) if m.strip()]

        out.append(TeamStanding(
            rank=rank, name=name, team_points=team_points,
            total_points=total_points, members=members or [name],
            team_id=team_id_match.group(1) if team_id_match else None,
        ))

    out.sort(key=lambda t: t.rank)
    return out


@dataclass
class DivisionOptions:
    teamsets: Dict[str, str] = field(default_factory=dict)      # label -> teamset id
    sequences: Dict[str, str] = field(default_factory=dict)     # label -> sequence id
    default_sequence: Optional[str] = None                      # currently-selected sequence id

    def teamset_id(self, *label_fragments: str) -> str:
        for label, tid in self.teamsets.items():
            low = label.lower()
            if all(frag.lower() in low for frag in label_fragments):
                return tid
        raise KeyError(f"No division matched {label_fragments!r}. Available: {sorted(self.teamsets)}")


def parse_division_options(html: str) -> DivisionOptions:
    """Parse the 'Divisions/Teams' and 'Series' <select> options off the
    customized_team_standings page (see module docstring)."""
    soup = BeautifulSoup(html, "lxml")
    opts = DivisionOptions()
    teamset_select = soup.find("select", attrs={"name": "teamset"})
    if teamset_select:
        for opt in teamset_select.find_all("option"):
            value = (opt.get("value") or "").strip()
            label = opt.get_text(strip=True)
            if value and label:
                opts.teamsets[label] = value
    sequence_select = soup.find("select", attrs={"name": "sequence"})
    if sequence_select:
        for opt in sequence_select.find_all("option"):
            value = (opt.get("value") or "").strip()
            label = opt.get_text(strip=True)
            if not value or not label:
                continue
            opts.sequences[label] = value
            if opt.has_attr("selected"):
                opts.default_sequence = value
    return opts


def fetch_division_standings(client, league_id: str, page_id: str, *division_label: str) -> List[TeamStanding]:
    """Fetch team standings for a specific division (e.g. 'Titleist') by
    discovering its teamset id from the page's own dropdown rather than a
    hardcoded value — those ids are internal to each Golf Genius site."""
    base_url = client.widget_url(league_id, "customized_team_standings", page_id)
    base_html = client.get(base_url, dump_name="standings_form")
    opts = parse_division_options(base_html)
    teamset_id = opts.teamset_id(*division_label)
    sequence_id = opts.default_sequence or next(iter(opts.sequences.values()), None)

    params = {"teamset": teamset_id, "commit": "Go"}
    if sequence_id:
        params["sequence"] = sequence_id
    url = client.widget_url(league_id, "team_standings", page_id, **params)
    name = "standings_" + re.sub(r"[^a-z0-9]+", "_", division_label[0].lower()) if division_label else "standings_division"
    html = client.get(url, dump_name=name)
    return parse_standings(html)


@dataclass
class RoundResult:
    round_num: int
    date: str
    points: float


@dataclass
class Pairing:
    player: str
    opponent: str
    us: float
    them: float


@dataclass
class MatchResult:
    round_num: int
    date: str
    opponent: str
    us: float
    them: float
    pairings: List[Pairing]


def _team_info_blocks(html: str):
    """Yield (round_num, date, points, nested_match_table_or_None) for each
    round on a team_info page. The page interleaves a 4-cell summary row per
    round with a single-cell row holding that round's nested match-detail
    table (opponent, A-vs-A/B-vs-B pairings) — see module docstring."""
    soup = BeautifulSoup(html, "lxml")
    outer = find_table_by_headers(soup, ["round date", "points"])
    if outer is None:
        raise RuntimeError(
            "Couldn't find the team round-history table (looked for a header "
            "row containing 'Round Date' and 'Points'). The page layout may "
            "have changed — rerun with --dump-html and compare."
        )
    tbody = outer.find("tbody") or outer
    pending = None
    for tr in tbody.find_all("tr", recursive=False):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) >= 4:
            texts = [cell_text(c) for c in cells]
            m = re.search(r"Round\s*(\d+)", texts[2])
            pts = to_float(texts[3])
            if m and pts is not None:
                pending = (int(m.group(1)), texts[1], pts)
            else:
                pending = None
            continue
        if pending is None:
            continue
        yield pending[0], pending[1], pending[2], tr.find("table")
        pending = None


def parse_team_rounds(html: str) -> List[RoundResult]:
    """Parse a team_info page's round-by-round points — the league's own
    authoritative history for this team, not a diff-based reconstruction."""
    out = [RoundResult(round_num=rn, date=date, points=pts)
           for rn, date, pts, _ in _team_info_blocks(html)]
    out.sort(key=lambda r: r.round_num)
    return out


def parse_team_matchups(html: str) -> List[MatchResult]:
    """Parse full per-round opponent/result detail for one team: opponent
    name, team-level us/them points, and both individual A-vs-A/B-vs-B
    pairings — whoever actually played that round, subs included, with no
    single "watched" player assumed. Works identically for any team, so
    every team gets the same detail (not just one favorite)."""
    out = []
    for round_num, date, us_pts, nested in _team_info_blocks(html):
        if nested is None:
            continue
        nrows = nested.find_all("tr")
        if len(nrows) < 3:
            continue
        header = [cell_text(c) for c in nrows[0].find_all(["td", "th"])]
        if len(header) < 4:
            continue
        team_a, team_b = header[1], header[3]

        pairings, us_names = [], []
        for r in nrows[1:3]:
            rc = [cell_text(c) for c in r.find_all(["td", "th"])]
            if len(rc) < 5:
                continue
            us_names.append(rc[1])
            pairings.append(Pairing(player=rc[1], opponent=rc[3], us=to_float(rc[0]), them=to_float(rc[4])))

        opponent = team_b if any(n in team_a for n in us_names) else team_a
        them_pts = round(27 - us_pts, 2)  # league format: 27 pts split between the two teams each round

        out.append(MatchResult(round_num=round_num, date=date, opponent=opponent.strip(),
                                us=us_pts, them=them_pts, pairings=pairings))
    out.sort(key=lambda r: r.round_num)
    return out


def fetch_team_history(client, league_id: str, page_id: str, team_id: str, teamset_id: str,
                        sequence_id: Optional[str] = None):
    """Fetch one team's full round-by-round history (points + full match
    detail) in a single request. Returns (rounds, matchups)."""
    params = {"team": team_id, "teamset": teamset_id}
    if sequence_id:
        params["sequence"] = sequence_id
    url = client.widget_url(league_id, "team_standings/team_info", page_id, **params)
    html = client.get(url, dump_name=f"team_info_{team_id}")
    return parse_team_rounds(html), parse_team_matchups(html)
