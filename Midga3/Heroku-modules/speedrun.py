#M i d g a 3 

#meta developer: @midga3_modules
# scope: heroku_min 2.0.0

import srcomapi, srcomapi.datatypes as dt
import logging
from .. import loader, utils
from herokutl.tl.types import Message
__verison__ = (1, 1, 0)
logger = logging.getLogger(__name__)
@loader.tds
class speedruncom(loader.Module):
    strings = {
        "name": "Speedruns",
        "searching": "<tg-emoji emoji-id=5188217332748527444>🔍</tg-emoji>Searching...",
        "game": "<tg-emoji emoji-id=5370869711888194012>👾</tg-emoji> Game: {}\n<tg-emoji emoji-id=5789531407231487577>🎮</tg-emoji> Number of runs: {}. \n <tg-emoji emoji-id=5409008750893734809>🏆</tg-emoji>Top runs: \n{}",
        "not_found": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji>Not found, sry",
        "new_notify": "You got a new notification: {}",
        "token": "Token of sppedrun.com",
    }
    async def client_ready(self):
        self.asset_channel = self._db.get("heroku.forums", "channel_id", 0)
        self._notif_topic = await utils.asset_forum_topic(
            self._client,
            self._db,
            self.asset_channel,
            "speedrun.com",
            description="Here will be notifications from speedrun.com.\nRequries token(change in cfg)",
            icon_emoji_id=5345892905103932200,
        )
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "token",
                None,
                lambda: self.strings("token"),
            ),
            loader.ConfigValue(
                "show_all_15",
                False,
                "Show all 15 runs on one page",
                validator=loader.validators.Boolean(),
            ),
        )
        self.api = srcomapi.SpeedrunCom(self.config['token']); self.api.debug = 1
        utils.register_placeholder("notifications", self.ph, "Number of notifications on speedrun.com")
    async def ph(self):
        return len(self._db.get("speedrun", "unread_ids", default=[]))
    @loader.loop(interval=60, autostart=True)
    async def poller(self):
        if self.config['token'] is None:
            return
        else:
            self.api = srcomapi.SpeedrunCom(self.config['token']); self.api.debug = 1
        data = self.api.get("notifications")
        unread = [n for n in data if n.get('status') == 'unread']
        unread_ids = [n.get('id') for n in unread if n.get('id')]
        saved_ids = self._db.get("speedrun", "unread_ids", default=[])
        new_ids = [uid for uid in unread_ids if uid not in saved_ids]
        self._db.set("speedrun", "unread_ids", unread_ids)
        new_notifications = [n for n in unread if n.get('id') in new_ids]
        for notification in new_notifications:
            uri = None
            if 'item' in notification and notification['item'].get('uri'):
                uri = notification['item']['uri']
            keyboard = None
            if uri:
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔗 Link", "url": uri}]
                    ]
                }
            await self.inline.bot.send_message(
                int(f"-100{self.asset_channel}"),
                self.strings['new_notify'].format(notification.get('text')),
                disable_webpage_preview=True,
                message_thread_id=self._notif_topic.id,
                reply_markup=keyboard
            )

    def _game_nav(self, pages, index):
        if len(pages) <= 1:
            return None
        buttons = []
        if index > 0:
            buttons.append({"text": "◀️", "callback": self._game_page, "args": (pages, index - 1)})
        buttons.append({"text": f"{index + 1}/{len(pages)}", "callback": self._game_page, "args": (pages, index)})
        if index < len(pages) - 1:
            buttons.append({"text": "▶️", "callback": self._game_page, "args": (pages, index + 1)})
        return [buttons]

    async def _game_page(self, call, pages, index):
        await call.edit(pages[index], reply_markup=self._game_nav(pages, index))


    @loader.command()
    async def game(self, message: Message):
        args = utils.get_args_raw(message)
        game = self.api.search(srcomapi.datatypes.Game, {"name": f"{args}"})[0]
        await message.edit(self.strings['searching'])
        try:
            new_game_name = game.name
            runs_data = self.api.get(f"runs?game={game.id}")
            runs = runs_data['data'] if isinstance(runs_data, dict) and 'data' in runs_data else runs_data
            top_fifteen = runs[:15] if runs else []
        except Exception as e:
            logger.error(f"Error: {e}")
            await message.edit(self.strings['not_found'])
            return

        if not top_fifteen:
            await message.edit(self.strings['not_found'])
            return

        pages = []
        step = 15 if self.config["show_all_15"] else 5
        for page_start in range(0, len(top_fifteen), step):
            chunk = top_fifteen[page_start:page_start + step]
            lines = []
            for index, run in enumerate(chunk, start=page_start + 1):
                if not run:
                    continue
                player_id = run['players'][0]['id'] if 'players' in run and run['players'] else "Unknown"
                player_name = self.api.get_user(str(player_id)).name
                run_time = run['times']['realtime_t'] if 'times' in run else 0
                video_url = run['videos']['links'][0]['uri'] if 'videos' in run and 'links' in run['videos'] and run['videos']['links'] else None
                if video_url:
                    player_link = f'<a href="{video_url}">{player_name}</a>'
                else:
                    player_link = player_name
                lines.append(f"{index}. {player_link} - {run_time}s")
            runs_text = "<blockquote expandable>" + "\n".join(lines) + "</blockquote>"
            pages.append(self.strings['game'].format(new_game_name, len(runs), runs_text))

        await self.inline.form(
            message=message,
            text=pages[0],
            reply_markup=self._game_nav(pages, 0)
        )
