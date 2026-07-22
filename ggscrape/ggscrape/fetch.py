"""Thin HTTP layer for talking to a Golf Genius 'league portal' site.

These sites (e.g. https://mhgc-tuesdaynightleague.golfgenius.com) publish
standings, rosters, and player scorecards on public, unauthenticated pages
meant to be embedded as widgets. This module just fetches raw HTML; all
interpretation happens in ggscrape.parsers.
"""
from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("ggscrape")

DEFAULT_HEADERS = {
    "User-Agent": "ggscrape/0.1 (+https://github.com/) polite league-portal reader",
}


class Client:
    def __init__(self, base_url: str, delay: float = 0.6, timeout: int = 20,
                 dump_dir: Optional[str] = None):
        """
        base_url: the site root, e.g. https://mhgc-tuesdaynightleague.golfgenius.com
        delay: seconds to sleep between requests (be polite, this is someone's
               small club's site, not a CDN).
        dump_dir: if set, every fetched page is also saved here as raw HTML.
                  Extremely useful for debugging a parser that doesn't match
                  — send the dumped file back and it can be fixed against the
                  real markup instead of guessing.
        """
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.dump_dir = Path(dump_dir) if dump_dir else None
        if self.dump_dir:
            self.dump_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._last_request = 0.0

    def get(self, url: str, dump_name: Optional[str] = None, max_retries: int = 4) -> str:
        # Simple rate limit — don't hammer someone's league site.
        for attempt in range(max_retries):
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            resp = self.session.get(url, timeout=self.timeout)
            self._last_request = time.monotonic()
            if resp.status_code == 429 and attempt < max_retries - 1:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.strip().isdigit() else self.delay * (3 ** (attempt + 1))
                logger.warning("429 from %s — backing off %.1fs (attempt %d/%d)", url, wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        html = resp.text
        if self.dump_dir:
            name = dump_name or url.rsplit("/", 1)[-1].split("?")[0] or "page"
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
            (self.dump_dir / f"{safe}.html").write_text(html, encoding="utf-8")
        return html

    def widget_url(self, league_id: str, widget: str, page_id: str, **params) -> str:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}/leagues/{league_id}/widgets/{widget}?page_id={page_id}&shared=false"
        if qs:
            url += "&" + qs
        return url
