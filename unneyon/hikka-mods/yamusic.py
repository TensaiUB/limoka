__version__ = (1, 1, 0)
#          █▄▀ ▄▀█ █▀▄▀█ █▀▀ █▄▀ █  █ █▀█ █▀█
#          █ █ █▀█ █ ▀ █ ██▄ █ █ ▀▄▄▀ █▀▄ █▄█ ▄
#                © Copyright 2025
#            ✈ https://t.me/kamekuro

# 🔒 Licensed under CC-BY-NC-ND 4.0 unless otherwise specified.
# 🌐 https://creativecommons.org/licenses/by-nc-nd/4.0
# + attribution
# + non-commercial
# + no-derivatives

# You CANNOT edit, distribute or redistribute this file without direct permission from the author.

# meta banner: https://raw.githubusercontent.com/kamekuro/hikka-mods/main/banners/yamusic.png
# meta pic: https://raw.githubusercontent.com/kamekuro/hikka-mods/main/icons/yamusic.png
# meta developer: @kamekuro_hmods
# packurl: https://raw.githubusercontent.com/kamekuro/hikka-mods/main/langpacks/yamusic.yml
# scope: hikka_only
# scope: hikka_min 1.6.3
# requires: aiohttp asyncio requests pillow==11.2.1 git+https://github.com/MarshalX/yandex-music-api

import aiohttp
import asyncio
import io
import json
import logging
import random
import re
import requests
import string
import yandex_music

import telethon
import textwrap
from PIL import (
    Image, ImageDraw, ImageEnhance,
    ImageFilter, ImageFont
)

from .. import loader, utils


logger = logging.getLogger(__name__)


class YandexMusic():
    token: str
    client: yandex_music.ClientAsync

    def __init__(self, token: str):
        self.client = yandex_music.ClientAsync(token)
        self.token = token
    async def init(self):
        self.client = await self.client.init()
        return self

    # Original code: https://raw.githubusercontent.com/MIPOHBOPOHIH/YMMBFA/main/main.py
    async def _create_ynison_ws(self, ws_proto: dict) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                    "Origin": "http://music.yandex.ru",
                    "Authorization": f"OAuth {self.token}",
                },
            ) as ws:
                response = await ws.receive()
                return json.loads(response.data)

    # Original code: https://raw.githubusercontent.com/MIPOHBOPOHIH/YMMBFA/main/main.py
    async def _get_ynison(self):
        device_id = ''.join(random.choices(string.ascii_lowercase, k=16))
        ws_proto = {
            "Ynison-Device-Id": device_id,
            "Ynison-Device-Info": json.dumps({"app_name": "Chrome", "type": 1}),
        }
        data = await self._create_ynison_ws(ws_proto)
        ws_proto["Ynison-Redirect-Ticket"] = data["redirect_ticket"]
        payload = {
            "update_full_state": {
                "player_state": {
                    "player_queue": {
                        "current_playable_index": -1,
                        "entity_id": "",
                        "entity_type": "VARIOUS",
                        "playable_list": [],
                        "options": {"repeat_mode": "NONE"},
                        "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                        "version": {"device_id": device_id, "version": 9021243204784341000, "timestamp_ms": 0},
                        "from_optional": "",
                    },
                    "status": {
                        "duration_ms": 0,
                        "paused": True,
                        "playback_speed": 1,
                        "progress_ms": 0,
                        "version": {"device_id": device_id, "version": 8321822175199937000, "timestamp_ms": 0},
                    },
                },
                "device": {
                    "capabilities": {"can_be_player": True, "can_be_remote_controller": False, "volume_granularity": 16},
                    "info": {
                        "device_id": device_id,
                        "type": "WEB",
                        "title": "Chrome Browser",
                        "app_name": "Chrome",
                    },
                    "volume_info": {"volume": 0},
                    "is_shadow": True,
                },
                "is_currently_active": False,
            },
            "rid": "ac281c26-a047-4419-ad00-e4fbfda1cba3",
            "player_action_timestamp_ms": 0,
            "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
        }
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                f"wss://{data['host']}/ynison_state.YnisonStateService/PutYnisonState",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                    "Origin": "http://music.yandex.ru",
                    "Authorization": f"OAuth {self.token}",
                }
            ) as ws:
                await ws.send_str(json.dumps(payload))
                response = await ws.receive()
                ynison: dict = json.loads(response.data)
        return ynison
    
    async def get_lyrics(self, track_id: int, with_timecodes: bool = False):
        t = (await self.client.tracks(track_id))[0]
        if with_timecodes:
            if t.lyrics_info.has_available_sync_lyrics:
                lyrics = await self.client.tracks_lyrics(track_id, "LRC")
                return {
                    "text": requests.get(lyrics.download_url).text,
                    "writers": lyrics.writers
                }
        else:
            if t.lyrics_info.has_available_text_lyrics:
                lyrics = await self.client.tracks_lyrics(track_id, "TEXT")
                return {
                    "text": requests.get(lyrics.download_url).text,
                    "writers": lyrics.writers
                }
        return None

    async def get_now_playing(self):
        ynison = await self._get_ynison()
        if len(ynison.get("player_state", {}).get("player_queue", {}).get("playable_list", [])) == 0:
            return {}
        raw_track = ynison["player_state"]["player_queue"]["playable_list"][
            ynison["player_state"]["player_queue"]["current_playable_index"]
        ]
        return {
            "paused": ynison["player_state"]["status"]["paused"],
            "duration_ms": int(ynison["player_state"]["status"]["duration_ms"]),
            "progress_ms": int(ynison["player_state"]["status"]["progress_ms"]),
            "entity_id": ynison["player_state"]["player_queue"]["entity_id"],
            "entity_type": ynison["player_state"]["player_queue"]["entity_type"],
            "playable_id": raw_track["playable_id"],
            "device": [
                x for x in ynison['devices']
                if x['info']['device_id'] == ynison.get('active_device_id_optional', "")
            ],
            "track": (await self.client.tracks(raw_track["playable_id"]))[0]
        } if raw_track['playable_type'] != "LOCAL_TRACK" else {}


