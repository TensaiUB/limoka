"""
Точка входа для клонирования репозиториев.
"""

from __future__ import annotations

from limoka.repository import RepoCloner


def main() -> None:
    """Клонирует/обновляет все репозитории из repositories.json."""
    cloner = RepoCloner()
    cloner.process("repositories.json")


if __name__ == "__main__":
    main()
