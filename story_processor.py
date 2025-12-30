#!/usr/bin/env python3
"""
Story Video Processor for BB-Poster-Automation
==============================================
Processes raw videos with custom audio and signature outros.

Folder Structure:
  BB-Poster-Automation/
  +-- Reels_Audio/                              ? Shared audio files
  +-- United_States/Nyssa_Bloom/Instagram/
      +-- Videos/                               ? Raw input videos
      +-- Signatures/                           ? Signature images for outro
      +-- Stories/                              ? Output (processed videos)

Process:
  1. Get all videos from Videos/ (sorted)
  2. Cycle through audio files from Reels_Audio/ (in order)
  3. Cycle through signature images from Signatures/ (in order)
  4. Replace video audio with music
  5. If video < audio, extend with signature image until music ends
  6. Save to Stories/ with MM_DD_YYYY_am/pm.mp4 naming

Usage:
  python3 story_processor.py                    # Process all videos
  python3 story_processor.py --start-date 01_15_2026
  python3 story_processor.py --dry-run          # Preview without processing
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")

# Input paths
VIDEOS_DIR = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Videos")
AUDIO_DIR = os.path.join(PROJECT_ROOT, "Reels_Audio")
SIGNATURES_DIR = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Signatures")

# Output path
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "United_States/Nyssa_Bloom/Instagram/Stories")

# Signature settings
SIGNATURE_TEXT = "Nyssa Bloom"
SIGNATURE_FONT_SIZE = 40
SIGNATURE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Timing
TEXT_DURATION = 1.2      # How long text screen shows
FADE_DURATION = 0.5      # Fade in/out duration
MIN_OUTRO_TIME = 1.5     # Minimum extra time to trigger outro

# Quality
OUTPUT_FPS = 24
VIDEO_CRF = 20
AUDIO_BITRATE = "192k"


# =============================================================================
# HELPERS
# =============================================================================

def run_cmd(cmd):
    """Run command and return result"""
    return subprocess.run(cmd, capture_output=True, text=True)


def get_duration(filepath):
    """Get media duration in seconds"""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
    result = run_cmd(cmd)
    return float(result.stdout.strip())


def get_dimensions(video_path):
    """Get video width, height"""
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path]
    result = run_cmd(cmd)
    w, h = result.stdout.strip().split(',')
    return int(w), int(h)


def prepare_signature(src_image, width, height, output_path):
    """Resize signature image to match video dimensions"""
    cmd = ['ffmpeg', '-y', '-i', src_image, '-vf',
           f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
           f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
           output_path]
    run_cmd(cmd)


def get_sorted_files(directory, extensions):
    """Get sorted list of files with given extensions"""
    if not os.path.exists(directory):
        return []
    
    files = []
    for f in sorted(os.listdir(directory)):
        if any(f.lower().endswith(ext) for ext in extensions):
            files.append(os.path.join(directory, f))
    return files


def generate_output_name(index, start_date):
    """Generate MM_DD_YYYY_am/pm.mp4 filename"""
    days_offset = index // 2
    is_pm = index % 2 == 1
    
    target_date = start_date + timedelta(days=days_offset)
    slot = "pm" if is_pm else "am"
    
    return f"{target_date.strftime('%m_%d_%Y')}_{slot}.mp4"


# =============================================================================
# MAIN PROCESSOR
# =============================================================================

def process_video(video_path, audio_path, signature_path, output_path, verbose=True):
    """
    Process single video: replace audio, add signature outro if needed
    """
    if verbose:
        print(f"\n  Video: {os.path.basename(video_path)}")
        print(f"  Audio: {os.path.basename(audio_path)}")
        print(f"  Signature: {os.path.basename(signature_path)}")
    
    # Get info
    video_dur = get_duration(video_path)
    audio_dur = get_duration(audio_path)
    width, height = get_dimensions(video_path)
    extra_time = audio_dur - video_dur
    
    if verbose:
        print(f"  Duration - Video: {video_dur:.2f}s | Audio: {audio_dur:.2f}s | Extra: {extra_time:.2f}s")
    
    # Decide processing method
    use_signature = extra_time >= MIN_OUTRO_TIME
    
    if use_signature:
        if verbose:
            print(f"  ? Adding signature outro")
        
        # Prepare signature image
        temp_sig = '/tmp/sig_temp.png'
        prepare_signature(signature_path, width, height, temp_sig)
        
        # Calculate durations
        main_end = video_dur - FADE_DURATION
        sig_duration = extra_time - TEXT_DURATION + FADE_DURATION + 0.1
        
        # Complex filter for signature outro
        filter_complex = f"""
            color=black:{width}x{height}:d={TEXT_DURATION + 0.5},fps={OUTPUT_FPS}[black];
            
            [0:v]fps={OUTPUT_FPS},trim=0:{main_end + FADE_DURATION},setpts=PTS-STARTPTS,
            fade=t=out:st={main_end}:d={FADE_DURATION}[main];
            
            [black]drawtext=text='{SIGNATURE_TEXT}':fontsize={SIGNATURE_FONT_SIZE}:
            fontcolor=white:fontfile={SIGNATURE_FONT}:
            x=(w-text_w)/2:y=(h-text_h)/2:
            alpha='if(lt(t,0.4),t/0.4,if(lt(t,{TEXT_DURATION - 0.4}),1,({TEXT_DURATION}-t)/0.4))',
            trim=0:{TEXT_DURATION},setpts=PTS-STARTPTS[text];
            
            [1:v]fps={OUTPUT_FPS},loop=loop=-1:size=1:start=0,
            trim=0:{sig_duration},setpts=PTS-STARTPTS,
            fade=t=in:st=0:d={FADE_DURATION}[sig];
            
            [main][text][sig]concat=n=3:v=1:a=0[vout]
        """.replace('\n', ' ')
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', temp_sig,
            '-i', audio_path,
            '-filter_complex', filter_complex,
            '-map', '[vout]', '-map', '2:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', str(VIDEO_CRF),
            '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
            '-t', str(audio_dur),
            output_path
        ]
    
    elif extra_time > 0:
        # Loop video to match audio (no signature)
        if verbose:
            print(f"  ? Looping video to match audio")
        cmd = [
            'ffmpeg', '-y',
            '-stream_loop', '-1', '-i', video_path,
            '-i', audio_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', str(VIDEO_CRF),
            '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
            '-shortest',
            output_path
        ]
    
    else:
        # Audio shorter or equal to video - just replace audio
        if verbose:
            print(f"  ? Simple audio replacement")
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
            '-shortest',
            output_path
        ]
    
    # Execute
    result = run_cmd(cmd)
    
    if result.returncode == 0:
        if verbose:
            print(f"  ? Output: {os.path.basename(output_path)}")
        return True
    else:
        if verbose:
            print(f"  ? Error!")
            print(result.stderr[-500:] if result.stderr else "Unknown error")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Process raw videos into scheduled stories with custom audio',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--start-date', default='12_30_2025',
                        help='Start date in MM_DD_YYYY format (default: 12_30_2025)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without processing')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    # Parse start date
    try:
        parts = args.start_date.split('_')
        start_date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
    except:
        print(f"Invalid date format: {args.start_date}")
        print("Use MM_DD_YYYY format (e.g., 12_30_2025)")
        sys.exit(1)
    
    print("=" * 60)
    print("STORY VIDEO PROCESSOR")
    print("=" * 60)
    
    # Get all input files (sorted)
    video_exts = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    audio_exts = ['.mp3', '.wav', '.aac', '.m4a', '.ogg']
    image_exts = ['.jpg', '.jpeg', '.png', '.webp']
    
    videos = get_sorted_files(VIDEOS_DIR, video_exts)
    audios = get_sorted_files(AUDIO_DIR, audio_exts)
    signatures = get_sorted_files(SIGNATURES_DIR, image_exts)
    
    print(f"\nVideos folder: {VIDEOS_DIR}")
    print(f"Audio folder:  {AUDIO_DIR}")
    print(f"Signatures:    {SIGNATURES_DIR}")
    print(f"Output folder: {OUTPUT_DIR}")
    
    print(f"\nFound:")
    print(f"  {len(videos)} videos")
    print(f"  {len(audios)} audio files")
    print(f"  {len(signatures)} signature images")
    
    if not videos:
        print("\n? No videos found!")
        sys.exit(1)
    if not audios:
        print("\n? No audio files found!")
        sys.exit(1)
    if not signatures:
        print("\n? No signature images found!")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"\nStart date: {start_date.strftime('%B %d, %Y')} AM")
    end_index = len(videos) - 1
    end_days = end_index // 2
    end_slot = "PM" if end_index % 2 == 1 else "AM"
    end_date = start_date + timedelta(days=end_days)
    print(f"End date:   {end_date.strftime('%B %d, %Y')} {end_slot}")
    
    print(f"\n{'='*60}")
    
    if args.dry_run:
        print("DRY RUN - Preview only:\n")
        for i, video in enumerate(videos):
            audio = audios[i % len(audios)]
            sig = signatures[i % len(signatures)]
            output_name = generate_output_name(i, start_date)
            
            print(f"[{i+1:3}] {os.path.basename(video)}")
            print(f"      + {os.path.basename(audio)}")
            print(f"      + {os.path.basename(sig)}")
            print(f"      ? {output_name}")
            print()
        
        print(f"Total: {len(videos)} videos to process")
        print("Run without --dry-run to process")
        return
    
    # Process videos
    print("PROCESSING:\n")
    
    success = 0
    failed = 0
    
    for i, video in enumerate(videos):
        audio = audios[i % len(audios)]
        sig = signatures[i % len(signatures)]
        output_name = generate_output_name(i, start_date)
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        print(f"[{i+1}/{len(videos)}] ? {output_name}")
        
        if process_video(video, audio, sig, output_path, verbose=True):
            success += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print("COMPLETE")
    print("="*60)
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print(f"  Output:  {OUTPUT_DIR}")
    
    if success > 0:
        print(f"\n  Don't forget to run the scanner to pick up new files:")
        print(f"  python3 scanner.py --once")


if __name__ == "__main__":
    main()