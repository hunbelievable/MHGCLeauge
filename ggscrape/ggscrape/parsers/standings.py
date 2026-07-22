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
