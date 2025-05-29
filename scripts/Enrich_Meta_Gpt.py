
from dotenv import load_dotenv
import os
import yaml
import openai
import requests
import re
from pathlib import Path
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

BRICKS_DIR = Path("brick_repos")
openai.api_key = os.environ.get("OPENAI_API_KEY")

META_TEMPLATE = {
    "title": "",
    "description": "",
    "source": [],
    "license": "",
    "tags": [],
    "assets": [],
    "transformations": ""
}

MARK = "<!-- AUTO‑GENERATED‑README‑START -->"

def extract_manual_section(readme_path):
    if not readme_path.exists():
        return ""
    text = readme_path.read_text(encoding="utf-8")
    return text.split(MARK, 1)[0].strip()

def scrape_status_biobricks(brick_name):
    url = f"https://status.biobricks.ai/brick/{brick_name}"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()
        return text.strip()
    except Exception as e:
        print(f"⚠️ Failed to scrape status.biobricks.ai for {brick_name}: {e}")
        return ""

def extract_assets_from_status(scraped_text):
    assets = []
    matches = re.findall(r"(\S+\.(?:parquet|csv|tsv|json|sqlite|txt))\s+(\d+(?:\.\d+)?\s*[KMG]B)", scraped_text, re.IGNORECASE)
    for filename, size in matches:
        ext = filename.split(".")[-1].upper()
        assets.append({
            "file": filename,
            "format": ext,
            "description": f"Auto-detected file ({size.strip()}) from status.biobricks.ai"
        })
    return assets

def gpt_extract_meta(readme_text, scraped_text):
    combined = f"README:\n{readme_text}\n\nBIOBRICKS STATUS PAGE:\n{scraped_text}"

    prompt = f"""
From the following content, extract metadata as a YAML dictionary with the following structure:

- title: <title>
- description: <plain-language description>
- source:
  - name: <source name>
    url: <source url>
    citation: <optional citation>
    license: <license name>
- license: <overall repo license if available>
- tags: [list of relevant keywords]
- assets:
  - file: <filename>
    format: <file type>
    description: <short description>
- transformations: <data processing summary>

Only include fields you can infer. Output raw YAML only, with no code fences, markdown, or comments.
"""

    messages = [
        {"role": "system", "content": "You are a dataset documentation parser."},
        {"role": "user", "content": prompt + combined}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2
    )

    raw_yaml = response.choices[0].message.content
    print("\n📥 GPT Response (raw):\n", raw_yaml)

    try:
        extracted = yaml.safe_load(raw_yaml)
        if not isinstance(extracted, dict):
            raise yaml.YAMLError("Parsed result was not a dictionary")
        print("\n✅ Parsed YAML:\n", yaml.dump(extracted, sort_keys=False))
        return extracted
    except yaml.YAMLError as e:
        print("⚠️ Failed to parse YAML:\n", e)
        return {}

def is_stub(value):
    if isinstance(value, str):
        return value.strip().lower().startswith("todo")
    if isinstance(value, list):
        return all(is_stub(v) for v in value)
    if isinstance(value, dict):
        return all(is_stub(v) for v in value.values())
    return not value

def enrich_meta_yaml(brick_name):
    brick_path = BRICKS_DIR / brick_name
    readme_path = brick_path / "README.md"
    meta_path = brick_path / "meta.yaml"

    manual_readme = extract_manual_section(readme_path)
    scraped_text = scrape_status_biobricks(brick_name)
    gpt_meta = gpt_extract_meta(manual_readme, scraped_text)
    status_assets = extract_assets_from_status(scraped_text)

    # Load existing meta
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
    else:
        meta = {}

    # Fill missing or stub fields from GPT
    for key, default in META_TEMPLATE.items():
        if (not meta.get(key) or is_stub(meta.get(key))) and gpt_meta.get(key):
            meta[key] = gpt_meta[key]

    # Enrich assets: prefer GPT but fallback to status page
    if (not meta.get("assets") or is_stub(meta.get("assets"))):
        if status_assets:
            meta["assets"] = status_assets
            print(f"ℹ️ Used scraped asset info for {brick_name}")
    elif meta.get("assets") and status_assets:
        for g_asset in meta["assets"]:
            match = next((s for s in status_assets if s["file"] == g_asset.get("file")), None)
            if match and "size" in match["description"]:
                g_asset["description"] = match["description"]

    # Fallback for transformations
    if "transformations" not in meta or is_stub(meta.get("transformations")):
        meta["transformations"] = "None — preserved as-is"

    # Warn on missing fields from GPT
    missing = [k for k in META_TEMPLATE if k not in gpt_meta]
    if missing:
        print(f"⚠️ GPT did not return: {missing}")

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False)

    print(f"✅ {brick_name}: meta.yaml enriched")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--brick", help="Only enrich a specific brick")
    args = parser.parse_args()

    if args.brick:
        enrich_meta_yaml(args.brick)
    else:
        for brick in sorted(BRICKS_DIR.iterdir()):
            if brick.is_dir():
                enrich_meta_yaml(brick.name)

if __name__ == "__main__":
    main()
