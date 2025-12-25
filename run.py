#!/usr/bin/env python3
"""
BB-Poster-Automation Runner
Single command to start everything.

Usage:
    python3 run.py           # Start all services
    python3 run.py --status  # Check what's running
    python3 run.py --stop    # Stop all services
"""

import os
import sys
import time
import subprocess
import argparse

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")

# -----------------------------------------------------------------------------
# Process Checking
# -----------------------------------------------------------------------------

def is_process_running(search_term: str) -> bool:
    """Check if a process containing search_term is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", search_term],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_process_pid(search_term: str) -> list:
    """Get PIDs of processes matching search_term."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", search_term],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [int(pid) for pid in result.stdout.strip().split('\n') if pid]
        return []
    except Exception:
        return []


def kill_process(search_term: str) -> bool:
    """Kill processes matching search_term."""
    try:
        subprocess.run(["pkill", "-f", search_term], capture_output=True)
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Service Management
# -----------------------------------------------------------------------------

def start_media_server() -> bool:
    """Start media server if not running."""
    if is_process_running("media_server.py"):
        print("? Media server already running")
        return True
    
    print("? Starting media server...")
    subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "media_server.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(1)
    
    if is_process_running("media_server.py"):
        print("? Media server started")
        return True
    else:
        print("? Failed to start media server")
        return False


def start_cloudflared() -> bool:
    """Start cloudflared tunnel if not running."""
    if is_process_running("cloudflared tunnel run projectmodel"):
        print("? Cloudflare tunnel already running")
        return True
    
    print("? Starting cloudflare tunnel...")
    subprocess.Popen(
        ["cloudflared", "tunnel", "run", "projectmodel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(2)
    
    if is_process_running("cloudflared"):
        print("? Cloudflare tunnel started")
        return True
    else:
        print("? Failed to start cloudflare tunnel")
        return False


def start_scanner() -> bool:
    """Start scanner daemon if not running."""
    if is_process_running("scanner.py --daemon"):
        print("? Scanner already running")
        return True
    
    print("? Starting scanner...")
    subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "scanner.py"), "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(1)
    
    if is_process_running("scanner.py"):
        print("? Scanner started")
        return True
    else:
        print("? Failed to start scanner")
        return False


def start_poster() -> bool:
    """Start poster daemon if not running."""
    if is_process_running("poster.py --daemon"):
        print("? Poster already running")
        return True
    
    print("? Starting poster...")
    subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "poster.py"), "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(1)
    
    if is_process_running("poster.py"):
        print("? Poster started")
        return True
    else:
        print("? Failed to start poster")
        return False


# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------

def start_all():
    """Start all services."""
    print("=" * 50)
    print("BB-Poster-Automation")
    print("=" * 50)
    print()
    
    # Initialize database first
    print("? Initializing database...")
    subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "db.py"), "--init"],
        capture_output=True
    )
    print("? Database ready")
    print()
    
    # Start services
    success = True
    success = start_media_server() and success
    success = start_cloudflared() and success
    success = start_scanner() and success
    success = start_poster() and success
    
    print()
    if success:
        print("=" * 50)
        print("All services running!")
        print("=" * 50)
        print()
        print("View logs:    tail -f ~/BB-Poster-Automation/logs/all.log")
        print("Check status: python3 run.py --status")
        print("Stop all:     python3 run.py --stop")
        print()
    else:
        print("Some services failed to start. Check above for errors.")
        sys.exit(1)


def show_status():
    """Show status of all services."""
    print("=" * 50)
    print("BB-Poster-Automation Status")
    print("=" * 50)
    print()
    
    services = [
        ("Media Server", "media_server.py"),
        ("Cloudflare Tunnel", "cloudflared"),
        ("Scanner", "scanner.py"),
        ("Poster", "poster.py"),
    ]
    
    all_running = True
    for name, search in services:
        pids = get_process_pid(search)
        if pids:
            print(f"? {name}: Running (PID: {', '.join(map(str, pids))})")
        else:
            print(f"? {name}: Not running")
            all_running = False
    
    print()
    
    # Show queue stats
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "db.py"), "--stats"],
            capture_output=True,
            text=True
        )
        if "by_status" in result.stdout:
            print("Queue Stats:")
            import json
            lines = result.stdout.strip().split('\n')
            # Find the JSON part (skip "Database initialized" line)
            json_str = '\n'.join(lines[1:]) if len(lines) > 1 else lines[0]
            stats = json.loads(json_str)
            print(f"  Pending: {stats.get('by_status', {}).get('pending', 0)}")
            print(f"  Posted (24h): {stats.get('posted_24h', 0)}")
    except Exception:
        pass
    
    print()
    return all_running


def stop_all():
    """Stop all services."""
    print("=" * 50)
    print("Stopping BB-Poster-Automation")
    print("=" * 50)
    print()
    
    services = [
        ("Poster", "poster.py"),
        ("Scanner", "scanner.py"),
        ("Media Server", "media_server.py"),
        ("Cloudflare Tunnel", "cloudflared tunnel run projectmodel"),
    ]
    
    for name, search in services:
        if is_process_running(search):
            print(f"? Stopping {name}...")
            kill_process(search)
            time.sleep(0.5)
            if not is_process_running(search):
                print(f"? {name} stopped")
            else:
                print(f"? {name} may still be running")
        else:
            print(f"- {name} was not running")
    
    print()
    print("All services stopped.")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="BB-Poster-Automation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run.py           Start all services
  python3 run.py --status  Check what's running
  python3 run.py --stop    Stop all services
        """
    )
    parser.add_argument("--status", action="store_true", help="Show status of all services")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()
    
    os.chdir(PROJECT_ROOT)
    
    if args.status:
        show_status()
    elif args.stop:
        stop_all()
    else:
        start_all()


if __name__ == "__main__":
    main()