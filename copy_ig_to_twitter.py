#!/usr/bin/env python3
"""
Copy Instagram photos to Twitter with date shift.
Shifts dates back by 1 year (e.g., 12_31_2026 ? 12_31_2025)
"""

import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")

# Source and destination
INSTAGRAM_PHOTOS = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Photos")
TWITTER_PHOTOS = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Twitter/Photos")

# Date pattern: MM_DD_YYYY_am/pm.ext
DATE_PATTERN = re.compile(r'^(\d{1,2})_(\d{1,2})_(\d{4})_(am|pm)\.(.+)$', re.IGNORECASE)

# How many years to shift back
YEAR_SHIFT = 1


def shift_filename(filename: str) -> str:
    """Shift the year in a filename back by YEAR_SHIFT years."""
    match = DATE_PATTERN.match(filename)
    if not match:
        return None
    
    month, day, year, period, ext = match.groups()
    new_year = int(year) - YEAR_SHIFT
    
    return f"{month}_{day}_{new_year}_{period}.{ext}"


def main():
    # Ensure destination exists
    os.makedirs(TWITTER_PHOTOS, exist_ok=True)
    
    # Get all files from Instagram Photos
    files = sorted(os.listdir(INSTAGRAM_PHOTOS))
    
    copied = 0
    skipped = 0
    
    print(f"Source: {INSTAGRAM_PHOTOS}")
    print(f"Destination: {TWITTER_PHOTOS}")
    print(f"Year shift: -{YEAR_SHIFT} year(s)")
    print("-" * 60)
    
    for filename in files:
        src_path = os.path.join(INSTAGRAM_PHOTOS, filename)
        
        # Skip directories
        if os.path.isdir(src_path):
            continue
        
        # Try to shift the filename
        new_filename = shift_filename(filename)
        
        if not new_filename:
            print(f"  SKIP (no date pattern): {filename}")
            skipped += 1
            continue
        
        dst_path = os.path.join(TWITTER_PHOTOS, new_filename)
        
        # Check if destination already exists
        if os.path.exists(dst_path):
            print(f"  EXISTS: {new_filename}")
            skipped += 1
            continue
        
        # Copy file
        shutil.copy2(src_path, dst_path)
        print(f"  {filename} ? {new_filename}")
        copied += 1
    
    print("-" * 60)
    print(f"Done! Copied: {copied}, Skipped: {skipped}")
    print(f"\nTwitter Photos folder now has {len(os.listdir(TWITTER_PHOTOS))} files")


if __name__ == "__main__":
    main()