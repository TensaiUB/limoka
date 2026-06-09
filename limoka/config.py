from __future__ import annotations

import os
from dataclasses import dataclass, field

GITHUB_OWNER: str = os.getenv("LIMOKA_GITHUB_OWNER", "TensaiUB")
GITHUB_REPO_NAME: str = os.getenv("LIMOKA_GITHUB_REPO_NAME", "limoka")
GITHUB_BASE_URL: str = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO_NAME}"
GITHUB_RAW_URL: str = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/"
    f"{GITHUB_REPO_NAME}/refs/heads/main"
)

REPOSITORIES_JSON: str = "repositories.json"
MODULES_JSON: str = "modules.json"
DEVELOPERS_JSON: str = "developers.json"

IGNORED_DIRS: frozenset[str] = frozenset({"venv", ".venv", "env", ".env", ".git"})

DEFAULT_BASE_COMMIT: str = "HEAD~1"
DEFAULT_TELEGRAM_API_URL: str = "https://api.telegram.org"
ZIP_CHUNK_SIZE: str = "49M"


@dataclass
class RepoConfig:
    url: str
    tags: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)

    @property
    def owner(self) -> str:
        return self.url.rstrip("/").split("/")[-2]

    @property
    def name(self) -> str:
        return self.url.rstrip("/").split("/")[-1]

    @property
    def key(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class AppConfig:
    github_owner: str = GITHUB_OWNER
    github_repo: str = GITHUB_REPO_NAME
    repositories_json: str = REPOSITORIES_JSON
    modules_json: str = MODULES_JSON
    ignored_dirs: frozenset[str] = IGNORED_DIRS
    base_commit: str = DEFAULT_BASE_COMMIT
    telegram_api_url: str = DEFAULT_TELEGRAM_API_URL

    @property
    def github_base_url(self) -> str:
        return f"https://github.com/{self.github_owner}/{self.github_repo}"

    @property
    def github_raw_url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/"
            f"{self.github_owner}/{self.github_repo}/refs/heads/main"
        )
