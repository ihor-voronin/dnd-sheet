"""Інструменти MCP: гравець створює й веде персонажа так само, як у SPA.

Режим одного гравця (`DNDSHEET_AUTH=off`): токени перевіряють тести OAuth, тут —
що кожен інструмент доходить до правил сайту й повертає коротку форму.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent / "_tmp_mcp"
BASE = "http://localhost:8000"
HEADERS = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}

FIGHTER = [
    ("species", {"name": "Дарія", "species_key": "human"}),
    ("class", {"class_key": "fighter"}),
    (
        "abilities",
        {"method": "standard_array", "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}},
    ),
    (
        "background",
        {
            "background_key": "soldier",
            "picks": [
                {"kind": "skill", "value": "acrobatics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
            ],
        },
    ),
    (
        "equipment",
        {
            "items": [{"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True}],
            "money": {},
        },
    ),
]


@pytest.fixture(scope="module")
def site() -> TestClient:
    data = ROOT / "data"
    shutil.rmtree(ROOT, ignore_errors=True)
    data.mkdir(parents=True)
    patch = pytest.MonkeyPatch()
    patch.setenv("DNDSHEET_DATA_DIR", str(data))
    patch.setenv("DNDSHEET_AUTH", "off")
    patch.setenv("DNDSHEET_PUBLIC_URL", BASE)
    with TestClient(create_app(), base_url=BASE) as client:
        yield client
    patch.undo()
    shutil.rmtree(ROOT, ignore_errors=True)


def rpc(site: TestClient, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = site.post(
        "/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def tool(site: TestClient, name: str, /, **arguments: Any) -> dict[str, Any]:  # noqa: ANN401
    result = rpc(site, "tools/call", {"name": name, "arguments": arguments})
    assert result["isError"] is False, result["content"][0]["text"]
    return result["structuredContent"]


def tool_error(site: TestClient, name: str, /, **arguments: Any) -> str:  # noqa: ANN401
    result = rpc(site, "tools/call", {"name": name, "arguments": arguments})
    assert result["isError"] is True
    return result["content"][0]["text"]


@pytest.fixture(scope="module")
def fighter(site: TestClient) -> str:
    """Персонаж, створений лише інструментами — як це зробив би асистент."""
    started = tool(site, "start_character")
    draft_id = started["draft_id"]
    assert started["step"] == "species"
    assert any(option["key"] == "human" for option in started["options"]["species"])
    for step, answers in FIGHTER:
        result = tool(site, "set_creation_step", draft_id=draft_id, step=step, answers=answers)
        assert result["complete"], (step, result["errors"])
    finished = tool(site, "finish_character", draft_id=draft_id)
    assert finished["sheet"]["name"] == "Дарія"
    return finished["character_id"]


def test_server_describes_itself(site: TestClient) -> None:
    result = rpc(
        site,
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    )
    assert result["serverInfo"]["name"] == "dnd-sheet"
    assert "never compute or invent" in result["instructions"]


def test_tools_are_annotated(site: TestClient) -> None:
    tools = {item["name"]: item for item in rpc(site, "tools/list")["tools"]}
    assert tools["delete_character"]["annotations"]["destructiveHint"] is True
    assert tools["list_characters"]["annotations"]["readOnlyHint"] is True
    assert tools["manage_inventory"]["annotations"]["destructiveHint"] is True
    assert tools["update_character"]["annotations"]["idempotentHint"] is True
    assert tools["manage_custom_features"]["annotations"]["destructiveHint"] is True
    assert len(tools) == 21


def test_sheet_summary_is_short_and_has_numbers(site: TestClient, fighter: str) -> None:
    listed = tool(site, "list_characters")
    assert [item["id"] for item in listed["items"]] == [fighter]

    sheet = tool(site, "get_character", character_id=fighter)
    assert sheet["armor_class"] == 16
    assert sheet["classes"][0]["key"] == "fighter"
    assert sheet["hit_points"]["current"] == sheet["hit_points"]["maximum"]
    assert "perception" in sheet["skills"]
    assert len(json.dumps(sheet, ensure_ascii=False)) < 8000

    full = tool(site, "get_character", character_id=fighter, detail="full")
    assert "features" in full and "background_details" in full


def test_play_state_rest_and_conflicts(site: TestClient, fighter: str) -> None:
    sheet = tool(site, "get_character", character_id=fighter)
    hurt = tool(
        site, "update_character", character_id=fighter, version=sheet["version"], changes={"hp": {"damage": 5}}
    )
    assert hurt["sheet"]["hit_points"]["current"] == sheet["hit_points"]["maximum"] - 5

    stale = tool_error(
        site, "update_character", character_id=fighter, version=sheet["version"], changes={"inspiration": True}
    )
    assert "прочитайте лист ще раз" in stale

    rested = tool(site, "rest", character_id=fighter, kind="long")
    assert rested["sheet"]["hit_points"]["current"] == sheet["hit_points"]["maximum"]
    assert "rest" in rested

    bad_die = tool_error(site, "spend_hit_dice", character_id=fighter, die=4, roll=3)
    assert bad_die


def test_inventory_add_update_remove(site: TestClient, fighter: str) -> None:
    version = tool(site, "get_character", character_id=fighter)["version"]
    added = tool(
        site,
        "manage_inventory",
        character_id=fighter,
        version=version,
        action="add",
        item={"name_en": "rope, hempen (50 feet)", "kind": "gear", "quantity": 1},
    )
    index = next(item["index"] for item in added["sheet"]["items"] if item["name_en"].startswith("rope"))
    updated = tool(
        site,
        "manage_inventory",
        character_id=fighter,
        version=added["version"],
        action="update",
        index=index,
        item={"quantity": 2},
    )
    assert updated["sheet"]["items"][index]["quantity"] == 2
    assert "index" in tool_error(
        site, "manage_inventory", character_id=fighter, version=updated["version"], action="remove"
    )
    removed = tool(
        site, "manage_inventory", character_id=fighter, version=updated["version"], action="remove", index=index
    )
    assert all(not item["name_en"].startswith("rope") for item in removed["sheet"]["items"])


def test_level_up_options_are_short(site: TestClient, fighter: str) -> None:
    options = tool(site, "level_up_options", character_id=fighter)
    assert [plan["class_key"] for plan in options["plans"]] == ["fighter"]
    assert {item["class_key"] for item in options["other_classes"]} >= {"wizard", "rogue"}
    assert "feat_abilities" not in options
    assert len(json.dumps(options, ensure_ascii=False)) < 20_000

    wizard = tool(site, "level_up_options", character_id=fighter, class_key="Wizard")
    assert [plan["class_key"] for plan in wizard["plans"]] == ["wizard"]
    assert "немає плану" in tool_error(site, "level_up_options", character_id=fighter, class_key="pilot")


def test_level_up_and_class_choice(site: TestClient, fighter: str) -> None:
    version = tool(site, "get_character", character_id=fighter)["version"]
    taken = tool(
        site,
        "level_up",
        character_id=fighter,
        version=version,
        choices={"class_key": "fighter", "hp": {"mode": "average"}},
    )
    assert taken["sheet"]["level"] == 2
    assert "level_up" in taken

    sheet = tool(site, "get_character", character_id=fighter)
    open_group = next((item for item in sheet["open_choices"] if item["group"].startswith("fighter:")), None)
    assert open_group is not None, sheet["open_choices"]
    chosen = tool(
        site,
        "set_class_choice",
        character_id=fighter,
        version=sheet["version"],
        group=open_group["group"],
        values=["Defense"],
    )
    assert chosen["sheet"]["armor_class"] == 17
    assert tool_error(site, "set_expertise", character_id=fighter, version=chosen["version"], skills=["athletics"])


def test_spells_need_one_spell_for_learn(site: TestClient, fighter: str) -> None:
    version = tool(site, "get_character", character_id=fighter)["version"]
    message = tool_error(
        site, "manage_spells", character_id=fighter, version=version, action="learn", class_key="fighter", spells=[]
    )
    assert "по одному" in message
    assert tool_error(
        site,
        "manage_spells",
        character_id=fighter,
        version=version,
        action="prepare",
        class_key="wizard",
        spells=[],
    )
    assert tool_error(
        site,
        "manage_spells",
        character_id=fighter,
        version=version,
        action="forget",
        class_key="fighter",
        spells=[{"name_en": "Fire Bolt", "level": 0}],
    )


def test_custom_features_through_tools(site: TestClient, fighter: str) -> None:
    version = tool(site, "get_character", character_id=fighter)["version"]
    added = tool(
        site,
        "manage_custom_features",
        character_id=fighter,
        version=version,
        action="add",
        feature={"name": "Дар майстра", "text": "Раз на день — перекинути кидок.", "uses": 1},
    )
    feature_id = added["feature_id"]
    listed = added["sheet"]["custom_features"]
    assert listed == [
        {
            "id": feature_id,
            "name": "Дар майстра",
            "origin": None,
            "level": None,
            "text": "Раз на день — перекинути кидок.",
            "uses": 1,
            "used": 0,
            "recharge": "long",
            "key": f"custom:{feature_id}",
        }
    ]
    assert any(item["key"] == f"custom:{feature_id}" for item in added["sheet"]["feature_uses"])

    spent = tool(
        site,
        "update_character",
        character_id=fighter,
        version=added["version"],
        changes={"feature_used": {f"custom:{feature_id}": 1}},
    )
    assert spent["sheet"]["custom_features"][0]["used"] == 1

    changed = tool(
        site,
        "manage_custom_features",
        character_id=fighter,
        version=spent["version"],
        action="update",
        feature_id=feature_id,
        feature={"origin": "Перстень", "uses": None},
    )
    assert changed["sheet"]["custom_features"][0]["origin"] == "Перстень"
    assert "uses" not in changed["sheet"]["custom_features"][0]

    assert "feature_id" in tool_error(
        site, "manage_custom_features", character_id=fighter, version=changed["version"], action="remove"
    )
    assert "версі" in tool_error(
        site,
        "manage_custom_features",
        character_id=fighter,
        version=changed["version"] - 1,
        action="remove",
        feature_id=feature_id,
    )
    removed = tool(
        site,
        "manage_custom_features",
        character_id=fighter,
        version=changed["version"],
        action="remove",
        feature_id=feature_id,
    )
    assert removed["sheet"]["custom_features"] == []


def test_custom_spell_through_tools(site: TestClient, fighter: str) -> None:
    version = tool(site, "get_character", character_id=fighter)["version"]
    learned = tool(
        site,
        "manage_spells",
        character_id=fighter,
        version=version,
        action="learn",
        class_key="other",
        spells=[{"name_en": "Вогонь перстня", "level": 1, "custom": True, "description": "1d10 вогню."}],
    )
    spell = next(item for item in learned["sheet"]["spells"] if item["name"] == "Вогонь перстня")
    assert spell == {
        "name": "Вогонь перстня",
        "name_uk": None,
        "level": 1,
        "class": "other",
        "prepared": True,
        "custom": True,
        "description": "1d10 вогню.",
    }
    updated = tool(
        site,
        "manage_spells",
        character_id=fighter,
        version=learned["version"],
        action="update",
        class_key="other",
        spells=[{"name_en": "Вогонь перстня", "fields": {"level": 2, "school": "воплочення"}}],
    )
    assert next(item for item in updated["sheet"]["spells"] if item.get("custom"))["level"] == 2
    forgotten = tool(
        site,
        "manage_spells",
        character_id=fighter,
        version=updated["version"],
        action="forget",
        class_key="other",
        spells=[{"name_en": "Вогонь перстня"}],
    )
    assert not any(item.get("custom") for item in forgotten["sheet"]["spells"])


def test_share_and_pdf_links(site: TestClient, fighter: str) -> None:
    assert tool(site, "share_link", character_id=fighter) == {"url": None}
    created = tool(site, "share_link", character_id=fighter, action="create")
    assert created["url"].startswith(f"{BASE}/#/s/")
    assert tool(site, "share_link", character_id=fighter, action="revoke") == {"url": None}

    pdf = tool(site, "export_pdf", character_id=fighter)
    assert pdf["url"] == f"{BASE}/api/v1/characters/{fighter}/export/pdf"
    assert "немає" in tool_error(site, "export_pdf", character_id="nope")


def test_compendium_search_and_entry(site: TestClient) -> None:
    found = tool(site, "search_compendium", query="fireball", category="spell")
    assert any(item["id"].endswith("/fireball") for item in found["items"])
    entry_id = next(item["id"] for item in found["items"] if item["id"].endswith("/fireball"))
    entry = tool(site, "get_compendium_entry", entry_id=entry_id)
    assert entry["name_en"] == "Fireball"
    assert tool(site, "search_compendium", query="rope")["items"]


def test_creation_step_reads_and_locks(site: TestClient) -> None:
    started = tool(site, "start_character")
    locked = tool(site, "get_creation_step", draft_id=started["draft_id"], step="abilities")
    assert locked["locked"] is True
    message = tool_error(site, "set_creation_step", draft_id=started["draft_id"], step="abilities", answers={})
    assert "попередній крок" in message


def test_sheet_resource_and_prompts(site: TestClient, fighter: str) -> None:
    contents = rpc(site, "resources/read", {"uri": f"character://{fighter}"})["contents"]
    assert "Дарія" in contents[0]["text"]

    missing = site.post(
        "/mcp",
        headers=HEADERS,
        json={"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "character://nope"}},
    ).json()
    assert "error" in missing

    prompts = {item["name"] for item in rpc(site, "prompts/list")["prompts"]}
    assert prompts == {"character_from_idea", "level_up_advice", "session_recap"}
    for name, arguments in (
        ("character_from_idea", {"idea": "халфлінг-бард, колишній контрабандист"}),
        ("level_up_advice", {"character_id": fighter}),
        ("session_recap", {"character_id": fighter, "recap": "отримав 7 шкоди"}),
    ):
        text = rpc(site, "prompts/get", {"name": name, "arguments": arguments})["messages"][0]["content"]["text"]
        assert next(iter(arguments.values())) in text


def _quick_character(site: TestClient, name: str) -> str:
    draft_id = tool(site, "start_character")["draft_id"]
    for step, answers in FIGHTER:
        if step == "species":
            answers = {**answers, "name": name}
        tool(site, "set_creation_step", draft_id=draft_id, step=step, answers=answers)
    return tool(site, "finish_character", draft_id=draft_id)["character_id"]


def test_delete_needs_the_right_name(site: TestClient, fighter: str) -> None:
    doomed = _quick_character(site, "Тимчасовий")
    before = tool(site, "list_characters")
    assert before["limit"] == 50

    wrong = tool_error(site, "delete_character", character_id=doomed, name="Дарія")
    assert "не збігається" in wrong and "Тимчасовий" in wrong
    assert "немає персонажа" in tool_error(site, "delete_character", character_id="nope", name="x")

    deleted = tool(site, "delete_character", character_id=doomed, name="тимчасовий")
    assert deleted["deleted"] == doomed
    assert deleted["characters_left"] == before["total"] - 1
    after = tool(site, "list_characters")
    assert doomed not in [item["id"] for item in after["items"]]
    assert fighter in [item["id"] for item in after["items"]]


def test_limit_is_explained_to_the_assistant(site: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from dndsheet.characters.api import router as characters_router  # noqa: PLC0415

    total = tool(site, "list_characters")["total"]
    monkeypatch.setattr(characters_router, "CHARACTER_LIMIT", total)
    message = tool_error(site, "start_character")
    assert "межа" in message and "видаліть" in message
