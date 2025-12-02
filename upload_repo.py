#!/usr/bin/env python3
"""
upload_repo.py

Uploads files from a zip into a GitHub repo branch using the Contents API.

Environment variables:
  GITHUB_TOKEN  - personal access token (repo scope)
  REPO          - owner/repo (e.g. mblanke/StrikePackageGPT-Lab)
  BRANCH        - target branch name (default: c2-integration)
  ZIP_FILENAME  - name of zip file present in the current directory

Usage:
  export GITHUB_TOKEN='ghp_xxx'
  export REPO='owner/repo'
  export BRANCH='c2-integration'
  export ZIP_FILENAME='goose_c2_files.zip'
  python3 upload_repo.py
"""
import os, sys, base64, zipfile, requests, time
from pathlib import Path
from urllib.parse import quote_plus

API_BASE = "https://api.github.com"

def die(msg):
    print("ERROR:", msg); sys.exit(1)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPO")
BRANCH = os.environ.get("BRANCH", "c2-integration")
ZIP_FILENAME = os.environ.get("ZIP_FILENAME")

def api_headers():
    if not GITHUB_TOKEN:
        die("GITHUB_TOKEN not set")
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def get_default_branch():
    url = f"{API_BASE}/repos/{REPO}"
    r = requests.get(url, headers=api_headers())
    if r.status_code != 200:
        die(f"Failed to get repo info: {r.status_code} {r.text}")
    return r.json().get("default_branch")

def get_ref_sha(branch):
    url = f"{API_BASE}/repos/{REPO}/git/refs/heads/{branch}"
    r = requests.get(url, headers=api_headers())
    if r.status_code == 200:
        return r.json()["object"]["sha"]
    return None

def create_branch(new_branch, from_sha):
    url = f"{API_BASE}/repos/{REPO}/git/refs"
    payload = {"ref": f"refs/heads/{new_branch}", "sha": from_sha}
    r = requests.post(url, json=payload, headers=api_headers())
    if r.status_code in (201, 422):
        print(f"Branch {new_branch} created or already exists.")
        return True
    else:
        die(f"Failed to create branch: {r.status_code} {r.text}")

def get_file_sha(path, branch):
    url = f"{API_BASE}/repos/{REPO}/contents/{quote_plus(path)}?ref={branch}"
    r = requests.get(url, headers=api_headers())
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def put_file(path, content_b64, message, branch, sha=None):
    url = f"{API_BASE}/repos/{REPO}/contents/{quote_plus(path)}"
    payload = {"message": message, "content": content_b64, "branch": branch}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, json=payload, headers=api_headers())
    return (r.status_code in (200,201)), r.text

def extract_zip(zip_path, target_dir):
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(target_dir)

def gather_files(root_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            files.append(os.path.join(dirpath, fn))
    return files

def main():
    if not GITHUB_TOKEN or not REPO or not ZIP_FILENAME:
        print("Set env vars: GITHUB_TOKEN, REPO, ZIP_FILENAME. Optionally BRANCH.")
        sys.exit(1)
    if not os.path.exists(ZIP_FILENAME):
        die(f"Zip file not found: {ZIP_FILENAME}")
    default_branch = get_default_branch()
    print("Default branch:", default_branch)
    base_sha = get_ref_sha(default_branch)
    if not base_sha:
        die(f"Could not find ref for default branch {default_branch}")
    create_branch(BRANCH, base_sha)
    tmp_dir = Path("tmp_upload")
    if tmp_dir.exists():
        for p in tmp_dir.rglob("*"):
            try:
                if p.is_file(): p.unlink()
            except: pass
    tmp_dir.mkdir(exist_ok=True)
    print("Extracting zip...")
    extract_zip(ZIP_FILENAME, str(tmp_dir))
    files = gather_files(str(tmp_dir))
    print(f"Found {len(files)} files to upload")
    uploaded = 0
    for fpath in files:
        rel = os.path.relpath(fpath, str(tmp_dir))
        rel_posix = Path(rel).as_posix()
        with open(fpath, "rb") as fh:
            data = fh.read()
        content_b64 = base64.b64encode(data).decode("utf-8")
        sha = get_file_sha(rel_posix, BRANCH)
        msg = f"Add/update {rel_posix} via uploader"
        ok, resp = put_file(rel_posix, content_b64, msg, BRANCH, sha=sha)
        if ok:
            uploaded += 1
            print(f"[{uploaded}/{len(files)}] Uploaded: {rel_posix}")
        else:
            print(f"[!] Failed: {rel_posix} - {resp}")
        time.sleep(0.25)
    print(f"Completed. Uploaded {uploaded} files to branch {BRANCH}.")
    print(f"Open PR: https://github.com/{REPO}/compare/{BRANCH}")

if __name__ == "__main__":
    main()