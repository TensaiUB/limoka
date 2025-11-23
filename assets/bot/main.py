"""
main.py - bot for installin modules by buttons in Telegram channels via Limoka
"""

import os
import json
import logging
import time
import asyncio
import hashlib
import re
from datetime import datetime
from typing import Optional, Dict, List

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, BaseFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from aiogram.utils.formatting import (
    Text,
    Bold,
    Code,
    Italic,
    as_section,
    as_list,
    HashTag,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from dotenv import load_dotenv

# === CONFIGURATION ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:AA11CC22DD33EE44FF55GG66HH77II88JJ99")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "123").split(",")))
WHITELIST_FILE = "whitelist.json"
PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE", "key.pem")
MODULES_JSON_URL = "https://raw.githubusercontent.com/MuRuLOSE/limoka/main/modules.json"
MODULES_BASE_URL = MODULES_JSON_URL.replace("modules.json", "")
UPDATE_INTERVAL_MINUTES = 30

# === STRINGS (only plain text — formatting done via aiogram.utils.formatting) ===
STRINGS = {
    "en": {
        # Startup
        "logging_initialized": "✅ Logging initialized with UTF-8 support",
        "starting_bot": "🚀 Starting Limoka Install Bot...",
        "security_manager_initialized": "✅ Security manager initialized",
        "security_manager_failed": "❌ Failed to initialize security manager: {}",
        "security_critical_error": "Bot will not be able to sign modules - shutting down",
        "modules_loaded": "✅ Loaded {} modules from repository",
        "modules_auto_updater": "🔄 Starting modules.json auto-updater (every {} minutes)",
        "auto_update_failed": "❌ Auto-update failed: {}",
        "startup_notification_title": "Limoka Install Bot started successfully!",
        "startup_notification_body": [
            "• Enhanced whitelist: ✅ Active (channel→repo mapping)",
            "• Time validation: ❌ Removed",
            "• Module signing: ✅ Ed25519",
            "",
            "🔧 Admin commands:",
            "/addrepo <channel_id> <repo> — Add repo to channel",
            "/rmrepo <channel_id> <repo> — Remove repo from channel",
            "/whitelist — Show all whitelisted channels",
        ],
        "bot_running": "✅ Bot is now running and listening for updates",
        "shutting_down": "🛑 Shutting down Limoka Install Bot...",
        # Whitelist
        "whitelist_file_created": "Created new whitelist file: {}",
        "whitelist_loaded": "Loaded whitelist with {} channels",
        "whitelist_load_failed": "❌ Error loading whitelist: {}",
        "whitelist_saved": "✅ Saved whitelist with {} channels",
        "whitelist_save_failed": "❌ Error saving whitelist: {}",
        "channel_added": "✅ Channel {} added to whitelist.",
        "channel_already_exists": "ℹ️ Channel {} already in whitelist.",
        "channel_removed": "✅ Channel {} removed from whitelist.",
        "channel_not_found": "❌ Channel {} not found in whitelist.",
        "channel_normalized": "Normalized channel ID: {} → {}",
        "whitelist_empty": "📋 Whitelist is empty.",
        "whitelist_title": "📋 Whitelisted channels:",
        "repo_added": "✅ Repository {} added to channel {} whitelist.",
        "repo_already_exists": "ℹ️ Repository {} already in whitelist for channel {}.",
        "repo_removed": "✅ Repository {} removed from channel {} whitelist.",
        "repo_not_found": "❌ Repository {} not found in whitelist for channel {}.",
        "channel_not_in_whitelist": "❌ Channel {} not found in whitelist.",
        # Commands
        "unauthorized_access": "❌ You are not authorized to use this bot.",
        "start_command_title": "Limoka Install Bot",
        "start_command_body": [
            "Commands:",
            "/whitelist — Show whitelisted channels",
            "/addchannel <id> — Add channel to whitelist",
            "/rmchannel <id> — Remove channel from whitelist",
            "/reload — Reload modules.json",
        ],
        "addchannel_usage": "❌ Usage: /addchannel <channel_id>",
        "rmchannel_usage": "❌ Usage: /rmchannel <channel_id>",
        "addrepo_usage": "❌ Usage: /addrepo <channel_id> <repo>\nExample: /addrepo -1003377102183 MuRuLOSE/limoka-modules",
        "rmrepo_usage": "❌ Usage: /rmrepo <channel_id> <repo>\nExample: /rmrepo -1003377102183 MuRuLOSE/limoka-modules",
        "reload_command": "🔄 Reloading modules.json...",
        "modules_reloaded": "✅ Loaded {} modules.",
        "envforceupdate_success": "✅ Environment variables reloaded.",
        "current_admin_ids": "Current ADMIN_IDS:",
        # Callbacks
        "callback_format_invalid": "❌ Invalid callback data format",
        "service_unavailable": "❌ Service unavailable — modules database not loaded",
        "module_not_in_database": "❌ Module not found in database",
        "hash_collision": "⚠️ Hash collision detected for paths: {}",
        "ambiguous_module": "❌ Ambiguous module match — please try again",
        "signature_verification_failed": "❌ Signature verification failed! Installation aborted.",
        "signature_spoof_attempt": "❌ Signature spoof attempt detected for module: {}",
        "message_sent": "✅ Message sent! Check your private messages.",
        "cannot_send_messages": "❌ I can't send you messages. Please start a chat with me first!",
        "install_success": "✅ Module installed successfully!",
        "install_failed": "❌ Installation failed:\n<code>{}</code>",
        # Buttons
        "install_button_text": "🍋 Install via Limoka",
        "install_reply_text": "🍋 Install via Limoka:",
        # Filters
        "channel_whitelisted": "✅ Channel {} is whitelisted (allowed repos: {})",
        "channel_not_whitelisted": "❌ Channel {} is NOT whitelisted",
        "limoka_tag_found": "✅ Found limoka tag: {}",
        "limoka_tag_processing": "🎯 Processing limoka tag: {}",
    }
}

# === LOGGING ===
# Configure logging: write DEBUG+ to file, but keep console output concise (INFO+).
logger = logging.getLogger("LimokaBot")
logger.setLevel(logging.DEBUG)

# File handler: store all logs including DEBUG for diagnostics
file_handler = logging.FileHandler("limoka_bot.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(file_formatter)

# Console/stream handler: only INFO+ to avoid noisy debug output in production
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
stream_handler.setFormatter(stream_formatter)

# Attach handlers (avoid duplicate handlers if reloading)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

logger.info(STRINGS["en"]["logging_initialized"])

# === INIT ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

_cached_modules: Optional[Dict] = None
_modules_last_update: float = 0.0
_security_manager = None


# === SECURITY MANAGER ===
class SecurityManager:
    def __init__(self, private_key_path: str):
        if not os.path.exists(private_key_path):
            raise FileNotFoundError(f"Private key not found: {private_key_path}")
        try:
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
            if not isinstance(self.private_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Only Ed25519 keys are supported")
            logger.info("✅ Ed25519 private key loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load private key: {e}")
            raise

    def sign(self, data: str) -> str:
        try:
            signature = self.private_key.sign(data.encode())
            return signature.hex()
        except Exception as e:
            logger.error(f"❌ Signing failed: {e}")
            raise


# === WHITELIST ===
def load_whitelist() -> dict:
    try:
        if not os.path.exists(WHITELIST_FILE):
            default = {"channels": {}, "last_updated": datetime.now().isoformat()}
            with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2, ensure_ascii=False)
            logger.info(f"Created new whitelist file: {WHITELIST_FILE}")
            return default
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading whitelist: {e}")
        return {"channels": {}}


def save_whitelist(data: dict):
    data["last_updated"] = datetime.now().isoformat()
    try:
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Saved whitelist with {len(data['channels'])} channels")
    except Exception as e:
        logger.error(f"❌ Error saving whitelist: {e}")


# === MODULES ===
async def fetch_modules_json() -> Optional[Dict]:
    global _cached_modules, _modules_last_update
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MODULES_JSON_URL, timeout=15) as resp:
                if resp.status != 200:
                    logger.error(f"❌ Failed to fetch modules.json: HTTP {resp.status}")
                    return None
                text = await resp.text()
                data = json.loads(text)
                _cached_modules = data
                _modules_last_update = time.time()
                logger.info(STRINGS["en"]["modules_loaded"].format(len(data)))
                return data
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in modules.json: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Fetch failed: {e}")
        return None


async def get_modules() -> Dict:
    global _cached_modules
    if _cached_modules is None:
        await fetch_modules_json()
    return _cached_modules or {}


async def modules_updater():
    logger.info(STRINGS["en"]["modules_auto_updater"].format(UPDATE_INTERVAL_MINUTES))
    while True:
        try:
            await fetch_modules_json()
        except Exception as e:
            logger.error(STRINGS["en"]["auto_update_failed"].format(e))
        await asyncio.sleep(UPDATE_INTERVAL_MINUTES * 60)


# === FILTERS ===
class WhitelistChannelFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.chat:
            return False
        whitelist = load_whitelist()
        chat_id = str(message.chat.id)
        return chat_id in whitelist["channels"]


class LimokaTagFilter(BaseFilter):
    async def __call__(self, message: Message) -> Optional[Dict[str, str]]:
        text = (message.text or message.caption or "").strip()
        if not text:
            return False
        pattern = r"#limoka:([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+)/([a-zA-Z0-9_/.%-]+\.(?:py|pyc|pyo|pyd))"
        match = re.search(pattern, text)
        if not match:
            return False
        username, repo, module_path = match.groups()
        full_path = f"{username}/{repo}/{module_path}"
        return {
            "username": username,
            "repo": repo,
            "module_path": module_path,
            "full_path": full_path,
        }


# === UTILS ===
def normalize_channel_id(cid: str) -> str:
    if cid.startswith("-100"):
        return cid
    if cid.startswith("-"):
        return "-100" + cid[1:]
    if cid.isdigit():
        return "-100" + cid
    return cid


# === COMMAND HANDLERS ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(STRINGS["en"]["unauthorized_access"])
        return
    content = as_section(
        Bold(STRINGS["en"]["start_command_title"]),
        "",
        *STRINGS["en"]["start_command_body"],
        "",
        Bold("Current chat ID:"),
        Code(str(message.chat.id)),
    )
    await message.answer(**content.as_kwargs())


# === COMMAND HANDLERS ===
@router.message(Command("envforceupdate"))
async def cmd_envforceupdate(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(STRINGS["en"]["unauthorized_access"])
        return
    load_dotenv()
    content = as_section(
        Bold(STRINGS["en"]["envforceupdate_success"]),
        "",
        Bold(STRINGS["en"]["current_admin_ids"]),
        Code(str(ADMIN_IDS)),
    )
    await message.answer(**content.as_kwargs())


@router.message(Command("whitelist"))
async def cmd_whitelist(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    whitelist = load_whitelist()
    channels = whitelist["channels"]
    if not channels:
        await message.answer(STRINGS["en"]["whitelist_empty"])
        return
    items = [Code(cid) for cid in sorted(channels.keys())]
    content = as_section(Bold(STRINGS["en"]["whitelist_title"]), *items)
    await message.answer(**content.as_kwargs())


@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(STRINGS["en"]["addchannel_usage"])
        return
    raw_id = args[1].strip()
    norm_id = normalize_channel_id(raw_id)
    logger.info(f"Normalized: {raw_id} → {norm_id}")
    whitelist = load_whitelist()
    if norm_id not in whitelist["channels"]:
        whitelist["channels"][norm_id] = {
            "allowed_repos": [],
            "added_date": datetime.now().isoformat(),
        }
        save_whitelist(whitelist)
        await message.answer(STRINGS["en"]["channel_added"].format(norm_id))
    else:
        await message.answer(STRINGS["en"]["channel_already_exists"].format(norm_id))


@router.message(Command("rmchannel"))
async def cmd_rmchannel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(STRINGS["en"]["rmchannel_usage"])
        return
    raw_id = args[1].strip()
    norm_id = normalize_channel_id(raw_id)
    whitelist = load_whitelist()
    if norm_id in whitelist["channels"]:
        del whitelist["channels"][norm_id]
        save_whitelist(whitelist)
        await message.answer(STRINGS["en"]["channel_removed"].format(norm_id))
    else:
        await message.answer(STRINGS["en"]["channel_not_found"].format(norm_id))


@router.message(Command("addrepo"))
async def cmd_addrepo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        content = as_section(Bold("❌ Usage:"), Code("/addrepo <channel_id> <repo>"))
        await message.answer(**content.as_kwargs())
        return
    raw_cid, repo = args[1], args[2]
    cid = normalize_channel_id(raw_cid)
    whitelist = load_whitelist()
    if cid not in whitelist["channels"]:
        await message.answer(STRINGS["en"]["channel_not_in_whitelist"].format(cid))
        return
    if repo not in whitelist["channels"][cid]["allowed_repos"]:
        whitelist["channels"][cid]["allowed_repos"].append(repo)
        save_whitelist(whitelist)
        await message.answer(STRINGS["en"]["repo_added"].format(repo, cid))
    else:
        await message.answer(STRINGS["en"]["repo_already_exists"].format(repo, cid))


@router.message(Command("rmrepo"))
async def cmd_rmrepo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        content = as_section(Bold("❌ Usage:"), Code("/rmrepo <channel_id> <repo>"))
        await message.answer(**content.as_kwargs())
        return
    raw_cid, repo = args[1], args[2]
    cid = normalize_channel_id(raw_cid)
    whitelist = load_whitelist()
    if cid not in whitelist["channels"]:
        await message.answer(STRINGS["en"]["channel_not_in_whitelist"].format(cid))
        return
    if repo in whitelist["channels"][cid]["allowed_repos"]:
        whitelist["channels"][cid]["allowed_repos"].remove(repo)
        if not whitelist["channels"][cid]["allowed_repos"]:
            del whitelist["channels"][cid]
        save_whitelist(whitelist)
        await message.answer(STRINGS["en"]["repo_removed"].format(repo, cid))
    else:
        await message.answer(STRINGS["en"]["repo_not_found"].format(repo, cid))


@router.message(Command("reload"))
async def cmd_reload(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(STRINGS["en"]["reload_command"])
    data = await fetch_modules_json()
    await message.answer(
        STRINGS["en"]["modules_reloaded"].format(len(data) if data else 0)
    )


# === CHANNEL POST HANDLERS ===
@router.channel_post(WhitelistChannelFilter(), LimokaTagFilter())
@router.edited_channel_post(WhitelistChannelFilter(), LimokaTagFilter())
async def handle_limoka_tag(
    message: Message, username: str, repo: str, module_path: str, full_path: str
):
    logger.info(STRINGS["en"]["limoka_tag_found"].format(full_path))
    await process_limoka_tag_directly(message, username, repo, module_path, full_path)


async def process_limoka_tag_directly(
    message: Message, username: str, repo: str, module_path: str, full_path: str
):
    whitelist = load_whitelist()
    chat_id = str(message.chat.id)
    allowed_repos = whitelist["channels"][chat_id].get("allowed_repos", [])
    repo_full = f"{username}/{repo}"
    if allowed_repos and repo_full not in allowed_repos:
        logger.warning(f"Repo {repo_full} blocked for channel {chat_id}")
        return

    modules = await get_modules()
    if not modules or full_path not in modules:
        logger.warning(f"Module not in DB: {full_path}")
        return

    try:
        # Compute sha256 of remote module content and sign "full_path|sha256"
        module_url = MODULES_BASE_URL + full_path
        async with aiohttp.ClientSession() as session:
            async with session.get(module_url, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch module for signing: {module_url} (HTTP {resp.status})")
                    return
                module_bytes = await resp.read()
        sha256 = hashlib.sha256(module_bytes).hexdigest()
        payload = f"{full_path}|{sha256}"
        signature = _security_manager.sign(payload)
        path_hash = hashlib.sha256(full_path.encode()).hexdigest()[:8]
        cb_data = f"install:{path_hash}:{signature[:32]}"[:64]

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=STRINGS["en"]["install_button_text"], callback_data=cb_data
                    )
                ]
            ]
        )

        text = (message.text or message.caption or "").strip()
        new_text = (
            re.sub(r"#limoka:[^\s]+", "", text).strip()
            or "Module installation available"
        )

        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=new_text,
            reply_markup=keyboard,
        )
        logger.info(f"✅ Button added to message {message.message_id}")
    except TelegramAPIError as e:
        logger.error(f"Failed to add button: {e}")


