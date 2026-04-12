# █▀▀▄   █▀▄▀█ █▀█ █▀▄ █▀
# ▀▀▀█ ▄ █ ▀ █ █▄█ █▄▀ ▄█

# #### Copyright (c) 2025 Archquise #####

# 💬 Contact: https://t.me/archquise
# 🔒 Licensed under the GNU AGPLv3.
# 📄 LICENSE: https://raw.githubusercontent.com/archquise/Q.Mods/main/LICENSE
# ---------------------------------------------------------------------------------
# Name: IrisSimpleMod
# Description: Module for basic interaction with Iris.
# Author: @quise_m
# ---------------------------------------------------------------------------------
# meta developer: @quise_m
# meta banner: https://raw.githubusercontent.com/archquise/qmods_meta/main/IrisSimpleMod.png
# ---------------------------------------------------------------------------------

import logging

from .. import loader, utils

__version__ = (1, 0, 1)

logger = logging.getLogger(__name__)


@loader.tds
class IrisSimpleMod(loader.Module):
    """Module for basic interaction with Iris bot."""

    strings = {  # noqa: RUF012
        "name": "IrisSimpleMod",
        "checking_bag": "<emoji document_id=5188311512791393083>🌎</emoji> Checking bag...",
        "bag_result": "<emoji document_id=5854762571659218443>✅</emoji> Your bag: <code>{}</code>",
        "farming": "<emoji document_id=5188311512791393083>🌎</emoji> Farming iris-coins...",
        "farm_result": "<emoji document_id=5854762571659218443>✅</emoji> Farm result: <code>{}</code>",
        "getting_stats": "<emoji document_id=5188311512791393083>🌎</emoji> Getting user stats...",
        "stats_result": "<emoji document_id=5854762571659218443>✅</emoji> User stats: <code>{}</code>",
        "bot_stats": "<emoji document_id=5188311512791393083>🌎</emoji> Getting bot stats...",
        "bot_stats_result": "<emoji document_id=5854762571659218443>✅</emoji> Bot stats: <code>{}</code>",
        "error_no_response": "<emoji document_id=5854929766146118183>❌</emoji> No response from bot. Please try again.",
        "error_timeout": "<emoji document_id=5854929766146118183>❌</emoji> Request timeout. Please try again.",
        "error_general": "<emoji document_id=5854929766146118183>❌</emoji> An error occurred: {error}",
    }

    strings_ru = {  # noqa: RUF012
        "checking_bag": "<emoji document_id=5188311512791393083>🌎</emoji> Проверка мешка...",
        "bag_result": "<emoji document_id=5854762571659218443>✅</emoji> Ваш мешок: <code>{}</code>",
        "farming": "<emoji document_id=5188311512791393083>🌎</emoji> Фарм ирис-коинов...",
        "farm_result": "<emoji document_id=5854762571659218443>✅</emoji> Результат фарма: <code>{}</code>",
        "getting_stats": "<emoji document_id=5188311512791393083>🌎</emoji> Получение статистики пользователя...",
        "stats_result": "<emoji document_id=5854762571659218443>✅</emoji> Статистика пользователя: <code>{}</code>",
        "bot_stats": "<emoji document_id=5188311512791393083>🌎</emoji> Получение статистики ботов...",
        "bot_stats_result": "<emoji document_id=5854762571659218443>✅</emoji> Статистика ботов: <code>{}</code>",
        "error_no_response": "<emoji document_id=5854929766146118183>❌</emoji> Нет ответа от бота. Попробуйте еще раз.",
        "error_timeout": "<emoji document_id=5854929766146118183>❌</emoji> Таймаут запроса. Попробуйте еще раз.",
        "error_general": "<emoji document_id=5854929766146118183>❌</emoji> Произошла ошибка: {error}",
        "_cls_doc": "Модуль для базового взаимодействия с Ирисом!",
    }

    async def _send_and_delete(
        self,
        message,
        command_message: str,
        response_timeout: int = 15,  # noqa: ANN001
    ) -> str | None:
        """Send command to Iris and get response with timeout."""
        try:
            async with self.client.conversation(
                707693258,
                timeout=response_timeout,
            ) as conv:
                msg = await conv.send_message(command_message)
                await msg.delete()

                response_msg = await conv.get_response()
                if response_msg:
                    await utils.answer(message, response_msg.text)
                    return response_msg.text
                return None
        except Exception as e:
            logger.exception("Error in conversation!")
            await utils.answer(
                message,
                self.strings["error_general"].format(error=str(e)),
            )
            return None

    @loader.command(
        ru_doc="Проверить мешок",
        en_doc="Check bag",
    )
    async def bag(self, message):  # noqa: ANN001, ANN201
        """Check bag."""
        await utils.answer(message, self.strings["checking_bag"])

        result = await self._send_and_delete(message, "мешок", response_timeout=20)

        if result:
            await utils.answer(message, self.strings["bag_result"].format(result))

    @loader.command(
        ru_doc="Зафармить ирис-коины",
        en_doc="Farm iris-coins",
    )
    async def farm(self, message):  # noqa: ANN001, ANN201
        """Farm iris-coins."""
        await utils.answer(message, self.strings["farming"])

        result = await self._send_and_delete(message, "ферма", response_timeout=25)

        if result:
            await utils.answer(message, self.strings["farm_result"].format(result))

    @loader.command(
        ru_doc="Вывести анкету",
        en_doc="Display user stats",
    )
    async def irisstats(self, message):  # noqa: ANN001, ANN201
        """Display user stats."""
        await utils.answer(message, self.strings["getting_stats"])

        result = await self._send_and_delete(message, "анкета", response_timeout=20)

        if result:
            await utils.answer(message, self.strings["stats_result"].format(result))
