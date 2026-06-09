# description: Browse and search Tensai modules from the Limoka catalog
# author: @vsecoder
# requires: aiohttp

from __future__ import annotations

import asyncio
import html
import logging
from typing import Any

import aiohttp
from aiogram import types

from tensai import types as tensai_types
from tensai.decorators import callback_query, command, inline_command
from tensai.loader import Module
from tensai.main import loader as tensai_loader
from tensai.utils.topics import TopicRegistry

__version__ = "2.0.0"

logger = logging.getLogger(__name__)

LIMOKA_TOPIC = "Limoka"

# ──────────────────────────────────────────────────────────────────────────────
# Search helpers (module-level, no class state needed)
# ──────────────────────────────────────────────────────────────────────────────

def _desc(module: dict[str, Any], lang: str = "en") -> str:
    """Return a plain-string description for the given language, or empty."""
    raw = module.get("description") or ""
    if isinstance(raw, dict):
        return raw.get(lang) or raw.get("en") or next(iter(raw.values()), "") or ""
    return str(raw)


def _handler_desc(h: dict[str, Any], lang: str = "en") -> str:
    raw = h.get("description") or ""
    if isinstance(raw, dict):
        return raw.get(lang) or raw.get("en") or raw.get("default") or ""
    return str(raw)


def _score(module: dict[str, Any], tokens: list[str]) -> int:
    """Score a module against query tokens. Higher = more relevant."""
    name = (module.get("name") or "").lower()
    desc = _desc(module).lower()
    authors = " ".join(module.get("authors") or []).lower()

    # Collect all command names across all handler types
    cmd_names: list[str] = []
    for hlist in (module.get("handlers") or {}).values():
        for h in hlist:
            if h.get("name"):
                cmd_names.append(h["name"].lower())
            for alias in h.get("aliases") or []:
                cmd_names.append(alias.lower())

    score = 0
    for token in tokens:
        if not token:
            continue
        # Module name
        if name == token:
            score += 1000
        elif name.startswith(token):
            score += 500
        elif token in name:
            score += 200

        # Commands
        for cn in cmd_names:
            if cn == token:
                score += 400
            elif cn.startswith(token):
                score += 150
            elif token in cn:
                score += 50

        # Description + authors (lower weight)
        if token in desc:
            score += 30
        if token in authors:
            score += 20

    return score


def _search(
    modules: dict[str, dict[str, Any]],
    query: str,
    limit: int = 10,
) -> list[tuple[str, dict[str, Any]]]:
    """Return (path, data) pairs sorted by relevance. Empty list if query < 2 chars."""
    query = query.strip()
    if len(query) < 2:
        return []
    tokens = query.lower().split()
    scored = [
        (path, module, _score(module, tokens))
        for path, module in modules.items()
    ]
    scored = [(p, m, s) for p, m, s in scored if s > 0]
    scored.sort(key=lambda x: x[2], reverse=True)
    return [(p, m) for p, m, _ in scored[:limit]]


# ──────────────────────────────────────────────────────────────────────────────
# Card formatter (module-level for reuse in command and inline)
# ──────────────────────────────────────────────────────────────────────────────

