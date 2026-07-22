"""Parser for the `customized_team_standings` widget — team rank, points,
and roster, plus the team_info link/id needed to pull a team's round-by-round
history later.

Verified against the Tuesday Night League Callaway standings page (28 teams,
computed total matched the site's own grand total to the penny). The same
column layout (Number, Rank, Teams, Team Points, Team Participation Points,
Total Points, Team Members) is a Golf Genius template default, not something
Miracle Hill customized, so this should hold for other clubs on the same
template.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

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
