#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comment Responder Daemon for BB-Poster-Automation.

Polls Instagram for new comments, generates replies using OpenAI,
and posts them with a random delay to appear human-like.
"""

import os
import re
import sys
import time
import json
import random
import sqlite3
import argparse
import requests
from datetime import datetime, timedelta
from threading import Thread
from queue import Queue

# Add project root to path
PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
sys.path.insert(0, PROJECT_ROOT)

from config import setup_logger, FB_GRAPH_API, DB_FILE

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Polling interval (seconds)
POLL_INTERVAL = 600  # 10 minutes

# Reply delay range (seconds)
MIN_REPLY_DELAY = 900   # 15 minutes
MAX_REPLY_DELAY = 2700  # 45 minutes

# Rate limiting
MAX_REPLIES_PER_HOUR = 8  # Stay within 5-10 range

# -----------------------------------------------------------------------------
# Nyssa's Personality Prompt
# -----------------------------------------------------------------------------

NYSSA_SYSTEM_PROMPT = """You are Nyssa Rose Bloom, a 27-year-old fitness and lifestyle influencer.

BACKGROUND:
- Originally from New York, now living in Miami
- Moved to Miami for the weather and beach lifestyle
- Fitness enthusiast - believes in "strong not skinny"
- Works out daily, loves the gym, yoga, and outdoor activities

PERSONALITY:
- Warm, friendly, approachable
- Confident but not arrogant
- Self-deprecating humor
- Fiercely independent
- Supportive and encouraging to everyone

SPEAKING STYLE:
- Casual but articulate (NYC roots)
- Uses "babe" or "hun" (gender-neutral, common in influencer speak)
- NEVER use "girl", "queen", "sis" or gendered terms - you don't know who's commenting
- Says things are "unreal", "obsessed", "iconic", "insane"
- Keeps replies SHORT - 1-2 sentences max for Instagram comments
- Uses 1-2 emojis max, not excessive
- Never preachy or try-hard
- Authentic and real

RULES FOR INSTAGRAM COMMENT REPLIES:
- Keep it SHORT (1-2 sentences)
- Be warm and engaging
- Answer questions directly
- Sound like a real person, not a brand
- Match the energy of the commenter
- Use emojis sparingly (1-2 max)
- NEVER assume gender - avoid "girl", "queen", "king", "bro", "sis" etc."""

EMOJI_ONLY_INSTRUCTION = """The comment is emoji-only (no words). 
Reply with ONLY a single emoji or ultra-short acknowledgment (1-3 words max).
Examples: "??", "??", "thanks babe!", "love u! ??", "??"
Do NOT write a full sentence."""

# -----------------------------------------------------------------------------
# Database Setup
# -----------------------------------------------------------------------------

def init_comment_db():
    """Initialize the comments tracking table."""
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS comment_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE NOT NULL,
            media_id TEXT NOT NULL,
            username TEXT,
            comment_text TEXT,
            reply_text TEXT,
            scheduled_at INTEGER,
            replied_at INTEGER,
            status TEXT DEFAULT 'pending',
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_comment_id ON comment_replies(comment_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_status ON comment_replies(status)")
    con.commit()
    con.close()

def get_replied_comment_ids():
    """Get set of comment IDs we've already processed."""
    con = sqlite3.connect(DB_FILE)
    rows = con.execute("SELECT comment_id FROM comment_replies").fetchall()
    con.close()
    return {row[0] for row in rows}

def add_pending_reply(comment_id, media_id, username, comment_text, reply_text, scheduled_at):
    """Add a reply to the queue."""
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        INSERT OR IGNORE INTO comment_replies 
        (comment_id, media_id, username, comment_text, reply_text, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (comment_id, media_id, username, comment_text, reply_text, scheduled_at))
    con.commit()
    con.close()

def get_pending_replies():
    """Get replies that are due to be posted."""
    now = int(time.time())
    con = sqlite3.connect(DB_FILE)
    rows = con.execute("""
        SELECT id, comment_id, media_id, reply_text 
        FROM comment_replies 
        WHERE status = 'pending' AND scheduled_at <= ?
        ORDER BY scheduled_at ASC
    """, (now,)).fetchall()
    con.close()
    return rows

def mark_reply_sent(reply_id):
    """Mark a reply as sent."""
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        UPDATE comment_replies 
        SET status = 'sent', replied_at = strftime('%s', 'now')
        WHERE id = ?
    """, (reply_id,))
    con.commit()
    con.close()

def mark_reply_failed(reply_id, error_msg):
    """Mark a reply as failed."""
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        UPDATE comment_replies 
        SET status = 'failed', reply_text = reply_text || ' [ERROR: ' || ? || ']'
        WHERE id = ?
    """, (error_msg, reply_id))
    con.commit()
    con.close()

