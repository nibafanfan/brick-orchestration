#!/usr/bin/env python
"""
generate_readmes.py
-------------------
Render README.md from meta.yaml for one brick or for every brick
under brick_repos/.

Usage
=====
# regenerate all
python scripts/generate_readmes.py

# regenerate just one
python scripts/generate_readmes.py --brick aopwikirdf-kg
"""

from __future__ import annotations
import argparse, sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ────────────────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[1]   # brick-orchestration/
TEMPL_DIR  = ROOT / "templates"
BRICKS_DIR = ROOT / "brick_repos"
TEMPLATE_FN = "readme_template.j2"
# ────────────────────────────────────────────────────────────────────────────────


def load_meta(meta_path: Path) -> dict:
    with meta_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def render_readme(meta: dict, env: Environment) -> str:
    """
    Render README.md text from meta dict.
    - Keep meta['source'] (the entire list) available to the template
    - ALSO pass the first element as 'src' for convenience
    """
    tmpl = env.get_template(TEMPLATE_FN)
    first_src = meta["source"][0] if isinstance(meta.get("source"), list) else meta.get("source")
    context = {**meta, "src": first_src}  # use 'src', not 'source'
    return tmpl.render(**context)

MARK = "<!-- AUTO‑GENERATED‑README‑START -->"

def generate_for_brick(brick_name: str, env: Environment):
    brick_path = BRICKS_DIR / brick_name
    meta_path  = brick_path / "meta.yaml"

    if not meta_path.exists():
        print(f"⚠️  {brick_name}: meta.yaml not found – skipped")
        return

    try:
        meta = load_meta(meta_path)
    except yaml.YAMLError as e:
        print(f"❌  {brick_name}: meta.yaml invalid YAML – {e}")
        return

    generated_block = MARK + "\n" + render_readme(meta, env)
    readme_path = brick_path / "README.md"

    if readme_path.exists():
        old = readme_path.read_text(encoding="utf-8")
        
        # Split on the marker and keep only the manual content
        parts = old.split(MARK)
        manual = parts[0].rstrip()
        
        # If there's no manual content or it's just the generated content, just use the generated block
        if not manual.strip() or manual.strip() == render_readme(meta, env).strip():
            combined = generated_block
        else:
            # Combine manual content with new generated block
            combined = manual + "\n\n" + generated_block
    else:
        # no previous README: just the generated block
        combined = generated_block

    readme_path.write_text(combined, encoding="utf-8")
    print(f"✅  {brick_name}: README.md generated")


def main():
    parser = argparse.ArgumentParser(description="Render README from meta.yaml")
    parser.add_argument("--brick", help="Name of a single brick to process")
    args = parser.parse_args()

    env = Environment(
        loader=FileSystemLoader(str(TEMPL_DIR)),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if args.brick:
        generate_for_brick(args.brick, env)
    else:
        bricks = sorted(p.name for p in BRICKS_DIR.iterdir() if p.is_dir())
        for b in bricks:
            generate_for_brick(b, env)


if __name__ == "__main__":
    sys.exit(main())
