"""
Точка входа для бэкапа репозитория в Telegram.
"""

from __future__ import annotations

import argparse
import asyncio

from limoka.backup import BackupArchiver


def main() -> None:
    """Создаёт архив и отправляет в Telegram."""
    parser = argparse.ArgumentParser(description="Backup Script")
    parser.add_argument(
        "--token", type=str, required=True, help="Token of Telegram bot"
    )
    parser.add_argument(
        "--api_url",
        type=str,
        default="https://api.telegram.org",
        help="API URL of Telegram API",
    )
    parser.add_argument(
        "--chat_id",
        type=str,
        required=True,
        help="Chat ID to send backup message to",
    )
    args = parser.parse_args()

    archiver = BackupArchiver(
        token=args.token,
        chat_id=args.chat_id,
        api_url=args.api_url,
    )
    asyncio.run(archiver.backup())


if __name__ == "__main__":
    main()
