#!/usr/bin/env python3
"""
Shared configuration for BB-Poster-Automation.
All modules import from here for consistent settings and logging.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")
MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media_root")
MEDIA_SERVER_SCRIPT = os.path.join(PROJECT_ROOT, "media_server.py")

# -----------------------------------------------------------------------------
# Posting Schedule (24-hour format) - RANDOMIZED TIME RANGES
# Files named like: 12_26_2025_am.jpg or 12_26_2025_pm.mp4
#
# Each slot now has a range: ("start_time", "end_time")
# The scanner will pick a random time within this range.
# -----------------------------------------------------------------------------

POSTING_SCHEDULE = {
    "Photos": {
        "am": ("09:00", "11:30"),   # Random between 9:00 AM - 11:30 AM
        "pm": ("14:30", "17:00"),   # Random between 2:30 PM - 5:00 PM
    },
    "Feeds": {
        "am": ("09:00", "11:30"),
        "pm": ("14:30", "17:00"),
    },
    "Videos": {
        "am": ("10:00", "12:30"),   # 1 hour offset from photos
        "pm": ("15:30", "18:00"),
    },
    "Reels": {
        "am": ("10:00", "12:30"),
        "pm": ("15:30", "18:00"),
    },
    "Stories": {
        "am": ("09:30", "12:00"),
        "pm": ("15:00", "17:30"),
    },
}

# -----------------------------------------------------------------------------
# Media Server / Cloudflare
# -----------------------------------------------------------------------------

PUBLIC_MEDIA_BASE_URL = "https://projectmodel.mysticpulsecapital.com"
TOKEN_TTL_SECONDS = 1800  # 30 minutes
TOKEN_MAX_USES = 200

# -----------------------------------------------------------------------------
# Facebook/Instagram API
# -----------------------------------------------------------------------------

FB_GRAPH_API = "https://graph.facebook.com/v21.0"

# -----------------------------------------------------------------------------
# Rate Limits (per account per day)
# -----------------------------------------------------------------------------

RATE_LIMITS = {
    "Instagram": {
        "Feeds": 2,
        "Photos": 2,
        "Reels": 2,
        "Stories": 10,
        "Videos": 2,
    },
    "FB_Page": {
        "Feeds": 10,
        "Photos": 10,
        "Reels": 5,
        "Stories": 10,
        "Videos": 5,
    },
}

# -----------------------------------------------------------------------------
# Timing
# -----------------------------------------------------------------------------

POST_DELAY_SECONDS = 30
CONTAINER_STATUS_TIMEOUT = 300  # 5 minutes
CONTAINER_STATUS_INTERVAL = 10  # Check every 10 seconds

# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------

def setup_logger(name: str, verbose: bool = False) -> logging.Logger:
    """
    Set up a logger that writes to both console and file.
    
    Log files:
        ~/BB-Poster-Automation/logs/scanner.log
        ~/BB-Poster-Automation/logs/poster.log
        ~/BB-Poster-Automation/logs/all.log (combined)
    
    Each log file rotates at 5MB, keeps 5 backups.
    """
    # Create logs directory
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger
    
    # Format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # Module-specific log file
    module_log = os.path.join(LOG_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        module_log,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Combined log file (all modules)
    combined_log = os.path.join(LOG_DIR, "all.log")
    combined_handler = RotatingFileHandler(
        combined_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    combined_handler.setLevel(logging.DEBUG)
    combined_handler.setFormatter(formatter)
    logger.addHandler(combined_handler)
    
    return logger


# -----------------------------------------------------------------------------
# Quick test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Test logging setup
    log = setup_logger("config_test", verbose=True)
    log.info("Config loaded successfully")
    log.debug("Debug message test")
    log.warning("Warning message test")
    log.error("Error message test")
    print(f"\nLog files created in: {LOG_DIR}")
    print(f"  - {LOG_DIR}/config_test.log")
    print(f"  - {LOG_DIR}/all.log")
    
    print("\n--- Posting Schedule (Randomized Ranges) ---")
    for content_type, slots in POSTING_SCHEDULE.items():
        print(f"\n{content_type}:")
        for slot, time_range in slots.items():
            print(f"  {slot.upper()}: {time_range[0]} - {time_range[1]}")