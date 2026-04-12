# █▀▀▄   █▀▄▀█ █▀█ █▀▄ █▀
# ▀▀▀█ ▄ █ ▀ █ █▄█ █▄▀ ▄█

# #### Copyright (c) 2025 Archquise #####

# 💬 Contact: https://t.me/archquise
# 🔒 Licensed under the GNU AGPLv3.
# 📄 LICENSE: https://raw.githubusercontent.com/archquise/Q.Mods/main/LICENSE
# ---------------------------------------------------------------------------------
# Name: TempChat
# Description: Creates a temporary private chat with a message forwarding restriction and adds the specified user to it.
# Author: @quise_m
# ---------------------------------------------------------------------------------
# meta developer: @quise_m
# meta banner: https://raw.githubusercontent.com/archquise/qmods_meta/main/TempChat.png
# ---------------------------------------------------------------------------------

import logging
from datetime import UTC
from datetime import datetime as dt

from telethon import functions

from .. import loader, utils

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


@loader.tds
class TempChatMod(loader.Module):
    """Creates a temporary private chat with a message forwarding restriction and adds the specified user to it."""

    strings = {  # noqa: RUF012
        "name": "TempChat",
        "selfchat": "You can't create a chat with yourself.",
        "wrongargs": "<emoji document_id=5980953710157632545>❌</emoji> <b>Wrong arguments. Use </b><code>.tmpchat [@user/reply] [time]</code><b>",
        "alreadychatting": "<emoji document_id=5980953710157632545>❌</emoji> <b>You already have an active conversation with this person.</b>",
        "invalidtime": "<emoji document_id=5980953710157632545>❌</emoji> <b>Invalid time format. Use combinations like 1h30m.</b>",
        "invitemsg": "<emoji document_id=5818967120213445821>🛡</emoji> You've been invited to a temporary private chat!\n\n<emoji document_id=5451646226975955576>⌛️</emoji> Auto-deletes in ",
        "joinlink": "🔗 Join link: ",
        "chatcreated": "<emoji document_id=5980930633298350051>✅</emoji> The temporary chat has been successfully created!",
    }

    strings_ru = {  # noqa: RUF012
        "selfchat": "Ты не можешь создать чат сам с собой.",
        "wrongargs": "<emoji document_id=5980953710157632545>❌</emoji> <b>Неверные аргументы. Используй </b><code>.tmpchat [@user/reply] [время]</code>",
        "alreadychatting": "<emoji document_id=5980953710157632545>❌</emoji> <b>У вас уже есть открытая переписка с этим человеком.</b>",
        "invalidtime": "<emoji document_id=5980953710157632545>❌</emoji> <b>Неверный формат времени. Убедитесь, что вы вводите время в формате 1h, 2h30m.</b>",
        "invitemsg": "<emoji document_id=5818967120213445821>🛡</emoji> Вы были приглашены во временный приватный чат!\n\n<emoji document_id=5451646226975955576>⌛️</emoji> Авто-удаление через ",
        "joinlink": "🔗 Ссылка: ",
        "chatcreated": "<emoji document_id=5980930633298350051>✅</emoji> Временный чат успешно создан!",
        "_cls_doc": "Создает временный приватный чат с запретом на пересылку и добавляет туда выбранного человека",
    }

    def __init__(self):  # noqa: ANN204, D107
        self.temp_chats = {}

    @loader.loop(interval=30, autostart=True)
    async def check_expired_chats(self) -> None:
        """Check chats with expired life time."""
        now = dt.now(UTC).timestamp()
        for chat_id in list(self.temp_chats.keys()):
            if self.temp_chats[chat_id][1] <= now:
                try:
                    await self.client(
                        functions.channels.DeleteChannelRequest(chat_id),
                    )
                    del self.temp_chats[chat_id]
                    self.set("temp_chats", self.temp_chats)
                except Exception as e:
                    logger.exception("Error deleting chat {chat_id}!")
                    try:
                        self.client(
                            functions.channels.GetFullChannelRequest(
                                channel=chat_id,
                            ),
                        )
                    except Exception:  # noqa: BLE001
                        del self.temp_chats[chat_id]
                        self.set("temp_chats", self.temp_chats)

    async def client_ready(self, client, db):  # noqa: D102, ARG002, ANN001, ANN201
        self.hmodslib = await self.import_lib(
            "https://files.archquise.ru/HModsLibrary.py",
        )
        self.temp_chats = self.get("temp_chats", {})

    @loader.command(
        ru_doc="Создает временный чат. Использование: .tmpchat [@user/reply] [time]",
    )
    async def tmpchat(self, message):  # noqa: ANN001, ANN201
        """Create temporary chat. Usage: .tmpchat [@user/reply] [time]"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if reply:
            user = await self.client.get_entity(reply.sender_id)
            time_str = args.strip() if args else None
        else:
            parts = args.split(",", 1) if "," in args else args.rsplit(" ", 1)
            if len(parts) != 2:
                return await utils.answer(message, self.strings["wrongargs"])
            user_str, time_str = parts[0].strip(), parts[1].strip()
            try:
                user = await self.client.get_entity(user_str)
            except Exception:
                return await utils.answer(message, self.strings["wrongargs"])

        if not time_str:
            return await utils.answer(message, self.strings["wrongargs"])
        seconds = await self.hmodslib.parse_time(time_str)
        if not seconds:
            return await utils.answer(message, self.strings["invalidtime"])

        if any(user.id == uid for uid, _ in self.temp_chats.values()):
            return await utils.answer(message, self.strings["alreadychatting"])

        try:
            created = await self.client(
                functions.channels.CreateChannelRequest(
                    title=f"TempChat #{user.id}",
                    about=f"Temporary private chat with {user.id} | Expires after: {time_str}",
                    megagroup=True,
                ),
            )
            chat_id = created.chats[0].id
            expires_at = dt.now(UTC).timestamp() + seconds

            await self.client(
                functions.messages.ToggleNoForwardsRequest(peer=chat_id, enabled=True),
            )

            self.temp_chats[chat_id] = (user.id, expires_at)
            self.set("temp_chats", self.temp_chats)

            invite = await self.client(
                functions.messages.ExportChatInviteRequest(peer=chat_id, usage_limit=1),
            )
            invite_message = (
                self.strings["invitemsg"]
                + time_str
                + f"\n{self.strings['joinlink']} {invite.link}"
            )
            await self.client.send_message(user.id, invite_message)
            await utils.answer(message, self.strings["chatcreated"])

        except Exception as e:
            logger.exception("Error creating temp chat!")
            await utils.answer(message, "❌ Error! Check log-chat.")
