"""Контракт: схема валідна, фікстури їй відповідають, модель не розходиться зі схемою."""

from __future__ import annotations

import jsonschema
import pytest

from dndsheet.sheets.domain.document import SheetDocument


def test_schema_itself_is_valid(schema: dict) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("fixture_name", ["minimal", "full"])
def test_fixture_matches_schema(fixture_name: str, schema: dict, fixture_documents: dict[str, dict]) -> None:
    jsonschema.validate(instance=fixture_documents[fixture_name], schema=schema)


@pytest.mark.parametrize("fixture_name", ["minimal", "full"])
def test_fixture_loads_into_model_and_dumps_back(
    fixture_name: str, schema: dict, fixture_documents: dict[str, dict]
) -> None:
    document = SheetDocument.model_validate(fixture_documents[fixture_name])
    dumped = document.to_contract_dict()
    # Головне: те, що віддає Python-модель, проходить ту саму схему, що й фікстури.
    jsonschema.validate(instance=dumped, schema=schema)


@pytest.mark.parametrize("fixture_name", ["minimal", "full"])
def test_all_referenced_fields_exist(fixture_name: str, fixture_documents: dict[str, dict]) -> None:
    document = SheetDocument.model_validate(fixture_documents[fixture_name])
    for page in document.pages:
        for section in page.sections:
            for field_id in section.fields:
                assert field_id in document.fields, (
                    f"Секція {section.id!r} посилається на неіснуюче поле {field_id!r}"
                )


@pytest.mark.parametrize("fixture_name", ["minimal", "full"])
def test_field_id_matches_key(fixture_name: str, fixture_documents: dict[str, dict]) -> None:
    document = SheetDocument.model_validate(fixture_documents[fixture_name])
    for key, field in document.fields.items():
        assert field.id == key


def test_model_rejects_unknown_field_key(schema: dict, fixture_documents: dict[str, dict]) -> None:
    broken = dict(fixture_documents["minimal"])
    broken["fields"] = {
        **broken["fields"],
        "str.score": {**broken["fields"]["str.score"], "unexpected": "x"},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=broken, schema=schema)

    with pytest.raises(Exception):
        SheetDocument.model_validate(broken)


def test_schema_requires_original_english_text(schema: dict, fixture_documents: dict[str, dict]) -> None:
    broken = dict(fixture_documents["minimal"])
    broken["title"] = {"uk": "Без оригіналу"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=broken, schema=schema)
