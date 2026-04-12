# NOT OFFICIAL FHeta MODULE | НЕ ОФИЦИАЛЬНЫЙ FHeta МОДУЛЬ

#Fix tomorrow mb

# meta developer: @midga3_modules
# meta banner: https://ia801007.us.archive.org/BookReader/BookReaderImages.php?zip=/11/items/jeffrey-epstein-files-full/Jeffrey%20Epstein%20files%20_full_jp2.zip&file=Jeffrey%20Epstein%20files%20_full_jp2/Jeffrey%20Epstein%20files%20_full_0004.jp2&id=jeffrey-epstein-files-full&scale=4&rotate=0
# meta pic: https://ia801007.us.archive.org/BookReader/BookReaderImages.php?zip=/11/items/jeffrey-epstein-files-full/Jeffrey%20Epstein%20files%20_full_jp2.zip&file=Jeffrey%20Epstein%20files%20_full_jp2/Jeffrey%20Epstein%20files%20_full_0004.jp2&id=jeffrey-epstein-files-full&scale=4&rotate=0

#хуй
from herokutl.tl.types import Message
from .. import loader, utils
import requests

@loader.tds
class FHetaStatus(loader.Module):
    """NOT OFFICIAL FHeta MODULE\nCheck fheta status"""

    strings = {
        "name": "FHetaStatus",
        "working": "<b><emoji document_id=5427009714745517609>✅</emoji>FHeta is working</b>",
        "not_working": "<b><emoji document_id=5465665476971471368>❌</emoji>Fheta is unavailable</b>", 
        "_cmd_doc_fping": "check fheta status."
    }
    
    strings_ru = {
        "working": "<b><emoji document_id=5427009714745517609>✅</emoji>FHeta работает</b>",
        "not_working": "<b><emoji document_id=5465665476971471368>❌</emoji>Fheta недоступна</b>", 
        "_cmd_doc_fping": "проверить статус FHeta.", 
        "_cls_doc": "НЕ ОФИЦИАЛЬНЫЙ FHeta МОДУЛЬ\nПроверьте статус FHeta"
    }

    async def fpingcmd(self, message: Message):
        """check fheta status"""

        url = "https://api.fixyres.com/module/Midga3/heroku-modules/radiolistener.py" # Не ии это мне на будущее если менять
        response = requests.get(url)
        if response.status_code == 200 and response.text != "[]":
            meassage = await utils.answer(message, self.strings("working"))
        else:
            meassage = await utils.answer(message, self.strings("not_working"))
