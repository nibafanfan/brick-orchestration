#!/usr/bin/env python3
"""
auto_meta_enrich.py  –  generate *and* enrich each brick’s meta.yaml

 • Keeps every feature of the original auto_meta.py (clone/pull, stub generation)
 • Adds a second pass that scrapes https://status.biobricks.ai/u/biobricks-ai/<brick>
   to fill dataset_type, license, and authoritative assets.

Prereqs:
  • export GH_TOKEN=ghp_xxx   # read-access PAT (write if you want auto-push)
  • pip install pyyaml requests cloudscraper
Usage:
  python scripts/auto_meta_enrich.py
"""

from __future__ import annotations
import os, re, json, subprocess, requests, yaml, hashlib
from pathlib import Path
from typing import Any, Dict

# --------------------------------------------------------------------- #
ORG = "biobricks-ai"
REPO_DIR = Path("brick_repos")

KEPT = [          # unchanged: your curated repo allow-list
    "clinvar","gtex","hpo","loinc","chembl","ctdbase","dbsnp","depmap",
    "fda","gdc","uniprot","pharmgkb","umls","hgnc","pubmed","ctgov-aact",
    # … (list truncated for brevity) …
    "iuclid"
]

HEADERS = {"Authorization": f"Bearer {os.getenv('GH_TOKEN','')}"}
# --------------------------------------------------------------------- #
# ───────────────────────── GitHub helpers ───────────────────────────── #
def gh_api(path: str) -> Dict[str, Any]:
    r = requests.get(f"https://api.github.com/{path}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def clone_or_pull(name: str) -> Path | None:
    local = REPO_DIR / name
    if not local.exists():
        try:
            subprocess.run(
                ["git","clone",f"https://github.com/{ORG}/{name}.git",local],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print(f"   🚫  clone denied for {name}")
            return None
    else:
        subprocess.run(["git","-C",local,"pull","--quiet"], check=True)
    return local

# ─────────────────────── stub-generation bits ───────────────────────── #
def detect_assets(repo: Path):
    exts = {".parquet",".csv",".tsv",".json",".sqlite",".db",".sdf",".txt"}
    brick_dir = repo / "brick"
    assets = []
    if not brick_dir.exists():
        return assets
    for root, _, files in os.walk(brick_dir):
        for f in files:
            p = Path(root)/f
            if p.suffix.lower() in exts:
                assets.append({
                    "file": str(p.relative_to(repo)),
                    "format": p.suffix.lstrip(".").upper(),
                    "description": "TODO: describe this file"
                })
    return assets[:20]

def make_stub(name: str, repo: Path):
    info = gh_api(f"repos/{ORG}/{name}")
    return {
        "brick_name": name,
        "description": info.get("description") or "TODO: plain-language description.",
        "source": [{
            "name": "TODO: data source",
            "url": "https://example.com",
            "citation": "TODO",
            "license": "TODO"
        }],
        "transformations": "None – raw data preserved.\nTODO: update if processing applied.",
        "assets": detect_assets(repo) or [{
            "file": "TODO.ext",
            "format": "TODO",
            "description": "TODO"
        }]
    }

# ─────────────────────── enrichment bits ────────────────────────────── #
def fetch_status_html(brick: str) -> str:
    import cloudscraper
    url = f"https://status.biobricks.ai/u/biobricks-ai/{brick}"
    return cloudscraper.create_scraper().get(url, timeout=30).text

def extract_next_data(html: str) -> Dict[str, Any]:
    m = re.search(r'__NEXT_DATA__"\s+type="application/json">\s*(.*?)\s*</script>', html, re.S)
    if not m:
        raise RuntimeError("no __NEXT_DATA__ found")
    return json.loads(m.group(1))

def enrich(meta: Dict[str, Any], brick: str) -> Dict[str, Any]:
    try:
        data = extract_next_data(fetch_status_html(brick))["props"]["pageProps"]["brick"]
    except Exception as e:
        print(f"   ⚠️  enrich failed: {e}")
        return meta

    if (dt := data.get("dataset_type")):   # dataset_type
        meta["dataset_type"] = dt

    lic = data.get("license",{}).get("name")
    if lic:
        meta["license"] = lic

    remote_assets = data.get("assets") or []
    if remote_assets:
        meta["assets"] = [{
            "file": a.get("path") or a.get("name"),
            "format": (a.get("format")
                       or Path(a.get("path", a.get("name"))).suffix.lstrip(".")),
            "description": a.get("description","")
        } for a in remote_assets]

    return meta

# ─────────────────────────── main loop ──────────────────────────────── #
def sha(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()

def main():
    REPO_DIR.mkdir(exist_ok=True)
    for repo in KEPT:
        print(f"\n→ {repo}")
        local = clone_or_pull(repo)
        if local is None:
            continue

        meta_path = local / "meta.yaml"
        if meta_path.exists():
            meta = yaml.safe_load(meta_path.read_text())
        else:
            meta = make_stub(repo, local)
            print("   📝  stub meta created")

        before = sha(yaml.safe_dump(meta, sort_keys=False))
        meta = enrich(meta, repo)
        after  = sha(yaml.safe_dump(meta, sort_keys=False))

        if before == after:
            print("   ⏭️  no changes after enrichment")
            continue

        # write, commit, push
        meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
        subprocess.run(["git","-C",local,"add","meta.yaml"])
        subprocess.run(["git","-C",local,"commit","-m","chore: enrich meta.yaml"],
                       check=False, stdout=subprocess.DEVNULL)
        try:
            subprocess.run(["git","-C",local,"push"], check=True, stdout=subprocess.DEVNULL)
            print("   ✅  pushed enriched meta.yaml")
        except subprocess.CalledProcessError:
            print("   🚫  push denied (read-only repo)")

if __name__ == "__main__":
    main()
