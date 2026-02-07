import ast
import json
import os
import logging
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

def safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if hasattr(node, "id"):
            return str(node.id)
        return str(node)

def load_blacklist(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        repositories = data.get("repositories", [])
        blacklisted_modules = {}

        for i in repositories:
            path = i.get("path", "")
            blacklist = i.get("blacklist", [])
            if path and blacklist:
                blacklisted_modules[path] = blacklist

    return blacklisted_modules

def is_loader_tds(deco: ast.AST) -> bool:
    return (
        isinstance(deco, ast.Attribute)
        and isinstance(deco.value, ast.Name)
        and deco.value.id == "loader"
        and deco.attr == "tds"
    )

def extract_string_value(node: ast.AST) -> Optional[str]:
    try:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        if isinstance(node, ast.Str):
            return node.s

        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif isinstance(v, ast.FormattedValue):
                    parts.append("{" + safe_unparse(v.value) + "}")
            return "".join(parts)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            return f"{safe_unparse(node.value)}.{node.attr}"

        return None
    except Exception:
        return None

def extract_loader_command_args(decorator: ast.Call) -> Dict[str, Any]:
    args = {"lang_docs": {}, "aliases": [], "usage": None}
    try:
        for kw in decorator.keywords:
            arg_name = kw.arg
            if not arg_name:
                continue
            if arg_name.endswith("_doc"):
                lang = arg_name[:-4]
                args["lang_docs"][lang] = extract_string_value(kw.value)
            elif arg_name == "aliases":
                try:
                    val = ast.literal_eval(kw.value)
                    if isinstance(val, (list, tuple)):
                        args["aliases"] = list(val)
                except (ValueError, SyntaxError):
                    pass
            elif arg_name == "usage":
                args["usage"] = extract_string_value(kw.value)
    except Exception:
        pass
    return args

def get_module_info(module_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        logger.warning(f"Skipping {module_path}: read failed — {e}")
        return None

    source = source.lstrip('\ufeff')
    source = ''.join(c for c in source if ord(c) >= 32 or c in '\n\r\t') if source else source

    meta = {"pic": None, "banner": None, "developer": None}
    for line in source.splitlines():
        line = line.strip()
        if line.startswith("# meta "):
            try:
                key, val = line[len("# meta "):].split(":", 1)
                meta[key.strip()] = val.strip()
            except ValueError:
                pass

    try:
        tree = ast.parse(source, filename=module_path)
    except SyntaxError as e:
        logger.warning(f"Skipping {module_path}: syntax error — {e}")
        return {
            "name": module_path.split(os.sep)[-1].replace(".py", ""),
            "description": "",
            "cls_doc": {},
            "meta": meta,
            "commands": [],
            "new_commands": [],
            "inline_handlers": [],
            "strings": {},
            "has_on_load": False,
            "has_on_unload": False,
            "class_cmd_names": {},
        }

    module_data = None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        is_module_class = (
            "Mod" in node.name or
            any(is_loader_tds(d) for d in node.decorator_list) or
            any(isinstance(d, ast.Name) and d.id == "loader" for d in node.decorator_list)
        )

        if not is_module_class:
            continue

        info = {
            "name": node.name,
            "description": ast.get_docstring(node) or "",
            "cls_doc": {},
            "meta": meta,
            "commands": [],
            "new_commands": [],
            "inline_handlers": [],
            "strings": {},
            "has_on_load": False,
            "has_on_load": False,
            "has_on_unload": False,
            "class_cmd_names": {},
        }

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and (target.id == "strings" or target.id.startswith("strings_")):
                        try:
                            lit = ast.literal_eval(item.value)
                            if isinstance(lit, dict):
                                if target.id == "strings":
                                    info["strings"].update(lit)
                                    if "_cls_doc" in lit:
                                        info["cls_doc"]["default"] = lit["_cls_doc"]
                                else:
                                    lang = target.id.split("_", 1)[1] if "_" in target.id else None
                                    if lang:
                                        for k, v in lit.items():
                                            if isinstance(k, str) and isinstance(v, str):
                                                if k == "_cls_doc":
                                                    info["cls_doc"][lang] = v
                                                elif k.startswith("_cmd_doc_"):
                                                    rest = k[len("_cmd_doc_"):]
                                                    info["strings"][f"_cmd_doc_{lang}_{rest}"] = v
                                                    info["strings"][f"_cmd_doc_{rest}_{lang}"] = v
                                                elif k.startswith("_ihandle_doc_"):
                                                    rest = k[len("_ihandle_doc_"):]
                                                    info["strings"][f"_ihandle_doc_{lang}_{rest}"] = v
                                                    info["strings"][f"_ihandle_doc_{rest}_{lang}"] = v
                                                elif k.startswith("_cls_cmd_"):
                                                    info["class_cmd_names"][lang] = v
                                                else:
                                                    info["strings"][f"{k}_{lang}"] = v
                        except Exception:
                            pass

        if "_cls_doc" in info["strings"]:
            info["cls_doc"]["default"] = info["strings"]["_cls_doc"]

        for func in node.body:
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            name = func.name
            if name == "on_load":
                info["has_on_load"] = True
                continue
            if name == "on_unload":
                info["has_on_unload"] = True
                continue

            is_decorated = any(
                isinstance(d, ast.Call) and hasattr(d.func, 'attr') and 
                d.func.attr in ("command", "inline_handler", "unrestricted", "owner")
                for d in func.decorator_list
            )
            
            if name.startswith("_") and not is_decorated:
                continue

            cmd = {
                "name": name,
                "doc": ast.get_docstring(func) or "",
                "lang_docs": {},
                "aliases": [],
                "usage": None,
                "inline": False,
                "is_inline_handler": False,
                "decorators": [],
                "cmd_names": {},
            }

            for dec in func.decorator_list:
                if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr'):
                    attr = dec.func.attr
                    if attr == "command":
                        cmd.update(extract_loader_command_args(dec))
                    elif attr == "inline_handler":
                        cmd["inline"] = True
                        cmd["is_inline_handler"] = True
                    elif attr in ("unrestricted", "owner", "support"):
                        cmd["decorators"].append(attr)

            for stmt in func.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute):
                            attr = target.attr
                            val = extract_string_value(stmt.value)
                            if not val:
                                continue
                            if attr == "_cmd":
                                cmd["name"] = val
                            elif attr == "_doc":
                                cmd["doc"] = val
                            elif attr == "_cls_doc":
                                info["cls_doc"]["default"] = val
                            elif attr.startswith("_cls_doc_"):
                                lang = attr[len("_cls_doc_"):]
                                info["cls_doc"][lang] = val
                            elif attr.startswith("_cmd_"):
                                lang = attr[len("_cmd_"):]
                                cmd["cmd_names"][lang] = val

            is_command_name = "cmd" in name and not name.startswith("__")
            if not (is_decorated or is_command_name):
                continue

            clean_name = cmd["name"].replace("cmd", "").replace("_", "")
            
            descs = []
            legacy_key = f"_cmd_doc_{clean_name}"
            legacy_doc = info["strings"].get(legacy_key)
            base_doc = legacy_doc if legacy_doc else cmd["doc"]
            if base_doc:
                descs.append(base_doc)
            
            for lang, text in cmd["lang_docs"].items():
                if text:
                    descs.append(f"({lang.upper()}) {text}")
            
            for k, v in info["strings"].items():
                if k.startswith("_cmd_doc_") and clean_name in k and v:
                    if k.endswith(f"_{clean_name}"):
                        lang_part = k[len("_cmd_doc_"):-len(f"_{clean_name}")-1]
                        if lang_part:
                            descs.append(f"({lang_part.upper()}) {v}")
                    elif k.startswith(f"_cmd_doc_{clean_name}_"):
                        lang_part = k[len(f"_cmd_doc_{clean_name}_"):]
                        if lang_part:
                            descs.append(f"({lang_part.upper()}) {v}")

            full_desc = " | ".join(filter(None, descs))
            info["commands"].append({clean_name: full_desc})

            desc_map = {"default": legacy_doc or cmd["doc"]}
            desc_map.update(cmd["lang_docs"])
            
            for k, v in info["strings"].items():
                if k.startswith("_cmd_doc_") and clean_name in k and v:
                    if k.endswith(f"_{clean_name}"):
                        lang_part = k[len("_cmd_doc_"):-len(f"_{clean_name}")-1]
                        if lang_part:
                            desc_map[lang_part] = v
                    elif k.startswith(f"_cmd_doc_{clean_name}_"):
                        lang_part = k[len(f"_cmd_doc_{clean_name}_"):]
                        if lang_part:
                            desc_map[lang_part] = v

            info["new_commands"].append({
                "name": clean_name,
                "original_name": cmd["name"],
                "description": desc_map,
                "cmd_names": cmd["cmd_names"],
                "aliases": cmd["aliases"],
                "usage": cmd["usage"],
                "inline": cmd["inline"],
                "is_inline_handler": cmd["is_inline_handler"],
                "decorators": cmd["decorators"],
            })

            if cmd["is_inline_handler"]:
                inline_desc_map = {"default": cmd["doc"]}
                inline_desc_map.update(cmd["lang_docs"])
                
                for k, v in info["strings"].items():
                    if k.startswith("_ihandle_doc_") and clean_name in k and v:
                        if k.endswith(f"_{clean_name}"):
                            lang_part = k[len("_ihandle_doc_"):-len(f"_{clean_name}")-1]
                            if lang_part:
                                inline_desc_map[lang_part] = v
                        elif k.startswith(f"_ihandle_doc_{clean_name}_"):
                            lang_part = k[len(f"_ihandle_doc_{clean_name}_"):]
                            if lang_part:
                                inline_desc_map[lang_part] = v
                
                info["inline_handlers"].append({
                    "name": clean_name,
                    "description": inline_desc_map,
                    "decorators": cmd["decorators"],
                })

        module_data = info
        break

    return module_data

def main():
    base_dir = os.getcwd()
    modules = {}
    blacklisted_modules = load_blacklist("repositories.json")

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ("venv", ".venv", "env", ".env", ".git")]

        for file in files:
            if file.endswith(".py") and not file.startswith("_") and file not in blacklisted_modules.get(os.path.relpath(root, base_dir), []):
                path = os.path.join(root, file)
                try:
                    data = get_module_info(path)
                    if data:
                        rel = os.path.relpath(path, base_dir).replace("\\", "/")
                        modules[rel] = data
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")

    output = {
        "modules": modules,
        "meta": {
            "total_modules": len(modules),
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
    }

    with open("modules.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"modules.json written ({len(modules)} modules)")

if __name__ == "__main__":
    main()