@loader.tds
class YaMusicMod(loader.Module):
    """The module for Yandex.Music streaming service"""
    strings = {"name": "YaMusic"}
    strings_ru = {"_cls_doc": "Модуль для стримингового сервиса Яндекс.Музыка"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "token",
                None,
                lambda: self.strings["_cfg"]["token"],
                validator=loader.validators.Hidden()
            ),
            loader.ConfigValue(
                "now_playing_text",
                "<emoji document_id=5474304919651491706>🎧</emoji> <b>{performer} — {title}</b>\n\n" \
                "<emoji document_id=6039404727542747508>⌨️</emoji> <b>Now is listening on</b> " \
                "<code>{device}</code> <b>(</b><emoji document_id=6039454987250044861>🔊</emoji><b> " \
                "{volume}%)</b>\n<emoji document_id=6039630677182254664>🗂</emoji> <b>Playing from:</b> " \
                "{playing_from}\n\n<emoji document_id=5429189857324841688>🎵</emoji> <b>{link} | " \
                "</b><a href=\"https://song.link/ya/{track_id}\"><b>song.link</b></a>",
                lambda: self.strings["_cfg"]["now_playing_text"],
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "autobio",
                "🎧 {artist} - {title}",
                lambda: self.strings["_cfg"]["autobio"],
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "no_playing_bio",
                "Hello!",
                lambda: self.strings["_cfg"]["no_playing_bio"],
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "banner_version",
                "new",
                "Version of track banner (old/new)",
                validator=loader.validators.Choice(["new", "old"])
            )
        )

    async def on_dlmod(self):
        if not self.get("guide_send", False):
            await self.inline.bot.send_message(self._tg_id, self.strings("iguide"))
            self.set("guide_send", True)

    async def client_ready(self, client, db):
        self._client = client
        self._db = db

        me = await self._client.get_me()
        self._premium = me.premium if hasattr(me, "premium") else False
        self.premium_check.start()

        if self.get("autobio", False):
            self.autobio.start()


    @loader.loop(1800)
    async def premium_check(self):
        me = await self._client.get_me()
        self._premium = me.premium if hasattr(me, "premium") else False


    @loader.loop(30)
    async def autobio(self):
        if not self.config['token']:
            self.autobio.stop(); self.set("autobio", False)
            return
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if now and (not now['paused']):
            out = self.config['autobio'].format(
                title=now['track'].title,
                artist=", ".join([x.name for x in now['track'].artists])
            )[:(140 if self._premium else 70)]
            try:
                await self._client(
                    telethon.functions.account.UpdateProfileRequest(about=out)
                )
            except telethon.errors.rpcerrorlist.FloodWaitError as e:
                logger.info(f"Sleeping {max(e.seconds, 60)} because of floodwait")
                await asyncio.sleep(max(e.seconds, 60))


    @loader.command(
        ru_doc="👉 Гайд по получению токена Яндекс.Музыки",
        alias="yg"
    )
    async def yguidecmd(self, message: telethon.types.Message):
        """👉 Guide for obtaining a Yandex.Music token"""
        await utils.answer(message, self.strings("guide"))


    @loader.command(
        ru_doc="👉 Включить/выключить автобио",
        alias="yb"
    )
    async def ybiocmd(self, message: telethon.types.Message):
        """👉 Enable/disable autobio"""

        if (not self.config['token']) and self.get("autobio", False):
            return await utils.answer(message, self.strings("no_token"))

        bio = not self.get("autobio", False)
        self.set("autobio", bio)
        if bio: self.autobio.start()
        else:
            self.autobio.stop()
            try:
                await self._client(
                    telethon.functions.account.UpdateProfileRequest(
                        about=self.config['no_playing_bio'][:(140 if self._premium else 70)]
                    )
                )
            except: pass

        await utils.answer(
            message,
            self.strings("autobio")['e' if bio else 'd']
        )


    @loader.command(
        ru_doc="👉 Получить трек, который играет сейчас (с файлом трека)",
        alias="ynt"
    )
    async def ynowtcmd(self, message: telethon.types.Message):
        """👉 Get now playing track (with track file)"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))
        if now['entity_type'] not in self.strings("queue_types").keys():
            now['entity_type'] = "VARIOUS"

        playlist_name = ""
        if now['entity_type'] == "PLAYLIST":
            playlist = (await ym.client.playlists_list(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/users/" \
                            f"{playlist.owner.login}/playlists/{playlist.kind}" \
                            f"\">{playlist.title}</a></b>"
        if now['entity_type'] == "ALBUM":
            album = (await ym.client.albums(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/album/" \
                            f"{album.id}\">{album.title}</a></b>"
        if now['entity_type'] == "ARTIST":
            artist = (await ym.client.artists(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/artist/" \
                            f"{artist.id}\">{artist.name}</a></b>"

        device, volume = "Unknown Device", "❓"
        if now['device']:
            device=now['device'][0]['info']['title']
            volume=round(now['device'][0]['volume']*100, 2)

        out = self.config['now_playing_text'].format(
            title=now['track'].title,
            performer=", ".join([x.name for x in now['track'].artists]),
            device=device, volume=volume,
            playing_from=self.strings("queue_types").get(now['entity_type']).format(playlist_name),
            track_id=now['track'].id,
            album_id=now['track'].albums[0].id,
            link=f"<a href=\"https://music.yandex.ru/album/{now['track'].albums[0].id}/track/{now['track'].id}\">Яндекс.Музыка</a>"
        )
        await utils.answer(
            message, out+self.strings("downloading")
        )

        audio = io.BytesIO((await utils.run_sync(requests.get, (await ym.client.tracks_download_info(now['track'].id, get_direct_links=True))[0].direct_link)).content)
        audio.name = "audio.mp3"
        await utils.answer(
            message=message, response=out,
            file=audio,
            attributes=([
                telethon.types.DocumentAttributeAudio(
                    duration=now['track'].duration_ms // 1000,
                    title=now['track'].title,
                    performer=", ".join([x.name for x in now['track'].artists])
                )
            ])
        )


    @loader.command(
        ru_doc="👉 Получить баннер трека, который играет сейчас",
        alias="yn"
    )
    async def ynowcmd(self, message: telethon.types.Message):
        """👉 Get now playing track's banner"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))
        if now['entity_type'] not in self.strings("queue_types").keys():
            now['entity_type'] = "VARIOUS"

        playlist_name = ""
        if now['entity_type'] == "PLAYLIST":
            playlist = (await ym.client.playlists_list(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/users/" \
                            f"{playlist.owner.login}/playlists/{playlist.kind}" \
                            f"\">{playlist.title}</a></b>"
        if now['entity_type'] == "ALBUM":
            album = (await ym.client.albums(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/album/" \
                            f"{album.id}\">{album.title}</a></b>"
        if now['entity_type'] == "ARTIST":
            artist = (await ym.client.artists(now['entity_id']))[0]
            playlist_name = f"<b><a href =\"https://music.yandex.ru/artist/" \
                            f"{artist.id}\">{artist.name}</a></b>"

        device, volume = "Unknown Device", "❓"
        if now['device']:
            device=now['device'][0]['info']['title']
            volume=round(now['device'][0]['volume']*100, 2)

        out = self.config['now_playing_text'].format(
            title=now['track'].title,
            performer=", ".join([x.name for x in now['track'].artists]),
            device=device, volume=volume,
            playing_from=self.strings("queue_types").get(now['entity_type']).format(playlist_name),
            track_id=now['track'].id,
            album_id=now['track'].albums[0].id,
            link=f"<a href=\"https://music.yandex.ru/album/{now['track'].albums[0].id}/track/{now['track'].id}\">Яндекс.Музыка</a>"
        )
        await utils.answer(
            message, out+self.strings("uploading_banner")
        )

        lyrics = await ym.get_lyrics(now['track'].id, True)
        func = self.__create_banner if self.config['banner_version'] == "new" else self.__create_banner_old
        file = func(
            now['track'].title, [x.name for x in now['track'].artists],
            now['duration_ms'], now['progress_ms'],
            requests.get(f"https://{now['track'].cover_uri[:-2]}1000x1000").content,
            lyrics['text'] if lyrics else None
        )
        await utils.answer(
            message=message, response=out, file=file
        )


    @loader.command(
        ru_doc="👉 Лайкнуть играющий сейчас трек"
    )
    async def ylikecmd(self, message: telethon.types.Message):
        """👉 Like now playing track's banner"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))

        await ym.client.users_likes_tracks_add(now['track'].id)
        await utils.answer(
            message, self.strings("likes")['liked'].format(
                track_id=now['track'].id, album_id=now['track'].albums[0].id,
                track=f"{', '.join([x.name for x in now['track'].artists])} — {now['track'].title}"
            )
        )

    @loader.command(
        ru_doc="👉 Убрать лайк с играющего сейчас трека"
    )
    async def yunlikecmd(self, message: telethon.types.Message):
        """👉 Unlike now playing track"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))

        await ym.client.users_likes_tracks_remove(now['track'].id)
        await utils.answer(
            message, self.strings("likes")['unliked'].format(
                track_id=now['track'].id, album_id=now['track'].albums[0].id,
                track=f"{', '.join([x.name for x in now['track'].artists])} — {now['track'].title}"
            )
        )

    @loader.command(
        ru_doc="👉 Дизлайкнуть играющий сейчас трек",
        alias="ydis"
    )
    async def ydislikecmd(self, message: telethon.types.Message):
        """👉 Dislike now playing track"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))

        await ym.client.users_dislikes_tracks_add(now['track'].id)
        await utils.answer(
            message, self.strings("likes")['disliked'].format(
                track_id=now['track'].id, album_id=now['track'].albums[0].id,
                track=f"{', '.join([x.name for x in now['track'].artists])} — {now['track'].title}"
            )
        )


    @loader.command(
        ru_doc="👉 Получить текст играющего сейчас трека"
    )
    async def ylyricscmd(self, message: telethon.types.Message):
        """👉 Get lyrics of the now playing track"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()
        now = await ym.get_now_playing()
        if not now:
            return await utils.answer(message, self.strings("there_is_no_playing"))

        lyrics = await ym.get_lyrics(now['playable_id'])
        if lyrics:
            await utils.answer(
                message, self.strings("lyrics").format(
                    track_id=now['track'].id, album_id=now['track'].albums[0].id,
                    track=f"{', '.join([x.name for x in now['track'].artists])} — {now['track'].title}",
                    text=lyrics['text'],
                    writers=", ".join(lyrics['writers'])
                )
            )
        else:
            await utils.answer(
                message, self.strings("no_lyrics").format(
                    track_id=now['track'].id, album_id=now['track'].albums[0].id,
                    track=f"{', '.join([x.name for x in now['track'].artists])} — {now['track'].title}"
                )
            )


    @loader.command(
        ru_doc="<запрос> 👉 Поиск трека в Яндекс.Музыке",
        alias="yq"
    )
    async def ysearchcmd(self, message: telethon.types.Message):
        """<query> 👉 Search track in Yandex.Music"""

        if not self.config['token']:
            return await utils.answer(message, self.strings("no_token"))
        ym = await YandexMusic(self.config['token']).init()

        query = utils.get_args_raw(message)
        if not query:
            await utils.answer(message, self.strings("args"))
            return

        message = await utils.answer(message, self.strings("searching"))

        search = await ym.client.search(query, type_="track")
        if (not search.tracks) or (len(search.tracks.results) == 0):
            return await utils.answer(message, self.strings("404"))

        out = self.strings("search").format(
            title=search.tracks.results[0].title + (
                f" ({search.tracks.results[0].version})" if search.tracks.results[0].version else ""
            ),
            performer=", ".join([x.name for x in search.tracks.results[0].artists]),
            album_id=search.tracks.results[0].albums[0].id, track_id=search.tracks.results[0].id
        )
        message = await utils.answer(message, out+self.strings("downloading"))

        info = await ym.client.tracks_download_info(search.tracks.results[0].id, True)
        link = info[0].direct_link
        audio = None
        audio = io.BytesIO((await utils.run_sync(requests.get, link)).content)
        audio.name = "audio.mp3"

        await utils.answer(
            message=message, response=out,
            file=audio,
            attributes=([
                telethon.types.DocumentAttributeAudio(
                    duration=int(search.tracks.results[0].duration_ms / 1000),
                    title=search.tracks.results[0].title,
                    performer=", ".join([x.name for x in search.tracks.results[0].artists])
                )
            ])
        )


    def __create_banner(
        self,
        title: str, artists: list,
        duration: int, progress: int,
        track_cover: bytes, lyrics: str,
    ):
        # ——————————————— CONSTS ———————————————
        W, H = 1920, 768
        title_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf"
        ).content), 55)
        artist_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf"
        ).content), 46)
        time_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf"
        ).content), 36)
        lyrics_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/YSMusic-HeadlineBold.ttf"
        ).content), 75)
        nlyrics_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/YSMusic-HeadlineBold.ttf"
        ).content), 60)
        def measure(t: str, f: ImageFont.FreeTypeFont, d: ImageDraw.ImageDraw):
            bb = d.textbbox((0, 0), t, font=f)
            return bb[2] - bb[0], bb[3] - bb[1]

        # ——————————————— BACKGROUND ———————————————
        track_cov = Image.open(io.BytesIO(track_cover)).convert("RGBA")
        banner = (
            track_cov.resize((W, W))
            .crop((0, (W-H) // 2, W, ((W-H) // 2) + H))
            .filter(ImageFilter.GaussianBlur(radius=14))
        )
        banner = ImageEnhance.Brightness(banner).enhance(0.3)
        draw = ImageDraw.Draw(banner)

        # ——————————————— TRACK COVER ———————————————
        track_cov = track_cov.resize((H-350, H-350))
        mask = Image.new("L", track_cov.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, track_cov.size[0], track_cov.size[1]), radius=35, fill=255
        )
        track_cov.putalpha(mask)
        track_cov = track_cov.crop(track_cov.getbbox())
        banner.paste(track_cov, (175, 175), mask)

        # ——————————————— ARTIST & TITLE ———————————————
        text_width, _ = measure(f"{', '.join(artists)} — {title}", title_font, draw)
        if text_width > 1680:
            lines = [f"{title}", f"{', '.join(artists)}"]
            lsizes = [measure(lines[0], title_font, draw), measure(lines[1], artist_font, draw)]
        else:
            lines = [f"{', '.join(artists)} — {title}"]
            lsizes = [measure(lines[0], title_font, draw)]
        text_h = sum(th for _, th in lsizes) + (len(lines) - 1)
        text_y = (150 - text_h) / 2
        for i, (l, (lw, lh)) in enumerate(zip(lines, lsizes)):
            if len(lines) == 2 and i == 1:
                ftu = artist_font
            else:
                ftu = title_font
            if lw > 1680:
                while lw > 1680 and len(l) > 3:
                    l = l[:-4] + "…"
                    lw, _ = measure(l, ftu, draw)
            tx = (W - lw) / 2
            draw.text((tx, text_y), l, font=ftu, fill="#A0A0A0")
            text_y += lh + 5

        # ——————————————— LYRICS ———————————————
        if lyrics:
            lyrics_lines = []
            for match in re.finditer(r"\[(\d{2}):(\d{2}\.\d{2})\] (.+)", lyrics):
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3)
                time_ms = int((minutes * 60 + seconds) * 1000)
                lyrics_lines.append((time_ms, text))
            llast, lnext = "", ""
            for i, (time_ms, text) in enumerate(lyrics_lines):
                if time_ms <= progress:
                    llast = text
                    if i+1 < len(lyrics_lines):
                        lnext = lyrics_lines[i+1][1]
                else:
                    break
            y_start = None
            if llast:
                lines = textwrap.wrap(llast, width=23)
                if len(lines) > 3:
                    lines = lines[:3]
                    lines[-1] += "…"
                lines_sizes = [draw.textbbox((0, 0), l, font=lyrics_font) for l in lines]
                line_heights = [bb[3] - bb[1] for bb in lines_sizes]
                total_text_height = sum(line_heights) + (len(lines) - 1) * 10
                y_start = (150 + (track_cov.size[0]-total_text_height)) / 2
                for i, line in enumerate(lines):
                    lw = lines_sizes[i][2] - lines_sizes[i][0]
                    tx = (track_cov.size[0]+325 + ((W-track_cov.size[0]+285) - lw)) / 2
                    draw.text((tx, y_start), line, font=lyrics_font, fill="#FFFFFF")
                    y_start += line_heights[i] + 10
            if lnext:
                next_lines = textwrap.wrap(lnext, width=23)
                if len(next_lines) > 2:
                    next_lines = next_lines[:2]
                    next_lines[-1] += "…"
                next_sizes = [draw.textbbox((0, 0), l, font=nlyrics_font) for l in next_lines]
                next_heights = [bb[3] - bb[1] for bb in next_sizes]
                total_text_height = sum(next_heights) + (len(next_lines) - 1) * 10
                if not y_start:
                    y_start = (150 + (track_cov.size[0] - total_text_height))/2 + 150
                for j, line in enumerate(next_lines):
                    lw = next_sizes[j][2] - next_sizes[j][0]
                    tx = (track_cov.size[0] + 325 + ((W - track_cov.size[0] + 285) - lw)) / 2
                    draw.text((tx, y_start + 40), line, font=nlyrics_font, fill="#A0A0A0")
                    y_start += next_heights[j] + 10

        # ——————————————— STATUS BAR ———————————————
        draw.rounded_rectangle([75, 700, 768 + 1072, 700 + 15], radius=15 // 2, fill="#A0A0A0")
        draw.rounded_rectangle([75, 700, 768 + int(1072 * (progress / duration)), 700 + 15], radius=15 // 2, fill="#FFFFFF")
        draw.text((75, 650), f"{(progress//1000//60):02}:{(progress//1000%60):02}", font=time_font, fill="#FFFFFF")
        draw.text((1745, 650), f"{(duration//1000//60):02}:{(duration//1000%60):02}", font=time_font, fill="#FFFFFF")

        # ——————————————— SAVE ———————————————
        by = io.BytesIO()
        banner.save(by, format="PNG"); by.seek(0)
        by.name = "banner.png"
        return by


    def __create_banner_old(
        self,
        title: str, artists: list,
        duration: int, progress: int,
        track_cover: bytes,
        *args, **kwargs
    ):
        w, h = 1920, 768
        title_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf"
        ).content), 80)
        art_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Regular.ttf"
        ).content), 55)
        time_font = ImageFont.truetype(io.BytesIO(requests.get(
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf"
        ).content), 36)

        # Gen banner (bg)
        track_cov = Image.open(io.BytesIO(track_cover)).convert("RGBA")
        banner = track_cov.resize((w, w)).crop(
            (0, (w-h)//2, w, ((w-h)//2)+h)
        ).filter(ImageFilter.GaussianBlur(radius=14))
        banner = ImageEnhance.Brightness(banner).enhance(0.3)

        # Gen track cover and put to bg
        track_cov = track_cov.resize((banner.size[1]-150, banner.size[1]-150))
        mask = Image.new("L", track_cov.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, track_cov.size[0], track_cov.size[1]), radius=35, fill=255)
        track_cov.putalpha(mask)
        track_cov = track_cov.crop(track_cov.getbbox())
        banner.paste(track_cov, (75, 75), mask)

        # Editing text
        title_lines = textwrap.wrap(title, 23)
        if len(title_lines) > 1:
            title_lines[1] = title_lines[1] + "..." if len(title_lines) > 2 else title_lines[1]
        title_lines = title_lines[:2]
        artists_lines = textwrap.wrap(" • ".join(artists), width=40)
        if len(artists_lines) > 1:
            for index, art in enumerate(artists_lines):
                if "•" in art[-2:]:
                    artists_lines[index] = art[:art.rfind("•") - 1]

        # Put title and artists to banner
        draw = ImageDraw.Draw(banner)
        x, y = 150+track_cov.size[0], 110
        for index, line in enumerate(title_lines):
            draw.text((x, y), line, font=title_font, fill="#FFFFFF")
            if index != len(title_lines)-1:
                y += 70
        x, y = 150+track_cov.size[0], 110*2
        if len(title_lines) > 1: y += 70
        for index, line in enumerate(artists_lines):
            draw.text((x, y), line, font=art_font, fill="#A0A0A0")
            if index != len(artists_lines)-1:
                y += 50

        # Drawing status bar
        draw.rounded_rectangle([768, 650, 768+1072, 650+15], radius=15//2, fill="#A0A0A0")
        draw.rounded_rectangle([768, 650, 768+int(1072*(progress/duration)), 650+15], radius=15//2, fill="#FFFFFF")
        draw.text((768, 600), f"{(progress//1000//60):02}:{(progress//1000%60):02}", font=time_font, fill="#FFFFFF")
        draw.text((1745, 600), f"{(duration//1000//60):02}:{(duration//1000%60):02}", font=time_font, fill="#FFFFFF")

        by = io.BytesIO()
        banner.save(by, format="PNG"); by.seek(0)
        by.name = "banner.png"
        return by