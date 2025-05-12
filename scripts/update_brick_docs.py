# scripts/update_brick_docs.py
"""
Auto‑generate meta.yaml + README.md for every *dataset* repo in biobricks‑ai.

Usage
-----
$ python scripts/update_brick_docs.py \
        --org biobricks-ai \
        --author "doc‑bot <docs@biobricks.ai>" \
        --token $GH_TOKEN
     # GH_TOKEN must have repo‑scope push rights (or set up fork/PR logic).

Requires: requests, pyyaml, jinja2
pip install requests pyyaml jinja2
"""


from __future__ import annotations

"""
Auto‑generate meta.yaml + README.md for every *dataset* repo in biobricks‑ai.
(…docstring continues…)
"""

import argparse, json, os, re, subprocess, sys, textwrap, time
from pathlib import Path
from typing import List, Dict, Any

import requests, yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

STATUS_API = "https://status.biobricks.ai/api/v0"
GITHUB_API = "https://api.github.com"

THIS_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = THIS_DIR / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)
TEMPLATE_FILE = TEMPLATE_DIR / "readme_template.j2"

# ------------------------------------------------------------------------
# 0.  Discover brick list
# ------------------------------------------------------------------------
def discover_bricks(owner: str) -> List[str]:
    bricks = []
    page = 1
    while True:
        url = f"{STATUS_API}/owner/{owner}/brick?page={page}&per_page=100"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        bricks += [b["name"] for b in data]
        page += 1
    return sorted(bricks)


# ------------------------------------------------------------------------
# 1.  Fetch status JSON
# ------------------------------------------------------------------------
def fetch_status(owner: str, brick: str) -> Dict[str, Any] | None:
    url = f"{STATUS_API}/owner/{owner}/brick/{brick}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


