from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from string import punctuation
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from .resolver import DiskTTLCache


logger = logging.getLogger(__name__)


@dataclass
class CourseMatch:
    course_id: str
    course_name: str
    score: float


class CourseResolver:
    def __init__(self, session: requests.Session, cache_dir: Path = Path("data/.cache")):
        self.session = session
        self.cache = DiskTTLCache(cache_dir / "course_cache.json")

    def resolve(self, institute_slug: str, course_name: str) -> CourseMatch:
        cache_key = self._cache_key(institute_slug, course_name)
        cached = self.cache.get(cache_key)
        if cached:
            match = CourseMatch(**cached)
            logger.info("Course cache hit for %s/%s -> %s", institute_slug, course_name, match.course_id)
            return match

        base_url = f"https://www.shiksha.com/university/{institute_slug}/reviews"
        page = self.session.get(base_url, timeout=30)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        candidates: dict[str, str] = {}
        for cid, cname in self._extract_course_infos(soup):
            candidates[cid] = cname
        if not candidates:
            for cid, cname in self._extract_filter_response(soup):
                candidates[cid] = cname
        if not candidates:
            for cid, cname in self._extract_dropdown(soup):
                candidates[cid] = cname

        if not candidates:
            raise ValueError(f"No course IDs discovered for institute '{institute_slug}'")

        query_norm = self._normalize(course_name)
        ranked = sorted(
            [
                CourseMatch(
                    course_id=cid,
                    course_name=cname,
                    score=float(fuzz.token_set_ratio(query_norm, self._normalize(cname))),
                )
                for cid, cname in candidates.items()
            ],
            key=lambda x: x.score,
            reverse=True,
        )

        for match in ranked:
            if self._validate_match(institute_slug, match.course_id, course_name):
                self.cache.set(cache_key, asdict(match))
                logger.info(
                    "Resolved course for slug=%s, query='%s' -> course_id=%s (%s, score=%.2f)",
                    institute_slug,
                    course_name,
                    match.course_id,
                    match.course_name,
                    match.score,
                )
                return match

        raise ValueError(f"Could not validate course match for '{course_name}'")

    def _extract_course_infos(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for script in soup.find_all("script"):
            content = script.string or script.text or ""
            if "courseInfos" not in content:
                continue
            obj_text = self._extract_balanced_object(content, "courseInfos")
            if not obj_text:
                continue
            try:
                parsed = json.loads(obj_text)
            except json.JSONDecodeError:
                continue
            for cid, info in parsed.items():
                if isinstance(info, dict):
                    name = info.get("name") or info.get("courseName") or ""
                else:
                    name = str(info)
                if str(cid).isdigit() and name:
                    yield str(cid), name

    def _extract_filter_response(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for script in soup.find_all("script"):
            content = script.string or script.text or ""
            if "filterResponseDTO" not in content:
                continue
            for cid, name in re.findall(r'"courseId"\s*:\s*"?(\d+)"?.{0,180}?"courseName"\s*:\s*"([^"]+)"', content, flags=re.S):
                yield cid, name

    def _extract_dropdown(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for option in soup.select("select option[value]"):
            value = option.get("value", "")
            label = option.get_text(" ", strip=True)
            if value.isdigit() and label:
                yield value, label

    def _extract_balanced_object(self, content: str, key: str) -> str | None:
        idx = content.find(key)
        if idx == -1:
            return None
        start = content.find("{", idx)
        if start == -1:
            return None
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(content)):
            ch = content[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[start : i + 1]
        return None

    def _validate_match(self, slug: str, course_id: str, course_name: str) -> bool:
        url = f"https://www.shiksha.com/university/{slug}/reviews?course={course_id}&sort_by=relevance"
        response = self.session.get(url, timeout=30)
        if response.status_code >= 400:
            return False
        soup = BeautifulSoup(response.text, "html.parser")
        title = " ".join(filter(None, [soup.title.string if soup.title else "", self._meta_content(soup, "description")]))
        return fuzz.partial_ratio(self._normalize(course_name), self._normalize(title)) >= 65

    def _meta_content(self, soup: BeautifulSoup, name: str) -> str:
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content", "") if tag else ""

    def _normalize(self, value: str) -> str:
        table = str.maketrans("", "", punctuation)
        return " ".join(value.lower().translate(table).split())

    def _cache_key(self, institute_slug: str, course_name: str) -> str:
        raw = f"{institute_slug.strip().lower()}::{self._normalize(course_name)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
