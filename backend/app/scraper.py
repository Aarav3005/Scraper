from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed


class ScraperEngine:
    def __init__(self, session: requests.Session, data_root: Path):
        self.session = session
        self.data_root = data_root

    @retry(wait=wait_fixed(1), stop=stop_after_attempt(3))
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
            html = self._fetch(url)
            out = storage / f"{key}.html"
            out.write_text(html, encoding="utf-8")
            page_map[key] = str(out)

        review_page = 1
        while review_page <= 5:
            review_url = f"{base}/reviews?course={course_id}&sort_by=relevance&page={review_page}"
            html = self._fetch(review_url)
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("[class*='review']")
            if review_page > 1 and not cards:
                break
            out = storage / f"reviews_page_{review_page}.html"
            out.write_text(html, encoding="utf-8")
            page_map[f"reviews_page_{review_page}"] = str(out)
            review_page += 1

        return storage, page_map
