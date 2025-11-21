# meta developer: @limokanews
# requires: whoosh

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser, OrGroup
from whoosh.query import FuzzyTerm, Wildcard

import aiohttp
import random
import logging
import os
import html
import json
import re
from datetime import datetime
import asyncio

from typing import Union, List, Dict, Any, Optional

from telethon.types import Message
from telethon.errors.rpcerrorlist import WebpageMediaEmptyError
from telethon import events
try:
    from aiogram.utils.exceptions import BadRequest
except ImportError:
    from aiogram.exceptions import TelegramBadRequest as BadRequest

from .. import utils, loader
from ..types import InlineQuery, InlineCall

logger = logging.getLogger("Limoka")

__version__ = (1, 2, 1)


class Search:
    def __init__(self, query, ix):
        self.schema = Schema(
            title=TEXT(stored=True), 
            path=ID(stored=True), 
            content=TEXT(stored=True)
        )
        self.query = query
        self.ix = ix

    def search_module(self):
        with self.ix.searcher() as searcher:
            parser = QueryParser("content", self.ix.schema, group=OrGroup.factory(0.8))
            query = parser.parse(self.query)
            wildcard_query = Wildcard("content", f"*{self.query}*")
            fuzzy_query = FuzzyTerm("content", self.query, maxdist=2, prefixlength=1)

            for search_query in [query, wildcard_query, fuzzy_query]:
                results = searcher.search(search_query)
                if results:
                    return list(set(result["path"] for result in results))
            return []


