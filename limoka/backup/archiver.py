from __future__ import annotations

import glob
import logging
import os
import subprocess

import aiohttp

from ..config import AppConfig
from ..utils.git import GitHelper

logger = logging.getLogger(__name__)


class BackupArchiver:
    _ORIGINAL_ZIP: str = "repository-original.zip"
    _ZIP_NAME: str = "repository.zip"
    _PART_PREFIX: str = "repository-part-"

    def __init__(
        self,
        token: str,
        chat_id: str,
        config: AppConfig | None = None,
        git: GitHelper | None = None,
        api_url: str | None = None,
        chunk_size: str = "49M",
    ) -> None:
        self.config = config or AppConfig()
        self.git = git or GitHelper()
        self.token = token
        self.chat_id = chat_id
        self.api_url = api_url or self.config.telegram_api_url
        self.chunk_size = chunk_size

    async def _send_file(
        self, session: aiohttp.ClientSession, file_path: str, caption: str | None = None
    ) -> dict:
        url = f"{self.api_url}/bot{self.token}/sendDocument"
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("chat_id", self.chat_id)
            data.add_field("document", f, filename=os.path.basename(file_path))
            if caption:
                data.add_field("caption", caption)
                data.add_field("parse_mode", "Markdown")
            async with session.post(url, data=data) as resp:
                return await resp.json()

    def _create_archive(self) -> list[str]:
        subprocess.run(
            ["git", "archive", "--format=zip", "--output", self._ORIGINAL_ZIP, "HEAD"],
            check=True,
        )
        subprocess.run(["zip", "-9", self._ZIP_NAME, self._ORIGINAL_ZIP], check=True)
        os.remove(self._ORIGINAL_ZIP)
        subprocess.run(
            ["split", "-b", self.chunk_size, self._ZIP_NAME, self._PART_PREFIX],
            check=True,
        )
        return sorted(glob.glob(f"{self._PART_PREFIX}*"))

    def _cleanup(self, parts: list[str]) -> None:
        for p in [self._ZIP_NAME, *parts]:
            if os.path.exists(p):
                os.remove(p)

    def _build_caption(self) -> str:
        msg = self.git.commit_message()
        date = self.git.commit_date_iso()
        short_hash = self.git.current_sha(short=True)
        url = self.git.commit_url(self.config.github_base_url)
        return (
            f"Commit Date: {date}, "
            f"Commit Message: {msg}, "
            f"Commit Hash: [`{short_hash}`]({url})"
        )

    async def backup(self) -> None:
        parts = self._create_archive()
        async with aiohttp.ClientSession() as session:
            first = True
            caption = self._build_caption()
            for part in parts:
                cap = caption if first else None
                result = await self._send_file(session, part, caption=cap)
                logger.info("Sent %s: %s", part, result)
                first = False
        self._cleanup(parts)
