#!/usr/bin/env python3
import os, sys
from pathlib import Path

def env(k):
    v = os.environ.get(k)
    return "<SET>" if v else "<NOT SET>"

print("Python:", sys.version.splitlines()[0])
print("PWD:", os.getcwd())
print("Workspace files:")
for p in Path(".").iterdir():
    print(" -", p)

print("\nImportant env vars:")
for k in ("GITHUB_TOKEN","REPO","BRANCH","ZIP_FILENAME"):
    print(f" {k}: {env(k)}")

print("\nAttempting to read ZIP_FILENAME if set...")
zipf = os.environ.get("ZIP_FILENAME")
if zipf:
    p = Path(zipf)
    print("ZIP path:", p.resolve())
    print("Exists:", p.exists(), "Size:", p.stat().st_size if p.exists() else "N/A")
else:
    print("ZIP_FILENAME not set; cannot check file.")