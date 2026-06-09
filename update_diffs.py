"""
Точка входа для отправки диффов изменённых модулей.

Отправляет в указанный топик форум-чата (message_thread_id).
"""

from __future__ import annotations

import argparse
import asyncio

from limoka.config import AppConfig
from limoka.reporter import DiffReporter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send module change diffs to a Telegram forum topic."
    )
    parser.add_argument("--token", required=True, help="Telegram bot token")
    parser.add_argument("--chat_id", required=True, help="Forum supergroup chat ID")
    parser.add_argument(
        "--topic_id",
        type=int,
        default=None,
        help="message_thread_id of the updates topic (omit to send without topic)",
    )
    parser.add_argument(
        "--api_url",
        default="https://api.telegram.org",
        help="Telegram Bot API URL",
    )
    parser.add_argument(
        "--base_commit",
        default="HEAD~1",
        help="Base commit to diff against (default: HEAD~1)",
    )
    args = parser.parse_args()

    config = AppConfig(
        base_commit=args.base_commit,
        telegram_api_url=args.api_url,
    )
    reporter = DiffReporter(
        token=args.token,
        chat_id=args.chat_id,
        topic_id=args.topic_id,
        config=config,
        api_url=args.api_url,
    )
    asyncio.run(reporter.report())


if __name__ == "__main__":
    main()
