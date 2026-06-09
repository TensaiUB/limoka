from __future__ import annotations

import ast
import hashlib
import logging
import os
import re
import textwrap
from typing import Any

from .models import HandlerEntry, ModuleInfo

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Mirrored from Loader.HANDLER_TYPES in loader/loader.py.
# Order matters: longer prefixes must come before shorter ones to avoid
# false matches (e.g. "_inlinecmd_" before "_inline_").
LEGACY_PREFIX_MAP: list[tuple[str, str]] = [
    ("_inlinecmd_", "inline_command"),
    ("_inlineq_", "inline_query"),
    ("_inline_", "inline"),
    ("_botcmd_", "bot_command"),
    ("_botmsg_", "bot_message"),
    ("_edchnpost_", "edited_channel_post"),
    ("_chnpost_", "channel_post"),
    ("_editmsg_", "edited_message"),
    ("_choseninline_", "chosen_inline_result"),
    ("_mychatmember_", "my_chat_member"),
    ("_chatmember_", "chat_member"),
    ("_chatjoin_", "chat_join_request"),
    ("_reactioncount_", "message_reaction_count"),
    ("_reaction_", "message_reaction"),
    ("_rmchatboost_", "removed_chat_boost"),
    ("_chatboost_", "chat_boost"),
    ("_precheckout_", "pre_checkout_query"),
    ("_shipq_", "shipping_query"),
    ("_pollans_", "poll_answer"),
    ("_poll_", "poll"),
    ("_cbq_", "callback_query"),
    ("_errors_", "errors"),
    ("_bisedit_", "edited_business_message"),
    ("_bisdel_", "deleted_business_message"),
    ("_bismsg_", "business_message"),
    ("_msg_", "message"),
    ("_cmd_", "command"),
]

# Maps decorator name → list of handler types it registers.
# full_command registers command + inline_command + chosen_inline_result.
DECORATOR_TYPE_MAP: dict[str, list[str]] = {
    "command": ["command"],
    "bot_command": ["bot_command"],
    "inline_command": ["inline_command"],
    "full_command": ["command", "inline_command", "chosen_inline_result"],
    "inline": ["inline"],
    "inline_query": ["inline_query"],
    "bot_message": ["bot_message"],
    "message": ["message"],
    "edited_message": ["edited_message"],
    "channel_post": ["channel_post"],
    "edited_channel_post": ["edited_channel_post"],
    "chosen_inline_result": ["chosen_inline_result"],
    "callback_query": ["callback_query"],
    "shipping_query": ["shipping_query"],
    "pre_checkout_query": ["pre_checkout_query"],
    "poll": ["poll"],
    "poll_answer": ["poll_answer"],
    "my_chat_member": ["my_chat_member"],
    "chat_member": ["chat_member"],
    "chat_join_request": ["chat_join_request"],
    "message_reaction": ["message_reaction"],
    "message_reaction_count": ["message_reaction_count"],
    "chat_boost": ["chat_boost"],
    "removed_chat_boost": ["removed_chat_boost"],
    "errors": ["errors"],
    "business_message": ["business_message"],
    "edited_business_message": ["edited_business_message"],
    "deleted_business_message": ["deleted_business_message"],
}

# Header comment keys the loader itself reads (from Loader._parse_metadata).
_HEADER_META_KEYS: frozenset[str] = frozenset({
    "description", "author", "version", "requires", "banner", "pic",
    "developer",  # alias for author
})

# Ordered list of (pattern, spdx_name) for detecting license from file content.
# Patterns are matched case-insensitively against the first ~512 bytes of LICENSE.
_LICENSE_FILE_PATTERNS: list[tuple[str, str]] = [
    (r"GNU AFFERO GENERAL PUBLIC LICENSE\s+Version 3", "AGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3", "LGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 2\.1", "LGPL-2.1"),
    (r"GNU GENERAL PUBLIC LICENSE\s+Version 3", "GPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE\s+Version 2", "GPL-2.0"),
    (r"Apache License\s+Version 2\.0", "Apache-2.0"),
    (r"Mozilla Public License\s+Version 2\.0", "MPL-2.0"),
    (r"Mozilla Public License 2\.0", "MPL-2.0"),
    (r"MIT License", "MIT"),
    (r"ISC License", "ISC"),
    (r"BSD 3-Clause", "BSD-3-Clause"),
    (r"BSD 2-Clause", "BSD-2-Clause"),
    (r"The Unlicense", "Unlicense"),
    (r"Creative Commons Zero", "CC0-1.0"),
    (r"WTFPL", "WTFPL"),
]

