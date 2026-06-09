from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass

from ..utils.git import GitHelper

logger = logging.getLogger(__name__)

DIFFS_DIR = "diffs"


@dataclass
class DiffEntry:
    path: str           # "vsecoder/tensai_modules/Downloader.py"
    module_name: str
    commit_message: str
    commit_sha: str     # short (7 chars)
    added: int
    removed: int
    diff_key: str       # sanitized key used as filename: "vsecoder_tensai_modules_Downloader"


def _path_to_key(path: str) -> str:
    return path.replace("/", "_").replace("\\", "_").removesuffix(".py")


def _count_diff_lines(diff_text: str) -> tuple[int, int]:
    added = removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


class ModuleDiffer:
    def __init__(self, diffs_dir: str = DIFFS_DIR, git: GitHelper | None = None) -> None:
        self.diffs_dir = diffs_dir
        self.git = git or GitHelper()

    def generate(
        self,
        old_modules: dict[str, dict],
        new_modules: dict[str, dict],
    ) -> list[DiffEntry]:
        """Compare sha256 values, write diff files, return list of changed entries.

        Always writes diffs/index.json (empty list when nothing changed) so that
        ``git add diffs/`` never fails and the Limoka module can reliably fetch it.
        """
        self._clean()
        os.makedirs(self.diffs_dir, exist_ok=True)

        changed = [
            path for path, info in new_modules.items()
            if old_modules.get(path, {}).get("sha256") != info.get("sha256")
        ]

        entries: list[DiffEntry] = []
        for path in changed:
            entry = self._process(path, new_modules[path])
            if entry:
                entries.append(entry)

        index_path = os.path.join(self.diffs_dir, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in entries], f, ensure_ascii=False, indent=2)

        logger.info("ModuleDiffer: %d changed modules → %s", len(entries), index_path)
        return entries

    def _clean(self) -> None:
        if os.path.isdir(self.diffs_dir):
            shutil.rmtree(self.diffs_dir)

    def _process(self, path: str, module_info: dict) -> DiffEntry | None:
        diff_key = _path_to_key(path)
        module_name = module_info.get("name") or diff_key

        diff_text = self.git.file_diff(path, "HEAD~1")
        added, removed = _count_diff_lines(diff_text)

        commit_sha = ""
        try:
            commit_sha = self.git.resolve_commit("HEAD", path)[:7]
        except Exception:
            pass

        commit_message = self.git.file_commit_message(path) or self.git.commit_message()

        if diff_text:
            diff_path = os.path.join(self.diffs_dir, f"{diff_key}.diff")
            with open(diff_path, "w", encoding="utf-8") as f:
                f.write(diff_text)

        return DiffEntry(
            path=path,
            module_name=module_name,
            commit_message=commit_message,
            commit_sha=commit_sha,
            added=added,
            removed=removed,
            diff_key=diff_key,
        )
