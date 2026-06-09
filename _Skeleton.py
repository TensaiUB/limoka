# description: Reference module showing every public Tensai API
# author: tensai team
# requires:
#
# This file is a hands-on reference for module authors. Drop a renamed copy
# into ``modules/`` to test it live; each section corresponds to one kind of
# handler or one helper on :class:`Module`. Comments explain *why* each piece
# looks the way it does, not just *what*.
#
# Tip: open this file in an IDE — every helper used below has a docstring,
# so hovering over ``self.answer``, ``self.config.get``, ``Dialog(...)`` etc.
# gives full IntelliSense.

from __future__ import annotations

from aiogram import types

from tensai import types as tensai_types
from tensai.decorators import (
    ArticleDefaults,
    CommandInlineContext,
    business_message,
    callback_query,
    chosen_inline_result,
    command,
    full_command,
    inline_command,
    message,
)
from tensai.loader import Module
from tensai.utils.dialog import (
    Back,
    Button,
    Cancel,
    CopyText,
    Dialog,
    DialogContext,
    Done,
    DynamicMedia,
    Media,
    Switch,
    SwitchCurrent,
    Url,
    WebApp,
    Window,
)

import asyncio
import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# DIALOG — defined at module level so Dialog._registry sees it once
# ------------------------------------------------------------------
# A multi-step inline-button flow. The framework handles state
# (current window, back stack, accumulated user data), persistence in
# mdb, and routing of every ``tnsdlg:*`` callback back into the right
# button via the bundled ``TensaiDialogs`` core module.
#
# We define small async ``on_click`` callbacks first so the dialog
# definition reads top-to-bottom.


