import asyncio
import aiohttp
import argparse
import subprocess
import os
import tempfile
from pathlib import Path
import ast

import parse

parser = argparse.ArgumentParser(description="Update Diffs Script")
parser.add_argument(
    "--token",
    type=str,
    required=True,
    help="Token of Telegram bot",
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
    help="Chat ID to send updates to",
)
parser.add_argument(
    "--base_commit",
    type=str,
    default="HEAD~1",
    help="Base commit to compare against",
)

arguments = parser.parse_args()

async def send_message(session, text):
    """Send a text message to the channel"""
    url = f"{arguments.api_url}/bot{arguments.token}/sendMessage"
    data = {
        'chat_id': arguments.chat_id,
        'text': text,
        'parse_mode': 'Markdown',
    }
    async with session.post(url, data=data) as response:
        return await response.json()

async def send_document(session, file_path, caption=None):
    """Send a document to the channel"""
    url = f"{arguments.api_url}/bot{arguments.token}/sendDocument"
    with open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('chat_id', arguments.chat_id)
        data.add_field('document', f, filename=os.path.basename(file_path))
        data.add_field('parse_mode', 'HTML')
        if caption:
            data.add_field('caption', caption)
            data.add_field('parse_mode', 'Markdown')
        async with session.post(url, data=data) as response:
            return await response.json()

def get_changed_files(base_commit):
    """Get list of changed files between commits"""
    try:
        result = subprocess.check_output(
            ['git', 'diff', '--name-only', base_commit, 'HEAD'],
            cwd=os.getcwd()
        ).decode().strip().split('\n')
        return [f for f in result if f]
    except subprocess.CalledProcessError:
        return []

def get_deleted_files(base_commit):
    """Get list of deleted files between commits"""
    try:
        result = subprocess.check_output(
            ['git', 'diff', '--diff-filter=D', '--name-only', base_commit, 'HEAD'],
            cwd=os.getcwd()
        ).decode().strip().split('\n')
        return [f for f in result if f]
    except subprocess.CalledProcessError:
        return []

def get_diff_files(base_commit, diff_filter):
    """Get list of files for a specific git diff filter"""
    try:
        result = subprocess.check_output(
            ['git', 'diff', f'--diff-filter={diff_filter}', '--name-only', base_commit, 'HEAD'],
            cwd=os.getcwd()
        ).decode().strip().splitlines()
        return [f for f in result if f]
    except subprocess.CalledProcessError:
        return []


def get_added_files(base_commit):
    return get_diff_files(base_commit, 'A')


def get_modified_files(base_commit):
    return get_diff_files(base_commit, 'M')


def get_file_diff(file_path, base_commit):
    """Get diff for a specific file"""
    try:
        diff = subprocess.check_output(
            ['git', 'diff', base_commit, 'HEAD', '--', file_path],
            cwd=os.getcwd()
        ).decode()
        return diff
    except subprocess.CalledProcessError:
        return ""


def get_module_developer(file_path):
    """Read module metadata and return the developer handle"""
    try:
        module_info = parse.get_module_info(file_path)
    except Exception:
        return None

    if not module_info:
        return None

    developer = module_info.get('meta', {}).get('developer')
    if developer:
        return developer.strip()

    return None

def _parse_version_from_source(source: str):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return None


def is_module_file(file_path):
    """Check if file is a Python module in a modules directory"""
    # Check if it's a .py file and in a modules-like directory
    dir_depth = len(Path(file_path).parts)
    return file_path.endswith('.py') and (
        dir_depth := len(Path(file_path).parts) >= 2
    )

def extract_module_name(file_path):
    """Extract module name from file path"""
    return Path(file_path).stem

