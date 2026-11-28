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
- There is no deletion of characters.
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
        for extra in ("rest", "level_up"):
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
                    "notes {section: text}; equip {index: bool}"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Change the play state of a sheet: hit points, spent slots and feature uses, death saves,
        exhaustion, inspiration, notes, equipped items. Returns the recomputed sheet."""
        return await changed("PATCH", f"{_API}/{segment(character_id)}", {**changes, "version": version})

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
                    'species: {"name", "species_key", "subspecies_key", "ability_choices", "spell_choices"}; '
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
        action: Literal["learn", "forget", "prepare"],
        class_key: Annotated[str, Field(description="The class the spell belongs to, e.g. wizard")],
        spells: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    'learn/forget: one spell {"name_en", "level", "entry_id"?}; '
                    "prepare: the whole prepared list for the class"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Learn or forget a spell outside a level-up, or set the day's prepared spells of a class."""
        base = f"{_API}/{segment(character_id)}/spells"
        if action == "prepare":
            return await changed(
                "POST", f"{base}/prepare", {"class_key": class_key, "spells": spells, "version": version}
            )
        if len(spells) != 1:
            raise ToolError("learn і forget — по одному закляттю")
        body = {**spells[0], "class_key": class_key, "version": version}
        return await changed("POST" if action == "learn" else "DELETE", base, body)

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
    async def level_up_options(character_id: CharacterId) -> dict[str, Any]:
        """What the next level gives in each current class and each class the character could add."""
        return compact(await api("GET", f"{_API}/{segment(character_id)}/level-up"))

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
