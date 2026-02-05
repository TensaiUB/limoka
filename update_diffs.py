import asyncio
import aiohttp
import argparse
import subprocess
import os
import tempfile
from pathlib import Path


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

def is_module_file(file_path):
    """Check if file is a Python module in a modules directory"""
    # Check if it's a .py file and in a modules-like directory
    return file_path.endswith('.py') and any(
        part in file_path.lower() for part in [
            'modules', 'mods', 'ftg', 'hikka'
        ]
    )

def extract_module_name(file_path):
    """Extract module name from file path"""
    return Path(file_path).stem

async def main():
    changed_files = get_changed_files(arguments.base_commit)
    
    if not changed_files:
        print("No changes detected")
        return
    
    # Filter for module files only
    module_files = [f for f in changed_files if is_module_file(f)]
    
    if not module_files:
        print("No module changes detected")
        return
    
    async with aiohttp.ClientSession() as session:
        for file_path in module_files:
            try:
                module_name = extract_module_name(file_path)
                
                # Create message with raw GitHub URL
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
                message = (
                    f"🪼 <b>Module <code>{module_name}</code> changes approved</b>\n\n"
                    f"<b><a href=\"{github_url}\">File URL</a></b> | "
                    f"<b><a href=\"{diff_url}\">Diff URL</a></b>"
                )
                
                # Get diff
                diff = get_file_diff(file_path, arguments.base_commit)
                
                if not diff:
                    print(f"Skipping {file_path} - no diff content")
                    continue
                
                # Create temporary file with diff using only module name
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
                    # Rename temp file to have proper name
                    final_path = os.path.join(tempfile.gettempdir(), diff_filename)
                    os.rename(tmp_file_path, final_path)
                    
                    # Send diff as document with full message as caption
                    doc_result = await send_document(
                        session,
                        final_path,
                        caption=message
                    )
                    print(f"Sent diff for {module_name}: {doc_result}")
                    
                except Exception as e:
                    print(f"Error sending {module_name}: {e}")
                finally:
                    # Cleanup temp files
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
                print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    asyncio.run(main())