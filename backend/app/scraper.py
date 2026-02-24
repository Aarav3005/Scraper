from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)
CACHE_TTL = timedelta(days=7)


class ScraperEngine:
    def __init__(self, session: requests.Session, data_root: Path):
        self.session = session
        self.data_root = data_root
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
                "Referer": "https://www.google.com/",
            }
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _fetch(self, url: str) -> str:
        time.sleep(1)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def scrape_all(self, slug: str, course_id: str) -> tuple[Path, Dict[str, str]]:
        base = f"https://www.shiksha.com/university/{slug}"
        urls = {
            "overview": f"{base}/",
            "fees": f"{base}/fees",
            "admission": f"{base}/admission",
            "placement": f"{base}/placement",
            "cutoff": f"{base}/cutoff",
            "infrastructure": f"{base}/infrastructure",
        }
        storage = self.data_root / slug
        storage.mkdir(parents=True, exist_ok=True)

        page_map: Dict[str, str] = {}
        for key, url in urls.items():
            out = storage / f"{key}.html"
            html = self._get_or_fetch(url, out)
            if html is None:
                continue
            page_map[key] = str(out)

        for review_page in range(1, 6):
            review_url = self._build_review_url(base, course_id, review_page)
            out = storage / f"reviews_page_{review_page}.html"
            html = self._get_or_fetch(review_url, out)
            if html is None:
                if review_page == 1:
                    logger.warning("Failed to fetch first review page for slug=%s course=%s", slug, course_id)
                break
            soup = BeautifulSoup(html, "html.parser")
            cards = self._review_cards(soup)
            if review_page > 1 and not cards:
                break
            page_map[f"reviews_page_{review_page}"] = str(out)

        return storage, page_map

    def _get_or_fetch(self, url: str, out: Path) -> str | None:
        if self._is_cache_valid(out):
            logger.info("Using cached page: %s", out)
            return out.read_text(encoding="utf-8")
        try:
            html = self._fetch(url)
            out.write_text(html, encoding="utf-8")
            logger.info("Fetched page: %s", url)
            return html
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch %s: %s", url, exc)
            if out.exists():
                return out.read_text(encoding="utf-8")
            return None

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds <= CACHE_TTL.total_seconds()

    def _build_review_url(self, base: str, course_id: str, page: int) -> str:
        suffix = "/reviews" if page == 1 else f"/reviews-{page}"
        return f"{base}{suffix}?course={course_id}&sort_by=relevance"

    def _review_cards(self, soup: BeautifulSoup):
        return soup.select("[data-review-id], .review-card, .user-review")
