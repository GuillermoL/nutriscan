"""Tests del extractor con IA: el SDK de Anthropic se falsea siempre, nunca
se llama a la API real."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.domain.models import FieldStatus
from app.extraction.claude.extractor import ClaudeExtractor

JPEG_HEADER = b"\xff\xd8\xff" + b"0" * 20


def _fake_response(fields: dict) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = json.dumps({"fields": fields})
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    return response


def test_extracts_the_four_fields_from_a_well_formed_response() -> None:
    fields = {
        "energy_kcal": {"found": True, "value": 452, "raw_text": "452 kcal"},
        "fat_g": {"found": True, "value": 21, "raw_text": "21 g"},
        "carbohydrates_g": {"found": True, "value": 58, "raw_text": "58 g"},
        "protein_g": {"found": True, "value": 6.5, "raw_text": "6.5 g"},
    }
    with patch("app.extraction.claude.extractor.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = _fake_response(fields)
        result = ClaudeExtractor().extract(JPEG_HEADER, "image/jpeg")

    assert result.extractor == "claude-vision@1.0"
    assert result.fields["energy_kcal"].value == 452
    assert result.fields["energy_kcal"].source == "claude-vision"
    assert all(f.status != FieldStatus.NOT_FOUND for f in result.fields.values())


def test_field_not_found_by_claude_is_marked_not_found() -> None:
    fields = {
        "energy_kcal": {"found": False, "value": None, "raw_text": None},
        "fat_g": {"found": True, "value": 21, "raw_text": "21 g"},
        "carbohydrates_g": {"found": True, "value": 58, "raw_text": "58 g"},
        "protein_g": {"found": True, "value": 6.5, "raw_text": "6.5 g"},
    }
    with patch("app.extraction.claude.extractor.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = _fake_response(fields)
        result = ClaudeExtractor().extract(JPEG_HEADER, "image/jpeg")

    assert result.fields["energy_kcal"].status == FieldStatus.NOT_FOUND
    assert result.fields["energy_kcal"].value is None


def test_value_out_of_plausible_range_is_marked_doubtful() -> None:
    fields = {
        "energy_kcal": {"found": True, "value": 5000, "raw_text": "5000 kcal"},
        "fat_g": {"found": True, "value": 21, "raw_text": "21 g"},
        "carbohydrates_g": {"found": True, "value": 58, "raw_text": "58 g"},
        "protein_g": {"found": True, "value": 6.5, "raw_text": "6.5 g"},
    }
    with patch("app.extraction.claude.extractor.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = _fake_response(fields)
        result = ClaudeExtractor().extract(JPEG_HEADER, "image/jpeg")

    assert result.fields["energy_kcal"].status == FieldStatus.DOUBTFUL


def test_refusal_raises_claude_extraction_error() -> None:
    from app.extraction.claude.extractor import ClaudeExtractionError

    response = MagicMock()
    response.stop_reason = "refusal"
    response.content = []
    with patch("app.extraction.claude.extractor.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = response
        try:
            ClaudeExtractor().extract(JPEG_HEADER, "image/jpeg")
            assert False, "debía lanzar ClaudeExtractionError"
        except ClaudeExtractionError:
            pass
