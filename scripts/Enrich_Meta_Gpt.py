#!/usr/bin/env python3
"""
Enrich_Meta_Gpt.py — refresh / create brick_repos/<brick>/meta.yaml
───────────────────────────────────────────────────────────────────
Adds a *complete* `assets:` list by merging:
  • biobricks.assets(<brick>)                (if available locally)
  • every *.parquet / *.csv / … actually sitting in brick/
  • regex scrape of status.biobricks.ai      (fallback)

Usage
─────
# one brick
python scripts/Enrich_Meta_Gpt.py --brick chembl --overwrite

# all bricks, fill only missing fields
python scripts/Enrich_Meta_Gpt.py --all
"""

from __future__ import annotations

import argparse, os, re
from pathlib import Path
from types import SimpleNamespace

import yaml, requests, openai, biobricks as bb
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ───────────────────────── env / constants ─────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

BRICKS_DIR = Path("brick_repos")
MARK = "<!-- AUTO-GENERATED-README-START -->"

EXT2FMT = dict(
    parquet="Parquet", csv="CSV", tsv="TSV",
    json="JSON", h5="HDF5", hdf5="HDF5",
)

META_TEMPLATE = dict(
    title="",
    description="",
    source=[],
    license="",
    tags=[],
    assets=[],
    transformations="",
)

# ───────────────────────── helpers ─────────────────────────
def extract_manual_section(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").split(MARK, 1)[0].strip()

def scrape_status(brick: str) -> str:
    url = f"https://status.biobricks.ai/brick/{brick}"
    try:
        return BeautifulSoup(requests.get(url, timeout=10).text,
                             "html.parser").get_text(" ", strip=True)
    except Exception:
        return ""

def assets_from_status(text: str) -> list[dict]:
    out = []
    rx = r"(\S+\.(?:parquet|csv|tsv|json|sqlite|txt|h5))\s+(\d+(?:\.\d+)?\s*[KMG]B)"
    for fn, size in re.findall(rx, text, flags=re.I):
        out.append(dict(file=fn,
                        format=fn.split(".")[-1].upper(),
                        description=f"Auto-detected file ({size.strip()})"))
    return out

def assets_from_bb(brick: str) -> list[dict]:
    try:
        ns: SimpleNamespace = bb.assets(brick)
    except Exception:
        return []
    res = []
    for alias, pth in vars(ns).items():
        p = Path(pth)
        res.append(dict(file=p.name,
                        format=EXT2FMT.get(p.suffix.lstrip('.').lower(),
                                           p.suffix.upper()),
                        description=alias.replace("_", " ")))
    return res


def assets_from_disk(brick: str) -> list[dict]:
    """
    Recursively walk *any* directory under brick_repos/<brick>/ and
    collect every file with a known data-extension.  The previous
    version stopped at brick/ ; this one goes as deep as needed.
    """
    root = BRICKS_DIR / brick       # start at the brick root
    res  = []
    for p in root.rglob("*.*"):      # depth-first search
        if p.suffix.lstrip(".").lower() in EXT2FMT:
            res.append(
                dict(
                    file=p.name,
                    format=EXT2FMT[p.suffix.lstrip('.').lower()],
                    description="file present in repo",
                )
            )
    return res

def merge_assets(*sources: list[dict]) -> list[dict]:
    seen, merged = set(), []
    for src in sources:
        for d in src:
            if d["file"] in seen:
                continue
            seen.add(d["file"])
            merged.append(d)
    return sorted(merged, key=lambda x: x["file"])

# ───────────────────────── GPT excerpt (unchanged) ────────────
def gpt_extract_meta(readme: str, status: str) -> dict:
    if openai.api_key is None:
        return {}
    prompt = (
        "Extract dataset metadata in YAML with keys:\n"
        "title, description, source(list), license, tags(list), "
        "assets(list of {file,format,description}), transformations.\n"
        "Return RAW YAML only.\n\n"
        f"README:\n{readme}\n\nSTATUS:\n{status}"
    )
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    try:
        data = yaml.safe_load(rsp.choices[0].message.content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def is_stub(v):
    if isinstance(v, str):
        return v.strip().lower().startswith("todo") or v.strip() == ""
    if isinstance(v, list):
        return all(is_stub(x) for x in v)
    if isinstance(v, dict):
        return all(is_stub(x) for x in v.values())
    return not v

# ───────────────────────── main enrichment ─────────────────────
def enrich(brick: str, overwrite: bool = False):
    path = BRICKS_DIR/brick
    meta_p = path/"meta.yaml"
    readme_p = path/"README.md"

    manual = extract_manual_section(readme_p)
    status_txt = scrape_status(brick)
    gpt_meta = gpt_extract_meta(manual, status_txt)

    # existing meta (if any)
    meta = yaml.safe_load(meta_p.read_text()) if meta_p.exists() else {}
    meta = meta or {}

    # assemble assets
    if overwrite or not meta.get("assets") or is_stub(meta["assets"]):
        meta["assets"] = merge_assets(
            assets_from_bb(brick),
            assets_from_disk(brick),
            gpt_meta.get("assets", []),
            assets_from_status(status_txt),
        )

    # other keys
    for k in META_TEMPLATE:
        if k == "assets":
            continue
        if overwrite or not meta.get(k) or is_stub(meta[k]):
            if gpt_meta.get(k):
                meta[k] = gpt_meta[k]

    if "transformations" not in meta or is_stub(meta["transformations"]):
        meta["transformations"] = "None — preserved as-is"

    meta_p.write_text(yaml.safe_dump(meta, sort_keys=False))
    print(f"✓ {brick}")

# ───────────────────────── CLI ─────────────────────────
# ───────── CLI glue ─────────
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--brick")                  # e.g. --brick chembl
    g.add_argument("--all", action="store_true")
    
    # 👇 this line must exist, otherwise --overwrite is “unrecognized”
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing values instead of merging")
    
    args = ap.parse_args()

    bricks = ([args.brick] if args.brick else
              sorted(p.name for p in BRICKS_DIR.iterdir() if p.is_dir()))
    for b in bricks:
        enrich(b, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
