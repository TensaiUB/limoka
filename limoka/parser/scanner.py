from __future__ import annotations

import json
import logging
import os

from ..config import RepoConfig
from .extractor import ModuleExtractor
from .models import ModuleInfo, ParseResult

logger = logging.getLogger(__name__)


class ModuleScanner:
    def __init__(
        self,
        base_dir: str | None = None,
        ignored_dirs: frozenset[str] | None = None,
        blacklist: dict[str, list[str]] | None = None,
    ) -> None:
        self.base_dir = base_dir or os.getcwd()
        self.ignored_dirs = set(
            ignored_dirs
            if ignored_dirs is not None
            else {"venv", ".venv", "env", ".env", ".git", "limoka", "loader"}
        )
        self.blacklist = blacklist or {}

    @classmethod
    def from_repositories_json(
        cls,
        json_path: str,
        base_dir: str | None = None,
        ignored_dirs: frozenset[str] | None = None,
    ) -> "ModuleScanner":
        blacklist: dict[str, list[str]] = {}
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            for repo_data in data.get("repositories", []):
                repo = RepoConfig(
                    url=repo_data.get("url", ""),
                    tags=repo_data.get("tags", []),
                    blacklist=repo_data.get("blacklist", []),
                )
                if repo.url and repo.blacklist:
                    blacklist[repo.key] = repo.blacklist
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load blacklist: %s", exc)

        return cls(base_dir=base_dir, ignored_dirs=ignored_dirs, blacklist=blacklist)

    def scan(self) -> ParseResult:
        modules: dict[str, ModuleInfo] = {}
        extractor = ModuleExtractor()

        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            rel_root = os.path.relpath(root, self.base_dir).replace("\\", "/")
            parts = rel_root.split("/")
            repo_key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else None

            for filename in files:
                if not self._should_process(filename, repo_key):
                    continue
                path = os.path.join(root, filename)
                try:
                    data = extractor.extract(path)
                    if data is not None:
                        rel = os.path.relpath(path, self.base_dir).replace("\\", "/")
                        modules[rel] = data
                except Exception as exc:
                    logger.error("Error processing %s: %s", path, exc)

        return ParseResult(modules=modules)

    def _should_process(self, filename: str, repo_key: str | None) -> bool:
        # Only scan files inside an owner/repo directory (at least 2 levels deep)
        if not repo_key:
            return False
        if not (filename.endswith(".py") and not filename.startswith("_")):
            return False
        if repo_key in self.blacklist and filename in self.blacklist[repo_key]:
            return False
        return True
