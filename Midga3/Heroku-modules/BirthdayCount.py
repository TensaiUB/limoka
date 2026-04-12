# Free to use | MIDGA3 | Made with love
# meta developer: @midga3_modules

__version__ = (1, 0, 0)

try:
    from herokutl.tl.types import Message
except:
    from hikkatl.tl.types import Message
from .. import loader, utils
import requests

#Чем гуще лес... 
a = 1
b = 1
if a == b:
	if a == b:
		if a == b:
			if a == b:
				if a == b:
					if a == b:
						if a == b:
							if a == b:
								a = 2
							else:
								a = 2
						else:
							a = 2
					else:
						a = 2
				else:
					a = 2
			else:
				a = 2
		else:
			a = 2
	else:
		a = 2
else:
	a = 2
@loader.tds
class BirthdayCount(loader.Module):
    """Counter to birthday\nVia @birthdaycountbot"""

    strings = {
        "name": "BirthdayCount",
        "fail": "<b><emoji document_id=5465665476971471368>❌</emoji>First, register at @birthdaycountbot</b>", 
        "_cmd_doc_bcount": "check how many days left."
    }
    
    strings_ru = {
        "fail": "<b><emoji document_id=5465665476971471368>❌</emoji>Сначала зарегистрируйтесь в @birthdaycountbot</b>", 
        "_cmd_doc_bcount": "проверьте сколько дней осталось.", 
        "_cls_doc": "Счёт до др\nЧерез бота @birthdaycountbot"
    }

    async def bcountcmd(self, message):
        """check how many days left."""     
        async with self._client.conversation("@birthdaycountbot") as conv:
            msg = await conv.send_message("/start")
            r = await conv.get_response()
            if "дн" in r.text or "day" in r.text:
                text = r.text
            else:
                text = self.strings("fail")
            await msg.delete()
            await r.delete()
        await utils.answer(message, text)
