# description: Browse and search Tensai modules from the Limoka catalog
# author: @vsecoder
# requires: aiohttp

"""Limoka — search the community-module catalog from inside Tensai.

The catalog and a list of upstream developer repositories are fetched
over HTTP.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
from pathlib import Path
from typing import Any, cast

import aiohttp
from aiogram import types
from aiogram.types import BufferedInputFile

from tensai import types as tensai_types
from tensai.decorators import (
    CommandInlineContext,
    callback_query,
    command,
    full_command,
)
from tensai.loader import Module
from tensai.main import loader as tensai_loader
from tensai.utils.dialog import (
    Button,
    Dialog,
    DialogContext,
    DynamicMedia,
    Format,
    Media,
    State,
    StatesGroup,
    Url,
    Window,
)
from tensai.utils.inline_button import build_inline_button
from tensai.utils.topics import TopicRegistry

__version__ = "3.0.0"

logger = logging.getLogger(__name__)

LIMOKA_TOPIC = "Limoka"
REPOSITORIES_URL = "https://raw.githubusercontent.com/TensaiUB/limoka/refs/heads/main/repositories.json"


# ──────────────────────────────────────────────────────────────────────────────
# Catalog helpers (pure functions over the raw JSON shape)
# ──────────────────────────────────────────────────────────────────────────────


def _desc(module: dict[str, Any], lang: str = "en") -> str:
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
    name = (module.get("name") or "").lower()
    desc = _desc(module).lower()
    authors = " ".join(module.get("authors") or []).lower()
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
        if name == token:
            score += 1000
        elif name.startswith(token):
            score += 500
        elif token in name:
            score += 200
        for cn in cmd_names:
            if cn == token:
                score += 400
            elif cn.startswith(token):
                score += 150
            elif token in cn:
                score += 50
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
    query = query.strip()
    if len(query) < 2:
        return []
    tokens = query.lower().split()
    scored = [(path, m, _score(m, tokens)) for path, m in modules.items()]
    scored = [(p, m, s) for p, m, s in scored if s > 0]
    scored.sort(key=lambda x: x[2], reverse=True)
    return [(p, m) for p, m, _s in scored[:limit]]


# ──────────────────────────────────────────────────────────────────────────────
# Search dialog
# ──────────────────────────────────────────────────────────────────────────────


class SearchSG(StatesGroup):
    results = State()


def _current_path(ctx: DialogContext) -> str:
    paths: list[str] = list(ctx.data.get("paths") or [])
    idx = int(ctx.data.get("index") or 0)
    if 0 <= idx < len(paths):
        return paths[idx]
    return ""


def _search_text(ctx: DialogContext) -> str:
    mod = cast("Limoka", ctx.module)
    path = _current_path(ctx)
    module = mod._modules.get(path) or {}
    return mod._module_info_text(path, module)


async def _search_getter(ctx: DialogContext) -> dict[str, Any]:
    mod = cast("Limoka", ctx.module)
    path = _current_path(ctx)
    module = mod._modules.get(path) or {}
    banner = module.get("banner")
    if banner:
        return {"banner": Media(source=str(banner), type="photo")}
    return {}


async def _prev_card(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    idx = int(ctx.data.get("index") or 0)
    if idx > 0:
        ctx.data["index"] = idx - 1


async def _next_card(ctx: DialogContext, _cb: types.CallbackQuery) -> None:
    paths: list[str] = list(ctx.data.get("paths") or [])
    idx = int(ctx.data.get("index") or 0)
    if idx + 1 < len(paths):
        ctx.data["index"] = idx + 1


async def _install_current(ctx: DialogContext, cb: types.CallbackQuery) -> None:
    mod = cast("Limoka", ctx.module)
    path = _current_path(ctx)
    if not path:
        await cb.answer()
        return
    try:
        name = await mod._install(path)
        await cb.answer(
            mod.strings("install_success").format(name=name), show_alert=True
        )
    except Exception as exc:
        logger.error("Limoka: install failed for %s: %s", path, exc)
        await cb.answer(mod.strings("install_failed"), show_alert=True)


def _search_layout(ctx: DialogContext) -> list:
    paths: list[str] = list(ctx.data.get("paths") or [])
    idx = int(ctx.data.get("index") or 0)
    total = max(1, len(paths))

    nav: list = []
    if idx > 0:
        nav.append(Button(":e:previous", on_click=_prev_card, style="primary"))
    nav.append(Button(f"{idx + 1}/{total}"))
    if idx < total - 1:
        nav.append(Button(":e:next", on_click=_next_card, style="primary"))

    return [
        nav,
        [
            Button(
                Format("btn_install"),
                on_click=_install_current,
                style="primary",
            )
        ],
    ]


SEARCH_DIALOG = Dialog(
    Window(
        _search_text,
        _search_layout,
        media=DynamicMedia("banner"),
        getter=_search_getter,
        state=SearchSG.results,
    ),
)


# ──────────────────────────────────────────────────────────────────────────────
# Developer-repositories dialog (.modules)
# ──────────────────────────────────────────────────────────────────────────────


class ReposSG(StatesGroup):
    list = State()


def _repos_layout(ctx: DialogContext) -> list:
    repos: list[dict[str, Any]] = list(ctx.data.get("repos") or [])
    rows: list = []
    for r in repos:
        url = str(r.get("url") or "")
        if not url:
            continue
        label = url.replace("https://github.com/", "").rstrip("/") or url
        rows.append([Url(f":e:github {label}", url=url)])
    return rows


REPOS_DIALOG = Dialog(
    Window(
        Format("modules_intro"),
        _repos_layout,
        state=ReposSG.list,
    ),
)


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
            en="<blockquote>:e:cross Usage: <code>{prefix}limoka &lt;query&gt;</code></blockquote>",
            ru="<blockquote>:e:cross Использование: <code>{prefix}limoka &lt;запрос&gt;</code></blockquote>",
        ),
        tensai_types.Translation(
            "loading",
            en="<blockquote>:e:hourglass Loading catalog…</blockquote>",
            ru="<blockquote>:e:hourglass Загружаю каталог…</blockquote>",
        ),
        tensai_types.Translation(
            "load_error",
            en="<blockquote>:e:cross Failed to load catalog. Try again later.</blockquote>",
            ru="<blockquote>:e:cross Не удалось загрузить каталог. Попробуйте позже.</blockquote>",
        ),
        tensai_types.Translation(
            "not_found",
            en="<blockquote>:e:cross No modules found for <code>{query}</code></blockquote>",
            ru="<blockquote>:e:cross Модули по запросу <code>{query}</code> не найдены</blockquote>",
        ),
        tensai_types.Translation(
            "btn_install",
            en=":e:package Install",
            ru=":e:package Установить",
        ),
        tensai_types.Translation(
            "install_success",
            en=":e:check {name} installed!",
            ru=":e:check {name} установлен!",
        ),
        tensai_types.Translation(
            "install_failed",
            en=":e:cross Installation failed",
            ru=":e:cross Ошибка установки",
        ),
        # Inline-stage hint when query is missing.
        tensai_types.Translation(
            "inline_hint_title",
            en="Limoka — search Tensai modules",
            ru="Limoka — поиск модулей Tensai",
        ),
        tensai_types.Translation(
            "inline_hint_description",
            en="Type a few characters to search the catalog",
            ru="Начни печатать, чтобы искать в каталоге",
        ),
        # .modules — developer repositories list.
        tensai_types.Translation(
            "modules_intro",
            en=(
                "<b>:e:github Developer repositories</b>\n"
                "<blockquote>These GitHub repositories feed the Limoka "
                "catalog. Tap to open in browser.</blockquote>"
            ),
            ru=(
                "<b>:e:github Репозитории разработчиков</b>\n"
                "<blockquote>Эти GitHub-репозитории питают каталог "
                "Limoka. Нажми, чтобы открыть в браузере.</blockquote>"
            ),
        ),
        tensai_types.Translation(
            "repos_load_error",
            en="<blockquote>:e:cross Failed to load repositories list.</blockquote>",
            ru="<blockquote>:e:cross Не удалось загрузить список репозиториев.</blockquote>",
        ),
        tensai_types.Translation(
            "module-info",
            en=(
                "<b>:e:folder Module</b> {module_title}\n\n"
                "<i>:e:info {description}</i>\n\n"
                "<b>:e:code Developer:</b> <code>{author}</code>"
            ),
            ru=(
                "<b>:e:folder Модуль</b> {module_title}\n\n"
                "<i>:e:info {description}</i>\n\n"
                "<b>:e:code Разработчик:</b> <code>{author}</code>"
            ),
        ),
        tensai_types.Translation(
            "no-doc",
            en="No description",
            ru="Нет описания",
        ),
        tensai_types.Translation(
            "not-mentioned",
            en="Not mentioned",
            ru="Не указан",
        ),
        # ── Update notifications
        tensai_types.Translation(
            "update_notify",
            en=(
                ":e:bell <b>{module_name}</b> has an update\n\n"
                "<code>{commit_sha}</code> {commit_message}\n"
                "<code>+{added} / -{removed}</code>"
            ),
            ru=(
                ":e:bell <b>{module_name}</b> обновился\n\n"
                "<code>{commit_sha}</code> {commit_message}\n"
                "<code>+{added} / -{removed}</code>"
            ),
        ),
        tensai_types.Translation(
            "btn_view_diff",
            en=":e:eye View diff",
            ru=":e:eye Посмотреть diff",
        ),
        tensai_types.Translation(
            "btn_dismiss",
            en=":e:check Dismiss",
            ru=":e:check Закрыть",
        ),
        tensai_types.Translation(
            "diff_unavailable",
            en="<blockquote>:e:alert Diff not available for this module.</blockquote>",
            ru="<blockquote>:e:alert Diff для этого модуля недоступен.</blockquote>",
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
            key="repositories_url",
            name="Repositories JSON URL",
            default=REPOSITORIES_URL,
            type=tensai_types.StringType(),
            description="URL of the upstream developer repositories index (repositories.json).",
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

    # ── Lifecycle ────────────────────────────────────────────────────────────

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

    # ── Catalog ──────────────────────────────────────────────────────────────

    async def _load_catalog(self) -> bool:
        url = str(self.config.get("modules_url") or "")
        if not url:
            return False
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "Limoka: catalog fetch returned HTTP %s", resp.status
                        )
                        return False
                    data = await resp.json(content_type=None)
            generated_at = (data.get("meta") or {}).get("generated_at")
            if generated_at and generated_at == self._generated_at:
                return True
            prev = self._generated_at
            self._modules = data.get("modules") or {}
            self._generated_at = generated_at
            logger.info("Limoka: catalog updated — %d modules", len(self._modules))
            if prev is not None:
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
                return (
                    await resp.json(content_type=None) if resp.status == 200 else None
                )

    async def _fetch_bytes(self, url: str) -> bytes | None:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                return await resp.read() if resp.status == 200 else None

    # ── Module info renderer ──────────────────────

    def _module_info_text(self, path: str, module: dict[str, Any]) -> str:
        lang = self.get_lang()
        name = module.get("name") or path.split("/")[-1]
        version = str(module.get("version") or "")
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")
        source_url = f"{raw_base}/{path}" if path else ""

        title_line = f"<b>{html.escape(str(name))}</b>"
        if version and source_url:
            title_line += (
                f' <a href="{html.escape(source_url)}">v{html.escape(version)}</a>'
            )
        elif version:
            title_line += f" v{html.escape(version)}"

        handlers = module.get("handlers") or {}
        prefix = self.get_prefix()
        bot_username = self.get_bot_username()
        cmd_lines: list[str] = []
        for h in handlers.get("command") or []:
            cmd_name = h.get("name") or ""
            if not cmd_name:
                continue
            d = html.escape(_handler_desc(h, lang))
            entry = f"<code>{html.escape(prefix)}{html.escape(cmd_name)}</code>"
            if d:
                entry += f" <i>{d}</i>"
            cmd_lines.append(entry)
        for h in handlers.get("inline_command") or []:
            cmd_name = h.get("name") or ""
            if not cmd_name:
                continue
            d = html.escape(_handler_desc(h, lang))
            entry = f"<code>@{html.escape(bot_username)} {html.escape(cmd_name)}</code>"
            if d:
                entry += f" <i>{d}</i>"
            cmd_lines.append(entry)

        commands_block = (
            "\n<blockquote expandable>" + "\n".join(cmd_lines) + "</blockquote>"
            if cmd_lines
            else ""
        )
        module_title = title_line + commands_block

        description = html.escape(_desc(module, lang)) or self.strings("no-doc")
        authors = ", ".join(
            html.escape(a) for a in (module.get("authors") or [])
        ) or self.strings("not-mentioned")

        return self.strings("module-info").format(
            module_title=module_title,
            description=description,
            author=authors,
        )

    # ── Install ──────────────────────────────────────────────────────────────

    async def _install(self, path: str) -> str:
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")
        url = f"{raw_base}/{path}"
        filename = Path(path).name
        content = await self._fetch_bytes(url)
        if not content:
            raise RuntimeError(f"Failed to fetch {url}")
        tensai_loader.modules_dir.mkdir(parents=True, exist_ok=True)
        destination = tensai_loader.modules_dir / filename
        existing = tensai_loader.find_module(Path(filename).stem)
        if existing is not None:
            tensai_loader.unload_module(existing.name)
        source = content.decode("utf-8")
        head = source.splitlines()[:20]
        if not any(line.lstrip().startswith("# source_url:") for line in head):
            source = f"# source_url: {url}\n{source}"
        destination.write_text(source, encoding="utf-8")
        tensai_loader.load_module(destination, source_url=url)
        loaded = tensai_loader.find_module(Path(filename).stem)
        return loaded.name if loaded else Path(filename).stem

    # ── Update notifications ─────────────────────────────────────────────────

    def _installed_limoka_modules(self) -> dict[str, Any]:
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/") + "/"
        result: dict[str, Any] = {}
        for mod_info in tensai_loader.modules.values():
            source_url: str = getattr(mod_info, "source_url", "") or ""
            if source_url.startswith(raw_base):
                catalog_path = source_url[len(raw_base) :]
                if catalog_path in self._modules:
                    result[catalog_path] = mod_info
                continue
            name: str = getattr(mod_info, "name", "") or ""
            if not name:
                continue
            for catalog_path, info in self._modules.items():
                if (info.get("name") or "").lower() == name.lower():
                    result[catalog_path] = mod_info
                    break
        return result

    async def _check_updates(self) -> None:
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")
        diffs_by_key: dict[str, dict] = {}
        try:
            entries = await self._fetch_json(f"{raw_base}/diffs/index.json")
            if isinstance(entries, list):
                diffs_by_key = {e["diff_key"]: e for e in entries if e.get("diff_key")}
        except Exception as exc:
            logger.debug("Limoka: diffs/index.json fetch failed: %s", exc)

        owner_id = self.get_user_me_id()
        if not owner_id:
            return

        notified: dict[str, str] = self.mdb.get("notified_diffs") or {}
        for catalog_path, mod_info in self._installed_limoka_modules().items():
            entry = self._modules.get(catalog_path)
            if not entry:
                continue
            if not (catalog_sha := entry.get("sha256") or ""):
                continue
            if not (installed_sha := getattr(mod_info, "sha256", "") or ""):
                continue
            if catalog_sha == installed_sha:
                continue

            def _path_to_key(path: str) -> str:
                return path.replace("/", "_").replace("\\", "_").removesuffix(".py")

            diff_key = _path_to_key(catalog_path)
            if notified.get(diff_key) == self._generated_at:
                continue

            await self._send_update_notification(
                owner_id,
                diffs_by_key.get(diff_key)
                or {
                    "module_name": entry.get("name") or diff_key,
                    "diff_key": diff_key,
                    "commit_message": "",
                    "commit_sha": "",
                    "added": 0,
                    "removed": 0,
                },
            )
            notified[diff_key] = self._generated_at or ""
        self.mdb.set("notified_diffs", notified)

    async def _resolve_topic(self, owner_id: int) -> tuple[int, int | None] | None:
        try:
            return await TopicRegistry.resolve_destination(
                LIMOKA_TOPIC, owner_id=owner_id
            )
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
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    build_inline_button(
                        text=self.strings("btn_view_diff"),
                        callback_data=f"lm_diff:{diff_key}",
                    ),
                    build_inline_button(
                        text=self.strings("btn_dismiss"),
                        callback_data=f"lm_dismiss:{diff_key}",
                    ),
                ]
            ]
        )
        kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": markup,
        }
        if topic_id is not None:
            kwargs["message_thread_id"] = topic_id
        try:
            await self.bot.send_message(**kwargs)
        except Exception as exc:
            logger.error("Limoka: failed to send update notification: %s", exc)

    # ── Long-lived callback handlers (notification buttons) ─────────────────

    @callback_query(data=lambda d: bool(d and d.startswith("lm_diff:")))
    async def _cb_view_diff(self, cb: types.CallbackQuery) -> None:
        if self.bot is None:
            await cb.answer()
            return
        diff_key = (cb.data or "").split(":", 1)[1]
        raw_base = str(self.config.get("raw_base_url") or "").rstrip("/")
        content = await self._fetch_bytes(f"{raw_base}/diffs/{diff_key}.diff")
        if not content:
            await cb.answer(self.strings("diff_unavailable"), show_alert=True)
            return
        owner_id = self.get_user_me_id()
        dest = await self._resolve_topic(owner_id) if owner_id else None
        doc_kwargs: dict[str, Any] = {
            "document": BufferedInputFile(content, filename=f"{diff_key}.diff")
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
            logger.error("Limoka: failed to send diff: %s", exc)
        await cb.answer()

    @callback_query(data=lambda d: bool(d and d.startswith("lm_dismiss:")))
    async def _cb_dismiss(self, cb: types.CallbackQuery) -> None:
        if isinstance(cb.message, types.Message):
            try:
                await cb.message.delete()
            except Exception:
                pass
        await cb.answer()

    # ── User commands ───────────────────────────────────────────────────────

    @full_command(aliases=["ls", "limoka"])
    async def limoka(self, ctx: CommandInlineContext) -> None:
        """
        en: <query> — search the Limoka catalog (command + inline)
        ru: <запрос> — поиск модулей в каталоге Limoka (команда + инлайн)
        """
        query = ctx.text().strip()

        if ctx.is_chosen and ctx.chosen is not None:
            rid = ctx.chosen.result_id or ""
            if not rid.startswith("lm_inline:"):
                return
            try:
                _prefix, session_key, idx_str = rid.split(":", 2)
                idx = int(idx_str)
            except ValueError:
                return
            sessions: dict[str, list[str]] = self.mdb.get("inline_sessions") or {}
            paths = sessions.get(session_key) or []
            if not paths or idx >= len(paths):
                return
            await self.start_dialog(
                ctx.chosen,
                SEARCH_DIALOG,
                initial_data={"paths": list(paths), "index": idx},
            )
            return

        if ctx.is_inline and ctx.inline_query is not None:
            if len(query) < 2:
                hint = self.make_article(
                    article_id="limoka_hint",
                    title=self.strings("inline_hint_title"),
                    description=self.strings("inline_hint_description"),
                    text=self.strings("no_args").format(prefix=self.get_prefix()),
                )
                await self.inline_articles(ctx.inline_query, [hint], is_personal=False)
                return
            if not self._modules:
                await self._load_catalog()
            results = _search(
                self._modules,
                query,
                limit=int(self.config.get("max_results") or 10),
            )
            if not results:
                await self.answer(
                    ctx.inline_query, inline_results=[], inline_cache_time=30
                )
                return

            session_key = hashlib.md5(query.lower().encode()).hexdigest()[:8]
            sessions: dict[str, list[str]] = self.mdb.get("inline_sessions") or {}
            sessions[session_key] = [p for p, _m in results]
            if len(sessions) > 20:
                sessions = dict(list(sessions.items())[-20:])
            self.mdb.set("inline_sessions", sessions)

            placeholder_kb = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        build_inline_button(
                            text="ㅤ",
                            callback_data="empty",
                            style="primary",
                        )
                    ]
                ]
            )
            loading_text = self.strings("loading")

            articles = [
                self.make_article(
                    article_id=f"lm_inline:{session_key}:{idx}",
                    title=str(module.get("name") or path.split("/")[-1]),
                    description=(_desc(module, self.get_lang()) or path)[:120],
                    text=loading_text,
                    reply_markup=placeholder_kb,
                    thumbnail_url=str(module.get("banner"))
                    if module.get("banner")
                    else None,
                )
                for idx, (path, module) in enumerate(results)
            ]
            await self.inline_articles(ctx.inline_query, articles, is_personal=False)
            return

        # ── Command stage: open the search dialog ────────────────────
        if not ctx.message:
            return
        message = ctx.message

        if not query:
            await self.answer(
                message, self.strings("no_args").format(prefix=self.get_prefix())
            )
            return

        if not self._modules:
            loading = await self.answer(message, self.strings("loading"))
            ok = await self._load_catalog()
            if not ok or not self._modules:
                await self.answer(
                    loading if isinstance(loading, types.Message) else message,
                    self.strings("load_error"),
                )
                return
            message = loading if isinstance(loading, types.Message) else message

        results = _search(
            self._modules,
            query,
            limit=int(self.config.get("max_results") or 10),
        )
        if not results:
            await self.answer(
                message,
                self.strings("not_found").format(query=html.escape(query)),
            )
            return

        await self.start_dialog(
            message,
            SEARCH_DIALOG,
            initial_data={
                "paths": [p for p, _m in results],
                "index": 0,
            },
        )

    @command(aliases=["modules"])
    async def _cmd_modules(self, message: types.Message) -> None:
        """
        en: list developer GitHub repositories that feed the catalog
        ru: список GitHub-репозиториев разработчиков из каталога
        """
        url = str(self.config.get("repositories_url") or REPOSITORIES_URL)
        data = await self._fetch_json(url)
        repos = (data or {}).get("repositories") if isinstance(data, dict) else None
        if not repos:
            await self.answer(message, self.strings("repos_load_error"))
            return
        await self.start_dialog(
            message,
            REPOS_DIALOG,
            initial_data={"repos": list(repos)},
        )