async def main():
    added_files = get_added_files(arguments.base_commit)
    modified_files = get_modified_files(arguments.base_commit)
    deleted_files = get_deleted_files(arguments.base_commit)
    
    all_files = added_files + modified_files + deleted_files
    
    if not all_files:
        print("No changes detected")
        return
    
    # Filter for module files only
    new_module_files = [f for f in added_files if is_module_file(f)]
    modified_module_files = [f for f in modified_files if is_module_file(f)]
    deleted_module_files = [f for f in deleted_files if is_module_file(f)]
    
    if not new_module_files and not modified_module_files and not deleted_module_files:
        print("No module changes detected")
        return
    
    async with aiohttp.ClientSession() as session:
        # Handle deleted files first
        for file_path in deleted_module_files:
            try:
                module_name = extract_module_name(file_path)
                message = f"🪼 <b>Module <code>{module_name}</code> has been deleted</b>"
                result = await send_message(session, message)
                print(f"Sent deletion notice for {module_name}: {result}")
            except Exception as e:
                print(f"Error processing deleted {file_path}: {e}")

        # Handle newly added modules
        for file_path in new_module_files:
            try:
                module_name = extract_module_name(file_path)
                developer = get_module_developer(file_path)

                github_url = f"https://raw.githubusercontent.com/MuRuLOSE/limoka/refs/heads/main/{file_path}"
                try:
                    new_hash = subprocess.check_output(
                        ['git', 'rev-list', '-n', '1', 'HEAD', '--', file_path],
                        cwd=os.getcwd()
                    ).decode().strip()
                except Exception:
                    new_hash = 'HEAD'

                try:
                    old_hash = subprocess.check_output(
                        ['git', 'rev-list', '-n', '1', arguments.base_commit, '--', file_path],
                        cwd=os.getcwd()
                    ).decode().strip()
                except Exception:
                    old_hash = arguments.base_commit

                diff_url = f"https://github.com/MuRuLOSE/limoka/compare/{old_hash}...{new_hash}.diff"
                title = f"🪼 <b>New module <code>{module_name}</code> approved</b>"
                if developer:
                    title += f"\n<code>{developer}</code>"

                message = (
                    f"{title}\n\n"
                    f"<b><a href=\"{github_url}\">File URL</a></b> | "
                    f"<b><a href=\"{diff_url}\">Diff URL</a></b>"
                )

                diff = get_file_diff(file_path, arguments.base_commit)
                if not diff:
                    print(f"Skipping {file_path} - no diff content")
                    continue

                diff_filename = f"{module_name}.diff"
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='',
                    prefix='',
                    delete=False,
                    encoding='utf-8',
                    dir=tempfile.gettempdir()
                ) as tmp_file:
                    tmp_file.write(diff)
                    tmp_file_path = tmp_file.name

                try:
                    final_path = os.path.join(tempfile.gettempdir(), diff_filename)
                    os.rename(tmp_file_path, final_path)
                    doc_result = await send_document(session, final_path, caption=message)
                    print(f"Sent new module diff for {module_name}: {doc_result}")
                except Exception as e:
                    print(f"Error sending {module_name}: {e}")
                finally:
                    if os.path.exists(tmp_file_path):
                        try:
                            os.remove(tmp_file_path)
                        except:
                            pass
                    final_path = os.path.join(tempfile.gettempdir(), diff_filename)
                    if os.path.exists(final_path):
                        try:
                            os.remove(final_path)
                        except:
                            pass
            except Exception as e:
                print(f"Error processing new file {file_path}: {e}")

        # Handle modified files
        for file_path in modified_module_files:
            try:
                module_name = extract_module_name(file_path)
                developer = get_module_developer(file_path)

                github_url = f"https://raw.githubusercontent.com/MuRuLOSE/limoka/refs/heads/main/{file_path}"
                try:
                    new_hash = subprocess.check_output(
                        ['git', 'rev-list', '-n', '1', 'HEAD', '--', file_path],
                        cwd=os.getcwd()
                    ).decode().strip()
                except Exception:
                    new_hash = 'HEAD'

                try:
                    old_hash = subprocess.check_output(
                        ['git', 'rev-list', '-n', '1', arguments.base_commit, '--', file_path],
                        cwd=os.getcwd()
                    ).decode().strip()
                except Exception:
                    old_hash = arguments.base_commit

                version = ""
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source = f.read()
                        version_tuple = _parse_version_from_source(source)
                        if version_tuple:
                            version = '.'.join(map(str, version_tuple))
                except Exception as e:
                    print(f"Error parsing version from {file_path}: {e}")

                diff_url = f"https://github.com/MuRuLOSE/limoka/compare/{old_hash}...{new_hash}.diff"
                title = f"🪼 <b>Module <code>{module_name}</code> <code>{version}</code> changes approved</b>"
                if developer:
                    title += f"\nby <code>{developer}</code>"

                message = (
                    f"{title}\n\n"
                    f"<b><a href=\"{github_url}\">File URL</a></b> | "
                    f"<b><a href=\"{diff_url}\">Diff URL</a></b>"
                )

                diff = get_file_diff(file_path, arguments.base_commit)
                if not diff:
                    print(f"Skipping {file_path} - no diff content")
                    continue

                diff_filename = f"{module_name}.diff"
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='',
                    prefix='',
                    delete=False,
                    encoding='utf-8',
                    dir=tempfile.gettempdir()
                ) as tmp_file:
                    tmp_file.write(diff)
                    tmp_file_path = tmp_file.name

                try:
                    final_path = os.path.join(tempfile.gettempdir(), diff_filename)
                    os.rename(tmp_file_path, final_path)
                    doc_result = await send_document(session, final_path, caption=message)
                    print(f"Sent diff for {module_name}: {doc_result}")
                except Exception as e:
                    print(f"Error sending {module_name}: {e}")
                finally:
                    if os.path.exists(tmp_file_path):
                        try:
                            os.remove(tmp_file_path)
                        except:
                            pass
                    final_path = os.path.join(tempfile.gettempdir(), diff_filename)
                    if os.path.exists(final_path):
                        try:
                            os.remove(final_path)
                        except:
                            pass
            except Exception as e:
                print(f"Error processing modified {file_path}: {e}")

if __name__ == "__main__":
    asyncio.run(main())