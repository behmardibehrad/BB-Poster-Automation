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