from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess

import requests

from ..config import RepoConfig
from ..utils.git import GitHelper

logger = logging.getLogger(__name__)


class RepoCloner:
    _PROTECTED_DIRS: set[str] = {".git", ".github", "assets", "limoka", "__pycache__"}

    def __init__(
        self, base_dir: str | None = None, git: GitHelper | None = None
    ) -> None:
        self.base_dir = base_dir or os.getcwd()
        self.git = git or GitHelper(cwd=self.base_dir)

    @staticmethod
    def load_repos(json_path: str) -> list[RepoConfig]:
        repos: list[RepoConfig] = []
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        for repo in data.get("repositories", []):
            repos.append(
                RepoConfig(
                    url=repo["url"],
                    tags=repo.get("tags", []),
                    blacklist=repo.get("blacklist", []),
                )
            )
        return repos

    @staticmethod
    def _repo_path(url: str) -> str:
        return url.replace("https://github.com/", "")

    @staticmethod
    def _is_valid_filename(name: str) -> bool:
        return not bool(re.search(r'[<>:"/\\|?*]', name))

    @classmethod
    def _rename_invalid_files(cls, local_path: str) -> None:
        for root, dirs, files in os.walk(local_path):
            for file in files:
                if not cls._is_valid_filename(file):
                    old = os.path.join(root, file)
                    new = os.path.join(root, re.sub(r'[<>:"/\\|?*]', "_", file))
                    try:
                        os.rename(old, new)
                        logger.info("Renamed: %s → %s", old, new)
                    except OSError as exc:
                        logger.error("Rename failed %s: %s", old, exc)

    @staticmethod
    def _is_url_accessible(url: str, timeout: int = 5) -> bool:
        try:
            return requests.head(url, timeout=timeout).status_code == 200
        except requests.RequestException:
            return False

    def clean_unused(self, repos: list[RepoConfig]) -> None:
        existing = {
            d
            for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
        }
        existing.difference_update(self._PROTECTED_DIRS)
        expected = {self._repo_path(r.url).split("/")[0] for r in repos}

        for dir_name in existing:
            dir_path = os.path.join(self.base_dir, dir_name)
            if dir_name not in expected:
                shutil.rmtree(dir_path, ignore_errors=True)
                logger.info("Removed (not in list): %s", dir_path)

        for repo in repos:
            local = os.path.join(self.base_dir, self._repo_path(repo.url))
            if os.path.exists(local) and not self._is_url_accessible(repo.url):
                shutil.rmtree(local, ignore_errors=True)
                logger.info("Removed (inaccessible): %s", local)

    def clone_or_update(self, repo: RepoConfig) -> None:
        repo_path = self._repo_path(repo.url)
        owner, repo_name = repo_path.split("/")
        local_path = os.path.join(self.base_dir, owner, repo_name)

        if os.path.exists(local_path):
            shutil.rmtree(local_path)
            logger.info("Removed old: %s", local_path)

        if not self.git.is_remote_accessible(repo.url):
            logger.warning("Skipping inaccessible: %s", repo.url)
            return

        os.makedirs(os.path.join(self.base_dir, owner), exist_ok=True)

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo.url, local_path],
                check=True,
                capture_output=True,
                text=True,
            )
            shutil.rmtree(os.path.join(local_path, ".git"), ignore_errors=True)
            self._rename_invalid_files(local_path)
            logger.info("Cloned: %s → %s", repo.url, local_path)
        except subprocess.CalledProcessError as exc:
            logger.error("Clone failed %s: %s", repo.url, exc.stderr)

    def process(self, json_path: str) -> None:
        repos = self.load_repos(json_path)
        self.clean_unused(repos)
        for repo in repos:
            self.clone_or_update(repo)
