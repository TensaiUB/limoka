#Midga3
#Placeholder system is the best

# meta banner: https://github.com/Midga3/heroku-modules/blob/main/new_module.jpg?raw=true
# meta developer: @midga3_modules
__version__ = (1, 0, 0)

import logging
import aiohttp
import asyncio
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class PingEmoji(loader.Module):
    strings = {
        "name": "PingEmoji"
    }

    async def client_ready(self, client, db):
        self._client = client
        utils.register_placeholder("ping_emoji", self.get_emoji)

    async def get_emoji(self, data):
        if data['ping'] > 300:
            return "<tg-emoji emoji-id=5276307163529092252>🔴</tg-emoji>"
        else:
            return ""