import asyncio
import aiohttp
import argparse
import subprocess
import os
import glob

parser = argparse.ArgumentParser(description="Backup Script")
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
    help="Chat ID to send backup message to",
)

arguments = parser.parse_args()

async def send_file(session, file_path, caption=None):
    url = f"{arguments.api_url}/bot{arguments.token}/sendDocument"
    with open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('chat_id', arguments.chat_id)
        data.add_field('document', f, filename=os.path.basename(file_path))
        if caption:
            data.add_field('caption', caption)
            data.add_field('parse_mode', 'Markdown')
        async with session.post(url, data=data) as response:
            return await response.json()

async def main():
    # Get commit info
    commit_message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B']).decode().strip()
    commit_date = subprocess.check_output(['git', 'log', '-1', '--pretty=%ci']).decode().strip()
    commit_hash = subprocess.check_output(['git', 'rev-parse', '--short=6', 'HEAD']).decode().strip()
    commit_url = f"https://github.com/MuRuLOSE/limoka/commit/{subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()}"
    message = f"Commit Date: {commit_date}, Commit Message: {commit_message}, Commit Hash: [`{commit_hash}`]({commit_url})"

    # Create zip
    subprocess.run(['git', 'archive', '--format=zip', '--output=repository-original.zip', 'HEAD'])
    subprocess.run(['zip', '-9', 'repository.zip', 'repository-original.zip'])
    os.remove('repository-original.zip')

    # Split zip
    subprocess.run(['split', '-b', '49M', 'repository.zip', 'repository-part-'])

    # Send parts
    async with aiohttp.ClientSession() as session:
        parts = sorted(glob.glob('repository-part-*'))
        first = True
        for part in parts:
            caption = message if first else None
            result = await send_file(session, part, caption)
            print(f"Sent {part}: {result}")
            first = False

    # Cleanup
    os.remove('repository.zip')
    for part in parts:
        os.remove(part)

if __name__ == "__main__":
    asyncio.run(main())