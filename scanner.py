#!/usr/bin/env python3
"""
Scanner module for BB-Poster-Automation.
Detects new media files in the folder structure and queues them for posting.
"""

import os
import time
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

import db
from config import PROJECT_ROOT, setup_logger

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Folders to scan (relative to PROJECT_ROOT)
SCAN_ROOTS: Optional[List[str]] = None  # None = auto-discover

# File extensions to consider as media
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# Folders that indicate content type
CONTENT_TYPE_FOLDERS = {"Feeds", "Photos", "Reels", "Stories", "Videos"}

# Platform folders
PLATFORM_FOLDERS = {"FB_Page", "FB_Account", "Instagram"}

# Files/folders to ignore
IGNORE_PATTERNS = {
    ".DS_Store",
    "Thumbs.db",
    ".gitkeep",
    "__pycache__",
    ".credentials",
}

# Logger (initialized in main)
logger = None

# -----------------------------------------------------------------------------
# Path Parsing
# -----------------------------------------------------------------------------

@dataclass
class ParsedPath:
    """Parsed information from a media file path."""
    file_path: str
    country: str
    model_name: str
    platform: str
    content_type: str
    filename: str
    extension: str
    is_valid: bool = True
    error: Optional[str] = None


def parse_media_path(abs_path: str) -> ParsedPath:
    """Parse a media file path to extract metadata."""
    try:
        rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
    except ValueError:
        return ParsedPath(
            file_path=abs_path, country="", model_name="", platform="",
            content_type="", filename="", extension="",
            is_valid=False, error="Path not under PROJECT_ROOT"
        )
    
    parts = Path(rel_path).parts
    filename = parts[-1] if parts else ""
    extension = os.path.splitext(filename)[1].lower()
    
    if len(parts) < 5:
        return ParsedPath(
            file_path=rel_path, country="", model_name="", platform="",
            content_type="", filename=filename, extension=extension,
            is_valid=False, error=f"Path too short: {len(parts)} parts, need 5"
        )
    
    country = parts[0]
    model_name = parts[1]
    platform = parts[2]
    content_type = parts[3]
    
    if platform not in PLATFORM_FOLDERS:
        return ParsedPath(
            file_path=rel_path, country=country, model_name=model_name,
            platform=platform, content_type=content_type,
            filename=filename, extension=extension,
            is_valid=False, error=f"Unknown platform: {platform}"
        )
    
    if content_type not in CONTENT_TYPE_FOLDERS:
        return ParsedPath(
            file_path=rel_path, country=country, model_name=model_name,
            platform=platform, content_type=content_type,
            filename=filename, extension=extension,
            is_valid=False, error=f"Unknown content type: {content_type}"
        )
    
    if extension not in MEDIA_EXTENSIONS:
        return ParsedPath(
            file_path=rel_path, country=country, model_name=model_name,
            platform=platform, content_type=content_type,
            filename=filename, extension=extension,
            is_valid=False, error=f"Not a media file: {extension}"
        )
    
    return ParsedPath(
        file_path=rel_path,
        country=country,
        model_name=model_name,
        platform=platform,
        content_type=content_type,
        filename=filename,
        extension=extension,
        is_valid=True
    )


# -----------------------------------------------------------------------------
# Directory Discovery
# -----------------------------------------------------------------------------

def discover_country_folders() -> List[str]:
    """Auto-discover country folders in PROJECT_ROOT."""
    countries = []
    
    for entry in os.scandir(PROJECT_ROOT):
        if not entry.is_dir():
            continue
        
        name = entry.name
        
        if name.startswith("."):
            continue
        if name in {"media_root", "media_tokens", "__pycache__", "venv", "env", "logs"}:
            continue
        if name.endswith(".py") or name.endswith(".sqlite3"):
            continue
            
        has_model_structure = False
        for subentry in os.scandir(entry.path):
            if subentry.is_dir():
                for platform in PLATFORM_FOLDERS:
                    if os.path.isdir(os.path.join(subentry.path, platform)):
                        has_model_structure = True
                        break
            if has_model_structure:
                break
        
        if has_model_structure:
            countries.append(name)
    
    return sorted(countries)


def should_ignore(name: str) -> bool:
    """Check if a file/folder should be ignored."""
    if name in IGNORE_PATTERNS:
        return True
    if name.startswith("."):
        return True
    return False


# -----------------------------------------------------------------------------
# Scanner Core
# -----------------------------------------------------------------------------

