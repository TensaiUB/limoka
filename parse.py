import os
import ast
import json

from clone_repos import repos
from typing import Dict

# TODO: ADD VENV IGNORE


def get_module_info(module_path):
    """Парсит Python-модуль и извлекает информацию о нем."""
    with open(module_path, "r", encoding="utf-8") as f:
        module_content = f.read()

    meta_info = {"pic": None, "banner": None}
    for line in module_content.split("\n"):
        if line.startswith("# meta"):
            key, value = line.replace("# meta ", "").split(": ")
            meta_info[key] = value

    tree = ast.parse(module_content)

    def get_decorator_names(decorator_list):
        return [ast.unparse(decorator) for decorator in decorator_list]

    def extract_loader_command_args(decorator):
        """Извлекает аргументы `ru_doc` и `en_doc` из `@loader.command`."""
        if (
            isinstance(decorator, ast.Call)
            and hasattr(decorator.func, "attr")
            and decorator.func.attr == "command"
        ):
            ru_doc = None
            en_doc = None
            for keyword in decorator.keywords:
                if keyword.arg == "ru_doc":
                    ru_doc = ast.literal_eval(keyword.value)
                elif keyword.arg == "en_doc":
                    en_doc = ast.literal_eval(keyword.value)
            return ru_doc, en_doc
        return None, None

    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            decorators = get_decorator_names(node.decorator_list)
            is_tds_mod = [d for d in decorators if "loader.tds" in d]
            if "Mod" not in node.name and not is_tds_mod:
                continue

            class_docstring = ast.get_docstring(node)
            class_info = {
                "name": node.name,
                "description": class_docstring,
                "meta": meta_info,
                "commands": [],
                "new_commands": [],
            }

            for class_body_node in node.body:
                if isinstance(class_body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorators = get_decorator_names(class_body_node.decorator_list)
                    is_loader_command = [d for d in decorators if "command" in d]
                    if not is_loader_command and "cmd" not in class_body_node.name:
                        continue

                    method_docstring = ast.get_docstring(class_body_node)
                    command_name = class_body_node.name
                    ru_doc, en_doc = None, None

                    for decorator in class_body_node.decorator_list:
                        ru_doc_tmp, en_doc_tmp = extract_loader_command_args(decorator)
                        if ru_doc_tmp:
                            ru_doc = ru_doc_tmp
                        if en_doc_tmp:
                            en_doc = en_doc_tmp

                    descriptions = []
                    if method_docstring:
                        descriptions.append(method_docstring)
                    if ru_doc:
                        descriptions.append(ru_doc)
                    if en_doc:
                        descriptions.append(en_doc)

                    class_info["commands"].append(
                        {command_name: ' '.join(descriptions)}
                    )

                    command_name = command_name.replace('cmd', '')

                    class_info["new_commands"].append(
                        {
                            command_name: {
                                "ru_doc": ru_doc,
                                "en_doc": en_doc,
                                "doc": method_docstring,
                            }
                        }
                    )

            result = class_info

    return result

def parse_developers(base_dir: str) -> Dict[str, list]:
    developers = {
        "repo": set(),  # используем set внутри функции
        "channel": set()
    }
    
    for repo_url in repos:
        repo_path = repo_url.replace("https://github.com/", "")
        try:
            owner, repo_name = repo_path.split("/")
            developers["repo"].add(owner)
        except ValueError:
            print(f"Incorrect URL of repository: {repo_url}")
            continue

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    module_info = get_module_info(file_path)
                    if module_info and "meta" in module_info:
                        developer = module_info["meta"].get('developer')
                        if developer:  # Проверяем, что developer не None
                            # Разделяем строки с запятыми, &, | и пробелами
                            for dev in developer.replace(',', ' ').replace('&', ' ').replace('|', ' ').split():
                                # Добавляем только элементы, начинающиеся с @
                                if dev.startswith('@'):
                                    developers["channel"].add(dev.strip())
                except Exception as e:
                    print(f"Ошибка при парсинге файла {file_path}: {e}")

    # Преобразуем set в list перед возвратом
    return {
        "repo": list(developers["repo"]),
        "channel": list(developers["channel"])
    }


modules_data = {}
base_dir = os.getcwd()

for root, _, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".py"):
            file_path = os.path.join(root, file)
            try:
                module_info = get_module_info(file_path)
                if module_info:
                    relative_path = os.path.relpath(file_path, base_dir)
                    modules_data[relative_path] = module_info
            except Exception as e:
                print(f"Ошибка при парсинге файла {file_path}: {e}")

developers = parse_developers(base_dir)

with open("modules.json", "w", encoding="utf-8") as json_file:
   json.dump(modules_data, json_file, ensure_ascii=False, indent=2)

print("Файл modules.json создан!")

with open("developers.json", "w", encoding="utf-8") as json_file:
   json.dump(developers, json_file, ensure_ascii=False, indent=2)

print("Файл developers.json создан!")