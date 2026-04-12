# █▀▀▄   █▀▄▀█ █▀█ █▀▄ █▀
# ▀▀▀█ ▄ █ ▀ █ █▄█ █▄▀ ▄█

# #### Copyright (c) 2026 Archquise #####

# 💬 Contact: https://t.me/archquise
# 🔒 Licensed under the GNU AGPLv3.
# 📄 LICENSE: https://raw.githubusercontent.com/archquise/Q.Mods/main/LICENSE
# ---------------------------------------------------------------------------------
# Name: YTDL
# Description: Downloads and sends audio/video from YouTube
# Author: @quise_m
# ---------------------------------------------------------------------------------
# meta developer: @quise_m
# meta banner: https://raw.githubusercontent.com/archquise/qmods_meta/main/ytdl.png
# requires: yt_dlp ffmpeg
# ---------------------------------------------------------------------------------

import logging
import os
import platform
import re
import shutil
import zipfile
from http import HTTPStatus

import aiofiles
import aiohttp
from yt_dlp import YoutubeDL

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class YTDLMod(loader.Module):
    """Downloads and sends audio/video from YouTube."""

    strings = {  # noqa: RUF012
        "name": "YTDL",
        "_cls_doc": "Downloads and sends audio/video from YouTube",
        "invalid_args": "<emoji document_id=5854929766146118183>❌</emoji> There is no arguments or they are invalid",  # noqa: E501
        "downloading": "<emoji document_id=5215484787325676090>🕐</emoji> Downloading...",  # noqa: E501
        "done": "<emoji document_id=5854762571659218443>✅</emoji> Done!",
        "cookie_desc": "Cookie account (helps downloading video with strict age rating restricrions)",  # noqa: E501
        "deno_err": '<tg-emoji emoji-id=5879813604068298387>❗️</tg-emoji> <b>Error!</b> The <a href="http://deno.land/">Deno</a> JavaScript engine was not install automatically.\nThis is a required dependency for <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> (a library for downloading video/audio) to work correctly.\n\n<b>To continue, you need to install the engine manually, or resolve any issues preventing automatic installation and restart the userbot.</b>',  # noqa: E501
        "err": "<tg-emoji emoji-id=5879813604068298387>❗️</tg-emoji> <b>Error!</b>\n\nAdditional info: {}",  # noqa: E501
    }

    strings_ru = {  # noqa: RUF012
        "_cls_doc": "Скачивает и отправляет аудио/видео с Ютуба",
        "invalid_args": "<emoji document_id=5854929766146118183>❌</emoji> Нет аргументов или они неверны",  # noqa: E501
        "downloading": "<emoji document_id=5215484787325676090>🕐</emoji> Скачиваю...",
        "done": "<emoji document_id=5854762571659218443>✅</emoji> Готово!",
        "cookie_desc": "Куки аккаунта (помогает скачивать видео с жесткими возрастными ограничениями)",  # noqa: E501, RUF001
        "deno_err": '<tg-emoji emoji-id=5879813604068298387>❗️</tg-emoji> <b>Ошибка!</b> JS-движок <a href="http://deno.land/">Deno</a> не установился автоматически.\nЭто необходимая зависимость для корректной работы <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> (библиотека для скачивания видео/аудио).\n\n<b>Для продолжения вам необходимо установить движок вручную, или устранить препятствия для автоматической установки и перезагрузить юзербота.</b>',  # noqa: E501
        "err": "<tg-emoji emoji-id=5879813604068298387>❗️</tg-emoji> <b>Ошибка!</b>\n\nДоп.информация: {}",  # noqa: E501, RUF001
    }

    deno_error = (
        "Deno wasn't installed in auto-mode.",
        "Please, install it manually or resolve the issue and reboot userbot.",
    )

    def _validate_url(self, url: str) -> bool:
        """Validate URL format."""
        if not url:
            return False

        url_pattern = re.compile(
            r"^(?:https?://)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be|music\.youtube\.com)/(?:watch\?v=|playlist\?list=|channel/|@|live/|shorts/)?[\w-]+",
            re.IGNORECASE,
        )

        return url_pattern.match(url) is not None

    async def get_target(self) -> str:
        """Check OS and processor architecture and return right postfix."""
        system = platform.system()
        machine = platform.machine().lower()

        if system == "Windows":
            return "Windows"

        if system == "Darwin":
            return (
                "aarch64-apple-darwin" if machine == "arm64" else "x86_64-apple-darwin"
            )

        if system == "Linux":
            return (
                "aarch64-unknown-linux-gnu"
                if machine in ("aarch64", "arm64")
                else "x86_64-unknown-linux-gnu"
            )

        return "x86_64-unknown-linux-gnu"

    def _get_deno(self) -> str | None:
        if not (source := self.get("deno_source")) or source == "install_failed" or not os.path.exists(source):
            logger.critical(self.deno_error)
            return None
        return source


    def __init__(self):  # noqa: ANN204, D107
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "youtube_cookie",
                None,
                lambda: self.strings["cookie_desc"],
                validator=loader.validators.Hidden(),
            ),
        )

    async def client_ready(self, client, db):  # noqa: ANN001, ANN201, D102, ARG002

        deno_which = shutil.which("deno", path=os.environ.get("PATH", "") + os.pathsep + os.getcwd())  # noqa: E501

        if deno_which:
            self.set("deno_source", deno_which)
            return

        logger.warning("Deno is not installed, attempting installation...")
        target = await self.get_target()
        if target == "Windows":
            logger.critical(
                "Windows platform is unsupported, please, unload the module.",
            )
            return
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(20)) as session:
            download_link = f"https://github.com/denoland/deno/releases/latest/download/deno-{target}.zip"
            async with session.get(download_link) as resp:
                if resp.status == HTTPStatus.OK:
                    async with aiofiles.open("deno.zip", mode="wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                else:
                    logger.critical("Failed to download Deno: HTTP %s", resp.status)
                    self.set("deno_source", "install_failed")
                    return
        if os.path.exists('deno.zip'):
            with zipfile.ZipFile("deno.zip", "r") as zip_ref:
                zip_ref.extractall()
            os.remove('deno.zip')
            os.chmod(path=os.path.join(os.getcwd(), "deno"), mode=0o755)
            self.set("deno_source", os.path.join(os.getcwd(), "deno"))
        return

    @loader.command(en_doc="Download video", ru_doc="Скачать видео")
    async def ytdlvcmd(self, message):  # noqa: ANN001, ANN201, D102
        args = utils.get_args(message)
        if not args or not self._validate_url(args[0]) or len(args) > 1:
            await utils.answer(message, self.strings["invalid_args"])
            return

        if not (source := self._get_deno()):
            await utils.answer(message, self.strings["deno_err"])
            return

        await utils.answer(message, self.strings["downloading"])

        filename_prefix = f"video_{message.id}"
        ydl_opts = {
            "quiet": True,
            "outtmpl": f"{filename_prefix}.%(ext)s",
            "js_runtimes": {"deno": {"path": source}},
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }
        if cookie := self.get("youtube_cookie"):
            ydl_opts["cookiefile"] = cookie
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = await utils.run_sync(lambda: ydl.extract_info(args[0], download=True))
                filename = ydl.prepare_filename(info)
                await utils.answer(
                    message,
                    self.strings["done"],
                    file=filename,
                    invert_media=True,
                )
                os.remove(filename)
        except Exception as e:
            logger.exception("Catched error during download!")
            await utils.answer(self.strings["err"].format(e))

    @loader.command(en_doc="Download audio", ru_doc="Скачать аудио")
    async def ytdlacmd(self, message):  # noqa: ANN001, ANN201, D102
        args = utils.get_args(message)
        if not args or not self._validate_url(args[0]) or len(args) > 1:
            await utils.answer(message, self.strings["invalid_args"])
            return

        if not (source := self._get_deno()):
            await utils.answer(message, self.strings["deno_err"])
            return

        await utils.answer(message, self.strings["downloading"])

        ydl_opts = {
            "quiet": True,
            "outtmpl": f"audio_{message.id}.%(ext)s",
            "js_runtimes": {"deno": {"path": source}},
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                },
            ],
            "writethumbnail": True,
        }
        if cookie := self.get("youtube_cookie"):
            ydl_opts["cookiefile"] = cookie
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = await utils.run_sync(lambda: ydl.extract_info(args[0], download=True))
                filename = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
                await utils.answer(message, self.strings["done"], file=filename)
                os.remove(filename)
        except Exception as e:
            logger.exception("Catched error during download!")
            await utils.answer(self.strings["err"].format(e))

