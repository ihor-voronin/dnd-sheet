"""MCP-сервер: інструменти для власних персонажів гравця (ADR 0005).

Кожен інструмент — тонкий перехідник до HTTP API сайту (`inprocess.call`) від
імені власника токена. Правила, перевірки, «чужий персонаж — як відсутній» —
ті самі, що для SPA; тут лише вибір запиту й коротка форма відповіді.

Описи інструментів — англійською (моделі так краще обирають інструмент),
дані й помилки — українською, як на сайті.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.types import ASGIApp

from dndsheet.assistant.inprocess import Reply, call, segment
from dndsheet.assistant.shaping import compact, summary
from dndsheet.identity.api.router import LOCAL_USER
from dndsheet.identity.domain.user import User

INSTRUCTIONS = """\
dnd-sheet: the player's own D&D 5e (2014 Player's Handbook rules) characters on dnd.voronin.app.
The site computes every number (AC, HP, attack bonuses, slots); never compute or invent them.

- Start with list_characters, then get_character for the sheet. Changing tools take the
  sheet's `version` from the last read; on a version conflict read the sheet again.
- Creating a character follows the site's wizard: start_character, then for each step
  get_creation_step (it lists the only options the rules allow, with their keys) and
  set_creation_step, then finish_character. Use the keys from the options, never guesses.
- Names and errors come back in Ukrainian; answer the player in their language.
- A player can have at most `limit` characters (list_characters shows it); at the limit, starting
  or finishing a character fails until one is deleted.
- Things the player's table has but the books don't (homebrew, a DM's boon, an item's power) go
  in as custom entries: manage_custom_features for features, manage_spells with `custom: true`
  for spells. Write their text as the player gives it; the site adds no numbers from them.
- Every character has a portrait the site draws (no uploads): set_avatar lists suggestions for
  its species, class and gender and sets one; the species step also takes an optional gender.
- delete_character is permanent. Use it only when the player explicitly asks to delete a
  specific character, and confirm the name with them first.
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
CHANGES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
IDEMPOTENT = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
)

Step = Literal["species", "class", "abilities", "background", "equipment", "spells"]
CharacterId = Annotated[str, Field(description="Character id from list_characters")]
Version = Annotated[int, Field(description="The sheet's `version` from the last read")]

_API = "/api/v1/characters"


