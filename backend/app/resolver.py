from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz


logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.shiksha.com/search?q={query}"
SLUG_ID_PATTERN = re.compile(r"/university/([a-z0-9\-]+-(\d+))(?:[/?#]|$)")
CACHE_TTL = timedelta(days=7)


@dataclass
class InstituteResult:
    slug: str
    primary_id: str
    url: str


class DiskTTLCache:
    def __init__(self, file_path: Path, ttl: timedelta = CACHE_TTL):
        self.file_path = file_path
        self.ttl = ttl
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict | None:
        data = self._load()
        entry = data.get(key)
        if not entry:
            return None
        ts = datetime.fromisoformat(entry["timestamp"])
        if datetime.now(timezone.utc) - ts > self.ttl:
            return None
        return entry["value"]

    def set(self, key: str, value: dict) -> None:
        data = self._load()
        data[key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": value,
        }
        self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> dict:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}


class InstituteResolver:
    def __init__(self, session: requests.Session, cache_dir: Path = Path("data/.cache")):
        self.session = session
        self.cache = DiskTTLCache(cache_dir / "institute_cache.json")

    def resolve(self, college_name: str) -> InstituteResult:
        cache_key = self._cache_key(college_name)
        cached = self.cache.get(cache_key)
        if cached:
            result = InstituteResult(**cached)
            logger.info("Resolver cache hit for '%s' -> %s", college_name, result.slug)
            return result

        search_url = SEARCH_URL.format(query=quote(college_name))
        response = self.session.get(search_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        candidates: list[tuple[float, str, str]] = []
        for anchor in soup.select("a[href*='/university/']"):
            href = anchor.get("href", "")
            matched = SLUG_ID_PATTERN.search(href)
            if not matched:
                continue
            slug, pid = matched.group(1), matched.group(2)
            text = anchor.get_text(" ", strip=True)
            score = float(fuzz.token_set_ratio(college_name, text))
            candidates.append((score, slug, pid))

        if not candidates:
            raise ValueError(f"No institute found for '{college_name}'")

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, slug, primary_id = candidates[0]
        url = f"https://www.shiksha.com/university/{slug}/"
        canonical_slug, canonical_id = self._canonical_fallback(url)

        result = InstituteResult(
            slug=canonical_slug or slug,
            primary_id=canonical_id or primary_id,
            url=f"https://www.shiksha.com/university/{canonical_slug or slug}/",
        )
        self.cache.set(cache_key, asdict(result))
        logger.info("Resolved institute '%s' -> slug=%s, primary_id=%s", college_name, result.slug, result.primary_id)
        return result

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

    def _cache_key(self, college_name: str) -> str:
        return hashlib.sha256(college_name.strip().lower().encode("utf-8")).hexdigest()