class LimokaAPI:
    async def get_all_modules(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return json.loads(await response.text())


@loader.tds
class Limoka(loader.Module):
    """Hikka modules are now in one place with easy searching!"""

    strings = {
        "name": "Limoka",
        "wait": (
            "Just wait\n"
            "<emoji document_id=5404630946563515782>🔍</emoji> A search is underway among {count} modules "
            "for the query: <code>{query}</code>\n\n<i>{fact}</i>"
        ),
        "found": (
            "<emoji document_id=5413334818047940135>🔍</emoji> Found module <b>{name}</b> "
            "by query: <b>{query}</b>\n\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Description:</b> {description}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Developer:</b> {username}\n\n"
            "{commands}\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {url}{module_path}</code>"
        ),
        "command_template": "{emoji} <code>{prefix}{command}</code> — {description}\n",
        "emojis": {
            1: "<emoji document_id=5416037945909987712>1️⃣</emoji>",
            2: "<emoji document_id=5413855071731470617>2️⃣</emoji>",
            3: "<emoji document_id=5416068826724850291>3️⃣</emoji>",
            4: "<emoji document_id=5415843998071803071>4️⃣</emoji>",
            5: "<emoji document_id=5415684843763686989>5️⃣</emoji>",
            6: "<emoji document_id=5415975458430796879>6️⃣</emoji>",
            7: "<emoji document_id=5415769763857060166>7️⃣</emoji>",
            8: "<emoji document_id=5416006506749383505>8️⃣</emoji>",
            9: "<emoji document_id=5415963015910544694>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Not found by query: <i>{query}</i></b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>No args</b>",
        "?": "<emoji document_id=5951895176908640647>🔎</emoji> Request too short / not found",
        "no_info": "No information",
        "facts": [
            "<emoji document_id=5472193350520021357>🛡</emoji> The limoka catalog is carefully moderated!",
            "<emoji document_id=5940434198413184876>🚀</emoji> Limoka performance allows you to search for modules quickly!",
        ],
        "inline404": "Not found",
        "inline?": "Request too short / not found",
        "inlinenoargs": "Please, enter query",
        "history": (
            "<emoji document_id=5879939498149679716>🔎</emoji> <b>Your search history:</b>\n"
            "{history}"
        ),
        "filter_menu": "Choose filters",
        "filter_cat": "📑 Filter by Category",
        "apply_filters": "✅ Apply Filters",
        "clear_filters": "🗑 Clear Filters",
        "back_to_results": "🔙 Back to Results",
        "empty_history": "<emoji document_id=5879939498149679716>🔎</emoji> <b>Your search history is empty!</b>",
        "enter_query": "🔍 Enter new search query:",
        "global_search": "<emoji document_id=5413334818047940135>🔍</emoji> Global search for <b>{query}</b> — found <b>{count}</b> modules",
        "change_query": "🔍 Change query",
        "no_modules": "No modules available.",
        "filter_title": "🏷 Filters",
        "category_title": "📂 Categories",
        "selected_categories": "✅ Selected categories: {categories}",
        "no_categories": "No categories found in the module database",
        "select_category": "Select categories for query: <code>{query}</code>\n(You can select multiple)",
        "back": "🔙 Back",
        "category": "📁 {category}",
        "no_category": "No category",
        "global_button": "🌍 Results",
        "filtered_button": "🏷️ Filtered search",
        "inline_search": "🔍 Search in Limoka",
        "inline_no_results": "❌ No modules found",
        "inline_error": "❌ Search error occurred",
        "inline_short_query": "❌ Query too short (min 2 chars)",
        "inline_switch_pm": "💬 Open in chat",
        "inline_switch_pm_text": "🔍 Results for: {query}",
        "inline_start_message": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Search</b>\n\nType module name or keyword",
    }

    strings_ru = {
        "name": "Limoka",
        "wait": (
            "Подождите\n"
            "<emoji document_id=5404630946563515782>🔍</emoji> Идёт поиск среди {count} модулей по запросу: <code>{query}</code>\n\n"
            "<i>{fact}</i>"
        ),
        "found": (
            "<emoji document_id=5413334818047940135>🔍</emoji> Найден модуль <b>{name}</b> "
            "по запросу: <b>{query}</b>\n\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Описание:</b> {description}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Разработчик:</b> {username}\n\n"
            "{commands}\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {url}{module_path}</code>"
        ),
        "command_template": "{emoji} <code>{prefix}{command}</code> — {description}\n",
        "emojis": {
            1: "<emoji document_id=5416037945909987712>1️⃣</emoji>",
            2: "<emoji document_id=5413855071731470617>2️⃣</emoji>",
            3: "<emoji document_id=5416068826724850291>3️⃣</emoji>",
            4: "<emoji document_id=5415843998071803071>4️⃣</emoji>",
            5: "<emoji document_id=5415684843763686989>5️⃣</emoji>",
            6: "<emoji document_id=5415975458430796879>6️⃣</emoji>",
            7: "<emoji document_id=5415769763857060166>7️⃣</emoji>",
            8: "<emoji document_id=5416006506749383505>8️⃣</emoji>",
            9: "<emoji document_id=5415963015910544694>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не найдено по запросу: <i>{query}</i></b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>Нет аргументов</b>",
        "?": "<emoji document_id=5951895176908640647>🔎</emoji> Запрос слишком короткий / не найден",
        "no_info": "Нет информации",
        "facts": [
            "<emoji document_id=5472193350520021357>🛡</emoji> Каталог Limoka тщательно модерируется!",
            "<emoji document_id=5940434198413184876>🚀</emoji> Limoka позволяет искать модули с невероятной скоростью!",
        ],
        "inline404": "Не найдено",
        "inline?": "Запрос слишком короткий / не найден",
        "inlinenoargs": "Введите запрос",
        "history": (
            "<emoji document_id=5879939498149679716>🔎</emoji> <b>История поиска:</b>\n"
            "{history}"
        ),
        "filter_menu": "Выберите фильтры",
        "filter_cat": "📑 Фильтр по категориям",
        "apply_filters": "✅ Применить фильтры",
        "clear_filters": "🗑 Очистить фильтры",
        "back_to_results": "🔙 Вернуться к результатам",
        "empty_history": "<emoji document_id=5879939498149679716>🔎</emoji> <b>История поиска пуста!</b>",
        "enter_query": "🔍 Введите новый поисковый запрос:",
        "global_search": "<emoji document_id=5413334818047940135>🔍</emoji> Глобальный поиск по <b>{query}</b> — найдено <b>{count}</b> модулей",
        "change_query": "🔍 Изменить запрос",
        "no_modules": "Модули недоступны.",
        "filter_title": "🏷 Фильтры",
        "category_title": "📂 Категории",
        "selected_categories": "✅ Выбранные категории: {categories}",
        "no_categories": "Категории не найдены в базе модулей",
        "select_category": "Выберите категории для запроса: <code>{query}</code>\n(Можно выбрать несколько)",
        "back": "🔙 Назад",
        "category": "📁 {category}",
        "no_category": "Без категории",
        "global_button": "🌍 Результаты",
        "filtered_button": "🏷️ Поиск с фильтрами",
        "inline_search": "🔍 Поиск в Limoka",
        "inline_no_results": "❌ Модули не найдены",
        "inline_error": "❌ Ошибка поиска",
        "inline_short_query": "❌ Запрос слишком короткий (мин. 2 символа)",
        "inline_switch_pm": "💬 Открыть в чате",
        "inline_switch_pm_text": "🔍 Результаты для: {query}",
        "inline_start_message": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Поиск</b>\n\nВведите название модуля или ключевое слово",
    }

    def __init__(self):
        self.api = LimokaAPI()
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "limokaurl",
                "https://raw.githubusercontent.com/MuRuLOSE/limoka/refs/heads/main/",
                lambda: "Зеркало (не работает): https://raw.githubusercontent.com/MuRuLOSE/limoka-mirror/refs/heads/main/",
                validator=loader.validators.String(),
            )
        )
        self.name = self.strings["name"]
        self._invalid_banners = set()
        self.fallback_banner = "https://github.com/MuRuLOSE/limoka/raw/main/assets/limoka404.png"

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.api = LimokaAPI()
        self.schema = Schema(
            title=TEXT(stored=True), 
            path=ID(stored=True), 
            content=TEXT(stored=True)
        )

        os.makedirs("limoka_search", exist_ok=True)
        if not os.path.exists("limoka_search/index"):
            self.ix = create_in("limoka_search", self.schema)
        else:
            self.ix = open_dir("limoka_search")

        self._history = self.pointer("history", [])
        self.modules = await self.api.get_all_modules(
            f"{self.config['limokaurl']}modules.json"
        )
        await self._update_index()

    async def _update_index(self):
        writer = self.ix.writer()
        for module_path, module_data in self.modules.items():
            writer.add_document(
                title=module_data["name"],
                path=module_path,
                content=module_data["name"] + " " + (module_data["description"] or "")
            )
            for func in module_data["commands"]:
                for command, description in func.items():
                    writer.add_document(
                        title=module_data["name"],
                        path=module_path,
                        content=f"{command} {description}"
                    )
        writer.commit()

    async def _validate_url(self, url: str) -> str:
        if not url or url in self._invalid_banners:
            return self.fallback_banner
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5) as response:
                    if response.status != 200:
                        self._invalid_banners.add(url)
                        return self.fallback_banner
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not content_type.startswith("image/"):
                        self._invalid_banners.add(url)
                        return self.fallback_banner
                    return url
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self._invalid_banners.add(url)
            return self.fallback_banner

    def generate_commands(self, module_info):
        commands = []
        for i, func in enumerate(module_info["commands"], 1):
            if i > 9:
                commands.append("…\n")
                break
            for command, description in func.items():
                emoji = self.strings["emojis"].get(i, "")
                desc = (description or self.strings["no_info"])
                if len(desc) > 150:
                    desc = desc[:147] + "…"
                commands.append(
                    self.strings["command_template"].format(
                        prefix=self.get_prefix(),
                        command=html.escape(command.replace("cmd", "")),
                        emoji=emoji,
                        description=html.escape(desc),
                    )
                )
        return commands[:5]

    async def _display_filter_menu(self, call: InlineCall, query: str, current_filters: dict):
        categories = current_filters.get("category", [])
        filters_text = self.strings["selected_categories"].format(
            categories=', '.join(categories) if categories else self.strings["no_category"]
        )

        markup = [
            [
                {"text": self.strings["filter_cat"], "callback": self._select_category, "args": (query, current_filters)},
            ],
            [
                {"text": self.strings["apply_filters"], "callback": self._apply_filters, "args": (query, current_filters)},
                {"text": self.strings["clear_filters"], "callback": self._clear_filters, "args": (query,)},
            ],
            [
                {"text": self.strings["back_to_results"], "callback": self._show_results, "args": (query, {})},
            ]
        ]
        
        text = self.strings["filter_menu"].format(query=query) + f"\n\n{filters_text}"
        await call.edit(text, reply_markup=markup)

    async def _select_category(self, call: InlineCall, query: str, current_filters: dict):
        all_categories = set()
        for module_data in self.modules.values():
            all_categories.update(module_data.get("category", ["No category"]))
        categories = sorted(all_categories)

        if not categories:
            await call.edit(self.strings["no_categories"], reply_markup=[
                [{"text": self.strings["back"], "callback": self._display_filter_menu, "args": (query, current_filters)}]
            ])
            return

        selected_categories = current_filters.get("category", [])
        buttons = []
        row = []
        
        for i, cat in enumerate(categories):
            button_text = (self.strings["category"].format(category=cat) if "category" in self.strings else f"📁 {cat}")
            if cat in selected_categories:
                button_text = "✅ " + button_text
            
            row.append({
                "text": button_text,
                "callback": self._toggle_category,
                "args": (query, current_filters, cat)
            })
            
            if (i + 1) % 3 == 0 or i == len(categories) - 1:
                buttons.append(row)
                row = []
        
        buttons.append([
            {"text": self.strings["back"], "callback": self._display_filter_menu, "args": (query, current_filters)}
        ])
        
        text = self.strings["select_category"].format(query=query)
        await call.edit(text, reply_markup=buttons)

    async def _toggle_category(self, call: InlineCall, query: str, current_filters: dict, category: str):
        new_filters = current_filters.copy()
        selected_categories = new_filters.get("category", [])
        
        if category in selected_categories:
            selected_categories.remove(category)
        else:
            selected_categories.append(category)
        
        if selected_categories:
            new_filters["category"] = selected_categories
        else:
            new_filters.pop("category", None)
        
        await self._select_category(call, query, new_filters)

    async def _apply_filters(self, call: InlineCall, query: str, filters: dict):
        await self._show_results(call, query, filters, from_filters=True)

    async def _clear_filters(self, call: InlineCall, query: str):
        await self._show_results(call, query, {}, from_filters=True)

    async def _show_results(self, call: InlineCall, query: str, filters: dict, from_filters: bool = False):
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[])
            return

        if not result:
            markup = [[{"text": self.strings["back"], "callback": self._display_filter_menu, "args": (query, filters)}]] if from_filters else []
            await call.edit(self.strings["404"].format(query=query), reply_markup=markup)
            return

        if filters.get("category"):
            filtered_result = [
                path for path in result 
                if any(cat in self.modules.get(path, {}).get("category", ["No category"]) for cat in filters["category"])
            ]
        else:
            filtered_result = result

        if not filtered_result:
            markup = [[{"text": self.strings["back"], "callback": self._display_filter_menu, "args": (query, filters)}]] if from_filters else []
            await call.edit(self.strings["404"].format(query=query), reply_markup=markup)
            return

        module_path = filtered_result[0]
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, filtered_result, 0, filters)

    async def _enter_query_handler(self, call: InlineCall, query: str, *args, **kwargs):
        """Handler for inline query input"""
        if len(query) <= 1:
            await call.edit(self.strings["?"], reply_markup=[[{"text": "🔄 " + self.strings["change_query"], "callback": self._enter_query}]])
            return
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[[{"text": "🔄 " + self.strings["change_query"], "callback": self._enter_query}]])
            return

        if not result:
            await call.edit(
                self.strings["404"].format(query=query),
                reply_markup=[[{"text": "🔄 " + self.strings["change_query"], "callback": self._enter_query}]]
            )
            return

        module_path = result[0]
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, result, 0, {})

    async def _enter_query(self, call: InlineCall):
        """Show input form for new query"""
        markup = [
            [
                {
                    "text": "✍️ " + self.strings["enter_query"],
                    "input": self.strings["enter_query"],
                    "handler": self._enter_query_handler,
                }
            ],
            [
                {
                    "text": self.strings["back_to_results"],
                    "callback": self._inline_void,
                }
            ]
        ]
        
        await call.edit(
            self.strings["enter_query"],
            reply_markup=markup
        )

    async def _display_module(
        self,
        message_or_call: Union[Message, InlineCall, None],
        module_info: Dict[str, Any],
        module_path: str,
        query: str,
        result: List[Any],
        index: int,
        filters: Dict[str, List[str]]
    ):
        name = html.escape(module_info.get("name") or self.strings["no_info"])
        description = html.escape(module_info.get("description") or self.strings["no_info"])
        dev_username = html.escape(module_info["meta"].get("developer", "Unknown"))
        
        clean_module_path = module_path.replace("\\", "/")
        banner_url = await self._validate_url(module_info["meta"].get("banner"))
        commands = self.generate_commands(module_info)
        page = index + 1

        categories = filters.get("category", [])
        filters_text = self.strings["selected_categories"].format(
            categories=', '.join(html.escape(c) for c in categories) if categories else self.strings["no_category"]
        )

        if len(description) > 300:
            description = description[:297] + "…"

        core_message = self.strings["found"].format(
            query=html.escape(query),
            name=name,
            description=description,
            url=html.escape(self.config["limokaurl"]),
            username=dev_username,
            commands="".join(commands),
            prefix=html.escape(self.get_prefix()),
            module_path=html.escape(clean_module_path),
        )

        full_message = core_message[:4096]

        caption_message = full_message
        if len(caption_message) > 1024:
            safe_query = html.escape(query[:30]) + ("..." if len(query) > 30 else "")
            safe_name = name[:40] + ("..." if len(name) > 40 else "")
            safe_desc = description[:100] + ("…" if len(description) > 100 else "")
            
            caption_message = (
                f"<emoji document_id=5413334818047940135>🔍</emoji> <b>{safe_name}</b>\n"
                f"<b><emoji document_id=5418376169055602355>ℹ️</emoji> Desc:</b> {safe_desc}\n"
                f"<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Dev:</b> {dev_username}\n\n"
                f"<emoji document_id=5411143117711624172>🪄</emoji> <code>{self.get_prefix()}dlm {self.config['limokaurl']}{html.escape(clean_module_path)}</code>"
            )[:1024]

        static_suffix = f"\n{filters_text}"
        if len(caption_message) + len(static_suffix) <= 1024:
            caption_message += static_suffix

        markup = [
            [
                {
                    "text": "⏪" if index > 0 else "🚫",
                    "callback": self._previous_page if index > 0 else self._inline_void,
                    "args": (result, index, query, filters) if index > 0 else (),
                },
                {"text": f"{page}/{len(result)}", "callback": self._inline_void},
                {
                    "text": "⏩" if index + 1 < len(result) else "🚫",
                    "callback": self._next_page if index + 1 < len(result) else self._inline_void,
                    "args": (result, index, query, filters) if index + 1 < len(result) else (),
                },
            ],
            [
                {"text": "🔍 " + self.strings["filter_menu"].split(":")[0], "callback": self._display_filter_menu, "args": (query, filters)},
                {"text": "🔄 " + self.strings["change_query"], "callback": self._enter_query},
            ],
            [
                {"text": self.strings["global_button"], "callback": self._show_global_results, "args": (query,)},
            ]
        ]

        try:
            if message_or_call is None:
                logger.error("message_or_call is None in _display_module")
                return

            if isinstance(message_or_call, Message):
                if banner_url and banner_url != self.fallback_banner:
                    await self.inline.form(
                        text=caption_message,
                        message=message_or_call,
                        reply_markup=markup,
                        photo=banner_url
                    )
                else:
                    await self.inline.form(
                        text=full_message,
                        message=message_or_call,
                        reply_markup=markup
                    )
            else:
                if banner_url and banner_url != self.fallback_banner:
                    await message_or_call.edit(
                        text=caption_message,
                        reply_markup=markup,
                        photo=banner_url
                    )
                else:
                    await message_or_call.edit(
                        text=full_message,
                        reply_markup=markup
                    )
        except (BadRequest, WebpageMediaEmptyError) as e:
            logger.exception(f"Error in _display_module: {e}")
            if message_or_call is None:
                return
                
            try:
                if isinstance(message_or_call, Message):
                    target_message = message_or_call
                elif hasattr(message_or_call, 'message') and isinstance(message_or_call.message, Message):
                    target_message = message_or_call.message
                else:
                    target_message = await self.client.send_message(
                        self._me, 
                        "Error occurred, please try again."
                    )
                    
                await self.inline.form(
                    text=full_message[:4096],
                    message=target_message,
                    reply_markup=markup
                )
            except Exception as inner_e:
                logger.exception(f"Secondary error in error handling: {inner_e}")
                try:
                    if isinstance(message_or_call, Message):
                        await utils.answer(message_or_call, "Error displaying module. Please try again.")
                except Exception:
                    pass

    async def _show_global_results(self, call: InlineCall, query: str):
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[])
            return

        if not result:
            await call.edit(self.strings["404"].format(query=query), reply_markup=[
                [{"text": "🔄 " + self.strings["change_query"], "callback": self._enter_query}]
            ])
            return

        text = self.strings["global_search"].format(
            query=html.escape(query),
            count=len(result)
        )
        buttons = []
        for i, path in enumerate(result[:15]):
            info = self.modules.get(path)
            if not info:
                continue
            name = info.get("name", "Unknown")
            buttons.append([
                {
                    "text": f"{i+1}. {name}",
                    "callback": self._display_module_from_global,
                    "args": (path, query, result)
                }
            ])
        buttons.append([{"text": self.strings["change_query"], "callback": self._enter_query}])

        await call.edit(
            text=text[:4096],
            reply_markup=buttons
        )

    async def _display_module_from_global(self, call: InlineCall, module_path: str, query: str, result: list):
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, result, result.index(module_path), {})

    async def _next_page(self, call: InlineCall, result: list, index: int, query: str, filters: dict):
        if index + 1 >= len(result):
            await call.answer("This is the last page!" if not hasattr(self, "strings_ru") else "Это последняя страница!")
            return

        index += 1
        module_path = result[index]
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, result, index, filters)

    async def _previous_page(self, call: InlineCall, result: list, index: int, query: str, filters: dict):
        if index - 1 < 0:
            await call.answer("This is the first page!" if not hasattr(self, "strings_ru") else "Это первая страница!")
            return

        index -= 1
        module_path = result[index]
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, result, index, filters)

    async def _inline_void(self, call: InlineCall):
        await call.answer()

    @loader.command(ru_doc="[запрос / ничего] — Поиск модулей")
    async def limokacmd(self, message: Message):
        """[query / nothing] - Search modules"""
        args = utils.get_args_raw(message)
        
        if not args:
            markup = [
                [
                    {
                        "text": "✍️ " + self.strings["enter_query"],
                        "input": self.strings["enter_query"],
                        "handler": self._enter_query_handler,
                    }
                ],
                [
                    {
                        "text": self.strings["global_button"],
                        "callback": self._show_global_form,
                        "args": (message,),
                    }
                ]
            ]
            
            await self.inline.form(
                text="<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Search</b>\n\n"
                     "Enter your query to search for Hikka modules:",
                message=message,
                reply_markup=markup,
                photo=self.fallback_banner
            )
            return

        if len(self._history) >= 10:
            self._history = self._history[-9:]
        self._history.append(args)
        self.pointer("history", self._history)

        if len(args) <= 1:
            return await utils.answer(message, self.strings["?"])

        await utils.answer(
            message,
            self.strings["wait"].format(
                count=len(self.modules),
                fact=random.choice(self.strings["facts"]),
                query=args,
            ),
        )

        searcher = Search(args.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            return await utils.answer(message, self.strings["?"])

        if not result:
            return await utils.answer(message, self.strings["404"].format(query=args))

        module_path = result[0]
        module_info = self.modules[module_path]
        await self._display_module(message, module_info, module_path, args, result, 0, {})

    async def _show_global_form(self, call: InlineCall, message: Message):
        markup = [
            [
                {
                    "text": "✍️ " + self.strings["enter_query"],
                    "input": self.strings["enter_query"],
                    "handler": self._global_search_handler,
                    "args": (message,),
                }
            ],
            [
                {
                    "text": "🔙 Back",
                    "callback": self._inline_void,
                }
            ]
        ]
        
        await call.edit(
            "<emoji document_id=5413334818047940135>🔍</emoji> <b>Global Search</b>\n\n"
            "Enter your query to search ALL modules without filters:",
            reply_markup=markup
        )

    async def _global_search_handler(self, call: InlineCall, query: str, message: Message, *args, **kwargs):
        if len(query) <= 1:
            await call.edit(self.strings["?"], reply_markup=[[{"text": "🔄 Try again", "callback": lambda c: self._show_global_form(c, message)}]])
            return
            
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[[{"text": "🔄 Try again", "callback": lambda c: self._show_global_form(c, message)}]])
            return

        if not result:
            await call.edit(
                self.strings["404"].format(query=query),
                reply_markup=[[{"text": "🔄 Try again", "callback": lambda c: self._show_global_form(c, message)}]]
            )
            return

        text = self.strings["global_search"].format(
            query=html.escape(query),
            count=len(result)
        )
        buttons = []
        for i, path in enumerate(result[:15]):
            info = self.modules.get(path)
            if not info:
                continue
            name = info.get("name", "Unknown")
            buttons.append([
                {
                    "text": f"{i+1}. {name}",
                    "callback": self._display_module_from_global,
                    "args": (path, query, result)
                }
            ])
        buttons.append([{"text": "🔄 " + self.strings["change_query"], "callback": lambda c: self._show_global_form(c, message)}])

        await call.edit(
            text=text[:4096],
            reply_markup=buttons
        )

    @loader.command(ru_doc="— Показать историю поиска")
    async def lshistorycmd(self, message: Message):
        """ - Show search history"""
        if not self._history:
            await utils.answer(message, self.strings["empty_history"])
            return

        formatted_history = [f"{i+1}. <code>{utils.escape_html(h)}</code>" for i, h in enumerate(self._history[-10:])]
        await utils.answer(
            message, 
            self.strings["history"].format(
                history='\n'.join(formatted_history)
            )
        )