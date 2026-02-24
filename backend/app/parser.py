from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup


class ParserEngine:
    money_re = re.compile(r"₹\s?[\d,.]+\s?(?:LPA|lakh|crore|Cr)?", re.I)

    def parse(self, storage_path: Path) -> Dict[str, Any]:
        parsed = {
            "reviews": self._parse_reviews(storage_path),
            "fees": self._parse_fees(storage_path / "fees.html"),
            "placement": self._parse_placement(storage_path / "placement.html"),
            "cutoff": self._parse_cutoff(storage_path / "cutoff.html"),
            "infrastructure": self._parse_infra(storage_path / "infrastructure.html"),
        }
        self._write_reviews_csv(storage_path, parsed["reviews"])
        (storage_path / "metadata.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        return parsed

    def _parse_reviews(self, storage_path: Path) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for page in sorted(storage_path.glob("reviews_page_*.html")):
            soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
            for card in soup.select("article, div"):
                text = " ".join(card.get_text(" ", strip=True).split())
                if len(text) < 80:
                    continue
                rating = None
                rate_m = re.search(r"([0-5](?:\.\d)?)\s*/\s*5", text)
                if rate_m:
                    rating = float(rate_m.group(1))
                rows.append(
                    {
                        "rating": rating,
                        "pros": self._extract_after(text, "Pros:"),
                        "cons": self._extract_after(text, "Cons:"),
                        "title": text[:120],
                        "year": self._search(text, r"(20\d{2})"),
                        "reviewer_type": self._search(text, r"(Student|Alumni)", re.I),
                    }
                )
        return rows[:100]

    def _parse_fees(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {}
        text = BeautifulSoup(file_path.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
        vals = self.money_re.findall(text)
        return {
            "tuition": vals[0] if len(vals) > 0 else "Insufficient data from reviews",
            "hostel": vals[1] if len(vals) > 1 else "Insufficient data from reviews",
            "total": vals[2] if len(vals) > 2 else "Insufficient data from reviews",
        }

    def _parse_placement(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {}
        text = BeautifulSoup(file_path.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
        vals = self.money_re.findall(text)
        return {
            "highest": self._extract_keyword(text, "highest", vals),
            "average": self._extract_keyword(text, "average", vals),
            "recruiters": self._search(text, r"(Top recruiters[^.]{0,140})", re.I) or "Insufficient data from reviews",
        }

    def _parse_cutoff(self, file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists():
            return []
        soup = BeautifulSoup(file_path.read_text(encoding="utf-8"), "html.parser")
        out = []
        for row in soup.select("table tr"):
            cols = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cols) >= 3:
                out.append({"exam": cols[0], "round": cols[1], "rank": cols[2]})
        return out

    def _parse_infra(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {}
        soup = BeautifulSoup(file_path.read_text(encoding="utf-8"), "html.parser")
        text = soup.get_text(" ", strip=True)
        facilities = []
        for keyword in ["Hostel", "Library", "Sports", "Labs", "Wi-Fi"]:
            if re.search(keyword, text, re.I):
                facilities.append(keyword)
        return {
            "facilities": facilities,
            "ratings": self._search(text, r"(Infrastructure[^.]{0,120})", re.I) or "Insufficient data from reviews",
        }

    def _extract_keyword(self, text: str, keyword: str, vals: List[str]) -> str:
        m = re.search(rf"{keyword}[^₹]{{0,30}}(₹\s?[\d,.]+\s?(?:LPA|lakh|crore|Cr)?)", text, flags=re.I)
        if m:
            return m.group(1)
        return vals[0] if vals else "Insufficient data from reviews"

    def _write_reviews_csv(self, storage_path: Path, reviews: List[Dict[str, Any]]) -> None:
        out = storage_path / "reviews.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["rating", "pros", "cons", "title", "year", "reviewer_type"])
            w.writeheader()
            w.writerows(reviews)

    def _search(self, text: str, pattern: str, flags: int = 0) -> str | None:
        m = re.search(pattern, text, flags)
        return m.group(1) if m else None

    def _extract_after(self, text: str, marker: str) -> str | None:
        if marker not in text:
            return None
        tail = text.split(marker, 1)[1]
        return tail.split("Cons:", 1)[0][:240].strip()
