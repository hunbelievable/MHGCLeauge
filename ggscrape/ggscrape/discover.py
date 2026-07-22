"""Figure out a league portal's league_id and the page_id for each section,
by reading its own homepage nav instead of hardcoding IDs per club.

Every Golf Genius league-portal site we've seen exposes its nav as a set of
`sections`, each containing one or more `pages`. The homepage HTML embeds a
widget src somewhere in the form:

    https://<host>/leagues/<league_id>/widgets/collages?page_id=<id>...

and the visible nav links point at:

    https://<host>/pages/<page_id>

This module extracts both without assuming any specific page_id in advance,
so it should work for any club running the same Golf Genius template, not
just Miracle Hill's Tuesday Night League.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict

from bs4 import BeautifulSoup

from .fetch import Client

LEAGUE_ID_RE = re.compile(r"/leagues/(\d+)/widgets/")
PAGE_LINK_RE = re.compile(r"/pages/(\d+)")


@dataclass
class SiteMap:
    base_url: str
    league_id: str
    pages: Dict[str, str] = field(default_factory=dict)  # label -> page_id

    def page_id(self, *label_fragments: str) -> str:
        """Look up a page_id by fuzzy label match, e.g. page_id('standings')."""
        for label, pid in self.pages.items():
            low = label.lower()
            if all(frag.lower() in low for frag in label_fragments):
                return pid
        raise KeyError(
            f"No nav page matched {label_fragments!r}. Available labels: "
            f"{sorted(self.pages)}"
        )


def discover(client: Client) -> SiteMap:
    html = client.get(client.base_url + "/", dump_name="homepage")

    league_id_match = LEAGUE_ID_RE.search(html)
    if not league_id_match:
        raise RuntimeError(
            "Could not find a /leagues/<id>/widgets/ reference on the "
            "homepage — is this actually a Golf Genius league-portal site?"
        )
    league_id = league_id_match.group(1)

    soup = BeautifulSoup(html, "lxml")
    pages: Dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        m = PAGE_LINK_RE.search(a["href"])
        if not m:
            continue
        label = a.get_text(strip=True)
        if not label:
            continue
        pages[label] = m.group(1)

    return SiteMap(base_url=client.base_url, league_id=league_id, pages=pages)
