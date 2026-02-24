from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz


@dataclass
class CourseMatch:
    course_id: str
    course_name: str
    score: float


class CourseResolver:
    def __init__(self, session: requests.Session):
        self.session = session

    def resolve(self, institute_slug: str, course_name: str) -> CourseMatch:
        base_url = f"https://www.shiksha.com/university/{institute_slug}/reviews"
        page = self.session.get(base_url, timeout=30)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        candidates = {}
        for cid, cname in self._extract_course_infos(soup):
            candidates[cid] = cname
        for cid, cname in self._extract_filter_response(soup):
            candidates[cid] = cname
        for cid, cname in self._extract_dropdown(soup):
            candidates[cid] = cname

        if not candidates:
            raise ValueError("No course IDs discovered for institute")

        ranked = sorted(
            [
                CourseMatch(course_id=cid, course_name=cname, score=float(fuzz.token_set_ratio(course_name, cname)))
                for cid, cname in candidates.items()
            ],
            key=lambda x: x.score,
            reverse=True,
        )

        for match in ranked:
            if self._validate_match(institute_slug, match.course_id, course_name):
                return match

        raise ValueError(f"Could not validate course match for '{course_name}'")

    def _extract_course_infos(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for script in soup.find_all("script"):
            content = script.string or script.text or ""
            if "courseInfos" not in content:
                continue
            match = re.search(r"courseInfos\s*:\s*(\{.*?\})\s*,\s*[a-zA-Z_]+\s*:", content, flags=re.S)
            if not match:
                continue
            payload = match.group(1)
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            for cid, info in parsed.items():
                if isinstance(info, dict):
                    name = info.get("name") or info.get("courseName") or str(info)
                else:
                    name = str(info)
                yield str(cid), name

    def _extract_filter_response(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for script in soup.find_all("script"):
            content = script.string or script.text or ""
            if "filterResponseDTO" not in content:
                continue
            for cid, name in re.findall(r'"courseId"\s*:\s*"?(\d+)"?.{0,120}?"courseName"\s*:\s*"([^"]+)"', content, flags=re.S):
                yield cid, name

    def _extract_dropdown(self, soup: BeautifulSoup) -> Iterable[tuple[str, str]]:
        for option in soup.select("select option[value]"):
            value = option.get("value", "")
            if value.isdigit() and option.text.strip():
                yield value, option.text.strip()

    def _validate_match(self, slug: str, course_id: str, course_name: str) -> bool:
        url = f"https://www.shiksha.com/university/{slug}/reviews?course={course_id}&sort_by=relevance"
        response = self.session.get(url, timeout=30)
        if response.status_code >= 400:
            return False
        soup = BeautifulSoup(response.text, "html.parser")
        title = " ".join(filter(None, [soup.title.string if soup.title else "", self._meta_content(soup, "description")]))
        return fuzz.partial_ratio(course_name.lower(), title.lower()) >= 65

    def _meta_content(self, soup: BeautifulSoup, name: str) -> str:
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content", "") if tag else ""
