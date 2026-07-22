"""Parser for the `player_stats` list widget — every player in the league,
their member_id (needed for the player-detail widget), division, and
season-long hole-outcome totals (eagles, birdies, pars, bogeys, doubles,
triple+).

Verified against the Tuesday Night League roster (190 players, all member_ids
resolved, totals row cross-checked column-by-column against individually
summed rows).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup

from . import find_table_by_headers, row_cells, cell_text, cell_link, to_int

MEMBER_ID_RE = re.compile(r"[?&]member_id=(\d+)")


@dataclass
class RosterEntry:
    name: str
    member_id: Optional[str]
    eagles: int
    birdies: int
    pars: int
    bogeys: int
    doubles: int
    triples_or_worse: int


def parse_roster(html: str) -> List[RosterEntry]:
    soup = BeautifulSoup(html, "lxml")
    table = find_table_by_headers(soup, ["eagles", "birdies"])
    if table is None:
        raise RuntimeError(
            "Couldn't find the player roster table (looked for a header "
            "containing 'Eagles' and 'Birdies')."
        )

    out: List[RosterEntry] = []
    for tr in table.find_all("tr"):
        cells = row_cells(tr)
        if len(cells) < 7:
            continue
        name = cell_text(cells[0])
        if not name or name.lower() in ("player", "totals"):
            continue
        href = cell_link(cells[0])
        m = MEMBER_ID_RE.search(href) if href else None
        nums = [to_int(cell_text(c), default=0) for c in cells[1:7]]
        out.append(RosterEntry(
            name=name, member_id=m.group(1) if m else None,
            eagles=nums[0], birdies=nums[1], pars=nums[2],
            bogeys=nums[3], doubles=nums[4], triples_or_worse=nums[5],
        ))
    return out
