import re
from bs4 import BeautifulSoup, Tag
from typing import List, Optional

_WS_RE = re.compile(r"\s+")


def _norm_ws(s: str) -> str:
    """Collapse any run of whitespace to a single space. get_text(' ', strip=True)
    only strips the ends — it doesn't collapse whitespace *within* the result,
    so a cell built from multiple text nodes (e.g. two <a> tags around a
    ' + ' separator) can come back with doubled-up spaces."""
    return _WS_RE.sub(" ", s).strip()


def find_table_by_headers(soup: BeautifulSoup, must_contain: List[str]) -> Optional[Tag]:
    """Return the first <table> whose header row contains all of `must_contain`
    (case-insensitive substring match), searching table headers wherever they
    live (<th>, or a bold/header-styled first <tr> of <td>s — Golf Genius'
    widgets aren't consistent about using real <th> tags)."""
    for table in soup.find_all("table"):
        header_cells = table.find_all("th")
        if not header_cells:
            first_row = table.find("tr")
            header_cells = first_row.find_all(["td", "th"]) if first_row else []
        header_text = " | ".join(_norm_ws(c.get_text(" ", strip=True)) for c in header_cells).lower()
        if all(frag.lower() in header_text for frag in must_contain):
            return table
    return None


def row_cells(tr: Tag) -> List[Tag]:
    return tr.find_all(["td", "th"])


def cell_text(cell: Tag) -> str:
    return _norm_ws(cell.get_text(" ", strip=True))


def cell_link(cell: Tag) -> Optional[str]:
    a = cell.find("a", href=True)
    return a["href"] if a else None


def to_float(s: str, default=None):
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return default


def to_int(s: str, default=None):
    f = to_float(s, default=None)
    return int(f) if f is not None else default
