from __future__ import annotations

import logging
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


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Shiksha Dynamic Scraper")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

session = requests.Session()
resolver = InstituteResolver(session)
course_resolver = CourseResolver(session)
scraper = ScraperEngine(session, data_root=Path("data"))
parser = ParserEngine()
ai_engine = AIComparisonEngine()


def run_pipeline(payload: ScrapeRequest) -> dict:
    institute = resolver.resolve(payload.college_name)
    course = course_resolver.resolve(institute.slug, payload.course_name)
    storage, page_map = scraper.scrape_all(institute.slug, course.course_id)
    parsed = parser.parse(storage)
    logger.info(
        "Pipeline completed for college='%s', course='%s' -> slug=%s, course_id=%s",
        payload.college_name,
        payload.course_name,
        institute.slug,
        course.course_id,
    )
    return {
        "institute": institute.__dict__,
        "course": course.__dict__,
        "storage_path": str(storage),
        "pages": page_map,
        "parsed": parsed,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/scrape")
def scrape(payload: ScrapeRequest) -> dict:
    try:
        return run_pipeline(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Scrape failed: {exc}") from exc


@app.post("/api/compare")
def compare(payload: CompareRequest) -> dict:
    try:
        datasets = []
        in_request_cache: dict[tuple[str, str], dict] = {}
        for item in payload.colleges:
            key = (item.college_name.strip().lower(), item.course_name.strip().lower())
            if key not in in_request_cache:
                in_request_cache[key] = run_pipeline(item)
            datasets.append(in_request_cache[key])
        report = ai_engine.compare(datasets)
        return {"report": report, "datasets": datasets}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Compare failed: {exc}") from exc