async def _on_pick_a(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    """Capture a choice into the dialog's per-conversation accumulator."""
    ctx.data["choice"] = "A"


async def _on_pick_b(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    ctx.data["choice"] = "B"


async def _on_step(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    """Bump a counter on every click — demonstrates that ``Button`` with
    only ``on_click`` re-renders the current window so dynamic ``text``
    reflects the new state."""
    ctx.data["clicks"] = (ctx.data.get("clicks") or 0) + 1


async def _on_finish(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    """Persist accumulated dialog data once the user hits Done.
    ``ctx.module`` gives access to the owning module for mdb / config /
    bot calls."""
    ctx.module.mdb.set("last_dialog_choice", ctx.data.get("choice"))


def _summary(ctx: DialogContext) -> str:
    """Window text built dynamically from accumulated dialog state.
    Closures over ``ctx`` are fine — the framework awaits sync/async
    indifferently via ``inspect.isawaitable``."""
    choice = ctx.data.get("choice", "?")
    clicks = ctx.data.get("clicks", 0)
    return (
        f"<b>Summary</b>\n"
        f"Choice: <code>{choice}</code>\n"
        f"Clicks: <code>{clicks}</code>\n\n"
        f"<i>Press Done to save, Cancel to drop.</i>"
    )


# ------------------------------------------------------------------
# Getter — populates ctx.view for the active window every render
# ------------------------------------------------------------------
# Returned dict is available to the window's text format string and
# to any DynamicMedia(selector=key). Re-run on every render — use it
# for fresh data (HTTP fetches, computed totals), NOT for accumulated
# user input (that goes in ctx.data, persisted across navigation).
async def _summary_getter(ctx: DialogContext) -> dict:
    return {
        "choice": ctx.data.get("choice", "?"),
        "clicks": ctx.data.get("clicks", 0),
        # In a real module you might fetch a prize image here, e.g.
        #   prize_image = Media(source="AgAC...file_id", type="photo")
        "prize_image": Media(
            source="https://placecats.com/300/200",
            type="photo",
        ),
    }


SKELETON_DIALOG = Dialog(
    "skeleton_wizard",
    # ----- Window 1: text + Url + Cancel ----------------------------
    Window(
        "start",
        "<b>Step 1.</b> Pick an option:",
        buttons=[
            [
                Button("Option A", on_click=_on_pick_a, goto="step2"),
                Button("Option B", on_click=_on_pick_b, goto="step2"),
            ],
            Url("Tensai docs", "https://github.com/TensaiUB/tensai"),
            Cancel(),
        ],
    ),
    # ----- Window 2: callable text + non-navigating Button ----------
    Window(
        "step2",
        lambda ctx: (
            f"<b>Step 2.</b> You picked <code>{ctx.data.get('choice', '?')}</code>.\n"
            f"Click 'Step' to demo non-navigating actions: "
            f"<code>{ctx.data.get('clicks', 0)}</code> so far."
        ),
        buttons=[
            Button("Step (no goto)", on_click=_on_step),
            [Button("Next →", goto="confirm"), Back()],
        ],
    ),
    # ----- Window 3: getter + DynamicMedia + format-string text ------
    Window(
        "confirm",
        # Format-string substitution from {**ctx.view, **ctx.data}.
        "<b>Summary</b>\n"
        "Choice: <code>{choice}</code>\n"
        "Clicks: <code>{clicks}</code>\n\n"
        "<i>Press Done to save, Cancel to drop.</i>",
        media=DynamicMedia("prize_image"),  # → ctx.view['prize_image']
        getter=_summary_getter,
        buttons=[[Done(on_click=_on_finish), Back()]],
    ),
)


# ------------------------------------------------------------------
# Showcase dialog — every existing button type in one screen
# ------------------------------------------------------------------
SKELETON_BUTTONS_DIALOG = Dialog(
    "skeleton_buttons_showcase",
    Window(
        "all",
        "<b>Every button type Tensai supports:</b>",
        buttons=[
            # callback-routed
            [Button("Action (.on_click)", on_click=_on_step)],
            # direct-action
            [Url("Url", "https://t.me/tensai_chat")],
            [CopyText("Copy this text", copy_text="copied!")],
            [WebApp("Mini App", "https://example.com/webapp")],
            [Switch("Switch (chat picker)", "skeleton query")],
            [SwitchCurrent("Switch in current chat", "skeleton query")],
            # navigation (also callback-routed)
            [Cancel()],
        ],
    ),
)


class Skeleton(Module):
    """
    en:
        A complete reference module — every public Tensai API in one file.
    ru:
        Полный референсный модуль — все публичные API Tensai в одном файле.
    """

    # ──────────────────────────────────────────────────────────────────
    # 0) Module description (this docstring above)
    # ──────────────────────────────────────────────────────────────────
    # The class docstring is shown in ``.help <Module>`` as the module
    # description. Three accepted forms (mix-and-match within the same
    # docstring is fine):
    #
    #   * Plain string — treated as English, shown to everyone:
    #         \"\"\"A short one-liner about what the module does.\"\"\"
    #
    #   * Per-language blocks — ``xx:`` header on its own line, indented
    #     body. English is the default; other languages are shown to
    #     users with that UI locale (falling back to ``en``):
    #         \"\"\"
    #         en:
    #             Short summary in English.
    #         ru:
    #             Короткое описание на русском.
    #         \"\"\"
    #
    #   * Inline per-language — ``xx: <text>`` on a single line:
    #         \"\"\"
    #         en: Short summary in English.
    #         ru: Короткое описание на русском.
    #         \"\"\"
    #
    # If the class has no docstring, the loader falls back to the file
    # header's ``# description:`` line (parsed the same way).

    # ──────────────────────────────────────────────────────────────────
    # 1) Localised strings — typed form mirrors ModuleConfig
    # ──────────────────────────────────────────────────────────────────
    # ``ModuleStrings(Translation(...), ...)`` validates duplicate keys
    # at import time and lets the IDE catch typos in ``en=`` / ``ru=``
    # kwargs. The plain ``dict`` form still works; pick whichever feels
    # cleaner for the size of your module.
    strings = tensai_types.ModuleStrings(
        tensai_types.Translation(
            "hello",
            en="[e:🎲:5] Hi, <b>{name}</b>!",
            ru="[e:wave] Привет, <b>{name}</b>!",
        ),
        tensai_types.Translation(
            "no_name",
            en="<b>Usage:</b> <code>{prefix}sk_hello &lt;name&gt;</code>",
            ru="<b>Использование:</b> <code>{prefix}sk_hello &lt;имя&gt;</code>",
        ),
        tensai_types.Translation(
            "yes",
            en="[e:check] Confirmed.",
            ru="[e:check] Подтверждено.",
        ),
        tensai_types.Translation(
            "no",
            en="[e:cross] Cancelled.",
            ru="[e:cross] Отменено.",
        ),
        tensai_types.Translation("saved", en="Saved.", ru="Сохранено."),
        tensai_types.Translation(
            "current",
            en="<b>Counter:</b> {n}",
            ru="<b>Счётчик:</b> {n}",
        ),
        tensai_types.Translation(
            "log_pinged",
            en="<i>Sent a heartbeat to the Skeleton topic.</i>",
            ru="<i>Хартбит отправлен в топик Skeleton.</i>",
        ),
    )

    # ──────────────────────────────────────────────────────────────────
    # 2) Typed config — settable via ``.config`` inline UI
    # ──────────────────────────────────────────────────────────────────
    # ``ModuleConfig`` registers persistent options. The ``type=`` field
    # enables type validation + UI hints (boolean toggle, list add/remove,
    # hidden value with show/hide button, regex with cast, …).
    config = tensai_types.ModuleConfig(
        tensai_types.ConfigValue(
            key="enabled",
            name="Enabled",
            default=True,
            type=tensai_types.BoolType(),
            description="Toggle Skeleton module.",
        ),
        tensai_types.ConfigValue(
            key="greeting",
            name="Greeting word",
            default="Hi",
            type=tensai_types.StringType(),
            description="Word to greet with.",
        ),
        tensai_types.ConfigValue(
            key="threshold",
            name="Threshold",
            default=10,
            type=tensai_types.IntType(),
            description="Numeric trigger threshold.",
        ),
        tensai_types.ConfigValue(
            key="ratio",
            name="Ratio",
            default=0.5,
            type=tensai_types.FloatType(),
            description="0.0–1.0 weight for some calc.",
        ),
        tensai_types.ConfigValue(
            key="favourites",
            name="Favourites",
            default=[],
            type=tensai_types.ListType(),
            description="A list — add/remove via the .config UI.",
        ),
        tensai_types.ConfigValue(
            key="api_token",
            name="API token",
            default="",
            type=tensai_types.HiddenType(tensai_types.StringType()),
            description="Secret token; rendered as *** in UI.",
        ),
        tensai_types.ConfigValue(
            key="webhook_url",
            name="Webhook URL",
            default="",
            type=tensai_types.RegexType(
                r"^https?://.+",
                name="url",
                cast=lambda s: s.strip(),
            ),
            description="Must be http(s)://…",
        ),
    )

    # ──────────────────────────────────────────────────────────────────
    # 3) Lifecycle hooks
    # ──────────────────────────────────────────────────────────────────
    # ``on_load`` runs after the loader wired up self.bot/self.db/etc.
    # ``on_unload`` runs when the module is being reloaded or removed —
    # use it to cancel background tasks. Both must be ``async``.

    _task: asyncio.Task | None = None

    async def on_load(self) -> None:
        # Background ticker — purely illustrative.
        self._task = asyncio.create_task(self._tick_forever())
        logger.info("Skeleton loaded; ticker task started.")

    async def on_unload(self) -> None:
        task = self._task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _tick_forever(self) -> None:
        # Demonstrates module-private DB via ``self.mdb``: namespaced so
        # other modules can't trample our keys.
        while True:
            await asyncio.sleep(60)
            current = self.mdb.get("ticks", 0) or 0
            self.mdb.set("ticks", current + 1)

    # ──────────────────────────────────────────────────────────────────
    # 4) A simple command (only_me=True by default — only the owner)
    # ──────────────────────────────────────────────────────────────────
    @command(aliases=["sk_hello", "sk_hi"])
    async def sk_hello(self, msg: types.Message) -> None:
        """
        <name> - greet someone
        """
        # ``self.get_args`` extracts everything after the command word.
        name = self.get_args(msg, raw=True)
        if not isinstance(name, str) or not name.strip():
            await self.answer(
                msg, self.strings("no_name").format(prefix=self.get_prefix())
            )
            return

        # ``escape_html`` so user-supplied text is HTML-safe.
        await self.answer(
            msg, self.strings("hello").format(name=self.escape_html(name))
        )

    # ── Localised docstrings ─────────────────────────────────────────
    # A plain docstring (like ``sk_hello`` above) is treated as English
    # and shown to everyone. For per-language help in ``.help``, use
    # ``xx:`` headers — either inline (``en: text``) or block-style with
    # an indented body. Both forms can be mixed. ``TensaiHelp`` shows
    # the user's language, falling back to ``en`` if missing.
    @command(aliases=["sk_localized"])
    async def sk_localized(self, msg: types.Message) -> None:
        """
        en: <text> - example command with a localized description
        ru: <текст> - пример команды с локализованным описанием
        """
        await self.answer(
            msg, "Localized doc example — check <code>.help Skeleton</code>."
        )

    # ──────────────────────────────────────────────────────────────────
    # 5) kb_confirm + callback handlers (vs. the new dialog framework)
    # ──────────────────────────────────────────────────────────────────
    # For any flow more complex than a single yes/no, prefer the dialog
    # framework (section 12) — kb_confirm is the lightweight option.
    @command(aliases=["sk_confirm"])
    async def sk_confirm(self, msg: types.Message) -> None:
        """
        - ask the user to confirm; replies via inline buttons
        """
        await self.answer(
            msg,
            "Are you sure?",
            reply_markup=self.kb_confirm("sk:yes", "sk:no"),
        )

    @callback_query(data="sk:yes")
    async def _cb_yes(self, callback: types.CallbackQuery) -> None:
        await self.answer(callback, self.strings("yes"))

    @callback_query(data="sk:no")
    async def _cb_no(self, callback: types.CallbackQuery) -> None:
        await self.answer(callback, self.strings("no"))

    # ──────────────────────────────────────────────────────────────────
    # 6) Inline command + ``inline_article`` helper
    # ──────────────────────────────────────────────────────────────────
    # Works as ``@<bot> sk_count`` in any chat.
    @inline_command(aliases=["sk_count"])
    async def _inlinecmd_count(self, query: types.InlineQuery) -> None:
        n = self.mdb.get("ticks", 0) or 0
        # ``inline_article`` collapses InlineQueryResultArticle +
        # InputTextMessageContent boilerplate into one call.
        await self.inline_article(
            query,
            article_id="count",
            title="Skeleton counter",
            description=f"Current value: {n}",
            text=self.strings("current").format(n=n),
        )

    # ──────────────────────────────────────────────────────────────────
    # 7) inline_command + chosen_inline_result two-stage flow
    # ──────────────────────────────────────────────────────────────────
    # Useful when the user has to *pick* a result for the action to
    # actually take effect. Here we let the user save a custom note
    # and the actual write happens only once they tap the article.
    @inline_command(aliases=["sk_note"])
    async def _inlinecmd_note(self, query: types.InlineQuery) -> None:
        parts = (query.query or "").split(maxsplit=1)
        body = parts[1] if len(parts) > 1 else ""
        if not body:
            await self.inline_article(
                query,
                article_id="sk_note_help",
                title="sk_note <text>",
                text="Type your note after the command.",
            )
            return
        await self.inline_article(
            query,
            article_id=f"sk_note:{body[:30]}",
            title="Save note",
            description=body[:60],
            text="<i>Saving note...</i>",
        )

    @chosen_inline_result()
    async def _save_note(self, result: types.ChosenInlineResult) -> None:
        rid = result.result_id or ""
        if not rid.startswith("sk_note:"):
            return
        parts = (result.query or "").split(maxsplit=1)
        if len(parts) < 2:
            return
        self.mdb.set("last_note", parts[1])
        await self.answer(result, self.strings("saved"))

    # ──────────────────────────────────────────────────────────────────
    # 8) Cross-module dispatch via self.invoke
    # ──────────────────────────────────────────────────────────────────
    @command(aliases=["sk_help"])
    async def sk_help(self, msg: types.Message) -> None:
        """
        - delegate to the help system
        """
        # Same as the user typing ``.help Skeleton``. Useful for forwarding
        # an unknown alias, building a chain of commands, or wrapping
        # behaviour with extra checks.
        await self.invoke("help", msg, args="Skeleton")

    # ──────────────────────────────────────────────────────────────────
    # 9) text= and filter= on a watcher
    # ──────────────────────────────────────────────────────────────────
    # ``@message`` without filters fires for every message. Use ``text=``
    # for exact / list / lambda matches and ``filter=`` for arbitrary
    # event predicates. Both are AND-composed.
    @message(
        text=["ping", "пинг"],
        filter=lambda m: m.from_user is not None and m.from_user.is_premium,
        only_me=False,  # public — anyone can trigger this
    )
    async def _premium_pong(self, m: types.Message) -> None:
        # Fires only when message text is exactly "ping" or "пинг" AND
        # the sender is a Telegram Premium user.
        await self.answer(m, "[e:ping] Pong (premium-only)")

    # ──────────────────────────────────────────────────────────────────
    # 10) @full_command — single function, three stages (cmd / inline / chosen)
    # ──────────────────────────────────────────────────────────────────
    # Use this when you want the same logic to run via ``.echo something``,
    # ``@<bot> echo something``, AND tap-to-execute on the chosen inline
    # result. The wrapped function receives a :class:`CommandInlineContext`
    # instead of the raw event; inspect ``ctx.is_command``/``is_inline``/
    # ``is_chosen`` if behaviour needs to differ per stage.
    @full_command(aliases=["sk_echo"])
    async def sk_echo(self, ctx: CommandInlineContext):
        """
        <text> - echo the argument; works as command and inline
        """
        text = await ctx.require_text(no_text="Provide some text to echo.")
        if not text:
            return

        async def do_echo(_event, cmd: str):
            return await ctx.reply_text(f"[e:repeat] {self.escape_html(cmd)}")

        return await ctx.run(
            text,
            action=do_echo,
            prefix="sk_echo",
            article_defaults=ArticleDefaults(
                title="Echo",
                description="Tap to send the echoed text",
            ),
            inline_message_template="[e:repeat] {command}",
        )

    # ──────────────────────────────────────────────────────────────────
    # 11) Bot-side logging helpers — log / log_document / send_general
    # ──────────────────────────────────────────────────────────────────
    # ``self.log`` and ``self.log_document`` send to the per-module
    # forum topic in the bot DM (creating it on first call). Use them
    # for *passive* output — backups, periodic reports, watcher digests
    # — that the user didn't directly ask for. Direct command replies
    # should go to the source chat via ``self.answer`` instead.
    #
    # ``self.send_general`` sends to the General thread (no topic) —
    # use for owner-facing notifications that aren't tied to any module.
    @command(aliases=["sk_log"])
    async def sk_log(self, msg: types.Message) -> None:
        """
        - send a heartbeat to the Skeleton topic
        """
        # Optional: pre-create the topic. ``log`` / ``log_document``
        # auto-create on first call too, but this is useful when you
        # need the topic id up front (e.g. to pin a header message).
        await self.ensure_topic(name="Skeleton")
        await self.log("Heartbeat 🫀", topic_name="Skeleton")
        await self.answer(msg, self.strings("log_pinged"))

    # ──────────────────────────────────────────────────────────────────
    # 12) Window / Dialog framework
    # ──────────────────────────────────────────────────────────────────
    # See ``SKELETON_DIALOG`` at module top for the declaration. The
    # entry point is ``self.start_dialog(event, dialog)``; every button
    # click after that is routed by the bundled ``TensaiDialogs`` core
    # module back into the right ``on_click`` / navigation action.
    @command(aliases=["sk_wizard"])
    async def sk_wizard(self, msg: types.Message) -> None:
        """
        - open the example dialog with three windows (incl. media + getter)
        """
        await self.start_dialog(msg, SKELETON_DIALOG)

    @command(aliases=["sk_buttons"])
    async def sk_buttons(self, msg: types.Message) -> None:
        """
        - showcase every supported inline button type in one window
        """
        await self.start_dialog(msg, SKELETON_BUTTONS_DIALOG)

    @command(aliases=["sk_dialogs_active"])
    async def sk_dialogs_active(self, msg: types.Message) -> None:
        """
        - list this module's currently open dialog instances
        """
        # ``self.dialogs`` is the per-module DialogManager. ``list_active``
        # scans the module's mdb for ``_dialog.*`` keys and returns a
        # snapshot of every open instance — useful for housekeeping.
        active = self.dialogs.list_active()
        if not active:
            await self.answer(msg, "<i>No open dialogs.</i>")
            return
        lines = ["<b>Active dialogs:</b>"]
        for inst in active:
            lines.append(
                f"• <code>{self.escape_html(inst.dialog_id)}</code> @ "
                f"chat=<code>{inst.chat_id}</code> "
                f"msg=<code>{inst.message_id}</code> "
                f"window=<code>{self.escape_html(inst.current or '?')}</code>"
            )
        await self.answer(msg, "\n".join(lines))

    # ──────────────────────────────────────────────────────────────────
    # 13) Keyboard helpers — kb_url, kb_callback, kb_confirm
    # ──────────────────────────────────────────────────────────────────
    @command(aliases=["sk_kb"])
    async def sk_kb(self, msg: types.Message) -> None:
        """
        - showcase the three keyboard helpers
        """
        # Single URL button.
        kb_url = self.kb_url(
            "Open Tensai chat",
            "https://t.me/tensai_chat",
            icon_key="chat",
            style="primary",
        )
        # 2D callback grid — tuples support optional icon_key and style.
        kb_grid = self.kb_callback(
            [
                [
                    ("Left", "sk:nav:left", "arrow_left"),
                    ("Up", "sk:nav:up", "arrow_up"),
                    ("Right", "sk:nav:right", "arrow_right"),
                ],
                [("Cancel", "sk:nav:cancel", "cross", "danger")],
            ]
        )
        # Confirm/cancel preset — same as ``kb_callback`` but with
        # standard ✅ / ❌ labels.
        _ = self.kb_confirm("sk:confirm:yes", "sk:confirm:no")

        await self.answer(msg, "Single URL button:", reply_markup=kb_url)
        await self.answer(msg, "Callback grid:", reply_markup=kb_grid)

    # ──────────────────────────────────────────────────────────────────
    # 14) Business message watcher (private chat as the bot owner)
    # ──────────────────────────────────────────────────────────────────
    # ``@business_message`` fires for every message in chats where the
    # bot has a Telegram Business connection. ``only_me=False`` means
    # senders other than the owner can trigger it too — perfect for
    # auto-replies / triggers based on incoming text.
    @business_message(
        text=lambda t: t.lower().strip() == "!sk_marker",
        only_me=False,
    )
    async def _bismsg_marker(self, m: types.Message) -> None:
        if m.from_user is None or m.chat is None:
            return
        # Avoid replying to ourselves.
        if m.from_user.id == self.get_user_me_id():
            return
        # ``self.send`` posts a fresh message into the same chat without
        # binding to a specific event reply. ``business_connection_id``
        # is auto-propagated when the source event was a business one.
        logger.info("Marker triggered by %s in chat %s", m.from_user.id, m.chat.id)
