from __future__ import annotations

from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ai_engine import AIComparisonEngine
from .course_resolver import CourseResolver
from .models import CompareRequest, ScrapeRequest
from .parser import ParserEngine
from .resolver import InstituteResolver
from .scraper import ScraperEngine


app = FastAPI(title="Shiksha Dynamic Scraper")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
)

resolver = InstituteResolver(session)
course_resolver = CourseResolver(session)
scraper = ScraperEngine(session, data_root=Path("data"))
parser = ParserEngine()
ai_engine = AIComparisonEngine()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/scrape")
def scrape(payload: ScrapeRequest) -> dict:
    try:
        institute = resolver.resolve(payload.college_name)
        course = course_resolver.resolve(institute.slug, payload.course_name)
        storage, page_map = scraper.scrape_all(institute.slug, course.course_id)
        parsed = parser.parse(storage)
        return {
            "institute": institute.__dict__,
            "course": course.__dict__,
            "storage_path": str(storage),
            "pages": page_map,
            "parsed": parsed,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/compare")
def compare(payload: CompareRequest) -> dict:
    datasets = []
    for item in payload.colleges:
        result = scrape(item)
        datasets.append(result)
    report = ai_engine.compare(datasets)
    return {"report": report, "datasets": datasets}
