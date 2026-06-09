from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GitHelper:
    def __init__(self, cwd: str | Path | None = None) -> None:
        self.cwd = str(cwd or Path.cwd())

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.cwd, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result.stdout

    def _run_silent(self, *args: str) -> int:
        return subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode

    def resolve_commit(self, ref: str, file_path: str) -> str:
        try:
            return self._run("rev-list", "-n", "1", ref, "--", file_path).strip()
        except subprocess.CalledProcessError:
            logger.warning("Cannot resolve commit for %s:%s", ref, file_path)
            return ref

    def current_sha(self, short: bool = False) -> str:
        args = ["rev-parse", "--short=6", "HEAD"] if short else ["rev-parse", "HEAD"]
        return self._run(*args).strip()

    def commit_message(self, ref: str = "HEAD") -> str:
        return self._run("log", "-1", "--pretty=%s", ref).strip()

    def file_commit_message(self, path: str, ref: str = "HEAD") -> str:
        """Return subject of the most recent commit touching path at ref."""
        try:
            return self._run("log", "-1", "--pretty=%s", ref, "--", path).strip()
        except subprocess.CalledProcessError:
            return ""

    def commit_date_iso(self) -> str:
        return self._run("log", "-1", "--pretty=%ci").strip()

    def commit_url(self, repo_base_url: str) -> str:
        return f"{repo_base_url}/commit/{self.current_sha()}"

    def changed_files(self, base_commit: str) -> list[str]:
        try:
            output = self._run("diff", "--name-only", base_commit, "HEAD")
            return [f for f in output.strip().split("\n") if f]
        except subprocess.CalledProcessError:
            return []

    def diff_filtered_files(self, base_commit: str, diff_filter: str) -> list[str]:
        try:
            output = self._run(
                "diff",
                f"--diff-filter={diff_filter}",
                "--name-only",
                base_commit,
                "HEAD",
            )
            return [f for f in output.strip().splitlines() if f]
        except subprocess.CalledProcessError:
            return []

    def file_diff(self, file_path: str, base_commit: str) -> str:
        try:
            return self._run("diff", base_commit, "HEAD", "--", file_path)
        except subprocess.CalledProcessError:
            return ""

    def diff_url(self, old_hash: str, new_hash: str, repo_base_url: str) -> str:
        return f"{repo_base_url}/compare/{old_hash}...{new_hash}.diff"

    def is_remote_accessible(self, repo_url: str) -> bool:
        return self._run_silent("ls-remote", repo_url) == 0
