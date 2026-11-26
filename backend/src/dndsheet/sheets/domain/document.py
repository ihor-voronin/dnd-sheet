"""Канонічний документ листка (`SheetDocument`).

Це доменний артефакт, а не DTO: його споживають React-рендер і серверні
адаптери (PDF, Markdown, …). Зміни тут вимагають оновлення
`contract/sheet-document.schema.json` і фікстур conformance-набору.

Кожен підпис двомовний: `uk` показуємо, `en` — оригінал для тултіпа.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field as PydField

SCHEMA_VERSION = "1.0"

FieldType = Literal["text", "number", "longtext", "checkbox", "list", "counter", "formula", "dice"]
FieldOrigin = Literal["input", "computed", "override"]
FieldValue = str | int | float | bool | None | list[str]
PageSize = Literal["A4", "A4-landscape", "A5"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LocalizedText(ContractModel):
    uk: str
    en: str
    glossary_id: str | None = PydField(default=None, alias="glossaryId")


class Formula(ContractModel):
    expr: str = PydField(min_length=1)
    deps: list[str] = PydField(default_factory=list)


class Field(ContractModel):
    id: str = PydField(min_length=1)
    type: FieldType
    value: FieldValue
    origin: FieldOrigin
    label: LocalizedText
    hint: LocalizedText | None = None
    editable: bool = False
    formula: Formula | None = None


class Section(ContractModel):
    id: str = PydField(min_length=1)
    title: LocalizedText
    columns: int = PydField(default=1, ge=1, le=6)
    fields: list[str] = PydField(min_length=1)


class Page(ContractModel):
    size: PageSize = "A4"
    sections: list[Section] = PydField(min_length=1)


class SheetDocument(ContractModel):
    schema_version: str = PydField(default=SCHEMA_VERSION, alias="schemaVersion", pattern=r"^[0-9]+\.[0-9]+$")
    edition: Literal["2014"] = "2014"
    title: LocalizedText
    pages: list[Page] = PydField(min_length=1)
    fields: dict[str, Field]

    def to_contract_dict(self) -> dict:
        return self.model_dump(by_alias=True, mode="json", exclude_none=False)
