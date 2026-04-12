# █▀▀▄   █▀▄▀█ █▀█ █▀▄ █▀
# ▀▀▀█ ▄ █ ▀ █ █▄█ █▄▀ ▄█

# #### Copyright (c) 2026 Archquise #####

# 💬 Contact: https://t.me/archquise
# 🔒 Licensed under the GNU AGPLv3.
# 📄 LICENSE: https://raw.githubusercontent.com/archquise/Q.Mods/main/LICENSE
# ---------------------------------------------------------------------------------
# Name: Aniliberty
# Description: Searches and gives random anime on the Aniliberty database.
# Author: @quise_m
# ---------------------------------------------------------------------------------
# meta developer: @quise_m
# meta banner: https://raw.githubusercontent.com/archquise/qmods_meta/main/AniLiberty.png
# requires: dacite
# ruff: noqa: D101
# ---------------------------------------------------------------------------------

import logging
from dataclasses import dataclass
from json import JSONDecodeError

import aiohttp
from aiogram.types import CallbackQuery, InlineQueryResultPhoto
from dacite import from_dict

from .. import loader
from ..inline.types import InlineQuery

logger = logging.getLogger(__name__)

BASE_API_URL = "https://aniliberty.top/api/v1"


# Датаклассы для парсинга и хранения json
@dataclass
class Genre:
    name: str


@dataclass
class Name:
    main: str


@dataclass
class Type:
    description: str


@dataclass
class Poster:
    preview: str
    thumbnail: str


@dataclass
class ReleaseInfo:
    id: int
    genres: list[Genre] | None
    name: Name
    is_ongoing: bool
    type: Type
    description: str
    added_in_users_favorites: int
    alias: str
    poster: Poster