def scan_directory(root_dir: str) -> List[ParsedPath]:
    """Recursively scan a directory for media files."""
    found_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not should_ignore(d)]
        
        for filename in filenames:
            if should_ignore(filename):
                continue
            
            abs_path = os.path.join(dirpath, filename)
            parsed = parse_media_path(abs_path)
            
            if parsed.is_valid:
                found_files.append(parsed)
            elif parsed.extension in MEDIA_EXTENSIONS:
                logger.debug(f"Skipped: {parsed.file_path} ({parsed.error})")
    
    return found_files


def scan_all() -> Tuple[int, int]:
    """Scan all configured directories for new media files."""
    if SCAN_ROOTS:
        roots = [os.path.join(PROJECT_ROOT, r) for r in SCAN_ROOTS]
    else:
        countries = discover_country_folders()
        roots = [os.path.join(PROJECT_ROOT, c) for c in countries]
        logger.info(f"Discovered country folders: {countries}")
    
    if not roots:
        logger.warning("No folders to scan!")
        return 0, 0
    
    all_files: List[ParsedPath] = []
    for root in roots:
        if os.path.isdir(root):
            files = scan_directory(root)
            all_files.extend(files)
            logger.debug(f"Found {len(files)} media files in {root}")
    
    logger.info(f"Total media files found: {len(all_files)}")
    
    added = 0
    for parsed in all_files:
        if db.file_exists(parsed.file_path):
            continue
        
        abs_path = os.path.join(PROJECT_ROOT, parsed.file_path)
        try:
            stat = os.stat(abs_path)
            file_size = stat.st_size
            file_mtime = stat.st_mtime
        except OSError as e:
            logger.warning(f"Cannot stat {parsed.file_path}: {e}")
            continue
        
        if file_size == 0:
            logger.warning(f"Skipping empty file: {parsed.file_path}")
            continue
        
        row_id = db.insert_media_file(
            file_path=parsed.file_path,
            file_size=file_size,
            file_mtime=file_mtime,
            country=parsed.country,
            model_name=parsed.model_name,
            platform=parsed.platform,
            content_type=parsed.content_type
        )
        
        if row_id:
            added += 1
            logger.info(f"NEW: [{row_id}] {parsed.platform}/{parsed.content_type} - {parsed.file_path}")
    
    return len(all_files), added


# -----------------------------------------------------------------------------
# Daemon Mode
# -----------------------------------------------------------------------------

def run_daemon(interval_seconds: int = 60) -> None:
    """Run scanner in daemon mode, polling at specified interval."""
    logger.info(f"Starting scanner daemon (interval: {interval_seconds}s)")
    logger.info(f"Project root: {PROJECT_ROOT}")
    
    while True:
        try:
            found, added = scan_all()
            if added > 0:
                logger.info(f"Scan complete: {added} new file(s) queued")
            else:
                logger.debug(f"Scan complete: no new files (total: {found})")
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
        
        time.sleep(interval_seconds)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    global logger
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan for new media files")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Scan interval (default: 60)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--list-countries", action="store_true", help="List discovered folders")
    args = parser.parse_args()
    
    logger = setup_logger("scanner", verbose=args.verbose)
    db.init_db()
    
    if args.list_countries:
        countries = discover_country_folders()
        print(f"Discovered {len(countries)} country folder(s):")
        for c in countries:
            print(f"  - {c}")
        return
    
    if args.dry_run:
        if SCAN_ROOTS:
            roots = [os.path.join(PROJECT_ROOT, r) for r in SCAN_ROOTS]
        else:
            countries = discover_country_folders()
            roots = [os.path.join(PROJECT_ROOT, c) for c in countries]
        
        all_files = []
        for root in roots:
            if os.path.isdir(root):
                all_files.extend(scan_directory(root))
        
        new_count = 0
        for parsed in all_files:
            is_new = not db.file_exists(parsed.file_path)
            status = "NEW" if is_new else "EXISTS"
            if is_new:
                new_count += 1
            print(f"[{status}] {parsed.platform}/{parsed.content_type}: {parsed.file_path}")
        
        print(f"\nTotal: {len(all_files)} files, {new_count} new")
        return
    
    if args.daemon:
        run_daemon(interval_seconds=args.interval)
    else:
        found, added = scan_all()
        print(f"Scan complete: {found} total files, {added} new file(s) queued")


if __name__ == "__main__":
    main()