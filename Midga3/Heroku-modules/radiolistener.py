import json
from .. import loader, utils
import logging
import difflib
import aiohttp
# meta developer: @midga3_modules
# meta banner: https://meta.hostingradio.ru/files/elements/cover-images/600x600/434e51ce-b4ac-4157-a699-4954c02dabb9.jpg 

logger = logging.getLogger(__name__)
version = (1, 0, 0)

@loader.tds
class RadioListener(loader.Module):
    """Listen and check radio stations"""
    strings = {
        "name": "RadioListener",
        "searching": "<b><tg-emoji emoji-id=5188217332748527444>🔍</tg-emoji> Searching for radio stations...</b>",
        "not_found": "<b>❌ No online radio stations found. {}</b>",
        "found": "<b>{}\nLISTEN HERE</b>:\n{}\n\n<code>Current track:{}</code>",
    }
    strings_ru = {
        "searching": "<b><tg-emoji emoji-id=5188217332748527444>🔍</tg-emoji> Поиск радиостанций...</b>",
        "not_found": "<b>❌ Радиостанции не найдены. {}</b>",
        "found": "<b>{}\nСЛУШАТЬ ЗДЕСЬ:</b>\n{}\n\n<code>Текущий трек: {}</code>",
        "_cmd_doc_radio": "поиск радио.", 
        "_cls_doc": "Слушайте и проверяйте радиостанции"
    }
    async def radiocmd(self, message):
        """search radio."""
        args = utils.get_args_raw(message)
        if args:
            query = args
            await message.edit(self.strings("searching"))
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://raw.githubusercontent.com/Midga3/heroku-modules/refs/heads/main/radios.json") as response:
                        if response.status == 200:
                            text = await response.text()
                            radios_data = json.loads(text)
                        else:
                            logger.exception(f"{utils.ascii_face()}JSON ERROR: {response.status}")
                            await message.edit(self.strings("not_found").format("Error fetching data"))
                            return None
            except Exception as e:
                logger.exception(f"{utils.ascii_face()}ERROR: {e}")
                await message.edit(self.strings("not_found").format("Error fetching data"))
                return None
            found = False
            for radio in radios_data:
                if difflib.SequenceMatcher(None, query.lower(), radio["radio_name"].lower()).ratio() > 0.5:
                    found = True
                    async with aiohttp.ClientSession() as session:
                        async with session.get(radio["current_link"]) as resp:
                            if resp.status == 200:
                                try:
                                    data = await resp.json()
                                    current_track = f"{data.get('artist', 'Unknown Artist')} - {data.get('title', 'Unknown Title')}"
                                    media = data.get("cover", "")
                                except:
                                    current_track = "Unknown"
                                    media = ""
                            else:
                                current_track = "Unknown"
                                media = ""
                    await message.edit(self.strings("found").format(radio["radio_name"], radio["radio_link"], current_track), file=media if media else None)
                    break
            if not found:
                await message.edit(self.strings("not_found").format("No matching radio found"))
        else:
            await message.edit(self.strings("not_found").format("No args"))
