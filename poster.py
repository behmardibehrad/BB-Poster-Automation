#!/usr/bin/env python3
"""
Poster worker for BB-Poster-Automation.
Pulls pending jobs from the queue and posts to Facebook/Instagram/Twitter APIs.
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

# Twitter support
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False

import db
from config import (
    PROJECT_ROOT, MEDIA_ROOT, MEDIA_SERVER_SCRIPT,
    PUBLIC_MEDIA_BASE_URL, TOKEN_TTL_SECONDS, TOKEN_MAX_USES,
    FB_GRAPH_API, RATE_LIMITS, POST_DELAY_SECONDS,
    CONTAINER_STATUS_TIMEOUT, CONTAINER_STATUS_INTERVAL,
    setup_logger
)

# Logger (initialized in main)
logger = None

# -----------------------------------------------------------------------------
# Media Server Integration
# -----------------------------------------------------------------------------

def mint_media_token(relative_path: str) -> Optional[str]:
    """Mint a temporary token for a media file."""
    try:
        result = subprocess.run(
            [
                sys.executable, MEDIA_SERVER_SCRIPT,
                "--mint", relative_path,
                "--ttl", str(TOKEN_TTL_SECONDS),
                "--max-uses", str(TOKEN_MAX_USES),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            logger.debug(f"Minted token for {relative_path}: {token[:8]}...")
            return token
        else:
            logger.error(f"Failed to mint token: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error minting token: {e}")
        return None


def revoke_media_token(token: str) -> bool:
    """Revoke a media token after posting."""
    try:
        result = subprocess.run(
            [sys.executable, MEDIA_SERVER_SCRIPT, "--revoke", token],
            capture_output=True,
            text=True,
            timeout=10,
        )
        revoked = "revoked" in result.stdout.lower()
        logger.debug(f"Revoked token {token[:8]}...: {revoked}")
        return revoked
    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        return False


def get_public_media_url(token: str) -> str:
    """Get the public URL for a media token."""
    return f"{PUBLIC_MEDIA_BASE_URL}/m/{token}"


def copy_to_media_root(file_path: str) -> str:
    """Copy a file to media_root for serving."""
    import shutil
    import uuid
    
    ext = os.path.splitext(file_path)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    
    dest_path = os.path.join(MEDIA_ROOT, unique_name)
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    
    src_path = os.path.join(PROJECT_ROOT, file_path)
    shutil.copy2(src_path, dest_path)
    
    logger.debug(f"Copied {file_path} to media_root/{unique_name}")
    return unique_name


def remove_from_media_root(relative_path: str) -> bool:
    """Remove a file from media_root after posting."""
    try:
        full_path = os.path.join(MEDIA_ROOT, relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.debug(f"Removed {relative_path} from media_root")
            return True
        return False
    except Exception as e:
        logger.error(f"Error removing from media_root: {e}")
        return False


# -----------------------------------------------------------------------------
# Rate Limiting
# -----------------------------------------------------------------------------

def get_posts_today(model_name: str, platform: str, content_type: str) -> int:
    """Count how many posts were made today for this model/platform/content_type."""
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    
    with db.get_connection() as con:
        cur = con.execute(
            """
            SELECT COUNT(*) FROM media_files
            WHERE model_name = ? AND platform = ? AND content_type = ?
              AND status = ? AND posted_at >= ?
            """,
            (model_name, platform, content_type, db.STATUS_POSTED, today_start)
        )
        return cur.fetchone()[0]


def is_rate_limited(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if posting this job would exceed rate limits."""
    platform = job["platform"]
    content_type = job["content_type"]
    model_name = job["model_name"]
    
    limits = RATE_LIMITS.get(platform, {})
    daily_limit = limits.get(content_type, 999)
    
    posts_today = get_posts_today(model_name, platform, content_type)
    
    if posts_today >= daily_limit:
        reason = f"{platform}/{content_type}: {posts_today}/{daily_limit} today"
        return True, reason
    
    return False, ""


# -----------------------------------------------------------------------------
# Facebook/Instagram API Helpers
# -----------------------------------------------------------------------------

