from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import aiohttp

from ..config import AppConfig
from ..parser.extractor import ModuleExtractor
from ..utils.git import GitHelper

logger = logging.getLogger(__name__)

_extractor = ModuleExtractor()


class DiffReporter:
    """Send module change diffs to a single topic in a Telegram forum chat."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        topic_id: int | None = None,
        config: AppConfig | None = None,
        git: GitHelper | None = None,
        api_url: str | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.git = git or GitHelper()
        self.token = token
        self.chat_id = chat_id
        self.topic_id = topic_id          # message_thread_id of the updates topic
        self.api_url = (api_url or self.config.telegram_api_url).rstrip("/")

    # ── Telegram API ──────────────────────────────────────────────────────────

    def _url(self, method: str) -> str:
        return f"{self.api_url}/bot{self.token}/{method}"

    def _base_payload(self) -> dict:
        payload: dict = {"chat_id": self.chat_id, "parse_mode": "HTML"}
        if self.topic_id is not None:
            payload["message_thread_id"] = self.topic_id
        return payload

    async def _send_message(self, session: aiohttp.ClientSession, text: str) -> dict:
        payload = {**self._base_payload(), "text": text, "disable_web_page_preview": True}
        async with session.post(self._url("sendMessage"), data=payload) as resp:
            return await resp.json()

    async def _send_document(
        self,
        session: aiohttp.ClientSession,
        file_path: str,
        caption: str | None = None,
    ) -> dict:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            for key, val in self._base_payload().items():
                data.add_field(key, str(val))
            data.add_field("document", f, filename=os.path.basename(file_path))
            if caption:
                data.add_field("caption", caption)
            async with session.post(self._url("sendDocument"), data=data) as resp:
                return await resp.json()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_module_info(file_path: str):
        try:
            return _extractor.extract(file_path)
        except Exception:
            return None

    @staticmethod
    def _is_module_file(file_path: str) -> bool:
        return file_path.endswith(".py") and len(Path(file_path).parts) >= 2

    @staticmethod
    def _module_name(file_path: str) -> str:
        return Path(file_path).stem

    def _file_url(self, file_path: str) -> str:
        return f"{self.config.github_raw_url}/{file_path}"

    def _build_new_message(
        self, file_path: str, authors: list[str], old_hash: str, new_hash: str
    ) -> str:
        diff_url = self.git.diff_url(old_hash, new_hash, self.config.github_base_url)
        title = f"🆕 <b>New module <code>{self._module_name(file_path)}</code></b>"
        if authors:
            title += f"\n<i>by {', '.join(authors)}</i>"
        return (
            f"{title}\n\n"
            f'<a href="{self._file_url(file_path)}">Source</a> | '
            f'<a href="{diff_url}">Diff</a>'
        )

    def _build_modified_message(
        self,
        file_path: str,
        authors: list[str],
        version: str | None,
        old_hash: str,
        new_hash: str,
    ) -> str:
        diff_url = self.git.diff_url(old_hash, new_hash, self.config.github_base_url)
        version_str = f" <code>{version}</code>" if version else ""
        title = f"🔄 <b>{self._module_name(file_path)}{version_str} updated</b>"
        if authors:
            title += f"\n<i>by {', '.join(authors)}</i>"
        return (
            f"{title}\n\n"
            f'<a href="{self._file_url(file_path)}">Source</a> | '
            f'<a href="{diff_url}">Diff</a>'
        )

    async def _send_diff(
        self, session: aiohttp.ClientSession, file_path: str, caption: str
    ) -> None:
        diff = self.git.file_diff(file_path, self.config.base_commit)
        if not diff:
            await self._send_message(session, caption)
            return

        diff_filename = f"{self._module_name(file_path)}.diff"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="", prefix="", delete=False,
            encoding="utf-8", dir=tempfile.gettempdir(),
        ) as tmp:
            tmp.write(diff)
            tmp_path = tmp.name

        final_path = os.path.join(tempfile.gettempdir(), diff_filename)
        try:
            os.rename(tmp_path, final_path)
            result = await self._send_document(session, final_path, caption=caption)
            logger.info("Sent diff for %s: ok=%s", file_path, result.get("ok"))
        except Exception as exc:
            logger.error("Error sending diff for %s: %s", file_path, exc)
        finally:
            for p in (tmp_path, final_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    # ── Main ──────────────────────────────────────────────────────────────────

    async def report(self) -> None:
        base = self.config.base_commit

        new_modules = [
            f for f in self.git.diff_filtered_files(base, "A") if self._is_module_file(f)
        ]
        modified_modules = [
            f for f in self.git.diff_filtered_files(base, "M") if self._is_module_file(f)
        ]
        deleted_modules = [
            f for f in self.git.diff_filtered_files(base, "D") if self._is_module_file(f)
        ]

        if not (new_modules or modified_modules or deleted_modules):
            logger.info("No module changes detected")
            return

        async with aiohttp.ClientSession() as session:
            for fp in deleted_modules:
                try:
                    msg = f"🗑 <b>Module <code>{self._module_name(fp)}</code> removed</b>"
                    await self._send_message(session, msg)
                except Exception as exc:
                    logger.error("Error processing deleted %s: %s", fp, exc)

            for fp in new_modules:
                try:
                    info = self._get_module_info(fp)
                    authors = info.authors if info else []
                    new_hash = self.git.resolve_commit("HEAD", fp)
                    old_hash = self.git.resolve_commit(base, fp)
                    msg = self._build_new_message(fp, authors, old_hash, new_hash)
                    await self._send_diff(session, fp, msg)
                except Exception as exc:
                    logger.error("Error processing new %s: %s", fp, exc)

            for fp in modified_modules:
                try:
                    info = self._get_module_info(fp)
                    authors = info.authors if info else []
                    version = info.version if info else None
                    new_hash = self.git.resolve_commit("HEAD", fp)
                    old_hash = self.git.resolve_commit(base, fp)
                    msg = self._build_modified_message(fp, authors, version, old_hash, new_hash)
                    await self._send_diff(session, fp, msg)
                except Exception as exc:
                    logger.error("Error processing modified %s: %s", fp, exc)
