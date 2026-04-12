# █▀▀▄   █▀▄▀█ █▀█ █▀▄ █▀
# ▀▀▀█ ▄ █ ▀ █ █▄█ █▄▀ ▄█

# #### Copyright (c) 2026 Archquise #####

# 💬 Contact: https://t.me/archquise
# 🔒 Licensed under the GNU AGPLv3.
# 📄 LICENSE: https://raw.githubusercontent.com/archquise/Q.Mods/main/LICENSE
# ---------------------------------------------------------------------------------
# Name: TimeZone
# Description: Prints current time in selected timezone (UTC+n and tzdata formats supported)
# Author: @quise_m
# ---------------------------------------------------------------------------------
# meta developer: @quise_m
# meta banner: https://raw.githubusercontent.com/archquise/qmods_meta/main/timezone.png
# requires: tzdata
# ---------------------------------------------------------------------------------

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import tzdata  # noqa: F401

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class TimeZoneMod(loader.Module):
    """Prints current time in selected timezone (UTC+n and tzdata formats supported)."""

    strings = {  # noqa: RUF012
        "name": "TimeZone",
        "invalid_args": "<emoji document_id=5854929766146118183>❌</emoji> There is no arguments or they are invalid",
        "_cls_doc": "Prints current time in selected timezone (UTC+n and tzdata formats supported)",
        "time_utc": "<emoji document_id=5276412364458059956>🕓</emoji> Current time by UTC+{}: {}",
        "time_tzdata": "<emoji document_id=5276412364458059956>🕓</emoji> Current time in {}: {}",
    }

    strings_ru = {  # noqa: RUF012
        "_cls_doc": "Выводит текущее время в выбранном часовом поясе (поддерживаются форматы UTC+n и tzdata)",
        "invalid_args": "<emoji document_id=5854929766146118183>❌</emoji> Нет аргументов или они неверны",
        "tzdata_error": "<emoji document_id=5854929766146118183>❌</emoji> Произошла ошибка при получении времени по tzdata: {}\n\nУбедитесь, что часовой пояс указан верно",
        "time_utc": "<emoji document_id=5276412364458059956>🕓</emoji> Текущее время по UTC+{}: {}",
        "time_tzdata": "<emoji document_id=5276412364458059956>🕓</emoji> Текущее время в {}: {}",
    }

    @loader.command(
        ru_doc="Выводит время по UTC+n | Использование: .utc 4",
        en_doc="Prints UTC+n time | Usage: .utc 4",
    )
    async def utccmd(self, message):  # noqa: ANN001, ANN201, D102
        args = utils.get_args(message)
        if not args or not args[0].isdigit() or len(args) > 1:
            await utils.answer(message, self.strings["invalid_args"])
            return
        offset = timedelta(hours=int(args[0]))
        tz = timezone(offset)
        time = datetime.now(tz)
        await utils.answer(
            message,
            self.strings["time_utc"].format(args[0], time.strftime("%H:%M:%S")),
        )

    @loader.command(
        ru_doc="Выводит время по часовому поясу tzdata | Использование: .tzdata Europe/Moscow",
        en_doc="Prints time by tzdata timezone | Usage: .tzdata Europe/Moscow",
    )
    async def tzdatacmd(self, message):  # noqa: ANN001, ANN201, D102
        args = utils.get_args(message)
        if args[0].isdigit() or not args or len(args) > 1:
            await utils.answer(message, self.strings["invalid_args"])
            return
        try:
            time = datetime.now(ZoneInfo(args[0]))
        except Exception as e:
            await utils.answer(message, self.strings["tzdata_error"].format(e))
            logger.exception(self.strings["tzdata_error"])
            return
        await utils.answer(
            message,
            self.strings["time_tzdata"].format(args[0], time.strftime("%H:%M:%S")),
        )