# Candidate filenames for the license file in a repo directory.
_LICENSE_FILENAMES: tuple[str, ...] = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING")

# Regex matching language-block headers in docstrings: "en:", "ru:", "zh-cn:", etc.
_LANG_HEADER_RE = re.compile(r"^([a-z]{2,5}(?:-[a-z]{2,4})?):[ \t]*(.*)$", re.MULTILINE)



# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_string_value(node: ast.AST) -> str | None:
    """Return the string value of a constant string AST node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):  # Python < 3.8 compatibility
        return node.s
    return None


def _parse_localized_doc(text: str | None) -> str | dict[str, str]:
    """Convert a docstring into either a plain string or a {lang: text} dict.

    Matches the runtime behaviour of ``parse_localized_doc`` in
    ``loader/utils/strings.py`` so the stored data is consistent.
    """
    if not text:
        return ""
    matches = list(_LANG_HEADER_RE.finditer(text))
    if not matches:
        return text.strip()
    result: dict[str, str] = {}
    for i, match in enumerate(matches):
        lang = match.group(1)
        inline = match.group(2).strip()
        if inline:
            body = inline
        else:
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = textwrap.dedent(text[body_start:body_end]).strip()
        if body:
            result[lang] = body
    return result or text.strip()


def _decorator_name(dec: ast.AST) -> str:
    """Return the base name of a decorator node regardless of call/attribute form."""
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Call):
        return _decorator_name(dec.func)
    return ""


def _strip_prefix(method_name: str) -> tuple[str, str] | None:
    """Return (handler_type, display_name) if method_name has a known prefix."""
    for prefix, htype in LEGACY_PREFIX_MAP:
        if method_name.startswith(prefix):
            return htype, method_name[len(prefix):]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Extractor
# ──────────────────────────────────────────────────────────────────────────────

class ModuleExtractor:
    _FILE_ENCODING: str = "utf-8"

    # Public entry-point ──────────────────────────────────────────────────────

    def extract(self, module_path: str) -> ModuleInfo | None:
        try:
            with open(module_path, encoding=self._FILE_ENCODING) as f:
                source = f.read()
        except Exception as exc:
            logger.warning("Skipping %s: read failed — %s", module_path, exc)
            return None

        source = source.lstrip("﻿")
        source = "".join(c for c in source if ord(c) >= 32 or c in "\n\r\t")
        sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()

        header_meta = self._parse_header_meta(source)
        license_name = self._read_repo_license(module_path)

        try:
            tree = ast.parse(source, filename=module_path)
        except SyntaxError as exc:
            logger.warning("Skipping %s: syntax error — %s", module_path, exc)
            return self._empty_module(module_path, sha256, header_meta, license_name)

        stem = os.path.splitext(os.path.basename(module_path))[0]
        version = self._extract_version(tree) or header_meta.get("version", "")
        module_class = self._find_module_class(tree, stem)
        if module_class is None:
            return None

        return self._build_info(module_class, tree, sha256, header_meta, license_name, version)

    # Header / file-level parsing ─────────────────────────────────────────────

    @staticmethod
    def _parse_header_meta(source: str) -> dict[str, str]:
        """Parse ``# key: value`` comment lines from the file header."""
        meta: dict[str, str] = {}
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith("# "):
                continue
            parts = stripped[2:].split(":", 1)
            if len(parts) != 2:
                continue
            key, val = parts[0].strip(), parts[1].strip()
            if key in _HEADER_META_KEYS and val:
                meta.setdefault(key, val)  # first occurrence wins
        return meta

    @staticmethod
    def _read_repo_license(module_path: str) -> str | None:
        """Detect license name by reading the LICENSE file in the module's directory."""
        module_dir = os.path.dirname(os.path.abspath(module_path))
        for filename in _LICENSE_FILENAMES:
            license_path = os.path.join(module_dir, filename)
            if not os.path.isfile(license_path):
                continue
            try:
                with open(license_path, encoding="utf-8", errors="ignore") as f:
                    # Read only the first 512 bytes — the license type is always at the top
                    content = f.read(512)
                for pattern, spdx_name in _LICENSE_FILE_PATTERNS:
                    if re.search(pattern, content, re.IGNORECASE):
                        return spdx_name
            except OSError:
                pass
        return None

    @staticmethod
    def _extract_version(tree: ast.Module) -> str:
        """Read a module-level ``__version__ = "..."`` assignment."""
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    val = _extract_string_value(node.value)
                    if val is not None:
                        return val
        return ""

    # Module class detection ──────────────────────────────────────────────────

    @staticmethod
    def _find_module_class(tree: ast.Module, stem: str) -> ast.ClassDef | None:
        """Find the module class by filename stem (primary) or Module base (fallback)."""
        candidates: list[ast.ClassDef] = [
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        # Primary: class name matches file stem case-insensitively
        for cls in candidates:
            if cls.name.lower() == stem.lower():
                return cls
        # Secondary: inherits from Module (or loader.Module, tensai.loader.Module, …)
        for cls in candidates:
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id == "Module":
                    return cls
                if isinstance(base, ast.Attribute) and base.attr == "Module":
                    return cls
        return None

    # Main builder ────────────────────────────────────────────────────────────

    @classmethod
    def _build_info(
        cls,
        node: ast.ClassDef,
        tree: ast.Module,
        sha256: str,
        header_meta: dict[str, str],
        license_name: str | None,
        version: str,
    ) -> ModuleInfo:
        raw_doc = ast.get_docstring(node)
        description: str | dict[str, str] = (
            _parse_localized_doc(raw_doc)
            if raw_doc
            else _parse_localized_doc(header_meta.get("description", ""))
        )

        # author / developer — prefer "author" header, accept "developer" alias
        authors = cls._parse_authors(
            header_meta.get("author") or header_meta.get("developer") or ""
        )
        requires = cls._parse_requires(header_meta.get("requires", ""))

        handlers: dict[str, list[HandlerEntry]] = {}
        has_on_load = False
        has_on_unload = False

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name == "on_load":
                has_on_load = True
                continue
            if item.name == "on_unload":
                has_on_unload = True
                continue
            for htype, entry in cls._extract_handler(item):
                if entry.no_doc:
                    continue
                handlers.setdefault(htype, []).append(entry)

        return ModuleInfo(
            name=node.name,
            description=description,
            authors=authors,
            version=version or None,
            requires=requires,
            banner=header_meta.get("banner") or None,
            pic=header_meta.get("pic") or None,
            license_name=license_name,
            sha256=sha256,
            handlers=handlers,
            has_strings=cls._has_strings(node),
            has_config=cls._has_config(node),
            has_dialogs=cls._has_dialogs(node, tree),
            has_on_load=has_on_load,
            has_on_unload=has_on_unload,
        )

    # Field parsers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_authors(raw: str) -> list[str]:
        """Split ``"@fajox, @vsecoder"`` into ``["@fajox", "@vsecoder"]``."""
        if not raw:
            return []
        return [a.strip() for a in re.split(r"[,;]+", raw) if a.strip()]

    @staticmethod
    def _parse_requires(raw: str) -> list[str] | None:
        """Split ``"yt-dlp,aiohttp"`` into ``["yt-dlp", "aiohttp"]``, or None."""
        if not raw:
            return None
        parts = [r.strip() for r in raw.split(",") if r.strip()]
        return parts if parts else None

    # Handler extraction ──────────────────────────────────────────────────────

    @classmethod
    def _extract_handler(
        cls, func: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[tuple[str, HandlerEntry]]:
        """Return a list of (handler_type, HandlerEntry) for this method.

        Decorator-based handlers take precedence over name-prefix inference,
        mirroring what the runtime loader does via ``_handler_meta``.
        """
        # Decorator pass — one decorator may register multiple types (full_command).
        decorator_results = cls._from_decorators(func)
        if decorator_results:
            return decorator_results

        # Prefix pass — works even when there are no (matching) decorators.
        if prefix_result := _strip_prefix(func.name):
            htype, display_name = prefix_result
            doc = ast.get_docstring(func) or ""
            return [(htype, HandlerEntry(
                name=display_name,
                original_name=func.name,
                description=_parse_localized_doc(doc),
            ))]

        return []

    @classmethod
    def _from_decorators(
        cls, func: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[tuple[str, HandlerEntry]]:
        for dec in func.decorator_list:
            dec_name = _decorator_name(dec)
            if dec_name not in DECORATOR_TYPE_MAP:
                continue

            htypes = DECORATOR_TYPE_MAP[dec_name]
            args = cls._parse_decorator_args(dec) if isinstance(dec, ast.Call) else {}

            # Description: decorator kwarg > docstring
            description: str | dict[str, str]
            if args.get("description"):
                description = args["description"]
            else:
                description = _parse_localized_doc(ast.get_docstring(func) or "")

            # Display name: strip legacy prefix if the author combined both styles
            display_name = func.name
            if result := _strip_prefix(display_name):
                display_name = result[1]

            entry = HandlerEntry(
                name=display_name,
                original_name=func.name,
                description=description,
                aliases=args.get("aliases", []),
                no_doc=args.get("no_doc", False),
                only_me=args.get("only_me", True),
                flags=args.get("flags", {}),
            )
            return [(htype, entry) for htype in htypes]

        return []

    @staticmethod
    def _parse_decorator_args(dec: ast.Call) -> dict[str, Any]:
        """Extract known kwargs from a handler decorator call."""
        result: dict[str, Any] = {}
        for kw in dec.keywords:
            if not kw.arg:
                continue
            key, val_node = kw.arg, kw.value

            if key == "aliases":
                try:
                    parsed = ast.literal_eval(val_node)
                    if isinstance(parsed, (list, tuple, set, frozenset)):
                        result["aliases"] = list(parsed)
                except Exception:
                    pass

            elif key == "description":
                try:
                    parsed = ast.literal_eval(val_node)
                    if isinstance(parsed, (str, dict)):
                        result["description"] = parsed
                except Exception:
                    sv = _extract_string_value(val_node)
                    if sv is not None:
                        result["description"] = sv

            elif key == "no_doc":
                try:
                    result["no_doc"] = bool(ast.literal_eval(val_node))
                except Exception:
                    pass

            elif key == "only_me":
                try:
                    result["only_me"] = bool(ast.literal_eval(val_node))
                except Exception:
                    pass

            elif key == "access":
                sv = _extract_string_value(val_node)
                if sv is not None:
                    result["only_me"] = sv.lower() != "all"

            elif key == "flags":
                try:
                    parsed = ast.literal_eval(val_node)
                    if isinstance(parsed, dict):
                        result["flags"] = parsed
                except Exception:
                    pass

        return result

    # Presence detectors ──────────────────────────────────────────────────────

    @staticmethod
    def _has_strings(node: ast.ClassDef) -> bool:
        """Return True if the class declares a ``strings`` attribute."""
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "strings":
                    return True
        return False

    @staticmethod
    def _has_config(node: ast.ClassDef) -> bool:
        """Return True if the class declares a ``config`` attribute."""
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    return True
        return False

    @staticmethod
    def _has_dialogs(node: ast.ClassDef, tree: ast.Module) -> bool:
        """Return True if a ``Dialog(...)`` instantiation is found anywhere in scope."""
        def _contains_dialog_call(scope: ast.AST) -> bool:
            for subnode in ast.walk(scope):
                if isinstance(subnode, ast.Call):
                    if _decorator_name(subnode.func) == "Dialog":
                        return True
            return False

        for item in node.body:
            if _contains_dialog_call(item):
                return True
        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                continue
            if _contains_dialog_call(item):
                return True
        return False

    # Fallback ────────────────────────────────────────────────────────────────

    @classmethod
    def _empty_module(
        cls,
        path: str,
        sha256: str,
        header_meta: dict[str, str],
        license_name: str | None,
    ) -> ModuleInfo:
        return ModuleInfo(
            name=os.path.splitext(os.path.basename(path))[0],
            description=_parse_localized_doc(header_meta.get("description", "")),
            authors=cls._parse_authors(
                header_meta.get("author") or header_meta.get("developer") or ""
            ),
            version=header_meta.get("version") or None,
            requires=cls._parse_requires(header_meta.get("requires", "")),
            banner=header_meta.get("banner") or None,
            pic=header_meta.get("pic") or None,
            license_name=license_name,
            sha256=sha256,
        )
