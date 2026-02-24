# Shiksha Dynamic Scraper + AI Analyzer

Production-style web app that dynamically resolves Shiksha institute + course IDs from `college_name` and `course_name`, scrapes filtered pages, parses structured data, stores raw HTML, and generates AI comparison reports.

## Folder Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── ai_engine.py
│   │   ├── course_resolver.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   ├── resolver.py
│   │   └── scraper.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── data/
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── firebase.json
└── README.md
```

## Module Mapping

1. Resolver Module: `backend/app/resolver.py`
2. Course Resolver Module: `backend/app/course_resolver.py`
3. Scraper Engine: `backend/app/scraper.py`
4. Parser Engine: `backend/app/parser.py`
5. Storage Layer: `/data/<slug>/...` managed by scraper/parser
6. Backend API (FastAPI): `backend/app/main.py`
7. Frontend UI: `frontend/index.html`, `frontend/app.js`
8. AI Comparison Engine: `backend/app/ai_engine.py`
9. Firebase deployment compatibility: `firebase.json`, `backend/Dockerfile`

## Dynamic Resolution Guarantees

- Institute resolution via `https://www.shiksha.com/search?q=<college_name>`.
- Canonical fallback parsing for slug + primaryId.
- Course ID resolution hierarchy:
  1. `courseInfos` in scripts.
  2. `filterResponseDTO` payloads.
  3. Dropdown option parsing.
- Fuzzy matching + validation using:
  - `/reviews?course=<courseId>&sort_by=relevance`
  - title/meta contains target course context.
- No hardcoded course IDs.

## Storage Format

For each institute slug:

```text
data/<slug>/
  overview.html
  fees.html
  admission.html
  placement.html
  cutoff.html
  infrastructure.html
  reviews_page_1.html
  reviews_page_2.html
  ...
  metadata.json
  reviews.csv
```

## Run Locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

Serve static files:

```bash
cd frontend
python -m http.server 4173
```

Open `http://localhost:4173`.

## API Endpoints

- `GET /health`
- `POST /api/scrape`
  - body: `{ "college_name": "...", "course_name": "..." }`
- `POST /api/compare`
  - body: `{ "colleges": [{"college_name":"...","course_name":"..."}, ...] }`

## Firebase Deployment

### 1) Prerequisites

```bash
npm i -g firebase-tools
firebase login
firebase use <project-id>
```

### 2) Deploy backend to Cloud Run

```bash
cd backend
gcloud builds submit --tag gcr.io/<project-id>/shiksha-backend
gcloud run deploy shiksha-backend \
  --image gcr.io/<project-id>/shiksha-backend \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=<key>,OPENAI_MODEL=gpt-4o-mini
```

### 3) Deploy frontend hosting

```bash
cd ..
firebase deploy --only hosting
```

## Edge Cases Handled

- Multiple close course variants via fuzzy ranking.
- Empty or missing review pages.
- Missing embedded JSON falls back to semantic + regex extraction.
- Retries (3 attempts) with 1 req/sec pacing.
- Course validation retries ranked candidates.

## Dependencies

Backend Python dependencies in `backend/requirements.txt`.

## Testing Helper Inputs

See `backend/tests/test_cases.py` for ready-to-run college/course pairs for manual validation.
