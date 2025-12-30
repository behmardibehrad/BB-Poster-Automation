#!/usr/bin/env python3
"""
Sync captions from .txt files to the database.
Run this after updating caption files to ensure the database has the latest captions.

The poster reads from the database, so this ensures your updated captions get posted.
"""

import os
import sqlite3
import argparse

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")


def sync_captions(dry_run=False, pending_only=True):
    """Sync captions from .txt files to database"""
    
    con = sqlite3.connect(DB_FILE)
    
    # Get posts to sync
    if pending_only:
        query = "SELECT id, file_path, caption FROM media_files WHERE status = 'pending'"
        print("Syncing captions for PENDING posts only...")
    else:
        query = "SELECT id, file_path, caption FROM media_files"
        print("Syncing captions for ALL posts...")
    
    rows = con.execute(query).fetchall()
    print(f"Found {len(rows)} posts to check\n")
    
    updated = 0
    skipped = 0
    no_file = 0
    
    for row_id, file_path, db_caption in rows:
        # Get caption file path
        base = os.path.splitext(file_path)[0]
        caption_path = os.path.join(PROJECT_ROOT, base + '.txt')
        
        if not os.path.exists(caption_path):
            no_file += 1
            continue
        
        # Read caption from file
        try:
            with open(caption_path, 'r', encoding='utf-8') as f:
                file_caption = f.read().strip()
        except Exception as e:
            print(f"  Error reading {caption_path}: {e}")
            skipped += 1
            continue
        
        # Compare and update if different
        if file_caption != db_caption:
            filename = os.path.basename(file_path)
            print(f"  {filename}:")
            print(f"    DB:   {(db_caption or '(empty)')[:60]}...")
            print(f"    File: {file_caption[:60]}...")
            
            if not dry_run:
                con.execute("UPDATE media_files SET caption = ? WHERE id = ?", 
                           (file_caption, row_id))
                print(f"    ? Updated!")
            else:
                print(f"    ? Would update (dry-run)")
            
            updated += 1
            print()
        else:
            skipped += 1
    
    if not dry_run:
        con.commit()
    
    con.close()
    
    print("=" * 50)
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped} (already in sync)")
    print(f"No file:  {no_file} (no .txt file found)")
    
    if dry_run and updated > 0:
        print("\nRun without --dry-run to apply changes")


def main():
    parser = argparse.ArgumentParser(description='Sync captions from .txt files to database')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without updating')
    parser.add_argument('--all', action='store_true', help='Sync all posts, not just pending')
    args = parser.parse_args()
    
    sync_captions(dry_run=args.dry_run, pending_only=not args.all)


if __name__ == "__main__":
    main()