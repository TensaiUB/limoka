from __future__ import annotations

import json
import logging
import os

from .models import ParseResult

logger = logging.getLogger(__name__)


class ModuleWriter:
    def __init__(
        self,
        output_path: str = "modules.json",
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> None:
        self.output_path = output_path
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def write(self, result: ParseResult) -> str:
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(
                result.to_dict(),
                f,
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
            )
        full_path = os.path.abspath(self.output_path)
        logger.info("modules.json written (%d modules) → %s", result.total, full_path)
        return full_path
