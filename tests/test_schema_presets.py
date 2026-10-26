"""UI schema preset tests."""

from __future__ import annotations

from ui.schema_presets import SCHEMA_PRESETS, get_preset


def test_presets_are_valid_schemas() -> None:
    assert len(SCHEMA_PRESETS) >= 4
    assert "Pharmacy receipt" in SCHEMA_PRESETS
    for name, schema in SCHEMA_PRESETS.items():
        copy = get_preset(name)
        assert copy.name == schema.name
        assert len(copy.fields) >= 1