def get_replies_last_hour():
    """Count replies sent in the last hour."""
    one_hour_ago = int(time.time()) - 3600
    con = sqlite3.connect(DB_FILE)
    count = con.execute("""
        SELECT COUNT(*) FROM comment_replies 
        WHERE status = 'sent' AND replied_at >= ?
    """, (one_hour_ago,)).fetchone()[0]
    con.close()
    return count

# -----------------------------------------------------------------------------
# Instagram API Functions
# -----------------------------------------------------------------------------

def get_credentials():
    """Get Instagram credentials from database."""
    con = sqlite3.connect(DB_FILE)
    row = con.execute("""
        SELECT ig_user_id, access_token 
        FROM credentials 
        WHERE platform = 'Instagram' AND is_active = 1 
        LIMIT 1
    """).fetchone()
    con.close()
    if not row:
        raise Exception("No active Instagram credentials found")
    return row[0], row[1]

def get_recent_media(ig_user_id, access_token, limit=25):
    """Get recent media posts."""
    url = f"{FB_GRAPH_API}/{ig_user_id}/media"
    params = {
        "fields": "id,caption,timestamp,comments_count",
        "limit": limit,
        "access_token": access_token
    }
    response = requests.get(url, params=params)
    return response.json()

def get_comments(media_id, access_token):
    """Get comments for a media post."""
    url = f"{FB_GRAPH_API}/{media_id}/comments"
    params = {
        "fields": "id,text,timestamp,username",
        "access_token": access_token
    }
    response = requests.get(url, params=params)
    return response.json()

def post_reply(comment_id, message, access_token):
    """Post a reply to a comment."""
    url = f"{FB_GRAPH_API}/{comment_id}/replies"
    params = {
        "message": message,
        "access_token": access_token
    }
    response = requests.post(url, params=params)
    return response.json()

def get_media_caption(media_id, access_token):
    """Get the caption for a specific media post."""
    url = f"{FB_GRAPH_API}/{media_id}"
    params = {
        "fields": "caption",
        "access_token": access_token
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("caption", "")

# -----------------------------------------------------------------------------
# OpenAI Functions
# -----------------------------------------------------------------------------

def is_emoji_only(text):
    """Check if comment contains only emojis and whitespace."""
    # Remove all emojis and whitespace, check if anything remains
    # This regex matches most emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # misc
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols ext-A
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002700-\U000027BF"  # dingbats
        "]+", 
        flags=re.UNICODE
    )
    # Remove emojis and whitespace
    text_without_emoji = emoji_pattern.sub("", text)
    text_clean = text_without_emoji.strip()
    # If nothing left, it's emoji-only
    return len(text_clean) == 0