def _format_card(
    path: str,
    module: dict[str, Any],
    raw_base_url: str,
    prefix: str = ".",
    bot_username: str = "bot",
    lang: str = "en",
) -> str:
    """Build an HTML module card in the requested format."""
    name = html.escape(module.get("name") or path.split("/")[-1])
    version = module.get("version") or "0.0.0"
    source_url = f"{raw_base_url.rstrip('/')}/{path}"

    # Line 1: bold name + version as a link to source
    line1 = f'<b>{name}</b> <a href="{html.escape(source_url)}">v{html.escape(version)}</a>'

    # Line 2: authors + license in italics
    authors = module.get("authors") or []
    lic = module.get("license")
    by_parts: list[str] = []
    if authors:
        by_parts.append("by " + html.escape(", ".join(authors)))
    if lic:
        by_parts.append(html.escape(lic))
    line2 = "<i>" + "  •  ".join(by_parts) + "</i>" if by_parts else ""

    # Description blockquote — trim to first non-empty paragraph
    desc = _desc(module, lang)
    if desc:
        desc = desc.split("\n\n")[0].strip()
    desc_block = f"\n<blockquote>{html.escape(desc)}</blockquote>" if desc else ""

    # Commands blockquote — only command and inline_command types
    handlers = module.get("handlers") or {}
    cmd_handlers = handlers.get("command") or []
    inline_handlers = handlers.get("inline_command") or []

    cmd_lines: list[str] = []
    for h in cmd_handlers:
        cmd_name = h.get("name") or ""
        if not cmd_name:
            continue
        d = html.escape(_handler_desc(h, lang))
        entry = f"<code>{html.escape(prefix)}{html.escape(cmd_name)}</code>"
        if d:
            entry += f" {d}"
        cmd_lines.append(entry)

    for h in inline_handlers:
        cmd_name = h.get("name") or ""
        if not cmd_name:
            continue
        d = html.escape(_handler_desc(h, lang))
        entry = f"<code>@{html.escape(bot_username)} {html.escape(cmd_name)}</code>"
        if d:
            entry += f" {d}"
        cmd_lines.append(entry)

    cmds_block = (
        "\n<blockquote>" + "\n".join(cmd_lines) + "</blockquote>"
        if cmd_lines
        else ""
    )

    result = line1
    if line2:
        result += "\n" + line2
    result += desc_block
    result += cmds_block
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Module
# ──────────────────────────────────────────────────────────────────────────────