# === CALLBACKS ===
@router.callback_query(lambda c: c.data.startswith("install:"))
async def process_install(callback: CallbackQuery):
    try:
        parts = callback.data.split(":", 3)
        if len(parts) < 3:
            await callback.answer(
                STRINGS["en"]["callback_format_invalid"], show_alert=True
            )
            return

        _, path_hash, sig_short = parts[:3]
        modules = await get_modules()
        if not modules:
            await callback.answer(STRINGS["en"]["service_unavailable"], show_alert=True)
            return

        matches = [
            p
            for p in modules
            if hashlib.sha256(p.encode()).hexdigest()[:8] == path_hash
        ]
        if not matches:
            await callback.answer(
                STRINGS["en"]["module_not_in_database"], show_alert=True
            )
            return
        if len(matches) > 1:
            await callback.answer(STRINGS["en"]["ambiguous_module"], show_alert=True)
            logger.warning(STRINGS["en"]["hash_collision"].format(matches))
            return

        module_path = matches[0]
        # Recompute sha256 for module and verify signature prefix
        module_url = MODULES_BASE_URL + module_path
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(module_url, timeout=10) as resp:
                    if resp.status != 200:
                        await callback.answer(STRINGS["en"]["service_unavailable"], show_alert=True)
                        return
                    module_bytes = await resp.read()
        except Exception:
            await callback.answer(STRINGS["en"]["service_unavailable"], show_alert=True)
            return

        sha256 = hashlib.sha256(module_bytes).hexdigest()
        expected_sig = _security_manager.sign(f"{module_path}|{sha256}")
        if not expected_sig.startswith(sig_short):
            await callback.answer(
                STRINGS["en"]["signature_verification_failed"], show_alert=True
            )
            logger.warning(STRINGS["en"]["signature_spoof_attempt"].format(module_path))
            return

        install_code = f"#limoka:{module_path}:{expected_sig}"
        content = as_section(Code(install_code))
        await bot.send_message(callback.from_user.id, **content.as_kwargs())
        await callback.answer(STRINGS["en"]["message_sent"], show_alert=True)

    except TelegramForbiddenError:
        await callback.answer(STRINGS["en"]["cannot_send_messages"], show_alert=True)
    except Exception as e:
        logger.exception(f"Callback error: {e}")
        await callback.answer(f"❌ {type(e).__name__}", show_alert=True)