@loader.tds
class AniLibertyMod(loader.Module):
    """Ищет и возвращает случайное аниме из базы Aniliberty."""

    strings = {  # noqa: RUF012
        "name": "AniLiberty",
        "announce": "<b>The announcement</b>:",
        "ongoing": "<b>Ongoing</b>:",
        "type": "<b>Type</b>:",
        "genres": "<b>Genres</b>:",
        "favorite": "<b>Favourites &lt;3</b>:",  # &lt; == <
    }

    strings_ru = {  # noqa: RUF012
        "announce": "<b>Анонс</b>:",
        "ongoing": "<b>Онгоинг</b>:",
        "type": "<b>Тип</b>:",
        "genres": "<b>Жанры</b>:",
        "favorite": "<b>Избранное &lt;3</b>:",  # &lt; == <
        "_cls_doc": "Ищет и отправляет случайное аниме из базы AniLiberty",
    }

    async def client_ready(self, client, db):  # noqa: D102, ARG002, ANN001, ANN201
        self._aioclient = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(20))

    async def search_title(self, query) -> list:  # noqa: ANN001
        """Search title in the database."""
        async with self._aioclient.get(
            f"{BASE_API_URL}/app/search/releases?query={query}&include=id%2Cname.main%2Cis_ongoing%2Ctype.description%2Cdescription%2Cadded_in_users_favorites%2Calias%2Cposter.preview%2Cposter.thumbnail"
        ) as resp:
            json_answer = await resp.json()
            results = []
            for i in json_answer:
                obj = from_dict(data_class=ReleaseInfo, data=i)
                results.append(obj)
            return results

    async def get_title(self, release_id: str) -> ReleaseInfo | None:
        """Get full title information."""
        async with self._aioclient.get(
            f"{BASE_API_URL}/anime/releases/{release_id}?include=id%2Cgenres.name%2Cname.main%2Cis_ongoing%2Ctype.description%2Cdescription%2Cadded_in_users_favorites%2Calias%2Cposter.preview%2Cposter.thumbnail"
        ) as resp:
            try:
                json_answer = await resp.json()
                return from_dict(data_class=ReleaseInfo, data=json_answer)
            except JSONDecodeError:
                logger.exception("Ошибка парсинга JSON!")
                return None

    async def get_random_title(self) -> ReleaseInfo | None:
        """Get random title from the database."""
        async with self._aioclient.get(
            f"{BASE_API_URL}/anime/releases/random?limit=1&include=id"
        ) as resp:
            randid = await resp.json()
            """
            Приходится запрашивать по второму кругу, т.к. API в рандомных релизах не отдает жанры, даже если попросить через include
            """
            return await self.get_title(randid[0]["id"])

    @loader.command(
        ru_doc="Возвращает случайный релиз из базы",
        en_doc="Returns a random release from the database",
    )
    async def arandom(self, message) -> None:  # noqa: D102, ANN001
        anime_release = await self.get_random_title()
        genres_str = ""
        for genre in anime_release.genres[:-1]:
            genres_str += f"{genre.name}, "
        genres_str += anime_release.genres[-1].name

        text = f"{anime_release.name.main} \n"
        text += f"{self.strings['ongoing']} {'Да' if anime_release.is_ongoing else 'Нет'}\n\n"
        text += f"{self.strings['type']} {anime_release.type.description}\n"
        text += f"{self.strings['genres']} {genres_str}\n\n"

        text += f"<code>{anime_release.description}</code>\n\n"
        text += f"{self.strings['favorite']} {anime_release.added_in_users_favorites!s}"

        kb = [
            [
                {
                    "text": "Ссылка",
                    "url": f"https://aniliberty.top/anime/releases/release/{anime_release.alias}/episodes",
                },
            ],
        ]

        kb.append([{"text": "🔃 Обновить", "callback": self.inline__update}])
        kb.append([{"text": "🚫 Закрыть", "callback": self.inline__close}])

        await self.inline.form(
            text=text,
            photo=f"https://aniliberty.top{anime_release.poster.preview}",
            message=message,
            reply_markup=kb,
            silent=True,
        )

    @loader.inline_handler(
        ru_doc="Возвращает список найденных по названию тайтлов",
        en_doc="Returns a list of titles found by name",
    )
    async def asearch_inline_handler(self, query: InlineQuery) -> None:  # noqa: D102
        text = query.args

        if not text:
            return

        anime_releases = await self.search_title(text)

        inline_query = []
        for anime_release in anime_releases:
            """ 
            Приходится запрашивать по второму кругу, т.к. API в поиске не отдает жанры, даже если попросить через include
            """
            release_genres = await self.get_title(anime_release.id)
            genres_str = ""
            for genre in release_genres.genres[:-1]:
                genres_str += f"{genre.name}, "
            genres_str += release_genres.genres[-1].name
            release_text = (
                f"{anime_release.name.main}\n"
                f"{self.strings['ongoing']} {'Да' if anime_release.is_ongoing else 'Нет'}\n\n"
                f"{self.strings['type']} {anime_release.type.description}\n"
                f"{self.strings['genres']} {genres_str}\n\n"
                f"<code>{anime_release.description}</code>\n\n"
                f"{self.strings['favorite']} {anime_release.added_in_users_favorites}"
            )

            inline_query.append(
                InlineQueryResultPhoto(
                    id=str(anime_release.id),
                    title=anime_release.name.main,
                    description=anime_release.type.description,
                    caption=release_text,
                    thumbnail_url=f"https://aniliberty.top{anime_release.poster.thumbnail}",
                    photo_url=f"https://aniliberty.top{anime_release.poster.preview}",
                    parse_mode="html",
                ),
            )
        method = query.answer(inline_query, cache_time=0)
        await method.as_(self.inline.bot)

    async def inline__close(self, call: CallbackQuery) -> None:  # noqa: D102
        await call.delete()

    async def inline__update(self, call: CallbackQuery) -> None:  # noqa: D102
        anime_release = await self.get_random_title()
        genres_str = ""
        for genre in anime_release.genres[:-1]:
            genres_str += f"{genre.name}, "
        genres_str += anime_release.genres[-1].name

        text = f"{anime_release.name.main} \n"
        text += f"{self.strings['ongoing']} {'Да' if anime_release.is_ongoing else 'Нет'}\n\n"
        text += f"{self.strings['type']} {anime_release.type.description}\n"
        text += f"{self.strings['genres']} {genres_str}\n\n"

        text += f"<code>{anime_release.description}</code>\n\n"
        text += f"{self.strings['favorite']} {anime_release.added_in_users_favorites!s}"

        kb = [
            [
                {
                    "text": "Ссылка",
                    "url": f"https://aniliberty.top/anime/releases/release/{anime_release.alias}/episodes",
                },
            ],
        ]
        kb.append([{"text": "🔃 Обновить", "callback": self.inline__update}])
        kb.append([{"text": "🚫 Закрыть", "callback": self.inline__close}])

        await call.edit(
            text=text,
            photo=f"https://aniliberty.top{anime_release.poster.preview}",
            reply_markup=kb,
        )