def api_request(
    method: str,
    endpoint: str,
    access_token: str,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Make a request to the Facebook Graph API."""
    url = f"{FB_GRAPH_API}/{endpoint}"
    
    if params is None:
        params = {}
    params["access_token"] = access_token
    
    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=params, timeout=60)
        elif method.upper() == "POST":
            resp = requests.post(url, params=params, data=data, timeout=120)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        result = resp.json()
        
        if "error" in result:
            logger.error(f"API error: {result['error']}")
            return False, result
        
        return True, result
        
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return False, {"error": {"message": str(e)}}


def wait_for_ig_container(
    container_id: str,
    access_token: str,
    timeout: int = CONTAINER_STATUS_TIMEOUT,
) -> Tuple[bool, str]:
    """Wait for an Instagram media container to be ready for publishing."""
    start = time.time()
    
    while time.time() - start < timeout:
        success, result = api_request(
            "GET", container_id,
            access_token,
            params={"fields": "status_code,status"}
        )
        
        if not success:
            return False, result.get("error", {}).get("message", "Unknown error")
        
        status_code = result.get("status_code")
        logger.debug(f"Container {container_id} status: {status_code}")
        
        if status_code == "FINISHED":
            return True, "FINISHED"
        elif status_code == "ERROR":
            return False, result.get("status", "Container error")
        elif status_code in ("IN_PROGRESS", "PUBLISHED"):
            time.sleep(CONTAINER_STATUS_INTERVAL)
        else:
            time.sleep(CONTAINER_STATUS_INTERVAL)
    
    return False, "Timeout waiting for container"


# -----------------------------------------------------------------------------
# Instagram Posting Functions
# -----------------------------------------------------------------------------

def post_instagram_image(
    ig_user_id: str,
    access_token: str,
    image_url: str,
    caption: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Post an image to Instagram feed."""
    params = {"image_url": image_url}
    if caption:
        params["caption"] = caption
    
    success, result = api_request(
        "POST", f"{ig_user_id}/media",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to create container")
        return False, "", error
    
    container_id = result.get("id")
    if not container_id:
        return False, "", "No container ID returned"
    
    logger.info(f"Created IG image container: {container_id}, waiting for processing...")
    
    # Wait for container to be ready (images usually quick, but sometimes need a moment)
    ready, status = wait_for_ig_container(container_id, access_token, timeout=60)
    if not ready:
        return False, container_id, f"Container not ready: {status}"
    
    success, result = api_request(
        "POST", f"{ig_user_id}/media_publish",
        access_token,
        params={"creation_id": container_id},
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to publish")
        return False, container_id, error
    
    post_id = result.get("id")
    logger.info(f"Published IG image: {post_id}")
    return True, post_id, ""


def post_instagram_video(
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: Optional[str] = None,
    media_type: str = "VIDEO",
) -> Tuple[bool, str, str]:
    """Post a video to Instagram (Feed, Reels, or Stories)."""
    params = {
        "video_url": video_url,
        "media_type": media_type,
    }
    if caption and media_type != "STORIES":
        params["caption"] = caption
    
    if media_type == "REELS":
        params["share_to_feed"] = "true"
    
    success, result = api_request(
        "POST", f"{ig_user_id}/media",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to create container")
        return False, "", error
    
    container_id = result.get("id")
    if not container_id:
        return False, "", "No container ID returned"
    
    logger.info(f"Created IG {media_type} container: {container_id}, waiting for processing...")
    
    ready, status = wait_for_ig_container(container_id, access_token)
    if not ready:
        return False, container_id, f"Container not ready: {status}"
    
    success, result = api_request(
        "POST", f"{ig_user_id}/media_publish",
        access_token,
        params={"creation_id": container_id},
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to publish")
        return False, container_id, error
    
    post_id = result.get("id")
    logger.info(f"Published IG {media_type}: {post_id}")
    return True, post_id, ""


def post_instagram_story(
    ig_user_id: str,
    access_token: str,
    media_url: str,
    is_video: bool = False,
) -> Tuple[bool, str, str]:
    """Post a story to Instagram."""
    if is_video:
        return post_instagram_video(
            ig_user_id, access_token, media_url,
            caption=None, media_type="STORIES"
        )
    else:
        params = {
            "image_url": media_url,
            "media_type": "STORIES",
        }
        
        success, result = api_request(
            "POST", f"{ig_user_id}/media",
            access_token,
            params=params,
        )
        
        if not success:
            error = result.get("error", {}).get("message", "Failed to create container")
            return False, "", error
        
        container_id = result.get("id")
        if not container_id:
            return False, "", "No container ID returned"
        
        logger.info(f"Created IG STORIES container: {container_id}, waiting for processing...")
        
        # Wait for container to be ready before publishing
        ready, status = wait_for_ig_container(container_id, access_token, timeout=60)
        if not ready:
            return False, container_id, f"Container not ready: {status}"
        
        success, result = api_request(
            "POST", f"{ig_user_id}/media_publish",
            access_token,
            params={"creation_id": container_id},
        )
        
        if not success:
            error = result.get("error", {}).get("message", "Failed to publish")
            return False, container_id, error
        
        post_id = result.get("id")
        logger.info(f"Published IG STORIES: {post_id}")
        return True, post_id, ""


# -----------------------------------------------------------------------------
# Facebook Page Posting Functions
# -----------------------------------------------------------------------------

def post_fb_photo(
    page_id: str,
    access_token: str,
    photo_url: str,
    caption: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Post a photo to a Facebook Page."""
    params = {"url": photo_url}
    if caption:
        params["caption"] = caption
    
    success, result = api_request(
        "POST", f"{page_id}/photos",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to post photo")
        return False, "", error
    
    post_id = result.get("id") or result.get("post_id")
    logger.info(f"Posted FB photo: {post_id}")
    return True, post_id, ""


def post_fb_video(
    page_id: str,
    access_token: str,
    video_url: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Post a video to a Facebook Page."""
    params = {"file_url": video_url}
    if title:
        params["title"] = title
    if description:
        params["description"] = description
    
    success, result = api_request(
        "POST", f"{page_id}/videos",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to post video")
        return False, "", error
    
    post_id = result.get("id")
    logger.info(f"Posted FB video: {post_id}")
    return True, post_id, ""


def post_fb_reel(
    page_id: str,
    access_token: str,
    video_url: str,
    description: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Post a Reel to a Facebook Page."""
    params = {"upload_phase": "start"}
    success, result = api_request(
        "POST", f"{page_id}/video_reels",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to init reel upload")
        return False, "", error
    
    video_id = result.get("video_id")
    if not video_id:
        return False, "", "No video_id returned"
    
    params = {
        "upload_phase": "transfer",
        "video_id": video_id,
        "file_url": video_url,
    }
    
    success, result = api_request(
        "POST", f"{page_id}/video_reels",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to transfer video")
        return False, video_id, error
    
    params = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
    }
    if description:
        params["description"] = description
    
    success, result = api_request(
        "POST", f"{page_id}/video_reels",
        access_token,
        params=params,
    )
    
    if not success:
        error = result.get("error", {}).get("message", "Failed to publish reel")
        return False, video_id, error
    
    logger.info(f"Posted FB reel: {video_id}")
    return True, video_id, ""


# -----------------------------------------------------------------------------
# Twitter API Functions
# -----------------------------------------------------------------------------

def post_twitter_image(
    api_key: str,
    api_secret: str,
    access_token: str,
    access_secret: str,
    image_path: str,
    caption: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Post an image to Twitter using Tweepy.
    
    Args:
        api_key: Twitter API Key (Consumer Key)
        api_secret: Twitter API Secret (Consumer Secret)
        access_token: Twitter Access Token
        access_secret: Twitter Access Token Secret
        image_path: Local path to the image file
        caption: Tweet text (max 280 chars for text, but images allow more)
    
    Returns:
        Tuple of (success, tweet_id, error_message)
    """
    if not TWEEPY_AVAILABLE:
        return False, "", "tweepy module not installed. Run: pip install tweepy --break-system-packages"
    
    try:
        # Authenticate with Twitter API v1.1 for media upload
        auth = tweepy.OAuth1UserHandler(
            api_key, api_secret,
            access_token, access_secret
        )
        api_v1 = tweepy.API(auth)
        
        # Authenticate with Twitter API v2 for posting
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret
        )
        
        # Upload media using v1.1 API
        logger.debug(f"Uploading media: {image_path}")
        media = api_v1.media_upload(filename=image_path)
        media_id = media.media_id
        logger.debug(f"Media uploaded, ID: {media_id}")
        
        # Post tweet with media using v2 API
        tweet_text = caption if caption else ""
        
        # Twitter limit is 280 chars for text, but with images it's more flexible
        # Truncate if needed
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."
        
        response = client.create_tweet(
            text=tweet_text,
            media_ids=[media_id]
        )
        
        tweet_id = str(response.data['id'])
        logger.info(f"Posted tweet: {tweet_id}")
        return True, tweet_id, ""
        
    except tweepy.TweepyException as e:
        error_msg = str(e)
        logger.error(f"Twitter API error: {error_msg}")
        return False, "", error_msg
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Twitter posting error: {error_msg}")
        return False, "", error_msg


# -----------------------------------------------------------------------------
# Main Posting Logic
# -----------------------------------------------------------------------------

def is_video_file(filename: str) -> bool:
    """Check if a file is a video based on extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def post_job(job: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Process and post a single job."""
    creds = db.get_credentials(
        job["country"],
        job["model_name"],
        job["platform"]
    )
    
    if not creds:
        return False, "", f"No credentials for {job['country']}/{job['model_name']}/{job['platform']}"
    
    platform = job["platform"]
    content_type = job["content_type"]
    caption = job.get("caption")
    is_video = is_video_file(job["file_path"])
    
    # Twitter uses different credential fields and posts locally (no media URL needed)
    if platform == "Twitter":
        twitter_api_key = creds.get("twitter_api_key")
        twitter_api_secret = creds.get("twitter_api_secret")
        twitter_access_token = creds.get("twitter_access_token")
        twitter_access_secret = creds.get("twitter_access_secret")
        
        if not all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
            return False, "", "Missing Twitter credentials (need api_key, api_secret, access_token, access_secret)"
        
        # Twitter posts directly from local file
        local_path = os.path.join(PROJECT_ROOT, job["file_path"])
        if not os.path.isfile(local_path):
            return False, "", f"File not found: {local_path}"
        
        if is_video:
            return False, "", "Twitter video posting not yet implemented"
        
        success, post_id, error = post_twitter_image(
            twitter_api_key, twitter_api_secret,
            twitter_access_token, twitter_access_secret,
            local_path, caption=caption
        )
        return success, post_id, error
    
    # Instagram/Facebook use access_token and media URLs
    access_token = creds.get("access_token")
    if not access_token:
        return False, "", "No access token in credentials"
    
    media_root_path = copy_to_media_root(job["file_path"])
    token = mint_media_token(media_root_path)
    
    if not token:
        remove_from_media_root(media_root_path)
        return False, "", "Failed to mint media token"
    
    media_url = get_public_media_url(token)
    logger.info(f"Media URL: {media_url}")
    
    try:
        if platform == "Instagram":
            ig_user_id = creds.get("ig_user_id")
            if not ig_user_id:
                return False, "", "No ig_user_id in credentials"
            
            if content_type == "Reels":
                success, post_id, error = post_instagram_video(
                    ig_user_id, access_token, media_url,
                    caption=caption, media_type="REELS"
                )
            elif content_type == "Stories":
                success, post_id, error = post_instagram_story(
                    ig_user_id, access_token, media_url, is_video=is_video
                )
            elif content_type in ("Feeds", "Photos"):
                if is_video:
                    success, post_id, error = post_instagram_video(
                        ig_user_id, access_token, media_url,
                        caption=caption, media_type="VIDEO"
                    )
                else:
                    success, post_id, error = post_instagram_image(
                        ig_user_id, access_token, media_url, caption=caption
                    )
            elif content_type == "Videos":
                success, post_id, error = post_instagram_video(
                    ig_user_id, access_token, media_url,
                    caption=caption, media_type="VIDEO"
                )
            else:
                return False, "", f"Unknown Instagram content type: {content_type}"
        
        elif platform == "FB_Page":
            page_id = creds.get("page_id")
            if not page_id:
                return False, "", "No page_id in credentials"
            
            if content_type == "Reels":
                success, post_id, error = post_fb_reel(
                    page_id, access_token, media_url, description=caption
                )
            elif content_type in ("Photos", "Feeds") and not is_video:
                success, post_id, error = post_fb_photo(
                    page_id, access_token, media_url, caption=caption
                )
            elif content_type in ("Videos", "Feeds") and is_video:
                success, post_id, error = post_fb_video(
                    page_id, access_token, media_url,
                    title=None, description=caption
                )
            elif content_type == "Stories":
                success, post_id, error = post_fb_video(
                    page_id, access_token, media_url, description=caption
                )
            else:
                return False, "", f"Unknown FB_Page content type: {content_type}"
        
        elif platform == "FB_Account":
            return False, "", "FB_Account posting not implemented"
        
        else:
            return False, "", f"Unknown platform: {platform}"
        
        return success, post_id, error
    
    finally:
        revoke_media_token(token)
        remove_from_media_root(media_root_path)


# -----------------------------------------------------------------------------
# Worker Loop
# -----------------------------------------------------------------------------

def process_pending_jobs(limit: int = 1) -> int:
    """Process pending jobs up to the limit."""
    jobs = db.get_pending_jobs(limit=limit)
    processed = 0
    
    for job in jobs:
        job_id = job["id"]
        logger.info(f"Processing job [{job_id}]: {job['platform']}/{job['content_type']} - {job['file_path']}")
        
        limited, reason = is_rate_limited(job)
        if limited:
            logger.warning(f"Job [{job_id}] rate limited: {reason}")
            continue
        
        full_path = os.path.join(PROJECT_ROOT, job["file_path"])
        if not os.path.isfile(full_path):
            logger.warning(f"Job [{job_id}] file not found, marking as skipped")
            db.update_job_status(job_id, db.STATUS_SKIPPED, error_message="File not found")
            continue
        
        db.mark_job_posting(job_id)
        
        try:
            success, post_id, error = post_job(job)
            
            if success:
                db.update_job_status(job_id, db.STATUS_POSTED, platform_post_id=post_id)
                logger.info(f"Job [{job_id}] SUCCESS: {post_id}")
            else:
                db.update_job_status(job_id, db.STATUS_FAILED, error_message=error)
                logger.error(f"Job [{job_id}] FAILED: {error}")
            
            processed += 1
            
        except Exception as e:
            logger.error(f"Job [{job_id}] EXCEPTION: {e}", exc_info=True)
            db.update_job_status(job_id, db.STATUS_FAILED, error_message=str(e))
        
        if processed < len(jobs):
            logger.debug(f"Waiting {POST_DELAY_SECONDS}s before next post...")
            time.sleep(POST_DELAY_SECONDS)
    
    return processed


def run_worker(interval: int = 60, batch_size: int = 1) -> None:
    """Run the poster worker continuously."""
    logger.info(f"Starting poster worker (interval: {interval}s, batch: {batch_size})")
    
    stale = db.reset_stale_jobs()
    if stale:
        logger.info(f"Reset {stale} stale job(s)")
    
    while True:
        try:
            processed = process_pending_jobs(limit=batch_size)
            if processed > 0:
                logger.info(f"Processed {processed} job(s)")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        
        time.sleep(interval)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    global logger
    import argparse
    
    parser = argparse.ArgumentParser(description="Post media to Facebook/Instagram")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--batch", type=int, default=1, help="Jobs per batch")
    parser.add_argument("--job-id", type=int, help="Process a specific job by ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--add-credentials", nargs=5,
        metavar=("COUNTRY", "MODEL", "PLATFORM", "PAGE_ID/IG_USER_ID", "ACCESS_TOKEN"),
        help="Add credentials for an account"
    )
    parser.add_argument(
        "--show-credentials", nargs=3,
        metavar=("COUNTRY", "MODEL", "PLATFORM"),
        help="Show credentials for an account"
    )
    args = parser.parse_args()
    
    logger = setup_logger("poster", verbose=args.verbose)
    db.init_db()
    
    if args.add_credentials:
        country, model, platform, id_value, token = args.add_credentials
        if platform == "Instagram":
            db.upsert_credentials(country, model, platform, ig_user_id=id_value, access_token=token)
        else:
            db.upsert_credentials(country, model, platform, page_id=id_value, access_token=token)
        print(f"Credentials saved for {country}/{model}/{platform}")
        return
    
    if args.show_credentials:
        country, model, platform = args.show_credentials
        creds = db.get_credentials(country, model, platform)
        if creds:
            creds = dict(creds)
            if creds.get("access_token"):
                creds["access_token"] = creds["access_token"][:10] + "..."
            print(json.dumps(creds, indent=2, default=str))
        else:
            print("No credentials found")
        return
    
    if args.job_id:
        job = db.get_job_by_id(args.job_id)
        if not job:
            print(f"Job {args.job_id} not found")
            return
        print(f"Processing job {args.job_id}...")
        db.mark_job_posting(args.job_id)
        success, post_id, error = post_job(job)
        if success:
            db.update_job_status(args.job_id, db.STATUS_POSTED, platform_post_id=post_id)
            print(f"SUCCESS: {post_id}")
        else:
            db.update_job_status(args.job_id, db.STATUS_FAILED, error_message=error)
            print(f"FAILED: {error}")
        return
    
    if args.daemon:
        run_worker(interval=args.interval, batch_size=args.batch)
    else:
        processed = process_pending_jobs(limit=args.batch)
        print(f"Processed {processed} job(s)")


if __name__ == "__main__":
    main()