# === INSTALL RESULT CONFIRMATION ===
@router.message()
async def handle_install_result(message: Message):
    """Handle #limoka:sucsess: and #limoka:failed: from userbot"""
    if not message.text:
        return

    text = message.text.strip()

    # ✅ Success
    if text.startswith("#limoka:sucsess:"):
        parts = text.split(":", 3)
        if len(parts) >= 3:
            try:
                orig_msg_id = int(parts[2])
                await bot.delete_message(message.chat.id, orig_msg_id)
                logger.info(f"✅ Deleted original message {orig_msg_id} (success)")
            except Exception as e:
                logger.warning(f"Failed to delete success source msg {parts[2]}: {e}")
            await message.answer(STRINGS["en"]["install_success"])
            await message.delete()
        return

    # ✅ Failed
    if text.startswith("#limoka:failed:"):
        parts = text.split(":", 3)
        if len(parts) >= 3:
            try:
                orig_msg_id = int(parts[2])
                await bot.delete_message(message.chat.id, orig_msg_id)
                logger.info(f"✅ Deleted original message {orig_msg_id} (failure)")
            except Exception as e:
                logger.warning(f"Failed to delete failed source msg {parts[2]}: {e}")
            error_msg = parts[3] if len(parts) > 3 else "Unknown error"
            await message.answer(
                STRINGS["en"]["install_failed"].format(error_msg), parse_mode="HTML"
            )
            await message.delete()
        return

    # Ignore private non-service messages from non-admin users.
    # Keep silent (no logs or replies) for non-admin private messages.
    if message.chat.type == "private" and message.from_user.id not in ADMIN_IDS:
        return


# === STARTUP/SHUTDOWN ===
async def on_startup():
    global _security_manager
    logger.info(STRINGS["en"]["starting_bot"])
    try:
        _security_manager = SecurityManager(PRIVATE_KEY_FILE)
        logger.info(STRINGS["en"]["security_manager_initialized"])
    except Exception as e:
        logger.critical(STRINGS["en"]["security_manager_failed"].format(e))
        logger.critical(STRINGS["en"]["security_critical_error"])
        exit(1)

    await fetch_modules_json()
    asyncio.create_task(modules_updater())

    for admin in ADMIN_IDS:
        try:
            content = as_section(
                Bold(STRINGS["en"]["startup_notification_title"]),
                "",
                *STRINGS["en"]["startup_notification_body"],
            )
            await bot.send_message(admin, **content.as_kwargs())
        except Exception as e:
            logger.error(f"Failed to notify admin {admin}: {e}")


async def on_shutdown():
    logger.info(STRINGS["en"]["shutting_down"])
    await bot.session.close()


# === MAIN ===
async def main():
    await on_startup()
    dp.include_router(router)
    logger.info(STRINGS["en"]["bot_running"])
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
