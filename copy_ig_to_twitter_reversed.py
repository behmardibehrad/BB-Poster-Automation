#!/usr/bin/env python3
"""
Copy Instagram photos to Twitter with REVERSED date order.

This ensures different content posts on each platform on the same day:
- Instagram Jan 1: posts 01_01_2026 image (from beginning)
- Twitter Jan 1: posts 12_31_2026 image (from end)

Both platforms post on the same schedule, but with different images!
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")

# Source and destination
INSTAGRAM_PHOTOS = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Photos")
TWITTER_PHOTOS = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Twitter/Photos")

# Date pattern: MM_DD_YYYY_am/pm.ext
DATE_PATTERN = re.compile(r'^(\d{1,2})_(\d{1,2})_(\d{4})_(am|pm)\.(.+)$', re.IGNORECASE)


def parse_filename(filename: str):
    """Parse filename to extract date info. Returns (date, period, ext) or None."""
    match = DATE_PATTERN.match(filename)
    if not match:
        return None
    
    month, day, year, period, ext = match.groups()
    try:
        date = datetime(int(year), int(month), int(day))
        return (date, period.lower(), ext.lower())
    except ValueError:
        return None


def make_filename(date: datetime, period: str, ext: str) -> str:
    """Create filename from date components."""
    return f"{date.month:02d}_{date.day:02d}_{date.year}_{period}.{ext}"


def main():
    # Ensure destination exists
    os.makedirs(TWITTER_PHOTOS, exist_ok=True)
    
    # Get all image files from Instagram Photos
    all_files = []
    for filename in os.listdir(INSTAGRAM_PHOTOS):
        src_path = os.path.join(INSTAGRAM_PHOTOS, filename)
        if os.path.isdir(src_path):
            continue
        
        parsed = parse_filename(filename)
        if parsed:
            all_files.append((filename, parsed[0], parsed[1], parsed[2]))  # filename, date, period, ext
    
    if not all_files:
        print("No valid dated files found!")
        return
    
    # Separate AM and PM files
    am_files = sorted([f for f in all_files if f[2] == 'am'], key=lambda x: x[1])
    pm_files = sorted([f for f in all_files if f[2] == 'pm'], key=lambda x: x[1])
    
    print(f"Source: {INSTAGRAM_PHOTOS}")
    print(f"Destination: {TWITTER_PHOTOS}")
    print(f"Found {len(am_files)} AM files and {len(pm_files)} PM files")
    print("-" * 60)
    print("Strategy: Reverse image order so different content posts each day")
    print("-" * 60)
    
    copied = 0
    skipped = 0
    
    # Process AM files: reverse the IMAGE order but keep the DATE order
    # So earliest date gets the latest image, and vice versa
    am_dates = [f[1] for f in am_files]  # dates in ascending order
    am_images_reversed = list(reversed(am_files))  # images in descending order
    
    for i, target_date in enumerate(am_dates):
        if i >= len(am_images_reversed):
            break
        
        src_filename = am_images_reversed[i][0]  # image from the end
        src_ext = am_images_reversed[i][3]
        
        # Create new filename with target date but source image
        new_filename = make_filename(target_date, 'am', src_ext)
        
        src_path = os.path.join(INSTAGRAM_PHOTOS, src_filename)
        dst_path = os.path.join(TWITTER_PHOTOS, new_filename)
        
        # Also copy the caption file if it exists
        src_txt = os.path.splitext(src_path)[0] + ".txt"
        dst_txt = os.path.splitext(dst_path)[0] + ".txt"
        
        if os.path.exists(dst_path):
            print(f"  EXISTS: {new_filename}")
            skipped += 1
            continue
        
        shutil.copy2(src_path, dst_path)
        if os.path.exists(src_txt):
            shutil.copy2(src_txt, dst_txt)
        
        print(f"  {src_filename} -> {new_filename}")
        copied += 1
    
    # Process PM files: same logic
    pm_dates = [f[1] for f in pm_files]
    pm_images_reversed = list(reversed(pm_files))
    
    for i, target_date in enumerate(pm_dates):
        if i >= len(pm_images_reversed):
            break
        
        src_filename = pm_images_reversed[i][0]
        src_ext = pm_images_reversed[i][3]
        
        new_filename = make_filename(target_date, 'pm', src_ext)
        
        src_path = os.path.join(INSTAGRAM_PHOTOS, src_filename)
        dst_path = os.path.join(TWITTER_PHOTOS, new_filename)
        
        src_txt = os.path.splitext(src_path)[0] + ".txt"
        dst_txt = os.path.splitext(dst_path)[0] + ".txt"
        
        if os.path.exists(dst_path):
            print(f"  EXISTS: {new_filename}")
            skipped += 1
            continue
        
        shutil.copy2(src_path, dst_path)
        if os.path.exists(src_txt):
            shutil.copy2(src_txt, dst_txt)
        
        print(f"  {src_filename} -> {new_filename}")
        copied += 1
    
    print("-" * 60)
    print(f"Done! Copied: {copied}, Skipped: {skipped}")
    print(f"\nTwitter Photos folder now has {len(os.listdir(TWITTER_PHOTOS))} files")
    print("\nExample mapping:")
    print("  Instagram 01_01_2026_am.jpg (image A) -> posts Jan 1")
    print("  Twitter 01_01_2026_am.jpg (image Z) -> posts Jan 1 (DIFFERENT image!)")


if __name__ == "__main__":
    main()