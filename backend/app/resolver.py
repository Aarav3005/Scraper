from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


SEARCH_URL = "https://www.shiksha.com/search?q={query}"
SLUG_ID_PATTERN = re.compile(r"/university/([a-z0-9\-]+-(\d+))(?:[/?#]|$)")


@dataclass
class InstituteResult:
    slug: str
    primary_id: str
    url: str


class InstituteResolver:
    def __init__(self, session: requests.Session):
        self.session = session

    def resolve(self, college_name: str) -> InstituteResult:
        search_url = SEARCH_URL.format(query=quote(college_name))
        response = self.session.get(search_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        candidates: list[tuple[str, str]] = []
        for anchor in soup.select("a[href*='/university/']"):
            href = anchor.get("href", "")
            matched = SLUG_ID_PATTERN.search(href)
            if matched:
                slug, pid = matched.group(1), matched.group(2)
                candidates.append((slug, pid))

        if not candidates:
            raise ValueError(f"No institute found for '{college_name}'")

        slug, primary_id = candidates[0]
        url = f"https://www.shiksha.com/university/{slug}/"
        canonical_slug, canonical_id = self._canonical_fallback(url)
        return InstituteResult(
            slug=canonical_slug or slug,
            primary_id=canonical_id or primary_id,
            url=f"https://www.shiksha.com/university/{canonical_slug or slug}/",
        )

    def _canonical_fallback(self, url: str) -> tuple[str | None, str | None]:
        response = self.session.get(url, timeout=30)
        if response.status_code >= 400:
            return None, None
        soup = BeautifulSoup(response.text, "html.parser")
        canonical = soup.find("link", rel="canonical")
        if not canonical or not canonical.get("href"):
            return None, None
        matched = SLUG_ID_PATTERN.search(canonical["href"])
        if not matched:
            return None, None
        return matched.group(1), matched.group(2)
