#!/usr/bin/env python3
"""
Database migration to add Twitter credential columns.
Run this once after updating to the new version.
"""

import os
import sqlite3

DB_FILE = os.path.expanduser("~/BB-Poster-Automation/poster.sqlite3")

def migrate():
    print(f"Migrating database: {DB_FILE}")
    
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    # Check existing columns
    cur.execute("PRAGMA table_info(credentials)")
    columns = {row[1] for row in cur.fetchall()}
    
    new_columns = [
        ("twitter_api_key", "TEXT"),
        ("twitter_api_secret", "TEXT"),
        ("twitter_access_token", "TEXT"),
        ("twitter_access_secret", "TEXT"),
    ]
    
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"  Adding column: {col_name}")
            cur.execute(f"ALTER TABLE credentials ADD COLUMN {col_name} {col_type}")
            added += 1
        else:
            print(f"  Column exists: {col_name}")
    
    con.commit()
    con.close()
    
    print(f"\nMigration complete! Added {added} column(s).")


if __name__ == "__main__":
    migrate()