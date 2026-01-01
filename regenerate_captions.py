#!/usr/bin/env python3
"""
Regenerate captions for images using Claude Vision API.
Analyzes each image and creates a matching caption.
"""

import os
import sys
import base64
import time
import argparse
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Installing anthropic package...")
    os.system("pip install anthropic --break-system-packages")
    import anthropic

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
INSTAGRAM_PHOTOS = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Photos")

# Nyssa's persona for caption generation
PERSONA = """You are Nyssa Bloom, a 24-year-old AI-generated virtual influencer and model based in Miami. 
Your personality: warm, playful, confident but approachable, lifestyle-focused.
Your vibe: sunshine, pool days, golden hour, self-care, good energy.

You're writing an Instagram caption for this photo. Be authentic and match what's ACTUALLY in the image.
Don't mention things that aren't visible. Keep it relatable and engaging.

Format:
- Opening hook (1 line, can include emoji)
- 2-3 sentences of genuine, conversational content about the actual photo
- End with relevant hashtags (5-7): #DigitalCreator #VirtualInfluencer plus 3-5 relevant to the image

Keep it under 300 words total. Be genuine, not generic."""


def encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_image_media_type(image_path: str) -> str:
    """Get media type from file extension."""
    ext = Path(image_path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }.get(ext, "image/jpeg")


def generate_caption(client: anthropic.Anthropic, image_path: str) -> str:
    """Generate a caption for the image using Claude Vision."""
    
    image_data = encode_image(image_path)
    media_type = get_image_media_type(image_path)
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": PERSONA + "\n\nWrite the Instagram caption for this photo:"
                    }
                ],
            }
        ],
    )
    
    return message.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Regenerate captions using Claude Vision")
    parser.add_argument("--api-key", required=True, help="Anthropic API key")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--compare", action="store_true", help="Show old vs new comparison")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of images (0=all)")
    parser.add_argument("--start-from", type=str, default="", help="Start from this filename")
    parser.add_argument("--folder", type=str, default=INSTAGRAM_PHOTOS, help="Photos folder path")
    parser.add_argument("--log", type=str, default="", help="Log changes to file")
    args = parser.parse_args()
    
    client = anthropic.Anthropic(api_key=args.api_key)
    
    # Get all jpg files
    folder = Path(args.folder)
    images = sorted([f for f in folder.glob("*.jpg")])
    
    print(f"Found {len(images)} images in {folder}")
    
    # Filter if start-from specified
    if args.start_from:
        start_idx = next((i for i, f in enumerate(images) if f.name >= args.start_from), 0)
        images = images[start_idx:]
        print(f"Starting from {args.start_from}, {len(images)} remaining")
    
    # Apply limit
    if args.limit > 0:
        images = images[:args.limit]
        print(f"Limited to {len(images)} images")
    
    # Open log file if specified
    log_file = open(args.log, "w") if args.log else None
    
    processed = 0
    errors = 0
    
    for i, image_path in enumerate(images):
        txt_path = image_path.with_suffix(".txt")
        
        # Read old caption
        old_caption = ""
        if txt_path.exists():
            with open(txt_path, "r") as f:
                old_caption = f.read()
        
        print(f"[{i+1}/{len(images)}] {image_path.name}...", end=" ", flush=True)
        
        try:
            new_caption = generate_caption(client, str(image_path))
            
            if args.dry_run or args.compare:
                print(f"\n{'='*60}")
                print(f"FILE: {image_path.name}")
                print(f"{'-'*60}")
                print(f"OLD CAPTION (first 150 chars):")
                print(f"  {old_caption[:150]}...")
                print(f"{'-'*60}")
                print(f"NEW CAPTION (first 150 chars):")
                print(f"  {new_caption[:150]}...")
                print(f"{'='*60}\n")
                
                if not args.dry_run:
                    with open(txt_path, "w") as f:
                        f.write(new_caption)
                    print(f"  ? Saved!")
            else:
                with open(txt_path, "w") as f:
                    f.write(new_caption)
                print("?")
            
            # Log to file
            if log_file:
                log_file.write(f"{'='*60}\n")
                log_file.write(f"FILE: {image_path.name}\n")
                log_file.write(f"OLD: {old_caption[:200]}...\n")
                log_file.write(f"NEW: {new_caption[:200]}...\n\n")
                log_file.flush()
            
            processed += 1
            
            # Rate limiting - be gentle on the API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"? Error: {e}")
            errors += 1
            time.sleep(2)  # Back off on errors
    
    if log_file:
        log_file.close()
        print(f"\nChanges logged to: {args.log}")
    
    print(f"\nDone! Processed: {processed}, Errors: {errors}")


if __name__ == "__main__":
    main()