"""JSON sanitization for model responses."""

from __future__ import annotations

from providers.json_output import parse_model_json, sanitize_structuring_payload


def test_coerces_numeric_field_values() -> None:
    raw = {
        "fields": [
            {"key": "net_amount", "value": 27078.0, "review_status": "confirmed"},
        ]
    }
    payload = sanitize_structuring_payload(raw)
    assert payload["fields"][0]["value"] == "27078.0"


def test_parse_tolerates_extra_line_item_fields() -> None:
    text = """{
      "fields": [{"key": "total", "value": 1, "review_status": "confirmed"}],
      "line_items": [{"product_name": "TAB", "qty": 10, "extra": "x"}]
    }"""
    out = parse_model_json(text)
    assert out.fields[0].value == "1"
    assert len(out.line_items) == 1
    assert out.line_items[0].qty == "10"
