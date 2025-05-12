#!/usr/bin/env python
"""
clean_readmes.py
----------------
Clean up duplicate content in READMEs by keeping only the content above the marker
and removing any duplicate generated content.
"""

from __future__ import annotations
import sys
from pathlib import Path

# ────────────────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[1]   # brick-orchestration/
BRICKS_DIR = ROOT / "brick_repos"
MARK = "<!-- AUTO‑GENERATED‑README‑START -->"
# ────────────────────────────────────────────────────────────────────────────────

def clean_readme(brick_name: str):
    brick_path = BRICKS_DIR / brick_name
    readme_path = brick_path / "README.md"

    if not readme_path.exists():
        print(f"⚠️  {brick_name}: README.md not found – skipped")
        return

    # Read the current content
    content = readme_path.read_text(encoding="utf-8")
    
    # Split on the marker and keep only the manual content
    parts = content.split(MARK)
    if len(parts) > 1:
        # Keep only the manual content
        cleaned = parts[0].rstrip()
        readme_path.write_text(cleaned, encoding="utf-8")
        print(f"✅  {brick_name}: README.md cleaned")
    else:
        print(f"ℹ️  {brick_name}: No marker found – skipped")

def main():
    bricks = sorted(p.name for p in BRICKS_DIR.iterdir() if p.is_dir())
    for b in bricks:
        clean_readme(b)

if __name__ == "__main__":
    sys.exit(main()) 