def build_server(
    app: ASGIApp,
    *,
    public_url: str,
    auth: AuthSettings | None = None,
    provider: OAuthAuthorizationServerProvider[Any, Any, Any] | None = None,
) -> MCPServer:
    """Сервер з інструментами. Без `auth` — режим одного гравця (`DNDSHEET_AUTH=off`)."""
    server = MCPServer(
        "dnd-sheet",
        instructions=INSTRUCTIONS,
        website_url=public_url,
        auth=auth,
        auth_server_provider=provider,
    )

    def user() -> User:
        state = getattr(app, "state", None)
        if state is None or not state.auth_enabled:
            return LOCAL_USER
        token = get_access_token()
        found = state.auth.users.get(token.subject) if token is not None and token.subject else None
        if found is None:
            raise ToolError("немає входу: підключіть застосунок ще раз")
        return found

    async def api(method: str, path: str, *, body: Any = None, query: dict[str, Any] | None = None) -> Any:  # noqa: ANN401
        reply = await call(app, user(), method, path, body=body, query=query)
        return _checked(reply)

    async def changed(method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        result = await api(method, path, body=body)
        shaped = {"sheet": summary(result["sheet"]), "version": result.get("version")}
        for extra in ("rest", "level_up", "feature_id"):
            if extra in result:
                shaped[extra] = result[extra]
        return shaped

    # --- персонажі -------------------------------------------------------------

    @server.tool(title="List my characters", annotations=READ_ONLY)
    async def list_characters() -> dict[str, Any]:
        """The player's characters (newest first) and the id of an unfinished creation draft, if any."""
        return await api("GET", _API)

    @server.tool(title="Read a character sheet", annotations=READ_ONLY)
    async def get_character(
        character_id: CharacterId,
        detail: Annotated[
            Literal["summary", "full"],
            Field(description="summary: numbers and state; full: everything incl. feature texts (large)"),
        ] = "summary",
    ) -> dict[str, Any]:
        """A character's sheet as the site computes it, with its `version` for later changes."""
        result = await api("GET", f"{_API}/{segment(character_id)}")
        sheet = result["sheet"]
        return compact(sheet, 600) if detail == "full" else summary(sheet)

    @server.tool(title="Update the sheet", annotations=IDEMPOTENT)
    async def update_character(
        character_id: CharacterId,
        version: Version,
        changes: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Any of: hp {current?, temporary?} or {damage: n} or {heal: n}; "
                    'slots {"1": used, ...}; pact_used n; feature_used {key: used}; '
                    "death_saves {successes, failures}; exhaustion 0-6; inspiration bool; "
                    "notes {section: text}; equip {index: bool}; gender female/male/null; "
                    "avatar: a portrait id (see set_avatar)"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Change the play state of a sheet: hit points, spent slots and feature uses, death saves,
        exhaustion, inspiration, notes, equipped items. Returns the recomputed sheet."""
        return await changed("PATCH", f"{_API}/{segment(character_id)}", {**changes, "version": version})

    @server.tool(title="Choose a portrait", annotations=IDEMPOTENT)
    async def set_avatar(
        character_id: CharacterId,
        avatar: Annotated[
            str | None,
            Field(description="Portrait id from `suggestions` (e.g. elf-f-wizard-1); omit to only list suggestions"),
        ] = None,
        gender: Annotated[
            Literal["female", "male", "unset"] | None,
            Field(description="The character's gender, used to pick portraits; unset clears it"),
        ] = None,
        version: Annotated[int | None, Field(description="The sheet's `version`; required to change")] = None,
    ) -> dict[str, Any]:
        """The character's portrait (the site draws them; no uploads). Without `avatar` and `gender`
        returns the current portrait and 24 suggestions for the character's species, class and gender.
        With them sets the portrait and/or gender (needs `version`)."""
        path = f"{_API}/{segment(character_id)}"
        if avatar is None and gender is None:
            sheet = (await api("GET", path))["sheet"]
            character = sheet.get("character") or {}
            species = character.get("species") or {}
            classes = character.get("classes") or []
            query = {
                "species": " ".join(filter(None, (species.get("subspecies"), species.get("name_en")))) or None,
                "class": classes[0].get("key") if classes else None,
                "gender": character.get("gender"),
            }
            advice = await api("GET", "/api/v1/avatars/recommended", query={k: v for k, v in query.items() if v})
            return {
                "version": character.get("version"),
                "gender": character.get("gender"),
                "portrait": character.get("portrait"),
                "suggestions": [
                    {"id": item["id"], "label": item["label"], "url": public_url + item["url"]}
                    for item in advice["items"]
                ],
            }
        if version is None:
            raise ToolError("щоб змінити портрет чи стать, потрібна `version` листа")
        body: dict[str, Any] = {"version": version}
        if avatar is not None:
            body["avatar"] = avatar or None
        if gender is not None:
            body["gender"] = None if gender == "unset" else gender
        return await changed("PATCH", path, body)

    # --- створення -----------------------------------------------------------

    @server.tool(title="Start creating a character", annotations=CHANGES)
    async def start_character() -> dict[str, Any]:
        """Open a new creation draft. Returns its id and the first step (species) with its options."""
        return _step(await api("POST", f"{_API}/wizard"))

    @server.tool(title="Read a creation step", annotations=READ_ONLY)
    async def get_creation_step(draft_id: str, step: Step) -> dict[str, Any]:
        """A wizard step: the allowed `options` (keys and names), current `answers`, and whether it
        is locked (the previous step isn't done) or complete."""
        return _step(await api("GET", f"{_API}/wizard/{segment(draft_id)}/steps/{step}"))

    @server.tool(title="Answer a creation step", annotations=IDEMPOTENT)
    async def set_creation_step(
        draft_id: str,
        step: Step,
        answers: Annotated[
            dict[str, Any],
            Field(
                description=(
                    'species: {"name", "gender"?, "species_key", "subspecies_key", "ability_choices", "spell_choices"}; '
                    'class: {"class_key", "subclass_key"}; '
                    'abilities: {"method": "standard_array"|"point_buy"|"manual", "scores": {"str": 15, ...}}; '
                    'background: {"background_key", "alignment", "picks": [{"kind", "value", "source"}]}; '
                    'equipment: {"items": [...], "money": {"gp": 10}}; '
                    'spells: {"spells": [{"name_en", "level", "class_key", "entry_id"}]}. '
                    "Take keys from get_creation_step options."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Save the answers of one wizard step; the site validates them against the rules."""
        return _step(await api("PUT", f"{_API}/wizard/{segment(draft_id)}/steps/{step}", body=answers))

    @server.tool(title="Finish creating a character", annotations=CHANGES)
    async def finish_character(draft_id: str) -> dict[str, Any]:
        """Build the character from a complete draft and save it. Returns the new sheet."""
        result = await api("POST", f"{_API}/wizard/{segment(draft_id)}/finish")
        return {"character_id": result["character_id"], "sheet": summary(result["sheet"])}

    # --- гра ---------------------------------------------------------------

    @server.tool(title="Manage inventory", annotations=DESTRUCTIVE)
    async def manage_inventory(
        character_id: CharacterId,
        version: Version,
        action: Literal["add", "update", "remove"],
        item: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    'add: {"name_en", "kind": "weapon"|"armor"|"gear"|..., "quantity", "entry_id"?}; '
                    "update: the fields to change (quantity, equipped, attuned, notes)"
                )
            ),
        ] = None,
        index: Annotated[int | None, Field(description="Item index from the sheet (update/remove)")] = None,
    ) -> dict[str, Any]:
        """Add, change or remove an inventory item. `remove` drops the item from the sheet."""
        base = f"{_API}/{segment(character_id)}/items"
        if action == "add":
            return await changed("POST", base, {"item": item or {}, "version": version})
        if index is None:
            raise ToolError("вкажіть index предмета")
        if action == "update":
            return await changed("PATCH", f"{base}/{index}", {"fields": item or {}, "version": version})
        return await changed("DELETE", f"{base}/{index}", {"version": version})

    @server.tool(title="Manage spells", annotations=CHANGES)
    async def manage_spells(
        character_id: CharacterId,
        version: Version,
        action: Literal["learn", "forget", "prepare", "update"],
        class_key: Annotated[
            str,
            Field(
                description=(
                    'The class the spell belongs to, e.g. wizard; "other" for a custom spell that belongs '
                    "to no class (a DM's boon, an item's power)"
                )
            ),
        ],
        spells: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    'learn/forget: one spell {"name_en", "level", "entry_id"?}. A custom spell (not in the '
                    'books) is learned with {"name_en", "level" 0-9, "custom": true, "description", and '
                    'optionally "school", "casting_time", "range", "duration", "components" (free text), '
                    '"concentration", "ritual" (bool)}. update (custom spells only): '
                    '[{"name_en": current name, "fields": {any of those keys, incl. a new "name_en", '
                    '"level" or "class_key"}}]. prepare: the whole prepared list for the class'
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Learn or forget a spell outside a level-up, set the day's prepared spells of a class, or add
        and edit a custom spell. Custom spells are always prepared; under a class they count toward
        its limits, under "other" they don't."""
        base = f"{_API}/{segment(character_id)}/spells"
        if action == "prepare":
            return await changed(
                "POST", f"{base}/prepare", {"class_key": class_key, "spells": spells, "version": version}
            )
        if len(spells) != 1:
            raise ToolError("learn, forget і update — по одному закляттю")
        body = {**spells[0], "class_key": class_key, "version": version}
        if action == "update":
            return await changed("PATCH", base, body)
        return await changed("POST" if action == "learn" else "DELETE", base, body)

    @server.tool(title="Manage custom features", annotations=DESTRUCTIVE)
    async def manage_custom_features(
        character_id: CharacterId,
        version: Version,
        action: Literal["add", "update", "remove"],
        feature: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    'add: {"name", "text", "origin"? (where it comes from: a DM boon, an item), '
                    '"level"? 1-20, "uses"? 1-99 per rest, "recharge"? "short"|"long" (default long)}; '
                    "update: only the fields to change, null clears origin/level/uses"
                )
            ),
        ] = None,
        feature_id: Annotated[
            str | None, Field(description="The custom feature's `id` from the sheet (update/remove)")
        ] = None,
    ) -> dict[str, Any]:
        """Add, change or remove a custom feature: something the table has that the books don't
        (homebrew, a DM's boon, an item's ability). It is text only; with `uses` it gets a counter
        that rests restore, spent via update_character feature_used {"custom:<id>": n}."""
        base = f"{_API}/{segment(character_id)}/custom-features"
        if action == "add":
            return await changed("POST", base, {"feature": feature or {}, "version": version})
        if not feature_id:
            raise ToolError("вкажіть feature_id власного вміння")
        if action == "update":
            return await changed(
                "PATCH", f"{base}/{segment(feature_id)}", {"fields": feature or {}, "version": version}
            )
        return await changed("DELETE", f"{base}/{segment(feature_id)}", {"version": version})

    @server.tool(title="Rest", annotations=CHANGES)
    async def rest(character_id: CharacterId, kind: Literal["short", "long"]) -> dict[str, Any]:
        """Take a short or long rest: the site restores what the rules restore and reports it."""
        return await changed("POST", f"{_API}/{segment(character_id)}/rest", {"kind": kind})

    @server.tool(title="Spend a hit die", annotations=CHANGES)
    async def spend_hit_dice(
        character_id: CharacterId,
        die: Annotated[int, Field(description="Die size: 6, 8, 10 or 12")],
        roll: Annotated[int, Field(description="What the player rolled on the die")],
    ) -> dict[str, Any]:
        """Spend one hit die during a short rest; the site adds the Constitution modifier."""
        return await changed("POST", f"{_API}/{segment(character_id)}/hit-dice", {"die": die, "roll": roll})

    @server.tool(title="Level-up options", annotations=READ_ONLY)
    async def level_up_options(
        character_id: CharacterId,
        class_key: Annotated[
            str | None,
            Field(description="One class's plan, also a new class for multiclassing; omit for the current classes"),
        ] = None,
    ) -> dict[str, Any]:
        """What the next level gives: the plans of the character's current classes (or of `class_key`),
        plus which other classes could be added and why not."""
        return _level_up_plans(await api("GET", f"{_API}/{segment(character_id)}/level-up"), class_key)

    @server.tool(title="Level up", annotations=CHANGES)
    async def level_up(
        character_id: CharacterId,
        version: Version,
        choices: Annotated[
            dict[str, Any],
            Field(
                description=(
                    '{"class_key", "hp": {"mode": "average"|"roll", "roll"?}, "subclass_key"?, '
                    '"ability_increases"?: {"str": 1, "con": 1} or "feat_key"?, '
                    '"spells"?: [{"name_en", "level", "class_key"}], "replace_spell"?} '
                    "as level_up_options describes"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Take a level in a class with the choices that level needs."""
        return await changed("POST", f"{_API}/{segment(character_id)}/level-up", {**choices, "version": version})

    @server.tool(title="Choose a class option", annotations=IDEMPOTENT)
    async def set_class_choice(
        character_id: CharacterId,
        version: Version,
        group: Annotated[
            str, Field(description='A group from the sheet\'s open_choices, e.g. "fighter:Fighting Style"')
        ],
        values: list[str],
    ) -> dict[str, Any]:
        """Pick options of a class feature: fighting style, invocations, metamagic, maneuvers…"""
        return await changed(
            "POST",
            f"{_API}/{segment(character_id)}/class-choices",
            {"group": group, "values": values, "version": version},
        )

    @server.tool(title="Choose expertise", annotations=IDEMPOTENT)
    async def set_expertise(
        character_id: CharacterId,
        version: Version,
        skills: Annotated[list[str], Field(description='Skill keys (or "thieves\' tools") with doubled proficiency')],
    ) -> dict[str, Any]:
        """Set the character's expertise picks (rogue, bard)."""
        return await changed(
            "POST", f"{_API}/{segment(character_id)}/expertise", {"expertise": skills, "version": version}
        )

    @server.tool(title="Delete a character", annotations=DESTRUCTIVE)
    async def delete_character(
        character_id: CharacterId,
        name: Annotated[
            str,
            Field(description="The character's exact name from list_characters, confirmed with the player"),
        ],
    ) -> dict[str, Any]:
        """Delete a character for good, with its read-only share link. Irreversible: only on the
        player's explicit request. The name must match, so a wrong id can't delete someone else."""
        listed = await api("GET", _API)
        found = next((item for item in listed.get("items") or [] if item.get("id") == character_id), None)
        if found is None:
            raise ToolError(f"немає персонажа {character_id!r}")
        actual = str(found.get("name") or "")
        if actual.strip().casefold() != name.strip().casefold():
            raise ToolError(f"імʼя не збігається: це «{actual}». Видалення скасовано — уточніть у гравця")
        await api("DELETE", f"{_API}/{segment(character_id)}")
        return {
            "deleted": character_id,
            "name": actual,
            "characters_left": max(int(listed.get("total") or 1) - 1, 0),
            "limit": listed.get("limit"),
        }

    # --- посилання ---------------------------------------------------------

    @server.tool(title="Share link", annotations=DESTRUCTIVE)
    async def share_link(
        character_id: CharacterId,
        action: Annotated[
            Literal["status", "create", "revoke"],
            Field(description="create replaces the old link; revoke turns it off"),
        ] = "status",
    ) -> dict[str, Any]:
        """The read-only link to a character's sheet for the table or the DM."""
        method = {"status": "GET", "create": "POST", "revoke": "DELETE"}[action]
        result = await api(method, f"{_API}/{segment(character_id)}/share")
        return {"url": public_url + result["path"] if result.get("path") else None}

    @server.tool(title="PDF of the sheet", annotations=READ_ONLY)
    async def export_pdf(character_id: CharacterId) -> dict[str, Any]:
        """A download link for the sheet as PDF. The link works for 5 minutes."""
        await api("GET", f"{_API}/{segment(character_id)}/version")
        state = app.state  # type: ignore[attr-defined]
        token = state.auth.link_token(user()) if state.auth_enabled else None
        path = f"{_API}/{segment(character_id)}/export/pdf"
        return {"url": public_url + path + (f"?link={token}" if token else ""), "expires_in": 300 if token else None}

    # --- довідник ----------------------------------------------------------

    @server.tool(title="Search the compendium", annotations=READ_ONLY)
    async def search_compendium(
        query: Annotated[str, Field(description="Words of the name, English or Ukrainian")],
        category: Literal["class", "subclass", "species", "background", "feat", "optionalfeature", "spell", "item"]
        | None = None,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> dict[str, Any]:
        """Find rules entries: spells, items, feats, species… Returns ids for get_compendium_entry."""
        params: dict[str, Any] = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        return compact(await api("GET", "/api/v1/compendium/entries", query=params))

    @server.tool(title="Read a compendium entry", annotations=READ_ONLY)
    async def get_compendium_entry(
        entry_id: Annotated[str, Field(description='e.g. "phb-2014/spell/fireball"')],
    ) -> dict[str, Any]:
        """The full text of a rules entry from the books, with its Ukrainian translation."""
        return compact(await api("GET", f"/api/v1/compendium/entries/{entry_id}"), 4000)

    # --- ресурси й підказки -------------------------------------------------

    @server.resource("character://{character_id}", title="Character sheet", mime_type="text/markdown")
    async def character_sheet(character_id: str) -> str:
        """The sheet as the site's Markdown export."""
        reply = await call(app, user(), "GET", f"{_API}/{segment(character_id)}/export/markdown")
        if not reply.ok:
            raise ResourceError(reply.detail)
        return reply.body.decode("utf-8") if isinstance(reply.body, bytes) else str(reply.body)

    @server.prompt(title="A character from an idea")
    def character_from_idea(idea: str) -> str:
        """Build a character from a one-line concept through the site's wizard."""
        return (
            f"Create a D&D 5e (2014) character on dnd-sheet from this idea: {idea}\n"
            "Use start_character, then get_creation_step and set_creation_step for every step in order, "
            "choosing only from the options the site returns, then finish_character. "
            "Explain each choice briefly and ask me before anything the idea doesn't settle."
        )

    @server.prompt(title="Level-up advice")
    def level_up_advice(character_id: str) -> str:
        """Compare the options of the next level for a character."""
        return (
            f"Read character {character_id} with get_character and its level_up_options. "
            "Compare the reasonable options for the next level for how this character plays, "
            "recommend one, and take the level with level_up only after I agree."
        )

    @server.prompt(title="Apply a session recap")
    def session_recap(character_id: str, recap: str) -> str:
        """Turn a session recap into sheet changes."""
        return (
            f"Here is what happened to character {character_id} this session:\n{recap}\n\n"
            "Read the sheet, list the changes it implies (hit points, spent slots and features, "
            "hit dice, rests, items found or lost, money), ask me to confirm, then apply them "
            "with the sheet tools."
        )

    return server


def _checked(reply: Reply) -> Any:  # noqa: ANN401
    if reply.ok:
        return reply.body
    if reply.status == 409:
        raise ToolError(f"{reply.detail} — прочитайте лист ще раз і повторіть зі свіжою версією")
    raise ToolError(reply.detail)


def _level_up_plans(result: dict[str, Any], class_key: str | None) -> dict[str, Any]:
    """Не всі 13 планів (~75 КБ): лише потрібні, решта класів — одним рядком кожен."""
    plans = result.get("plans") or []
    if class_key:
        wanted = class_key.strip().casefold()
        chosen = [plan for plan in plans if plan.get("class_key") == wanted]
        if not chosen:
            raise ToolError(f"немає плану для класу {class_key!r}")
    else:
        chosen = [plan for plan in plans if not plan.get("is_new_class")]
    shown = {plan.get("class_key") for plan in chosen}
    shaped: dict[str, Any] = {
        key: result.get(key) for key in ("character_id", "name", "version", "total_level", "max_level", "can_level_up")
    }
    shaped["plans"] = compact(chosen)
    shaped["other_classes"] = [
        {
            "class_key": plan.get("class_key"),
            "class_name": plan.get("class_name"),
            "allowed": plan.get("allowed"),
            "blocked_reason": plan.get("blocked_reason"),
        }
        for plan in plans
        if plan.get("class_key") not in shown
    ]
    # Риси з +1 до характеристики потрібні лише тоді, коли цей рівень дає ASI.
    if any((plan.get("asi") or {}).get("pending") for plan in chosen):
        shaped["feat_abilities"] = result.get("feat_abilities")
    return shaped


def _step(result: dict[str, Any]) -> dict[str, Any]:
    draft = result.get("draft") or {}
    return {
        "draft_id": draft.get("id"),
        "revision": draft.get("revision"),
        "step": result.get("step"),
        "locked": result.get("locked"),
        "complete": result.get("complete"),
        "answers": result.get("answers"),
        "options": compact(result.get("options"), 160),
        "steps": draft.get("steps"),
        "errors": result.get("errors"),
    }