def generate_reply(comment_text, post_caption=""):
    """Generate a reply using OpenAI."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Build the user message
    emoji_only = is_emoji_only(comment_text)
    
    if emoji_only:
        user_message = f"Someone left this emoji comment on your post: \"{comment_text}\"\n\n{EMOJI_ONLY_INSTRUCTION}"
    else:
        user_message = f"Someone commented on your Instagram post"
        if post_caption:
            user_message += f" (caption: '{post_caption[:100]}')"
        user_message += f":\n\nComment: \"{comment_text}\"\n\nWrite a short reply as Nyssa."
    
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": NYSSA_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 100,
        "temperature": 0.8
    }
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if "choices" in result:
        return result["choices"][0]["message"]["content"].strip()
    else:
        raise Exception(f"OpenAI error: {result}")

# -----------------------------------------------------------------------------
# Main Logic
# -----------------------------------------------------------------------------

def scan_for_new_comments(log):
    """Scan all recent posts for new comments."""
    try:
        ig_user_id, access_token = get_credentials()
    except Exception as e:
        log.error(f"Failed to get credentials: {e}")
        return []
    
    replied_ids = get_replied_comment_ids()
    new_comments = []
    
    # Get recent media
    media_response = get_recent_media(ig_user_id, access_token)
    if "data" not in media_response:
        log.error(f"Failed to get media: {media_response}")
        return []
    
    for post in media_response["data"]:
        media_id = post["id"]
        comment_count = post.get("comments_count", 0)
        
        if comment_count == 0:
            continue
        
        # Get comments for this post
        comments_response = get_comments(media_id, access_token)
        if "data" not in comments_response:
            continue
        
        post_caption = post.get("caption", "")
        
        for comment in comments_response["data"]:
            comment_id = comment["id"]
            
            # Skip if already processed
            if comment_id in replied_ids:
                continue
            
            new_comments.append({
                "comment_id": comment_id,
                "media_id": media_id,
                "username": comment.get("username", "unknown"),
                "text": comment.get("text", ""),
                "caption": post_caption
            })
    
    return new_comments

def process_new_comments(comments, log):
    """Generate replies for new comments and schedule them."""
    for comment in comments:
        try:
            # Generate reply using OpenAI
            reply_text = generate_reply(comment["text"], comment["caption"])
            
            # Calculate random delay
            delay = random.randint(MIN_REPLY_DELAY, MAX_REPLY_DELAY)
            scheduled_at = int(time.time()) + delay
            scheduled_time = datetime.fromtimestamp(scheduled_at).strftime("%H:%M:%S")
            
            # Add to queue
            add_pending_reply(
                comment["comment_id"],
                comment["media_id"],
                comment["username"],
                comment["text"],
                reply_text,
                scheduled_at
            )
            
            log.info(f"Queued reply to @{comment['username']}: \"{comment['text'][:30]}...\" -> scheduled for {scheduled_time}")
            log.debug(f"  Reply: {reply_text}")
            
        except Exception as e:
            log.error(f"Failed to process comment {comment['comment_id']}: {e}")

def send_pending_replies(log):
    """Send replies that are due."""
    # Check rate limit
    replies_last_hour = get_replies_last_hour()
    if replies_last_hour >= MAX_REPLIES_PER_HOUR:
        log.debug(f"Rate limit reached ({replies_last_hour}/{MAX_REPLIES_PER_HOUR} replies this hour)")
        return
    
    remaining_quota = MAX_REPLIES_PER_HOUR - replies_last_hour
    pending = get_pending_replies()
    
    if not pending:
        return
    
    try:
        ig_user_id, access_token = get_credentials()
    except Exception as e:
        log.error(f"Failed to get credentials: {e}")
        return
    
    for reply in pending[:remaining_quota]:  # Respect rate limit
        reply_id, comment_id, media_id, reply_text = reply
        
        try:
            result = post_reply(comment_id, reply_text, access_token)
            
            if "id" in result:
                mark_reply_sent(reply_id)
                log.info(f"Sent reply to comment {comment_id}: {reply_text[:50]}...")
            else:
                error_msg = result.get("error", {}).get("message", str(result))
                mark_reply_failed(reply_id, error_msg)
                log.error(f"Failed to send reply: {error_msg}")
                
        except Exception as e:
            mark_reply_failed(reply_id, str(e))
            log.error(f"Exception sending reply: {e}")
        
        # Small delay between replies
        time.sleep(2)

def run_daemon(log):
    """Main daemon loop."""
    log.info("Comment Responder daemon started")
    log.info(f"Poll interval: {POLL_INTERVAL}s, Reply delay: {MIN_REPLY_DELAY}-{MAX_REPLY_DELAY}s")
    
    while True:
        try:
            # Scan for new comments
            new_comments = scan_for_new_comments(log)
            if new_comments:
                log.info(f"Found {len(new_comments)} new comment(s)")
                process_new_comments(new_comments, log)
            
            # Send pending replies
            send_pending_replies(log)
            
        except Exception as e:
            log.error(f"Error in main loop: {e}")
        
        # Wait for next poll
        time.sleep(POLL_INTERVAL)

def run_once(log):
    """Run a single scan and process cycle."""
    log.info("Running single scan...")
    
    # Scan for new comments
    new_comments = scan_for_new_comments(log)
    log.info(f"Found {len(new_comments)} new comment(s)")
    
    if new_comments:
        process_new_comments(new_comments, log)
    
    # Send pending replies
    send_pending_replies(log)
    
    log.info("Single scan complete")

def show_stats():
    """Show comment reply statistics."""
    con = sqlite3.connect(DB_FILE)
    
    stats = {}
    
    # Count by status
    rows = con.execute("""
        SELECT status, COUNT(*) FROM comment_replies GROUP BY status
    """).fetchall()
    stats["by_status"] = {row[0]: row[1] for row in rows}
    
    # Replies in last 24h
    day_ago = int(time.time()) - 86400
    stats["replied_24h"] = con.execute("""
        SELECT COUNT(*) FROM comment_replies WHERE status = 'sent' AND replied_at >= ?
    """, (day_ago,)).fetchone()[0]
    
    # Replies in last hour
    hour_ago = int(time.time()) - 3600
    stats["replied_1h"] = con.execute("""
        SELECT COUNT(*) FROM comment_replies WHERE status = 'sent' AND replied_at >= ?
    """, (hour_ago,)).fetchone()[0]
    
    # Pending replies
    pending = con.execute("""
        SELECT username, comment_text, reply_text, scheduled_at 
        FROM comment_replies 
        WHERE status = 'pending'
        ORDER BY scheduled_at ASC
        LIMIT 5
    """).fetchall()
    
    con.close()
    
    print(json.dumps(stats, indent=2))
    
    if pending:
        print("\nPending replies:")
        for row in pending:
            username, comment, reply, scheduled = row
            sched_time = datetime.fromtimestamp(scheduled).strftime("%H:%M:%S")
            print(f"  @{username}: \"{comment[:30]}...\" -> \"{reply[:30]}...\" at {sched_time}")

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comment Responder Daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    # Initialize database
    init_comment_db()
    
    if args.stats:
        show_stats()
    elif args.once:
        log = setup_logger("responder", verbose=args.verbose)
        run_once(log)
    else:
        log = setup_logger("responder", verbose=args.verbose)
        run_daemon(log)