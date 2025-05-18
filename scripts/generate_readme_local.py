import yaml
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

BRICKS_DIR = Path(__file__).parent.parent / "brick_repos"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
TEMPLATE_FN = "readme_template.j2"
MARK = "<!-- AUTO‑GENERATED‑README‑START -->"

def load_meta(meta_path):
    with open(meta_path, "r") as f:
        return yaml.safe_load(f)

def render_readme(meta, env):
    tmpl = env.get_template(TEMPLATE_FN)
    first_src = meta["source"][0] if isinstance(meta.get("source"), list) else meta.get("source")
    context = {**meta, "src": first_src}
    return tmpl.render(**context)

def generate_for_brick(brick_name, env):
    brick_path = BRICKS_DIR / brick_name
    meta_path = brick_path / "meta.yaml"

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
        manual = old.split(MARK, 1)[0].rstrip()
        combined = manual + "\n\n" + generated_block
    else:
        combined = generated_block

    readme_path.write_text(combined, encoding="utf-8")
    print(f"✅  {brick_name}: README.md generated")

def main():
    import sys
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--brick", help="Generate README for specific brick")
    args = parser.parse_args()

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    if args.brick:
        generate_for_brick(args.brick, env)
    else:
        for brick in sorted(BRICKS_DIR.iterdir()):
            if brick.is_dir():
                generate_for_brick(brick.name, env)

if __name__ == "__main__":
    main()

