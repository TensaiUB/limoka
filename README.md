# Limoka — Module Library

## Description

Limoka is a CI/CD-driven indexer for [Tensai userbot](https://github.com/TensaiUB/tensai) modules.
It clones community repositories on a schedule, parses every `.py` module file using AST introspection,
and produces a structured `modules.json` catalog consumed by the Tensai module store.

## Technology Stack

- **Python 3.11+** — parser, reporter, backup scripts
- **aiohttp** — async Telegram API calls (diff notifications, backup delivery)
- **requests** — repository cloning helpers
- **GitHub Actions / GitLab CI** — scheduled automation pipelines

## Infrastructure

```
limoka/
├── limoka/
│   ├── parser/          # AST-based module scanner & extractor
│   ├── repository/      # Git repo cloner
│   ├── reporter/        # Telegram diff notifications
│   ├── backup/          # ZIP archiver + Telegram delivery
│   └── utils/           # Git helpers
├── parse.py             # Entry: scan repos → modules.json
├── clone_repos.py       # Entry: clone/update repos from repositories.json
├── update_diffs.py      # Entry: send module change diffs to Telegram
├── backup.py            # Entry: archive repo and send to Telegram
├── repositories.json    # List of module repositories to track
└── modules.json         # Generated module catalog (auto-updated)
```

## Environment Variables

All variables are read at runtime; **bold** ones are required for their respective jobs to work.

### Git / Repository

| Variable | Default | Used in | Description |
|---|---|---|---|
| `LIMOKA_GIT_REMOTE` | `github.com/TensaiUB/limoka.git` | GitHub CI | Override the git remote URL (useful for self-hosted mirrors) |
| `LIMOKA_COMMIT_BASE_URL` | `https://github.com/TensaiUB/limoka` | GitHub CI | Base URL prepended to commit hashes in diff messages |
| `LIMOKA_GITHUB_OWNER` | `TensaiUB` | GitHub CI, scripts | GitHub organisation or user that owns the limoka repository |
| `LIMOKA_GITHUB_REPO_NAME` | `limoka` | GitHub CI, scripts | GitHub repository name |
| `LIMOKA_COMMIT_BASE_URL` | `https://git.vsecoder.dev/root/limoka` | GitLab CI | Override commit base URL on GitLab |
| `LIMOKA_GIT_REMOTE` | `git.vsecoder.dev/root/limoka.git` | GitLab CI | Override git remote on GitLab |

### Authentication

| Variable | Default | Used in | Description |
|---|---|---|---|
| **`GH_TOKEN`** | — | GitHub CI | GitHub Actions token for pushing branches and opening PRs (provided automatically by Actions) |
| **`GITLAB_TOKEN`** | — | GitLab CI | Personal access token or CI token with `write_repository` scope for push + MR creation |

### Telegram

| Variable | Default | Used in | Description |
|---|---|---|---|
| **`TELEGRAM_BOT_TOKEN`** | — | `backup.py`, `update_diffs.py`, GitHub CI, GitLab CI | Bot token from [@BotFather](https://t.me/BotFather) used for all Telegram API calls |
| **`TELEGRAM_CHAT_ID`** | — | `backup.py`, GitHub CI | Chat / channel ID where backup archive parts are sent |
| **`TELEGRAM_CHAT_ID_UPDATE`** | — | `update_diffs.py`, GitHub CI | Forum supergroup chat ID where module diff notifications are posted |
| `TELEGRAM_TOPIC_ID_UPDATE` | — | GitHub CI | `message_thread_id` of the updates topic inside the forum chat (optional — sends to General if omitted) |
| `TELEGRAM_API_URL` | `https://api.telegram.org` | `update_diffs.py`, `backup.py` | Override Telegram Bot API URL (e.g. for a local Bot API server) |

### CLI arguments (override env vars for one-off runs)

`update_diffs.py` and `backup.py` accept CLI flags that take precedence over environment variables:

```
python3 update_diffs.py --token <BOT_TOKEN> --chat_id <CHAT_ID> [--base_commit HEAD~1]
python3 backup.py       --token <BOT_TOKEN> --chat_id <CHAT_ID>
```

## Contributing

1. Add your repository URL to `repositories.json`.
2. Open a pull request — the CI pipeline will clone, parse, and validate the modules automatically.

## License

This project is licensed under the [MIT License](LICENSE).
