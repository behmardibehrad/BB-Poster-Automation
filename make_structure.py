#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

try:
    import yaml  # Debian/RPi: sudo apt install -y python3-yaml
except ImportError:
    print("Missing dependency: python3-yaml (or pyyaml).", file=sys.stderr)
    sys.exit(1)

created = []
deleted = []

MARKERS = ("FB_Account", "FB_Page", "Instagram")

def ensure_dir(path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))

def make_tree(base: Path, node):
    if isinstance(node, str):
        ensure_dir(base / node)
        return
    if isinstance(node, dict):
        for folder, children in node.items():
            p = base / folder
            ensure_dir(p)
            for child in children:
                make_tree(p, child)
        return
    raise TypeError(f"Unsupported node type: {type(node)}")

def looks_like_model_folder(p: Path) -> bool:
    return p.is_dir() and any((p / m).exists() for m in MARKERS)

def main():
    manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "structure.yml")
    cfg = yaml.safe_load(manifest.read_text())

    if "country_brands" not in cfg or "tree" not in cfg:
        raise KeyError("structure.yml must contain: country_brands and tree")

    mapping = cfg["country_brands"]  # country -> [brands]
    tree = cfg["tree"]

    # Build desired set of model folder paths
    desired_models = set()
    for country, brands in mapping.items():
        country_path = Path(country)
        ensure_dir(country_path)  # keep country folder itself
        for brand in brands:
            base = (country_path / brand).resolve()
            desired_models.add(base)

            ensure_dir(base)
            for node in tree:
                make_tree(base, node)

    # Prune: remove any model folder under each country not listed in YAML
    for country in mapping.keys():
        country_path = Path(country)
        if not country_path.exists():
            continue

        for child in country_path.iterdir():
            if not child.is_dir():
                continue

            child_res = child.resolve()
            if child_res in desired_models:
                continue

            # Only delete if it looks like one of our model folders
            if looks_like_model_folder(child):
                shutil.rmtree(child)
                deleted.append(str(child))

    # Report
    if created:
        print("Created:")
        for p in created:
            print(f"  + {p}")
    if deleted:
        print("Deleted:")
        for p in deleted:
            print(f"  - {p}")

    if not created and not deleted:
        print("Done. (no changes)")
    else:
        print(f"Done. ({len(created)} created, {len(deleted)} deleted)")

if __name__ == "__main__":
    main()
