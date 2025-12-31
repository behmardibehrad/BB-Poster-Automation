#!/usr/bin/env python3
"""
Folder Structure Manager for BB-Poster-Automation
=================================================
Creates and syncs folder structure based on structure.yml

Features:
- Creates folders for new countries/models
- DELETES folders for removed countries/models
- Syncs tree structure (Instagram, FB_Page, etc.)

Usage:
    python3 make_structure.py              # Apply changes
    python3 make_structure.py --dry-run    # Preview changes
    python3 make_structure.py --force      # Delete without confirmation
"""

import sys
import shutil
import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Missing dependency: python3-yaml", file=sys.stderr)
    print("Install with: sudo apt install python3-yaml", file=sys.stderr)
    sys.exit(1)

# Track changes
created = []
deleted = []

# Markers that identify a "model folder" (has platform subfolders)
PLATFORM_MARKERS = ("FB_Account", "FB_Page", "Instagram")


def ensure_dir(path: Path):
    """Create directory if it doesn't exist"""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))


def make_tree(base: Path, node):
    """Recursively create folder tree"""
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


def is_model_folder(p: Path) -> bool:
    """Check if path looks like a model folder (has platform subfolders)"""
    return p.is_dir() and any((p / m).exists() for m in PLATFORM_MARKERS)


def is_country_folder(p: Path) -> bool:
    """Check if path looks like a country folder (contains model folders)"""
    if not p.is_dir():
        return False
    for child in p.iterdir():
        if is_model_folder(child):
            return True
    return False


def delete_folder(path: Path, dry_run: bool, force: bool) -> bool:
    """Delete a folder with optional confirmation"""
    if dry_run:
        deleted.append(str(path))
        return True
    
    if not force:
        response = input(f"  Delete {path}? [y/N]: ").strip().lower()
        if response != 'y':
            print(f"  Skipped: {path}")
            return False
    
    shutil.rmtree(path)
    deleted.append(str(path))
    return True


def main():
    parser = argparse.ArgumentParser(description='Sync folder structure from YAML')
    parser.add_argument('manifest', nargs='?', default='structure.yml',
                        help='YAML file (default: structure.yml)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without applying')
    parser.add_argument('--force', action='store_true',
                        help='Delete without confirmation prompts')
    args = parser.parse_args()

    manifest = Path(args.manifest)
    if not manifest.exists():
        print(f"Error: {manifest} not found", file=sys.stderr)
        sys.exit(1)

    cfg = yaml.safe_load(manifest.read_text())

    if "country_brands" not in cfg or "tree" not in cfg:
        print("Error: structure.yml must contain 'country_brands' and 'tree'", file=sys.stderr)
        sys.exit(1)

    mapping = cfg["country_brands"]  # country -> [brands]
    tree = cfg["tree"]

    if args.dry_run:
        print("=" * 50)
        print("DRY RUN - No changes will be made")
        print("=" * 50)
        print()

    # =========================================================================
    # STEP 1: Build set of desired paths
    # =========================================================================
    
    desired_countries = set(mapping.keys())
    desired_models = set()  # Full paths to model folders

    for country, brands in mapping.items():
        for brand in (brands or []):  # Handle empty list
            desired_models.add(Path(country) / brand)

    # =========================================================================
    # STEP 2: DELETE countries/models that are NOT in YAML
    # =========================================================================
    
    print("Checking for folders to delete...")
    
    # Find all existing country-like folders in current directory
    cwd = Path(".")
    existing_countries = [
        p for p in cwd.iterdir() 
        if p.is_dir() 
        and not p.name.startswith('.')
        and not p.name.startswith('_')
        and p.name not in ('logs', 'media_root', 'media_tokens', 'backups', 
                           'Reels_Audio', '__pycache__', 'venv', 'env')
        and is_country_folder(p)
    ]

    for country_path in existing_countries:
        country_name = country_path.name
        
        # Case 1: Entire country removed from YAML
        if country_name not in desired_countries:
            print(f"\n  Country '{country_name}' not in YAML")
            delete_folder(country_path, args.dry_run, args.force)
            continue
        
        # Case 2: Country exists, check for removed models
        for model_path in country_path.iterdir():
            if not is_model_folder(model_path):
                continue
            
            relative_path = Path(country_name) / model_path.name
            
            if relative_path not in desired_models:
                print(f"\n  Model '{model_path.name}' not in YAML under {country_name}")
                delete_folder(model_path, args.dry_run, args.force)

    # =========================================================================
    # STEP 3: CREATE new countries/models from YAML
    # =========================================================================
    
    print("\nChecking for folders to create...")
    
    for country, brands in mapping.items():
        country_path = Path(country)
        ensure_dir(country_path)
        
        for brand in (brands or []):
            base = country_path / brand
            ensure_dir(base)
            
            # Create tree structure under each model
            for node in tree:
                make_tree(base, node)

    # =========================================================================
    # REPORT
    # =========================================================================
    
    print()
    print("=" * 50)
    
    if created:
        print("CREATED:")
        for p in created:
            print(f"  + {p}")
    
    if deleted:
        print("DELETED:")
        for p in deleted:
            print(f"  - {p}")
    
    if not created and not deleted:
        print("No changes needed - structure matches YAML")
    else:
        print()
        print(f"Summary: {len(created)} created, {len(deleted)} deleted")
    
    if args.dry_run and (created or deleted):
        print()
        print("Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()