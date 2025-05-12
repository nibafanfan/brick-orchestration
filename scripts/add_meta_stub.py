"""
Create a skeleton meta.yaml in every brick repo that lacks one.
Afterwards you can fill in the plain‑language fields.
"""
import os, subprocess, yaml
from pathlib import Path

ORG = "biobricks-ai"
REPO_DIR = Path("brick_repos")          # where repos are cloned

# ---------------- GitHub API to enumerate all brick repos ---------------- #
# requires gh CLI:  gh api orgs/biobricks-ai/repos --jq '.[].name'
import json, shutil, subprocess, sys

def list_bricks():
    return subprocess.check_output(
        ["gh", "api",
         "-H", "Accept: application/vnd.github+json",
         f"orgs/{ORG}/repos",
         "--paginate",                 # ← follow all pages
         "--jq", ".[].name"]
    ).decode().splitlines()


bricks = list_bricks()
print(f"\n🔎 Found {len(bricks)} brick repos in {ORG}:")
for name in bricks:
    print("   •", name)
print()  # blank line for readability
# -------------------- create stub meta if missing ------------------------ #
STUB = {
    "brick_name": "",
    "description": "TODO: one‑sentence plain‑language description.",
    "source": [
        {
            "name": "TODO: data source name",
            "url": "TODO: https://example.com",
            "citation": "TODO: Author et al. (YEAR)",
            "license": "TODO: license"
        }
    ],
    "transformations": "TODO: describe any processing, or say 'none — preserved as‑is'",
    "assets": [
        {
            "file": "TODO.parquet",
            "format": "Parquet",
            "description": "TODO: what this file contains"
        }
    ]
}

for brick in list_bricks():
    local = REPO_DIR / brick
    if not local.exists():
        subprocess.run(["git", "clone", f"https://github.com/{ORG}/{brick}.git", local])
    meta_path = local / "meta.yaml"
    if meta_path.exists():
        continue
    stub = STUB.copy()
    stub["brick_name"] = brick
    with open(meta_path, "w") as f:
        yaml.safe_dump(stub, f, sort_keys=False)
    print(f"📝  created stub meta.yaml for {brick}")