# ------------------------------------------------------------------------
# 2.  Cross‑check GitHub (fallback for description / homepage)
# ------------------------------------------------------------------------
def fetch_gh_repo(org: str, repo: str, token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    HEADERS = {"Accept": "application/json"}
    r = requests.get(f"{GITHUB_API}/repos/{org}/{repo}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------
def slugify(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-]", "_", s)

def ensure_template():
    if TEMPLATE_FILE.exists():
        return
    TEMPLATE_FILE.write_text(
        textwrap.dedent(
            """\
            # {{ brick_name }}

            ## 🔍 Overview
            {{ description }}

            ## 📦 Data Source
            - **{{ source.name }}**  
              URL: {{ source.url }}  
              {% if source.citation %}Citation: {{ source.citation }}{% endif %}{% if source.license %}<br>License: {{ source.license }}{% endif %}

            ## 🔄 Transformations
            {{ transformations }}

            ## 📁 Assets
            {% for a in assets -%}
            - `{{ a.file }}` ({{ a.format }}): {{ a.description }}
            {%- endfor %}

            ## 🧪 Usage
            ```bash
            biobricks install {{ brick_name }}
            ```

            ```python
            import biobricks as bb
            import pandas as pd

            paths = bb.assets("{{ brick_name }}")
            {% for a in assets if a.format in ["PARQUET","CSV","TSV","JSON"] -%}
            df_{{ loop.index }} = pd.read_{{ "parquet" if a.format=="PARQUET" else "csv" }}(
                paths.{{ a.file.replace('.','_').replace('-','_') }}
            )
            {%- endfor %}
            print(df_1.head())
            ```"""
        )
    )


# ------------------------------------------------------------------------
# 3.  Build meta.yaml dict
# ------------------------------------------------------------------------
def build_meta(brick: str, status: Dict[str, Any], gh_meta: Dict[str, Any]) -> Dict[str, Any]:
    description = status.get("description") or gh_meta.get("description") or "TODO: description"
    source_block = {
        "name": status.get("homepage") or gh_meta.get("homepage") or "TODO: data source",
        "url": status.get("source_url") or status.get("homepage") or gh_meta.get("homepage") or "TODO",
        "citation": status.get("citation") or "TODO: verify",
        "license": status.get("license") or "TODO: verify",
    }
    transformations = status.get("transform") or "None – raw data preserved."
    assets = []
    for a in status.get("assets", []):
        assets.append(
            {
                "file": a.get("path") or a.get("name"),
                "format": a.get("format", "").upper(),
                "description": a.get("name") or "TODO",
            }
        )
    if not assets:
        assets.append({"file": "TODO.ext", "format": "TODO", "description": "TODO"})
    meta = {
        "brick_name": brick,
        "description": description,
        "source": [source_block],
        "transformations": transformations,
        "assets": assets,
    }
    return meta


# ------------------------------------------------------------------------
# 4.  Render README
# ------------------------------------------------------------------------
def render_readme(meta: Dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape()
    )
    tmpl = env.get_template("readme_template.j2")
    return tmpl.render(**meta, source=meta["source"][0])


# ------------------------------------------------------------------------
# Git helpers
# ------------------------------------------------------------------------
def run(cmd, cwd=None, check=True, quiet=False):
    kwargs = {}
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    subprocess.run(cmd, cwd=cwd, check=check, **kwargs)


def clone_or_pull(org: str, repo: str, dest: Path):
    if dest.exists():
        run(["git", "pull", "--quiet"], cwd=dest)
    else:
        run(["git", "clone", f"https://github.com/{org}/{repo}.git", str(dest)], quiet=True)


def commit_and_push(repo_path: Path, author: str):
    run(["git", "add", "meta.yaml", "README.md"], cwd=repo_path)
    # If nothing to commit, skip
    res = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_path
    )
    if res.returncode == 0:  # no changes
        return False
    run(["git", "-c", f"user.name={author.split()[0]}", "-c", f"user.email={author.split()[-1].strip('<>')}",
         "commit", "-m", "docs: auto‑generate README/meta"], cwd=repo_path)
    try:
        run(["git", "push"], cwd=repo_path, quiet=True)
        return True
    except subprocess.CalledProcessError:
        return False  # permissions error; user can fork manually


# ------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="biobricks-ai")
    parser.add_argument("--author", default="doc‑bot <docs@biobricks.ai>")
    parser.add_argument("--token", default=os.getenv("GH_TOKEN", ""))
    parser.add_argument("--workdir", default="brick_repos")
    args = parser.parse_args()

    ensure_template()
    workdir = Path(args.workdir)
    workdir.mkdir(exist_ok=True)

    bricks = discover_bricks(args.org)
    print(f"Discovered {len(bricks)} bricks")

    start = time.time()
    summary = {"pushed": 0, "skipped": 0, "no_status": 0, "failed": 0}

    for b in bricks:
        print(f"→ {b}")
        status_json = fetch_status(args.org, b)
        if not status_json:
            print("   no status record")
            summary["no_status"] += 1
            continue

        # simple heuristic to skip non‑dataset repos
        if status_json.get("type") == "tool":
            print("   skipped (tool/template)")
            summary["skipped"] += 1
            continue

        repo_path = workdir / b
        clone_or_pull(args.org, b, repo_path)

        gh_meta = fetch_gh_repo(args.org, b, args.token)
        meta = build_meta(b, status_json, gh_meta)

        # write meta.yaml
        with open(repo_path / "meta.yaml", "w") as f:
            yaml.safe_dump(meta, f, sort_keys=False)

        # render README
        (repo_path / "README.md").write_text(render_readme(meta))

        # commit & push
        ok = commit_and_push(repo_path, args.author)
        if ok:
            summary["pushed"] += 1
            print("   ✅  pushed")
        else:
            summary["failed"] += 1
            print("   🟡  push denied or nothing to commit")

    elapsed = int(time.time() - start) // 60
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("time_minutes:", elapsed)


if __name__ == "__main__":
    main()
