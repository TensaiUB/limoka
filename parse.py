"""
Точка входа для парсинга модулей.
"""

from __future__ import annotations

import json
import logging
import os

from limoka.parser import ModuleScanner, ModuleWriter
from limoka.parser.differ import ModuleDiffer

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def _load_old_modules(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("modules") or {}
    except Exception:
        return {}


def main() -> None:
    modules_path = "modules.json"
    old_modules = _load_old_modules(modules_path)

    scanner = ModuleScanner.from_repositories_json("repositories.json")
    result = scanner.scan()

    writer = ModuleWriter(output_path=modules_path)
    writer.write(result)

    new_modules = {path: info.to_dict() for path, info in result.modules.items()}
    ModuleDiffer().generate(old_modules, new_modules)

    print(f"modules.json written ({result.total} modules)")


if __name__ == "__main__":
    main()
