import os
import shutil
import subprocess
import re
import requests
import json

def parse_repos(file_path: str) -> list:
    """Parse repository URLs from a given json file."""
    repos = []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for repo in data.get("repositories", []):
            repos.append(repo["path"])
    return repos

repos = parse_repos("repositories.json")

def configure_git():
    """Configure Git to ignore file mode changes."""
    try:
        subprocess.run(
            ["git", "config", "core.fileMode", "false"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("Git configured to ignore file mode changes.")
    except subprocess.CalledProcessError as e:
        print(f"Error configuring Git: {e.stderr}")

def is_repo_public(repo_url):
    """Check if the repository is accessible."""
    result = subprocess.run(
        ["git", "ls-remote", repo_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0

def is_repo_accessible(repo_url):
    """Check if the repository URL is accessible via HTTP."""
    try:
        response = requests.head(repo_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def is_valid_filename(filename):
    """Check if the filename contains invalid characters."""
    invalid_chars = r'[<>:"/\\|?*]'
    return not re.search(invalid_chars, filename)

def rename_invalid_files(local_path):
    """Rename files with invalid characters in their names."""
    for root, dirs, files in os.walk(local_path):
        for file in files:
            if not is_valid_filename(file):
                old_path = os.path.join(root, file)
                new_file = re.sub(r'[<>:"/\\|?*]', "_", file)
                new_path = os.path.join(root, new_file)
                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed file: {old_path} -> {new_path}")
                except OSError as e:
                    print(f"Error renaming file {old_path}: {e}")

def get_repo_path(repo_url):
    """Extract the repository path from the URL."""
    return repo_url.replace("https://github.com/", "")

def clean_unused_repos():
    """Remove directories not in the repos list or for inaccessible repositories."""
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")

    existing_dirs = {
        d
        for d in os.listdir(current_dir)
        if os.path.isdir(os.path.join(current_dir, d))
    }
    print(f"All directories before filtering: {existing_dirs}")

    protected_dirs = {".git", ".github", "assets"}
    existing_dirs.difference_update(protected_dirs)
    print(f"Directories after excluding protected: {existing_dirs}")

    expected_dirs = {get_repo_path(url).split("/")[0] for url in repos}
    print(f"Expected directories: {expected_dirs}")

    for dir_name in existing_dirs:
        dir_path = os.path.join(current_dir, dir_name)
        if dir_name not in expected_dirs:
            shutil.rmtree(dir_path, ignore_errors=True)
            print(f"Removed directory not in repos list: {dir_path}")

    for repo_url in repos:
        repo_path = get_repo_path(repo_url)
        local_path = os.path.join(current_dir, repo_path)
        if os.path.exists(local_path):
            if not is_repo_accessible(repo_url):
                shutil.rmtree(local_path, ignore_errors=True)
                print(f"Removed directory for inaccessible repository: {local_path}")

def clone_or_update_repo(repo_url):
    """Clone or update a repository and process its files."""
    repo_path = get_repo_path(repo_url)
    owner, repo_name = repo_path.split("/")
    local_path = os.path.join(owner, repo_name)

    if not os.path.exists(owner):
        os.makedirs(owner)

    if os.path.exists(local_path):
        shutil.rmtree(local_path)
        print(f"Removed old directory: {local_path}")

    if not is_repo_public(repo_url):
        print(f"Skipping private or inaccessible repository: {repo_url}")
        return

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, local_path],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(os.path.join(local_path, ".git"), ignore_errors=True)
        rename_invalid_files(local_path)
        print(f"Cloned and processed repository: {repo_url} -> {local_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning {repo_url}: {e.stderr}, skipping.")

if __name__ == "__main__":
    configure_git()  # Set Git configuration at the start
    clean_unused_repos()
    for repo_url in repos:
        clone_or_update_repo(repo_url)
