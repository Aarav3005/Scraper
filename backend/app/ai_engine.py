from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from openai import OpenAI


PROMPT_TEMPLATE = """You are an expert education analyst.

Generate:
**B.Tech Mechanical Engineering Review Analysis Report**

Rules:
* Only use provided dataset
* No external knowledge
* Missing data → “Insufficient data from reviews”

Structure:
1. Title
2. Colleges analyzed
3. Scope
4. Disclaimer

For EACH college include:
* Academics
* Faculty
* Infrastructure
* Placements (core)
* Placements (IT shift)
* Internships
* Peer group
* Campus culture
* Admin & ROI
* Location advantage

Each section must include:
✔ positives
✘ negatives
sentiment %

Then include:
* Top strengths
* Weaknesses
* Red flags
* Career outcome estimates

Then:
6. Cross college comparison table
7. Final ranking
8. Final conclusion (best for core, ROI, IT pivot, campus life, avoid)

Tone: blunt, analytical, use ✔ ✘ ⚠️.
"""


class AIComparisonEngine:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def compare(self, datasets: List[Dict[str, Any]]) -> str:
        if not self.client:
            return "OPENAI_API_KEY not configured. Unable to generate report."

        user_payload = json.dumps(datasets, indent=2)
        completion = self.client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": PROMPT_TEMPLATE},
                {"role": "user", "content": f"Dataset:\n{user_payload}"},
            ],
            temperature=0.2,
        )
        return completion.choices[0].message.content or "No report generated"
