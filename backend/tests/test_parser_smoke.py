from pathlib import Path

from app.parser import ParserEngine


def test_parser_handles_empty(tmp_path: Path):
    engine = ParserEngine()
    out = engine.parse(tmp_path)
    assert "reviews" in out
