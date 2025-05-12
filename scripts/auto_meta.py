#!/usr/bin/env python3
"""
auto_meta.py  –  Generate stub meta.yaml for every dataset brick.

Prereqs:
  • GH_TOKEN env var set to a PAT with repo read access (write optional)
  • git + GitHub CLI (gh) installed  (gh optional if GH_TOKEN used below)

Usage:
  export GH_TOKEN=ghp_xxx               # PAT with at least repo READ
  python scripts/auto_meta.py
"""

import os, subprocess, yaml, requests
from pathlib import Path

# --------------------------------------------------------------------- #
ORG = "biobricks-ai"
REPO_DIR = Path("brick_repos")          # where repos are cloned locally

# Paste your ✅  bricks list here (dataset repos only)
KEPT = [
    "clinvar","gtex","hpo","loinc","chembl","ctdbase","dbsnp","depmap",
    "fda","gdc","uniprot","pharmgkb","umls","hgnc","pubmed","ctgov-aact",
    "gencode","sider","meddra","medgen","targetscan","geneontology",
    "mirbase","stringdb","1000genomes","dbgap","bioportal","pmc","ice",
    "comptox","pubchem","pubchemrdf","chemblrdf","chebirdf","toxvaldb",
    "pdb","biosim","zinc","bindingdb","tox21","echemportal","ecotox",
    "faers","chebi","pubchemghs","cpdat","cpcat","chemharmony","toxcast",
    "cancerharmony","qm9","bioplanet","biobricks-okg","cosing-kg",
    "ctdbase-kg","mesh-kg","ice-kg","cvtdb","openalex","toxrefdb",
    "nih-reporter","uniprot-kg","rtecs","pubchemrdf-kg","cir-ingredients",
    "cpdb","USPTO_ChemReaction","clintox","toxicodb","moleculenet",
    "biogrid","skinsensdb","tox24","pubchem-annotations","wikipathways",
    "bayer-dili","pubtator","COSMIC","harmonizome","compait","adrecs",
    "onsides","dude","tape","drugbank-open","brenda","bace","tsar",
    "biorxiv","eutoxrisk-temposeq","stitch","PurificationDB","ctgov-kg",
    "eutoxrisk-temposeq-kg","guide-to-pharmacology",
    "therapeutic-target-database","structured-sds",
    "pubchem-annotations-kg","cebs","aopwikirdf-kg","cir-reports",
    "cosing","human-protein-pdb","orthodb","clinicaltrials","iuclid"
]

HEADERS = {"Authorization": f"Bearer {os.getenv('GH_TOKEN','')}"}
# --------------------------------------------------------------------- #

failed_clone = []
failed_push  = []

def gh_api(path):
    """Tiny helper for GitHub REST GET requests."""
    url = f"https://api.github.com/{path}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def clone_or_pull(name: str):
    """Ensures local clone; returns Path or None if clone denied."""
    local = REPO_DIR / name
    if not local.exists():
        try:
            subprocess.run(
                ["git", "clone",
                 f"https://github.com/{ORG}/{name}.git", local],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            failed_clone.append(name)
            print("   🚫  clone denied (no access)")
            return None
    else:
        subprocess.run(
            ["git", "-C", local, "pull", "--quiet"],
            check=True
        )
    return local

def detect_assets(repo_path: Path):
    """Return a list of asset dicts by scanning brick/ for data files."""
    exts = {".parquet",".csv",".tsv",".json",".sqlite",".db",".sdf",".txt"}
    assets = []
    brick_dir = repo_path / "brick"
    if not brick_dir.exists():
        return assets
    for root, _, files in os.walk(brick_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in exts:
                assets.append({
                    "file": str(p.relative_to(repo_path)),
                    "format": p.suffix.lstrip(".").upper(),
                    "description": "TODO: describe this file"
                })
    return assets[:20]

def make_meta(name: str, repo_path: Path):
    """Build initial meta dict using GitHub description + auto assets."""
    info = gh_api(f"repos/{ORG}/{name}")
    meta = {
        "brick_name": name,
        "description": info.get("description") or "TODO: plain‑language description.",
        "source": [{
            "name": "TODO: data source",
            "url": "https://example.com",
            "citation": "TODO",
            "license": "TODO"
        }],
        "transformations": "None – raw data preserved.\nTODO: update if processing applied.",
        "assets": detect_assets(repo_path) or [{
            "file": "TODO.ext",
            "format": "TODO",
            "description": "TODO"
        }]
    }
    return meta

def main():
    REPO_DIR.mkdir(exist_ok=True)
    for repo in KEPT:
        print(f"→ {repo}")
        local = clone_or_pull(repo)
        if local is None:
            continue                          # skip repo without clone rights

        meta_path = local / "meta.yaml"
        if meta_path.exists():
            print("   meta.yaml already present – skipping")
            continue

        meta = make_meta(repo, local)
        yaml.safe_dump(meta, open(meta_path, "w"), sort_keys=False)
        subprocess.run(["git", "-C", local, "add", "meta.yaml"])
        subprocess.run(
            ["git", "-C", local, "commit", "-m", "chore: add stub meta.yaml"],
            check=False, stdout=subprocess.DEVNULL
        )

        try:
            subprocess.run(
                ["git", "-C", local, "push"],
                check=True, stdout=subprocess.DEVNULL
            )
            print("   ✅  pushed stub meta.yaml")
        except subprocess.CalledProcessError:
            failed_push.append(repo)
            print("   🚫  push denied (no write access)")

    # ------------ summary -------------
    print("\n=========== SUMMARY ===========")
    if failed_clone:
        print(f"Could not clone ({len(failed_clone)}): " + ", ".join(failed_clone))
    if failed_push:
        print(f"Could not push  ({len(failed_push)}): " + ", ".join(failed_push))
    if not failed_clone and not failed_push:
        print("All bricks processed successfully!")

if __name__ == "__main__":
    main()
