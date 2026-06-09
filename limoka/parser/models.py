from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HandlerEntry:
    name: str
    original_name: str
    description: str | dict[str, str]
    aliases: list[str] = field(default_factory=list)
    no_doc: bool = False
    only_me: bool = True
    flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "original_name": self.original_name,
            "description": self.description,
            "aliases": self.aliases,
            "only_me": self.only_me,
            "flags": self.flags,
        }


@dataclass
class ModuleInfo:
    name: str
    description: str | dict[str, str] = ""
    authors: list[str] = field(default_factory=list)
    version: str | None = None
    requires: list[str] | None = None
    banner: str | None = None
    pic: str | None = None
    license_name: str | None = None
    sha256: str = ""
    handlers: dict[str, list[HandlerEntry]] = field(default_factory=dict)
    has_strings: bool = False
    has_config: bool = False
    has_dialogs: bool = False
    has_on_load: bool = False
    has_on_unload: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description or None,
            "authors": self.authors,
            "version": self.version or None,
            "requires": self.requires or None,
            "banner": self.banner or None,
            "pic": self.pic,
            "license": self.license_name,
            "sha256": self.sha256,
            "handlers": {
                htype: [h.to_dict() for h in hlist]
                for htype, hlist in self.handlers.items()
                if hlist
            },
            "has_strings": self.has_strings,
            "has_config": self.has_config,
            "has_dialogs": self.has_dialogs,
            "has_on_load": self.has_on_load,
            "has_on_unload": self.has_on_unload,
        }


@dataclass
class ParseResult:
    modules: dict[str, ModuleInfo]

    @property
    def total(self) -> int:
        return len(self.modules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modules": {path: info.to_dict() for path, info in self.modules.items()},
            "meta": {
                "total_modules": self.total,
                "generated_at": datetime.now().isoformat(),
            },
        }