class Limoka(Module):
    """
    en: Browse and search Tensai modules from the Limoka catalog.
    ru: Просматривай и ищи модули Tensai в каталоге Limoka.
    """

    strings = tensai_types.ModuleStrings(
        tensai_types.Translation(
            "no_args",
            en="<blockquote>❌ Usage: <code>{prefix}limoka &lt;query&gt;</code></blockquote>",
            ru="<blockquote>❌ Использование: <code>{prefix}limoka &lt;запрос&gt;</code></blockquote>",
        ),
        tensai_types.Translation(
            "loading",
            en="<blockquote>⏳ Loading catalog…</blockquote>",
            ru="<blockquote>⏳ Загружаю каталог…</blockquote>",
        ),
        tensai_types.Translation(
            "load_error",
            en="<blockquote>❌ Failed to load catalog. Try again later.</blockquote>",
            ru="<blockquote>❌ Не удалось загрузить каталог. Попробуйте позже.</blockquote>",
        ),
        tensai_types.Translation(
            "not_found",
            en="<blockquote>❌ No modules found for <code>{query}</code></blockquote>",
            ru="<blockquote>❌ Модули по запросу <code>{query}</code> не найдены</blockquote>",
        ),
        tensai_types.Translation(
            "results_header",
            en="<blockquote>🔍 <b>{count}</b> module(s) for <code>{query}</code>:</blockquote>",
            ru="<blockquote>🔍 <b>{count}</b> модуль(ей) по запросу <code>{query}</code>:</blockquote>",
        ),
        tensai_types.Translation(
            "empty_catalog",
            en="<blockquote>⚠️ Catalog is not loaded yet. Please wait a moment and try again.</blockquote>",
            ru="<blockquote>⚠️ Каталог ещё не загружен. Подождите немного и попробуйте снова.</blockquote>",
        ),
        tensai_types.Translation(
            "update_notify",
            en=(
                "🔔 <b>{module_name}</b> has an update\n\n"
                "<code>{commit_sha}</code> {commit_message}\n"
                "<code>+{added} / -{removed}</code>"
            ),
            ru=(
                "🔔 <b>{module_name}</b> обновился\n\n"
                "<code>{commit_sha}</code> {commit_message}\n"
                "<code>+{added} / -{removed}</code>"
            ),
        ),
        tensai_types.Translation(
            "btn_view_diff", en="👁 View diff", ru="👁 Посмотреть diff",
        ),
        tensai_types.Translation(
            "btn_dismiss", en="✅ Dismiss", ru="✅ Закрыть",
        ),
        tensai_types.Translation(
            "diff_unavailable",
            en="<blockquote>⚠️ Diff not available for this module.</blockquote>",
            ru="<blockquote>⚠️ Diff для этого модуля недоступен.</blockquote>",
        ),
    )

    config = tensai_types.ModuleConfig(
        tensai_types.ConfigValue(
            key="modules_url",
            name="Modules JSON URL",
            default="https://raw.githubusercontent.com/TensaiUB/limoka/refs/heads/main/modules.json",
            type=tensai_types.StringType(),
            description="URL to fetch modules.json catalog from.",
        ),
        tensai_types.ConfigValue(
            key="raw_base_url",
            name="Raw base URL",
            default="https://raw.githubusercontent.com/TensaiUB/limoka/refs/heads/main/",
            type=tensai_types.StringType(),
            description="Base URL for raw module file links.",
        ),
        tensai_types.ConfigValue(
            key="max_results",
            name="Max results",
            default=10,
            type=tensai_types.IntType(),
            description="Maximum number of search results to show.",
        ),
        tensai_types.ConfigValue(
            key="check_interval",
            name="Check interval (minutes)",
            default=10,
            type=tensai_types.IntType(),
            description="How often to ping the catalog and check for updates.",
        ),
    )

    _modules: dict[str, dict[str, Any]] = {}
    _generated_at: str | None = None
    _refresh_task: asyncio.Task | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_load(self) -> None:
        await self._load_catalog()
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def on_unload(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except (asyncio.CancelledError, Exception):
                pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load_catalog(self) -> bool:
        url = str(self.config.get("modules_url") or "")
        if not url:
            return False
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning("Limoka: catalog fetch returned HTTP %s", resp.status)
                        return False
                    data = await resp.json(content_type=None)

            generated_at = (data.get("meta") or {}).get("generated_at")
            if generated_at and generated_at == self._generated_at:
                return True  # catalog hasn't changed

            prev_generated_at = self._generated_at
            self._modules = data.get("modules") or {}
            self._generated_at = generated_at
            logger.info(
                "Limoka: catalog updated — %d modules (generated_at: %s)",
                len(self._modules),
                generated_at,
            )
            # Only check for module updates when this is not the initial load
            if prev_generated_at is not None:
                await self._check_updates()
            return True
        except Exception as exc:
            logger.error("Limoka: catalog fetch failed: %s", exc)
            return False

    async def _refresh_loop(self) -> None:
        while True:
            interval = int(self.config.get("check_interval") or 10)
            await asyncio.sleep(max(interval, 1) * 60)
            await self._load_catalog()

    async def _fetch_json(self, url: str) -> Any:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)

    async def _fetch_bytes(self, url: str) -> bytes | None:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.read()

    def _installed_limoka_modules(self) -> dict[str, Any]:
        """Return {catalog_path: ModuleInfo} for modules installed from this Limoka instance.

        Matches by source_url: if the module's source_url starts with raw_base_url,
        we extract the catalog path and return it.

        Falls back to name-based matching for modules loaded before source_url support
        was added to the Tensai loader (source_url field absent or empty).
        """
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/") + "/"
        result: dict[str, Any] = {}

        for mod_info in tensai_loader.modules.values():
            source_url: str = getattr(mod_info, "source_url", "") or ""

            if source_url.startswith(raw_base):
                # Exact match: strip base URL to recover catalog path
                catalog_path = source_url[len(raw_base):]
                if catalog_path in self._modules:
                    result[catalog_path] = mod_info
                continue

            # Fallback: match by module name against catalog keys
            name: str = getattr(mod_info, "name", "") or ""
            if not name:
                continue
            for catalog_path, catalog_info in self._modules.items():
                if (catalog_info.get("name") or "").lower() == name.lower():
                    result[catalog_path] = mod_info
                    break

        return result

    async def _check_updates(self) -> None:
        """Compare installed module sha256 against catalog; notify on mismatch."""
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")

        # Load diff metadata (commit message, +/- lines) — best-effort
        diffs_by_key: dict[str, dict] = {}
        try:
            entries = await self._fetch_json(f"{raw_base}/diffs/index.json")
            if isinstance(entries, list):
                for e in entries:
                    key = e.get("diff_key") or ""
                    if key:
                        diffs_by_key[key] = e
        except Exception as exc:
            logger.debug("Limoka: diffs/index.json fetch failed: %s", exc)

        owner_id = self.get_user_me_id()
        if not owner_id:
            return

        notified: dict[str, str] = self.mdb.get("notified_diffs") or {}
        installed = self._installed_limoka_modules()

        for catalog_path, mod_info in installed.items():
            catalog_entry = self._modules.get(catalog_path)
            if not catalog_entry:
                continue

            catalog_sha = catalog_entry.get("sha256") or ""
            installed_sha: str = getattr(mod_info, "sha256", "") or ""

            # If both sha256 values are known, compare them; otherwise skip
            if not catalog_sha or not installed_sha:
                continue
            if catalog_sha == installed_sha:
                continue

            # Module is outdated — find diff metadata if available
            from limoka.parser.differ import _path_to_key
            diff_key = _path_to_key(catalog_path)

            if notified.get(diff_key) == self._generated_at:
                continue  # already notified about this version

            diff_entry = diffs_by_key.get(diff_key) or {
                "module_name": catalog_entry.get("name") or diff_key,
                "diff_key": diff_key,
                "commit_message": "",
                "commit_sha": "",
                "added": 0,
                "removed": 0,
            }
            await self._send_update_notification(owner_id, diff_entry)
            notified[diff_key] = self._generated_at or ""

        self.mdb.set("notified_diffs", notified)

    async def _resolve_topic(self, owner_id: int) -> tuple[int, int | None] | None:
        """Return (chat_id, topic_id) for the Limoka topic, or None on failure."""
        try:
            return await TopicRegistry.resolve_destination(LIMOKA_TOPIC, owner_id=owner_id)
        except Exception as exc:
            logger.error("Limoka: failed to resolve topic: %s", exc)
            return None

    async def _send_update_notification(
        self, owner_id: int, entry: dict[str, Any]
    ) -> None:
        if self.bot is None:
            return

        dest = await self._resolve_topic(owner_id)
        if dest is None:
            return
        chat_id, topic_id = dest

        diff_key = entry.get("diff_key") or ""
        text = self.strings("update_notify").format(
            module_name=html.escape(entry.get("module_name") or ""),
            commit_sha=html.escape(entry.get("commit_sha") or ""),
            commit_message=html.escape(entry.get("commit_message") or ""),
            added=entry.get("added") or 0,
            removed=entry.get("removed") or 0,
        )

        markup = types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(
                text=self.strings("btn_view_diff"),
                callback_data=f"lm_diff:{diff_key}",
            ),
            types.InlineKeyboardButton(
                text=self.strings("btn_dismiss"),
                callback_data=f"lm_dismiss:{diff_key}",
            ),
        ]])

        kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text, "reply_markup": markup}
        if topic_id is not None:
            kwargs["message_thread_id"] = topic_id

        try:
            await self.bot.send_message(**kwargs)
        except Exception as exc:
            logger.error("Limoka: failed to send update notification: %s", exc)

    def _do_search(self, query: str) -> list[tuple[str, dict[str, Any]]]:
        limit = int(self.config.get("max_results") or 10)
        return _search(self._modules, query, limit=limit)

    def _card(self, path: str, module: dict[str, Any]) -> str:
        return _format_card(
            path,
            module,
            raw_base_url=str(self.config.get("raw_base_url") or ""),
            prefix=self.get_prefix(),
            bot_username=self.get_bot_username(),
            lang=self.get_lang(),
        )

    # ── Callback handlers ─────────────────────────────────────────────────────

    @callback_query(data=lambda d: bool(d and d.startswith("lm_diff:")))
    async def _cb_view_diff(self, cb: types.CallbackQuery) -> None:
        if self.bot is None:
            await cb.answer()
            return

        diff_key = (cb.data or "").split(":", 1)[1]
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")
        diff_url = f"{raw_base}/diffs/{diff_key}.diff"

        try:
            content = await self._fetch_bytes(diff_url)
        except Exception:
            content = None

        if not content:
            await cb.answer(self.strings("diff_unavailable"), show_alert=True)
            return

        owner_id = self.get_user_me_id()
        dest = await self._resolve_topic(owner_id) if owner_id else None

        from aiogram.types import BufferedInputFile
        doc_kwargs: dict[str, Any] = {
            "document": BufferedInputFile(content, filename=f"{diff_key}.diff"),
        }
        if dest is not None:
            chat_id, topic_id = dest
            doc_kwargs["chat_id"] = chat_id
            if topic_id is not None:
                doc_kwargs["message_thread_id"] = topic_id
        else:
            doc_kwargs["chat_id"] = cb.from_user.id

        try:
            await self.bot.send_document(**doc_kwargs)
        except Exception as exc:
            logger.error("Limoka: failed to send diff document: %s", exc)

        await cb.answer()

    @callback_query(data=lambda d: bool(d and d.startswith("lm_dismiss:")))
    async def _cb_dismiss(self, cb: types.CallbackQuery) -> None:
        if cb.message:
            try:
                await cb.message.delete()
            except Exception:
                await cb.answer()
        else:
            await cb.answer()

    # ── Commands ──────────────────────────────────────────────────────────────

    @command(aliases=["ls", "limoka"])
    async def _cmd_limoka(self, message: types.Message) -> None:
        """
        en: <query> — search modules in the Limoka catalog
        ru: <запрос> — поиск модулей в каталоге Limoka
        """
        query = self.get_args(message, raw=True)
        if not query or not query.strip():
            await self.answer(
                message,
                self.strings("no_args").format(prefix=self.get_prefix()),
            )
            return

        if not self._modules:
            msg = await self.answer(message, self.strings("loading"))
            ok = await self._load_catalog()
            if not ok or not self._modules:
                await self.answer(msg, self.strings("load_error"))
                return
            # Replace the loading message with results
            message = msg

        results = self._do_search(query.strip())
        if not results:
            await self.answer(
                message,
                self.strings("not_found").format(query=html.escape(query.strip())),
            )
            return

        if len(results) == 1:
            path, module = results[0]
            await self.answer(message, self._card(path, module))
            return

        # Multiple results — header list, then first card
        header = self.strings("results_header").format(
            count=len(results), query=html.escape(query.strip())
        )
        lines = [header]
        for i, (path, module) in enumerate(results, 1):
            name = html.escape(module.get("name") or path.split("/")[-1])
            desc = _desc(module, self.get_lang())
            line = f"{i}. <b>{name}</b>"
            if desc:
                line += f" — <i>{html.escape(desc[:80])}</i>"
            lines.append(line)

        await self.answer(message, "\n".join(lines))

    # ── Inline ────────────────────────────────────────────────────────────────

    @inline_command(aliases=["ls", "limoka"])
    async def _inlinecmd_limoka(self, query: types.InlineQuery) -> None:
        """
        en: <query> — search Limoka modules inline
        ru: <запрос> — инлайн-поиск модулей Limoka
        """
        q = (query.query or "").strip()
        if len(q) < 2:
            await self.answer(query, inline_results=[], inline_cache_time=0)
            return

        results = self._do_search(q)
        if not results:
            await self.answer(query, inline_results=[], inline_cache_time=30)
            return

        raw_base = str(self.config.get("raw_base_url") or "")
        prefix = self.get_prefix()
        bot_username = self.get_bot_username()
        lang = self.get_lang()
        articles: list[types.InlineQueryResultArticle] = []

        for path, module in results:
            name = module.get("name") or path.split("/")[-1]
            desc = _desc(module, lang)
            article_id = path.replace("/", "_").replace(".", "_")

            articles.append(
                types.InlineQueryResultArticle(
                    id=article_id,
                    title=name,
                    description=desc[:120] if desc else path,
                    input_message_content=types.InputTextMessageContent(
                        message_text=_format_card(
                            path, module,
                            raw_base_url=raw_base,
                            prefix=prefix,
                            bot_username=bot_username,
                            lang=lang,
                        ),
                        parse_mode="HTML",
                        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                    ),
                )
            )

        await self.answer(
            query,
            inline_results=articles,
            inline_is_personal=False,
            inline_cache_time=60,
        )
