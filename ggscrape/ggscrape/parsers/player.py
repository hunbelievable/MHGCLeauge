"""Parser for the `player_stats/member_info` widget — one player's HCP,
low gross/net, round-by-round scoring mix, and full 18-hole scorecards with
course par and league averages.

Status: this is the most structurally complex page ggscrape reads (nested,
collapsible tee-block tables) and the one most worth double-checking after
your first live run. The header stats and round-by-round scoring-mix table
were verified byte-for-byte against a sample player (name, low gross, low
net, HCP index, and every round's par/bogey/double/triple count matched the
site's own reported totals exactly). The hole-by-hole scorecard grid uses a
more general heuristic (see `_real_half` below) that wasn't checked against
raw HTML directly — run with `Client(..., dump_dir=...)` and inspect the
saved page if a player's scorecard looks off, and send it back to get this
patched against real markup instead of another guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from . import find_table_by_headers, row_cells, cell_text, to_float, to_int

DATE_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s*(\d{4})")
MONTH = {m[:3]: i + 1 for i, m in enumerate(
    ["January","February","March","April","May","June","July",
     "August","September","October","November","December"])}


@dataclass
class RoundScoring:
    round_num: int
    date: str
    eagles: int
    birdies: int
    pars: int
    bogeys: int
    doubles: int
    triples_or_worse: int

    @property
    def dist(self):
        return [self.eagles, self.birdies, self.pars, self.bogeys, self.doubles, self.triples_or_worse]


@dataclass
class NineDetail:
    par: List[int]
    league_avg: List[float]
    my_avg: List[float]


@dataclass
class HoleRound:
    round_num: int
    date: str
    nine: str  # 'Front' or 'Back'
    holes: List[int]


@dataclass
class PlayerDetail:
    name: str
    hcp_index: Optional[float]
    low_gross: Optional[float]
    low_net: Optional[float]
    rounds_played: Optional[int]
    scoring: List[RoundScoring] = field(default_factory=list)
    hole_rounds: List[HoleRound] = field(default_factory=list)
    course: Dict[str, NineDetail] = field(default_factory=dict)  # 'front'/'back'


def _header_stat(soup: BeautifulSoup, label: str) -> Optional[float]:
    text = soup.get_text("\n")
    m = re.search(re.escape(label) + r"[^\d\-]*([\-\d.]+)", text)
    return to_float(m.group(1)) if m else None


def _iter_hole_blocks(table: Tag):
    """Split a scorecard table into per-nine blocks.

    Golf Genius stacks a Back-9 block directly under a Front-9 block (or vice
    versa) inside the SAME <table>, each repeating its own 'Hole' header row
    and the full set of labelled rows (Course Par, League Average, per-date
    rows, ...). Treating the whole table as one block and keying rows by
    label (as the old code did) makes the second block's rows silently
    overwrite the first block's same-named rows, which corrupts both nines.
    """
    current: List[Tag] = []
    for tr in table.find_all("tr"):
        cells = row_cells(tr)
        if not cells:
            continue
        label = cell_text(cells[0])
        vals = [cell_text(c) for c in cells[1:]]
        if label.lower() == "hole" and len(vals) >= 18:
            if current:
                yield current
            current = [tr]
        elif current:
            current.append(tr)
    if current:
        yield current


def _real_half(row_vals: List[str]) -> Optional[slice]:
    """Given 18 cell values for a course-info row (Course Par etc.), figure out
    whether holes 1-9 or holes 10-18 hold the real data (the other half is
    blank on tee-block tables, since each table only covers one nine)."""
    front_has_data = any(v.strip() not in ("", "-") for v in row_vals[:9])
    back_has_data = any(v.strip() not in ("", "-") for v in row_vals[9:18])
    if front_has_data and not back_has_data:
        return slice(0, 9)
    if back_has_data and not front_has_data:
        return slice(9, 18)
    return None


def parse_player(html: str) -> PlayerDetail:
    soup = BeautifulSoup(html, "lxml")

    name_el = soup.find(["h1", "h2", "h3", "h4"])
    name = name_el.get_text(strip=True) if name_el else "Unknown"

    hcp = _header_stat(soup, "Handicap Index")
    low_gross = _header_stat(soup, "Low Gross")
    low_net = _header_stat(soup, "Low Net")
    rounds_played = _header_stat(soup, "Rounds Played")

    detail = PlayerDetail(
        name=name, hcp_index=hcp, low_gross=low_gross,
        low_net=low_net, rounds_played=int(rounds_played) if rounds_played is not None else None,
    )

    # ---- round-by-round scoring mix table ----
    scoring_table = find_table_by_headers(soup, ["eagles", "birdies", "bogeys"])
    round_num_by_date: Dict[tuple, int] = {}
    if scoring_table is not None:
        for tr in scoring_table.find_all("tr"):
            cells = row_cells(tr)
            texts = [cell_text(c) for c in cells]
            if len(texts) < 7:
                continue
            date_m = DATE_RE.search(texts[0])
            round_m = re.search(r"Round\s*(\d+)", " ".join(texts))
            if not date_m or not round_m:
                continue
            mon = date_m.group(1)[:3]
            if mon not in MONTH:
                continue
            day, year = int(date_m.group(2)), int(date_m.group(3))
            rnd = int(round_m.group(1))
            nums = [to_int(t, default=None) for t in texts[-6:]]
            if any(n is None for n in nums):
                continue
            detail.scoring.append(RoundScoring(rnd, f"{date_m.group(1)} {day}, {year}", *nums))
            round_num_by_date[(MONTH[mon], day)] = rnd

    # ---- hole-by-hole tee-block tables ----
    for table in soup.find_all("table"):
        for block in _iter_hole_blocks(table):
            rows = {}
            for tr in block:
                cells = row_cells(tr)
                label = cell_text(cells[0])
                if label.lower() == "hole":
                    continue
                rows[label] = [cell_text(c) for c in cells[1:]]

            if "Course Par" not in rows:
                continue  # not a tee-block

            half = _real_half(rows["Course Par"])
            if half is None:
                continue
            nine = "Front" if half.start == 0 else "Back"

            par = [to_int(v, default=0) for v in rows["Course Par"][half]]
            league_avg = [to_float(v, default=0.0) for v in rows.get("League Average", [""] * 18)[half]]
            my_avg = [to_float(v, default=0.0) for v in rows.get("Player Average", [""] * 18)[half]]
            detail.course[nine.lower()] = NineDetail(par=par, league_avg=league_avg, my_avg=my_avg)

            for label, vals in rows.items():
                date_m = DATE_RE.match(label)
                if not date_m:
                    continue
                mon = date_m.group(1)[:3]
                if mon not in MONTH:
                    continue
                key = (MONTH[mon], int(date_m.group(2)))
                rnd = round_num_by_date.get(key)
                if rnd is None:
                    continue
                sub = vals[half]
                if len(sub) != 9 or any(v.strip() in ("", "-") for v in sub):
                    continue
                holes = [int(float(v)) for v in sub]
                detail.hole_rounds.append(HoleRound(
                    round_num=rnd, date=f"{date_m.group(1)} {int(date_m.group(2))}, {date_m.group(3)}",
                    nine=nine, holes=holes,
                ))

    detail.hole_rounds.sort(key=lambda r: r.round_num)
    return detail
