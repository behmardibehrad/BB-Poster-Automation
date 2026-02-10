#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Dashboard with Login & Comment Approval - BB-Poster-Automation
Fixed: Replaced emojis with Font Awesome icons for cross-browser compatibility
"""
import os, sys, json, sqlite3, subprocess, requests, secrets, random, shutil
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, make_response, send_from_directory

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")
PHOTOS_DIR = os.path.join(PROJECT_ROOT, "United_States", "Nyssa_Bloom", "Instagram", "Photos")
STORIES_DIR = os.path.join(PROJECT_ROOT, "United_States", "Nyssa_Bloom", "Instagram", "Stories")
TWITTER_PHOTOS_DIR = os.path.join(PROJECT_ROOT, "United_States", "Nyssa_Bloom", "Twitter", "Photos")
FB_GRAPH_API = "https://graph.facebook.com/v21.0"

# Twitter support
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ============== CHANGE THESE PASSWORDS ==============
ADMIN_PASSWORD = "ThisIsaBadPassword.2025!"
GUEST_PASSWORD = "NyssaGuest2025"  # Share this with guests (read-only access)
# ====================================================

COOKIE_NAME = "nyssa_auth"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days
TOKENS_FILE = os.path.join(PROJECT_ROOT, ".dashboard_tokens")

def generate_auth_token():
    return secrets.token_hex(32)

def load_tokens():
    """Load valid tokens from file - returns dict of token: role"""
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, 'r') as f:
                tokens = {}
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(':')
                        if len(parts) == 2:
                            tokens[parts[0]] = parts[1]  # token: role
                        else:
                            tokens[line] = 'admin'  # legacy tokens default to admin
                return tokens
    except:
        pass
    return {}

def save_tokens(tokens):
    """Save valid tokens to file - tokens is dict of token: role"""
    try:
        with open(TOKENS_FILE, 'w') as f:
            for token, role in tokens.items():
                f.write(f"{token}:{role}\n")
    except:
        pass

def add_token(token, role='admin'):
    """Add a new valid token with role"""
    tokens = load_tokens()
    tokens[token] = role
    # Keep only last 20 tokens to prevent unlimited growth
    if len(tokens) > 20:
        items = list(tokens.items())[-20:]
        tokens = dict(items)
    save_tokens(tokens)

def remove_token(token):
    """Remove a token (logout)"""
    tokens = load_tokens()
    tokens.pop(token, None)
    save_tokens(tokens)

def get_user_role():
    """Get the role of the current user (admin or guest)"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    tokens = load_tokens()
    return tokens.get(token)

def is_authenticated():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    return token in load_tokens()

def is_admin():
    """Check if current user is admin"""
    return get_user_role() == 'admin'

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def requires_admin(f):
    """Decorator for admin-only routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        if not is_admin():
            return redirect(url_for('dashboard', error='Admin access required'))
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# HTML TEMPLATES
# =============================================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Nyssa Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-box { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); width: 100%; max-width: 400px; text-align: center; }
        h1 { color: #e94560; margin-bottom: 10px; font-size: 1.8rem; }
        .subtitle { color: #888; margin-bottom: 30px; }
        input[type="password"] { width: 100%; padding: 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; background: rgba(255,255,255,0.05); color: #fff; font-size: 1rem; margin-bottom: 20px; }
        input[type="password"]:focus { outline: none; border-color: #e94560; }
        button { width: 100%; padding: 15px; background: #e94560; border: none; border-radius: 10px; color: #fff; font-size: 1rem; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #d63850; }
        .error { color: #f87171; margin-bottom: 20px; padding: 10px; background: rgba(248,113,113,0.1); border-radius: 8px; }
        .remember { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 20px; color: #888; }
        .remember input { width: auto; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1><i class="fas fa-camera-retro"></i> Nyssa Dashboard</h1>
        <p class="subtitle">Enter password to continue</p>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="Password" autofocus>
            <div class="remember">
                <input type="checkbox" name="remember" id="remember" checked>
                <label for="remember">Remember this device (30 days)</label>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Nyssa Bloom Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 10px; font-size: 2rem; color: #e94560; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 0.9rem; }
        .nav { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; flex-wrap: wrap; }
        .nav a { color: #e94560; text-decoration: none; padding: 10px 20px; border: 1px solid #e94560; border-radius: 8px; transition: all 0.2s; font-size: 0.9rem; }
        .nav a:hover, .nav a.active { background: #e94560; color: #fff; }
        .nav a .badge { background: #f87171; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-left: 5px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .card h2 { font-size: 1rem; color: #e94560; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }
        .card-full { grid-column: 1 / -1; }
        .stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #888; }
        .stat-value { font-weight: bold; }
        .status-ok { color: #4ade80; }
        .status-error { color: #f87171; }
        .status-pending { color: #60a5fa; }
        .status-skipped { color: #fbbf24; }
        .big-number { font-size: 2.5rem; font-weight: bold; color: #e94560; }
        .big-label { color: #888; font-size: 0.85rem; }
        .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; text-align: center; }
        .profile-card { display: flex; align-items: center; gap: 20px; }
        .profile-avatar { width: 80px; height: 80px; border-radius: 50%; border: 3px solid #e94560; object-fit: cover; }
        .profile-info { flex: 1; }
        .profile-name { font-size: 1.3rem; font-weight: bold; margin-bottom: 5px; }
        .profile-username { color: #e94560; font-size: 0.9rem; margin-bottom: 8px; }
        .profile-bio { color: #aaa; font-size: 0.85rem; line-height: 1.4; white-space: pre-line; }
        .profile-stats { display: flex; gap: 30px; margin-top: 15px; }
        .profile-stat { text-align: center; }
        .profile-stat-num { font-size: 1.5rem; font-weight: bold; color: #fff; }
        .profile-stat-label { color: #888; font-size: 0.75rem; text-transform: uppercase; }
        .engagement-value { font-size: 2rem; font-weight: bold; color: #4ade80; }
        .engagement-label { color: #888; font-size: 0.8rem; }
        .engagement-detail { color: #aaa; font-size: 0.85rem; margin-top: 5px; }
        .posts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .post-card { background: rgba(255,255,255,0.03); border-radius: 10px; overflow: hidden; transition: transform 0.2s; }
        .post-card:hover { transform: scale(1.02); }
        .post-image { width: 100%; aspect-ratio: 1; object-fit: cover; background: #222; }
        .post-image-placeholder { width: 100%; aspect-ratio: 1; background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%); display: flex; align-items: center; justify-content: center; color: #666; font-size: 2rem; }
        .post-stats { padding: 12px; display: flex; justify-content: space-between; align-items: center; }
        .post-stat { display: flex; align-items: center; gap: 5px; color: #aaa; font-size: 0.85rem; }
        .post-type { font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; background: rgba(233, 69, 96, 0.2); color: #e94560; }
        .activity-item { padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px; font-size: 0.85rem; }
        .activity-time { color: #888; font-size: 0.75rem; }
        .reply-text { color: #4ade80; margin: 5px 0; font-style: italic; }
        .service-status { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
        .service-dot { width: 10px; height: 10px; border-radius: 50%; }
        .service-dot.running { background: #4ade80; }
        .service-dot.stopped { background: #f87171; }
        .comment-list { max-height: 500px; overflow-y: auto; }
        .comment-item { padding: 15px; background: rgba(255,255,255,0.03); border-radius: 10px; margin-bottom: 10px; border-left: 3px solid #e94560; }
        .comment-item.sent { border-left-color: #4ade80; }
        .comment-item.pending { border-left-color: #60a5fa; }
        .comment-item.skipped { border-left-color: #fbbf24; }
        .comment-item.failed { border-left-color: #f87171; }
        .comment-item.rejected { border-left-color: #f87171; }
        .comment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .comment-username { font-weight: bold; color: #e94560; }
        .comment-status { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; }
        .comment-status.sent { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .comment-status.pending { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
        .comment-status.skipped { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .comment-status.failed { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .comment-status.rejected { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .comment-text { color: #ccc; margin-bottom: 8px; }
        .comment-reply { color: #4ade80; font-style: italic; padding-left: 15px; border-left: 2px solid #4ade80; margin-top: 8px; }
        .comment-time { color: #666; font-size: 0.75rem; margin-top: 8px; }
        .comment-stats { display: flex; gap: 20px; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
        .comment-stat { text-align: center; }
        .comment-stat-num { font-size: 1.5rem; font-weight: bold; color: #e94560; }
        .comment-stat-label { font-size: 0.75rem; color: #888; }
        .refresh-note { text-align: center; color: #666; font-size: 0.8rem; margin-top: 20px; }
        .error-note { color: #f87171; font-size: 0.8rem; text-align: center; padding: 20px; }
        .logout-btn { position: fixed; top: 20px; right: 20px; background: rgba(255,255,255,0.1); border: none; color: #888; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-size: 0.8rem; text-decoration: none; }
        .logout-btn:hover { background: rgba(255,255,255,0.2); color: #fff; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: #e94560; border-radius: 4px; }
    </style>
</head>
<body>
    <a href="/logout" class="logout-btn">Logout</a>
    <div class="container">
        <h1><i class="fas fa-camera-retro"></i> Nyssa Bloom Dashboard</h1>
        <p class="subtitle">Last updated: {{ current_time }} | {% if user_role == 'admin' %}<span style="background: #4ade80; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;"><i class="fas fa-crown"></i> Admin</span>{% else %}<span style="background: #60a5fa; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;"><i class="fas fa-eye"></i> Guest (Read-Only)</span>{% endif %}</p>
        
        <div class="nav">
            <a href="/" class="active"><i class="fas fa-chart-line"></i> Dashboard</a>
            <a href="/posts"><i class="fas fa-images"></i> Post Review</a>
            <a href="/approve"><i class="fas fa-check-circle"></i> Approve Replies {% if pending_count > 0 %}<span class="badge">{{ pending_count }}</span>{% endif %}</a>
            <a href="/moderation"><i class="fas fa-shield-alt"></i> Moderation</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2><i class="fab fa-instagram"></i> Instagram Profile</h2>
                {% if profile %}
                <div class="profile-card">
                    <img src="{{ profile.avatar }}" alt="Profile" class="profile-avatar" onerror="this.style.display='none'">
                    <div class="profile-info">
                        <div class="profile-name">{{ profile.name }}</div>
                        <div class="profile-username">@{{ profile.username }}</div>
                        <div class="profile-bio" style="font-size: 0.75rem; max-height: 60px; overflow: hidden;">{{ profile.bio }}</div>
                    </div>
                </div>
                <div class="profile-stats">
                    <div class="profile-stat"><div class="profile-stat-num">{{ profile.followers }}</div><div class="profile-stat-label">Followers</div></div>
                    <div class="profile-stat"><div class="profile-stat-num">{{ profile.following }}</div><div class="profile-stat-label">Following</div></div>
                    <div class="profile-stat"><div class="profile-stat-num">{{ profile.posts }}</div><div class="profile-stat-label">Posts</div></div>
                </div>
                {% else %}<div class="error-note">Could not load Instagram profile</div>{% endif %}
            </div>
            <div class="card">
                <h2><i class="fab fa-x-twitter"></i> Twitter/X Profile</h2>
                {% if twitter_profile %}
                <div class="profile-card">
                    <img src="{{ twitter_profile.avatar }}" alt="Profile" class="profile-avatar" style="border-color: #1da1f2;" onerror="this.style.display='none'">
                    <div class="profile-info">
                        <div class="profile-name">{{ twitter_profile.name }}</div>
                        <div class="profile-username" style="color: #1da1f2;">@{{ twitter_profile.username }}</div>
                        <div class="profile-bio" style="font-size: 0.75rem; max-height: 60px; overflow: hidden;">{{ twitter_profile.bio }}</div>
                    </div>
                </div>
                <div class="profile-stats">
                    <div class="profile-stat"><div class="profile-stat-num">{{ twitter_profile.followers }}</div><div class="profile-stat-label">Followers</div></div>
                    <div class="profile-stat"><div class="profile-stat-num">{{ twitter_profile.following }}</div><div class="profile-stat-label">Following</div></div>
                    <div class="profile-stat"><div class="profile-stat-num">{{ twitter_profile.posts }}</div><div class="profile-stat-label">Posts</div></div>
                </div>
                {% else %}<div class="error-note">Could not load Twitter profile</div>{% endif %}
            </div>
            <div class="card">
                <h2><i class="fas fa-chart-pie"></i> Engagement</h2>
                {% if engagement %}
                <div style="text-align: center; padding: 10px 0;">
                    <div class="engagement-value">{{ engagement.rate }}%</div>
                    <div class="engagement-label">Engagement Rate</div>
                    <div class="engagement-detail">Based on last {{ engagement.post_count }} posts</div>
                </div>
                <div class="stat-row"><span class="stat-label">Avg Likes</span><span class="stat-value status-ok">{{ engagement.avg_likes }}</span></div>
                <div class="stat-row"><span class="stat-label">Avg Comments</span><span class="stat-value status-pending">{{ engagement.avg_comments }}</span></div>
                <div class="stat-row"><span class="stat-label">Total Likes</span><span class="stat-value">{{ engagement.total_likes }}</span></div>
                <div class="stat-row"><span class="stat-label">Total Comments</span><span class="stat-value">{{ engagement.total_comments }}</span></div>
                {% else %}<div class="error-note">Could not calculate engagement</div>{% endif %}
            </div>
        </div>
        <div class="grid">
            <div class="card">
                <h2><i class="fas fa-cogs"></i> Services Status</h2>
                {% for service in services %}
                <div class="service-status">
                    <div class="service-dot {{ 'running' if service.running else 'stopped' }}"></div>
                    <span>{{ service.name }}</span>
                    <span style="margin-left: auto; color: #888; font-size: 0.8rem;">{{ 'PID ' + service.pid|string if service.running else 'Stopped' }}</span>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <h2><i class="fas fa-images"></i> Posts Overview</h2>
                <div class="stat-grid">
                    <div><div class="big-number">{{ posts_today }}</div><div class="big-label">Posted Today</div></div>
                    <div><div class="big-number status-pending">{{ posts_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number status-error">{{ posts_failed }}</div><div class="big-label">Failed</div></div>
                </div>
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 8px;">
                        <span style="color: #888;"><i class="fab fa-instagram" style="color: #e94560;"></i> Instagram</span>
                        <span><span class="status-ok">{{ ig_today }}</span> / <span class="status-pending">{{ ig_pending }}</span> / <span class="status-error">{{ ig_failed }}</span></span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                        <span style="color: #888;"><i class="fab fa-x-twitter" style="color: #1da1f2;"></i> Twitter/X</span>
                        <span><span class="status-ok">{{ twitter_today }}</span> / <span class="status-pending">{{ twitter_pending }}</span> / <span class="status-error">{{ twitter_failed }}</span></span>
                    </div>
                </div>
            </div>
            <div class="card">
                <h2><i class="fas fa-comments"></i> Comment Responder</h2>
                <div class="stat-grid">
                    <div><div class="big-number status-ok">{{ comments_sent }}</div><div class="big-label">Sent</div></div>
                    <div><div class="big-number status-pending">{{ comments_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number">{{ comments_total }}</div><div class="big-label">Total</div></div>
                </div>
            </div>
        </div>
        <div class="grid">
            <div class="card card-full">
                <h2><i class="fas fa-th"></i> Recent Instagram Posts</h2>
                {% if ig_posts %}
                <div class="posts-grid">
                    {% for post in ig_posts %}
                    <a href="{{ post.permalink }}" target="_blank" style="text-decoration: none; color: inherit;">
                        <div class="post-card">
                            {% if post.thumbnail %}<img src="{{ post.thumbnail }}" alt="Post" class="post-image">{% else %}<div class="post-image-placeholder">{{ post.media_type[0] if post.media_type else '?' }}</div>{% endif %}
                            <div class="post-stats">
                                <div style="display: flex; gap: 15px;"><div class="post-stat"><i class="fas fa-heart"></i> {{ post.likes }}</div><div class="post-stat"><i class="fas fa-comment"></i> {{ post.comments }}</div></div>
                                <span class="post-type">{{ post.media_type }}</span>
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
                {% else %}<div class="error-note">No posts found</div>{% endif %}
            </div>
        </div>
        <div class="grid">
            <div class="card card-full">
                <h2><i class="fab fa-x-twitter"></i> Recent Twitter Posts</h2>
                {% if twitter_posts %}
                <div class="posts-grid">
                    {% for tweet in twitter_posts %}
                    <a href="{{ tweet.permalink }}" target="_blank" style="text-decoration: none; color: inherit;">
                        <div class="post-card">
                            {% if tweet.thumbnail %}<img src="{{ tweet.thumbnail }}" alt="Tweet" class="post-image">{% else %}<div class="post-image-placeholder" style="font-size: 0.8rem; padding: 10px; text-align: left; align-items: flex-start;">{{ tweet.text }}</div>{% endif %}
                            <div class="post-stats">
                                <div style="display: flex; gap: 12px;">
                                    <div class="post-stat"><i class="fas fa-heart"></i> {{ tweet.likes }}</div>
                                    <div class="post-stat"><i class="fas fa-retweet"></i> {{ tweet.retweets }}</div>
                                    <div class="post-stat"><i class="fas fa-reply"></i> {{ tweet.replies }}</div>
                                </div>
                                <span class="post-type" style="background: rgba(29, 161, 242, 0.2); color: #1da1f2;">TWEET</span>
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
                {% else %}<div class="error-note">No tweets found or Twitter API not configured</div>{% endif %}
            </div>
        </div>
        <div class="grid">
            <div class="card">
                <h2><i class="fas fa-list-ol"></i> Queue Statistics</h2>
                <div class="stat-row"><span class="stat-label">Photos Posted (24h)</span><span class="stat-value">{{ photos_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Stories Posted (24h)</span><span class="stat-value">{{ stories_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Total in Queue</span><span class="stat-value status-pending">{{ total_queued }}</span></div>
                <div class="stat-row"><span class="stat-label">Posts This Week</span><span class="stat-value">{{ posts_week }}</span></div>
            </div>
            <div class="card">
                <h2><i class="fas fa-clock"></i> Pending Replies</h2>
                {% if pending_replies %}{% for reply in pending_replies %}
                <div class="activity-item">
                    <div><strong>@{{ reply.username }}</strong>: "{{ reply.comment[:40] }}..."</div>
                    <div class="reply-text"><i class="fas fa-reply"></i> {{ reply.reply[:50] }}...</div>
                    <div class="activity-time">Scheduled: {{ reply.scheduled }} <a href="/approve" style="color: #e94560; margin-left: 10px;">Review <i class="fas fa-arrow-right"></i></a></div>
                </div>
                {% endfor %}{% else %}<div style="color: #888; text-align: center; padding: 20px;">No pending replies</div>{% endif %}
            </div>
            <div class="card">
                <h2><i class="fas fa-history"></i> Recent Activity</h2>
                {% if recent_activity %}{% for activity in recent_activity %}
                <div class="activity-item">
                    <div><span class="{{ 'status-ok' if activity.status == 'posted' else 'status-error' }}">{{ activity.status|upper }}</span> - {{ activity.content_type }}</div>
                    <div class="activity-time">{{ activity.time }}</div>
                </div>
                {% endfor %}{% else %}<div style="color: #888; text-align: center; padding: 20px;">No recent activity</div>{% endif %}
            </div>
        </div>
        <div class="grid">
            <div class="card card-full">
                <h2><i class="fas fa-scroll"></i> Comment History (Latest {{ comment_history|length }} of {{ total_comments }})</h2>
                <div class="comment-stats">
                    <div class="comment-stat"><div class="comment-stat-num status-ok">{{ stats_sent }}</div><div class="comment-stat-label">Sent</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-pending">{{ stats_pending }}</div><div class="comment-stat-label">Pending</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-skipped">{{ stats_skipped }}</div><div class="comment-stat-label">Skipped</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-error">{{ stats_failed }}</div><div class="comment-stat-label">Failed</div></div>
                </div>
                <div class="comment-list">
                    {% for comment in comment_history %}
                    <div class="comment-item {{ comment.status }}">
                        <div class="comment-header"><span class="comment-username">@{{ comment.username }}</span><span class="comment-status {{ comment.status }}">{{ comment.status }}</span></div>
                        <div class="comment-text">"{{ comment.text }}"</div>
                        {% if comment.reply %}<div class="comment-reply">{{ comment.reply }}</div>{% endif %}
                        <div class="comment-time">{{ comment.created }}{% if comment.replied_time %} | Replied: {{ comment.replied_time }}{% endif %}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        <p class="refresh-note">Auto-refreshes every 60 seconds</p>
    </div>
</body>
</html>
"""

APPROVE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>Approve Replies - Nyssa Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 10px; font-size: 2rem; color: #e94560; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 0.9rem; }
        .nav { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }
        .nav a { color: #e94560; text-decoration: none; padding: 10px 20px; border: 1px solid #e94560; border-radius: 8px; transition: all 0.2s; }
        .nav a:hover, .nav a.active { background: #e94560; color: #fff; }
        .message { padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .message.success { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .message.error { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .pending-card { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 25px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1); border-left: 4px solid #60a5fa; }
        .pending-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        .pending-user { font-size: 1.2rem; font-weight: bold; color: #e94560; }
        .pending-time { color: #888; font-size: 0.85rem; }
        .countdown { background: rgba(96, 165, 250, 0.2); color: #60a5fa; padding: 5px 12px; border-radius: 15px; font-size: 0.85rem; }
        .original-comment { background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; margin-bottom: 15px; }
        .original-label { color: #888; font-size: 0.8rem; margin-bottom: 8px; text-transform: uppercase; }
        .original-text { color: #fff; font-size: 1rem; line-height: 1.5; }
        .reply-section { margin-bottom: 20px; }
        .reply-label { color: #4ade80; font-size: 0.8rem; margin-bottom: 8px; text-transform: uppercase; display: flex; align-items: center; gap: 10px; }
        .reply-label span { background: rgba(74, 222, 128, 0.2); padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; }
        .reply-textarea { width: 100%; padding: 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; background: rgba(255,255,255,0.05); color: #fff; font-size: 1rem; min-height: 100px; resize: vertical; font-family: inherit; }
        .reply-textarea:focus { outline: none; border-color: #4ade80; }
        .actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { padding: 12px 24px; border-radius: 8px; text-decoration: none; font-size: 0.9rem; cursor: pointer; border: none; transition: all 0.2s; display: inline-flex; align-items: center; gap: 8px; }
        .btn-approve { background: #4ade80; color: #000; }
        .btn-approve:hover { background: #22c55e; }
        .btn-reject { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .btn-reject:hover { background: rgba(248, 113, 113, 0.4); }
        .btn-edit { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
        .btn-edit:hover { background: rgba(96, 165, 250, 0.4); }
        .empty { text-align: center; color: #888; padding: 60px 20px; background: rgba(255,255,255,0.05); border-radius: 15px; }
        .empty-icon { font-size: 4rem; margin-bottom: 20px; }
        .info-box { background: rgba(96, 165, 250, 0.1); border: 1px solid rgba(96, 165, 250, 0.3); border-radius: 10px; padding: 15px; margin-bottom: 30px; text-align: center; color: #60a5fa; font-size: 0.9rem; }
        .thread-indicator { color: #fbbf24; font-size: 0.8rem; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1><i class="fas fa-check-circle"></i> Approve Replies</h1>
        <p class="subtitle">Review and approve Nyssa's AI-generated responses</p>
        
        <div class="nav">
            <a href="/"><i class="fas fa-chart-line"></i> Dashboard</a>
            <a href="/posts"><i class="fas fa-images"></i> Post Review</a>
            <a href="/approve" class="active"><i class="fas fa-check-circle"></i> Approve Replies</a>
            <a href="/moderation"><i class="fas fa-shield-alt"></i> Moderation</a>
        </div>
        
        {% if message %}<div class="message success"><i class="fas fa-check"></i> {{ message }}</div>{% endif %}
        {% if error %}<div class="message error"><i class="fas fa-times"></i> {{ error }}</div>{% endif %}
        
        <div class="info-box">
            <i class="fas fa-info-circle"></i> Replies will be sent automatically at their scheduled time if not reviewed. Edit or reject to change.
        </div>
        
        {% if pending_replies %}
            {% for reply in pending_replies %}
            <div class="pending-card">
                <div class="pending-header">
                    <div class="pending-user">@{{ reply.username }}</div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span class="pending-time">Scheduled: {{ reply.scheduled_time }}</span>
                        <span class="countdown"><i class="fas fa-clock"></i> {{ reply.time_left }}</span>
                    </div>
                </div>
                
                {% if reply.is_thread %}<div class="thread-indicator"><i class="fas fa-code-branch"></i> Thread Reply (responding to their reply)</div>{% endif %}
                
                <div class="original-comment">
                    <div class="original-label">Their Comment</div>
                    <div class="original-text">"{{ reply.comment }}"</div>
                </div>
                
                <form action="/approve/update/{{ reply.id }}" method="POST">
                    <div class="reply-section">
                        <div class="reply-label">Nyssa's Response <span>AI Generated</span></div>
                        <textarea name="reply_text" class="reply-textarea" {% if user_role != 'admin' %}disabled{% endif %}>{{ reply.reply }}</textarea>
                    </div>
                    
                    {% if user_role == 'admin' %}
                    <div class="actions">
                        <button type="submit" name="action" value="approve" class="btn btn-approve"><i class="fas fa-check"></i> Approve & Send Now</button>
                        <button type="submit" name="action" value="edit" class="btn btn-edit"><i class="fas fa-save"></i> Save Edit</button>
                        <button type="submit" name="action" value="reject" class="btn btn-reject"><i class="fas fa-times"></i> Reject</button>
                    </div>
                    {% else %}
                    <div class="actions">
                        <span style="color: #888; font-size: 0.9rem;"><i class="fas fa-lock"></i> View-only access - admin required for actions</span>
                    </div>
                    {% endif %}
                </form>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty">
                <div class="empty-icon"><i class="fas fa-check-double"></i></div>
                <h3>All caught up!</h3>
                <p>No pending replies to review</p>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

MODERATION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comment Moderation - Nyssa Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 10px; font-size: 2rem; color: #e94560; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 0.9rem; }
        .nav { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }
        .nav a { color: #e94560; text-decoration: none; padding: 10px 20px; border: 1px solid #e94560; border-radius: 8px; transition: all 0.2s; }
        .nav a:hover, .nav a.active { background: #e94560; color: #fff; }
        .message { padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .message.success { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .message.error { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .comment-card { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.1); }
        .comment-card.hidden { opacity: 0.5; border-left: 3px solid #fbbf24; }
        .comment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
        .comment-username { font-weight: bold; color: #e94560; font-size: 1.1rem; }
        .comment-meta { color: #888; font-size: 0.8rem; }
        .comment-text { color: #ddd; font-size: 1rem; line-height: 1.5; margin-bottom: 15px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 8px; }
        .comment-post { color: #888; font-size: 0.85rem; margin-bottom: 15px; }
        .comment-post a { color: #60a5fa; }
        .comment-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; transition: all 0.2s; cursor: pointer; border: none; }
        .btn-hide { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .btn-hide:hover { background: rgba(251, 191, 36, 0.4); }
        .btn-unhide { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .btn-unhide:hover { background: rgba(74, 222, 128, 0.4); }
        .btn-delete { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .btn-delete:hover { background: rgba(248, 113, 113, 0.4); }
        .hidden-badge { background: rgba(251, 191, 36, 0.2); color: #fbbf24; padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; }
        .likes { color: #e94560; font-size: 0.85rem; }
        .empty { text-align: center; color: #888; padding: 50px; }
        .stats { display: flex; justify-content: center; gap: 30px; margin-bottom: 30px; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 15px; flex-wrap: wrap; }
        .stat { text-align: center; }
        .stat-num { font-size: 2rem; font-weight: bold; color: #e94560; }
        .stat-label { color: #888; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1><i class="fas fa-shield-alt"></i> Comment Moderation</h1>
        <p class="subtitle">Manage comments on your posts</p>
        
        <div class="nav">
            <a href="/"><i class="fas fa-chart-line"></i> Dashboard</a>
            <a href="/posts"><i class="fas fa-images"></i> Post Review</a>
            <a href="/approve"><i class="fas fa-check-circle"></i> Approve Replies</a>
            <a href="/moderation" class="active"><i class="fas fa-shield-alt"></i> Moderation</a>
        </div>
        
        {% if message %}<div class="message success"><i class="fas fa-check"></i> {{ message }}</div>{% endif %}
        {% if error %}<div class="message error"><i class="fas fa-times"></i> {{ error }}</div>{% endif %}
        
        <div class="stats">
            <div class="stat"><div class="stat-num">{{ comments|length }}</div><div class="stat-label">Total Comments</div></div>
            <div class="stat"><div class="stat-num">{{ comments|selectattr('hidden')|list|length }}</div><div class="stat-label">Hidden</div></div>
            <div class="stat"><div class="stat-num">{{ comments|rejectattr('hidden')|list|length }}</div><div class="stat-label">Visible</div></div>
        </div>
        
        {% if comments %}
            {% for comment in comments %}
            <div class="comment-card {{ 'hidden' if comment.hidden else '' }}">
                <div class="comment-header">
                    <div>
                        <span class="comment-username">@{{ comment.username }}</span>
                        {% if comment.hidden %}<span class="hidden-badge">HIDDEN</span>{% endif %}
                    </div>
                    <div class="comment-meta">
                        <span class="likes"><i class="fas fa-heart"></i> {{ comment.likes }}</span> • 
                        {{ comment.timestamp[:10] if comment.timestamp else 'Unknown' }}
                    </div>
                </div>
                <div class="comment-text">"{{ comment.text }}"</div>
                <div class="comment-post">On post: <a href="{{ comment.post_url }}" target="_blank">{{ comment.post_caption }}</a></div>
                {% if user_role == 'admin' %}
                <div class="comment-actions">
                    {% if comment.hidden %}
                    <a href="/moderation/unhide/{{ comment.id }}" class="btn btn-unhide"><i class="fas fa-eye"></i> Unhide</a>
                    {% else %}
                    <a href="/moderation/hide/{{ comment.id }}" class="btn btn-hide"><i class="fas fa-eye-slash"></i> Hide</a>
                    {% endif %}
                    <a href="/moderation/delete/{{ comment.id }}" class="btn btn-delete" onclick="return confirm('Delete this comment permanently?')"><i class="fas fa-trash"></i> Delete</a>
                </div>
                {% else %}
                <div class="comment-actions">
                    <span style="color: #888; font-size: 0.85rem;"><i class="fas fa-lock"></i> View-only</span>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="empty">No comments found on recent posts</div>
        {% endif %}
    </div>
</body>
</html>
"""

POST_REVIEW_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Post Review - Nyssa Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 10px; font-size: 2rem; color: #e94560; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 0.9rem; }
        .nav { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; flex-wrap: wrap; }
        .nav a { color: #e94560; text-decoration: none; padding: 10px 20px; border: 1px solid #e94560; border-radius: 8px; transition: all 0.2s; font-size: 0.9rem; }
        .nav a:hover, .nav a.active { background: #e94560; color: #fff; }
        
        .day-section { margin-bottom: 25px; }
        .date-header { background: rgba(233, 69, 96, 0.1); border: 1px solid rgba(233, 69, 96, 0.3); border-radius: 12px; padding: 12px 20px; margin-bottom: 15px; display: flex; align-items: center; gap: 12px; }
        .date-header.tomorrow { background: rgba(139, 92, 246, 0.1); border-color: rgba(139, 92, 246, 0.3); }
        .date-header i { color: #e94560; font-size: 1.2rem; }
        .date-header.tomorrow i { color: #8b5cf6; }
        .date-header h2 { font-size: 1.2rem; font-weight: 600; }
        .date-header .badge { background: #e94560; color: #fff; padding: 3px 10px; border-radius: 15px; font-size: 0.7rem; font-weight: bold; margin-left: auto; }
        .date-header.tomorrow .badge { background: #8b5cf6; }
        
        .content-section { margin-bottom: 15px; }
        .content-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding-left: 5px; }
        .content-header i { font-size: 1rem; }
        .content-header.photos i { color: #e94560; }
        .content-header.stories i { color: #06b6d4; }
        .content-header h3 { font-size: 0.95rem; font-weight: 600; color: #ccc; }
        
        .posts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        @media (max-width: 900px) { .posts-grid { grid-template-columns: 1fr; } }
        
        .post-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; overflow: hidden; }
        .post-card.story { border-color: rgba(6, 182, 212, 0.3); }
        .card-header { background: rgba(255,255,255,0.03); padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; gap: 8px; }
        .card-header.am { border-left: 3px solid #fbbf24; }
        .card-header.pm { border-left: 3px solid #8b5cf6; }
        .card-header.am i { color: #fbbf24; }
        .card-header.pm i { color: #8b5cf6; }
        .card-header h4 { font-size: 0.85rem; font-weight: 600; flex: 1; }
        .time-badge { background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 5px; font-size: 0.7rem; color: #4ade80; font-weight: 600; }
        
        .card-body { padding: 12px; }
        .post-content { display: flex; gap: 12px; }
        
        .post-image, .post-video { width: 100px; height: 100px; border-radius: 8px; object-fit: cover; background: #222; flex-shrink: 0; }
        .post-image.story, .post-video.story { border: 2px solid #06b6d4; }
        .post-video { cursor: pointer; }
        .video-container { position: relative; width: 100px; height: 100px; flex-shrink: 0; }
        .video-container .play-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 1.5rem; text-shadow: 0 0 10px rgba(0,0,0,0.8); pointer-events: none; }
        .post-image-placeholder { width: 100px; height: 100px; border-radius: 8px; background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%); display: flex; align-items: center; justify-content: center; flex-direction: column; color: #555; flex-shrink: 0; font-size: 0.7rem; }
        .post-image-placeholder i { font-size: 1.5rem; margin-bottom: 5px; }
        
        .post-details { flex: 1; min-width: 0; display: flex; flex-direction: column; }
        .caption-container { flex: 1; margin-bottom: 8px; }
        .caption-text { color: #ccc; font-size: 0.8rem; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; }
        .caption-text.collapsed { max-height: 60px; overflow: hidden; position: relative; }
        .caption-text.collapsed::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 20px; background: linear-gradient(transparent, rgba(26, 26, 46, 0.9)); }
        .expand-btn { color: #e94560; font-size: 0.7rem; cursor: pointer; margin-top: 4px; display: inline-block; }
        .expand-btn:hover { text-decoration: underline; }
        .status-badge { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 500; }
        .status-badge.pending { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
        .status-badge.posted { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
        .status-badge.failed { background: rgba(248, 113, 113, 0.15); color: #f87171; }
        
        .card-footer { padding: 8px 12px; background: rgba(0,0,0,0.2); display: flex; gap: 8px; }
        .btn-action { display: flex; align-items: center; justify-content: center; gap: 5px; flex: 1; padding: 6px 12px; border-radius: 5px; font-size: 0.75rem; font-weight: 500; cursor: pointer; transition: all 0.2s; text-decoration: none; border: none; }
        .btn-replace { background: rgba(233, 69, 96, 0.2); color: #e94560; border: 1px solid #e94560; }
        .btn-replace:hover { background: #e94560; color: #fff; }
        .btn-edit { background: rgba(96, 165, 250, 0.2); color: #60a5fa; border: 1px solid #60a5fa; }
        .btn-edit:hover { background: #60a5fa; color: #fff; }
        .btn-action.disabled { opacity: 0.5; pointer-events: none; }
        
        /* Edit Caption Modal */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
        .modal-overlay.active { display: flex; }
        .modal { background: #1a1a2e; border-radius: 15px; padding: 25px; max-width: 600px; width: 100%; max-height: 90vh; overflow-y: auto; border: 1px solid rgba(255,255,255,0.1); }
        .modal h3 { color: #e94560; margin-bottom: 15px; font-size: 1.2rem; }
        .modal-image { width: 100%; max-width: 200px; border-radius: 10px; margin-bottom: 15px; }
        .modal textarea { width: 100%; min-height: 150px; padding: 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; background: rgba(255,255,255,0.05); color: #fff; font-size: 0.95rem; font-family: inherit; resize: vertical; margin-bottom: 15px; }
        .modal textarea:focus { outline: none; border-color: #e94560; }
        .modal-actions { display: flex; gap: 10px; }
        .modal .btn { padding: 12px 24px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; border: none; transition: all 0.2s; }
        .modal .btn-save { background: #4ade80; color: #000; }
        .modal .btn-save:hover { background: #22c55e; }
        .modal .btn-cancel { background: rgba(255,255,255,0.1); color: #888; }
        .modal .btn-cancel:hover { background: rgba(255,255,255,0.2); color: #fff; }
        .modal-info { font-size: 0.8rem; color: #888; margin-bottom: 15px; }
        
        .message { padding: 12px 18px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; font-size: 0.9rem; }
        .message.success { background: rgba(74, 222, 128, 0.15); border: 1px solid rgba(74, 222, 128, 0.3); color: #4ade80; }
        .message.error { background: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.3); color: #f87171; }
        
        .swap-info { background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); color: #a78bfa; padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; margin-top: 15px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1><i class="fas fa-camera-retro"></i> Nyssa Dashboard</h1>
        <p class="subtitle">Post Review & Management</p>
        
        <nav class="nav">
            <a href="/"><i class="fas fa-chart-line"></i> Dashboard</a>
            <a href="/posts" class="active"><i class="fas fa-images"></i> Post Review</a>
            <a href="/approve"><i class="fas fa-check-circle"></i> Approve</a>
            <a href="/moderation"><i class="fas fa-shield-alt"></i> Moderation</a>
        </nav>
        
        {% if message %}<div class="message success"><i class="fas fa-check-circle"></i> {{ message }}</div>{% endif %}
        {% if error %}<div class="message error"><i class="fas fa-exclamation-circle"></i> {{ error }}</div>{% endif %}
        
        <!-- TODAY -->
        <div class="day-section">
            <div class="date-header">
                <i class="fas fa-calendar-day"></i>
                <h2>{{ today_data.date_display }}</h2>
                <span class="badge">TODAY</span>
            </div>
            
            <!-- Today's Photos -->
            <div class="content-section">
                <div class="content-header photos">
                    <i class="fas fa-image"></i>
                    <h3>Photos</h3>
                </div>
                <div class="posts-grid">
                    {% for slot, label, icon in [('am', 'Morning', 'sun'), ('pm', 'Evening', 'moon')] %}
                    <div class="post-card">
                        <div class="card-header {{ slot }}">
                            <i class="fas fa-{{ icon }}"></i>
                            <h4>{{ label }}</h4>
                            {% if today_data.photos[slot] and today_data.photos[slot].exists %}
                            <span class="time-badge">{{ today_data.photos[slot].scheduled_time }}</span>
                            {% endif %}
                        </div>
                        {% if today_data.photos[slot] and today_data.photos[slot].exists %}
                        <div class="card-body">
                            <div class="post-content">
                                <img src="/media/Photos/{{ today_data.photos[slot].filename }}" class="post-image" alt="{{ slot }} Photo">
                                <div class="post-details">
                                    <div class="caption-container">
                                        <div class="caption-text collapsed" id="caption-today-photos-{{ slot }}">{{ today_data.photos[slot].caption }}</div>
                                        {% if today_data.photos[slot].caption|length > 100 %}
                                        <span class="expand-btn" data-target="caption-today-photos-{{ slot }}">Show more</span>
                                        {% endif %}
                                    </div>
                                    <span class="status-badge {{ today_data.photos[slot].status }}"><i class="fas fa-{% if today_data.photos[slot].status == 'posted' %}check-circle{% elif today_data.photos[slot].status == 'failed' %}times-circle{% else %}clock{% endif %}"></i> {{ today_data.photos[slot].status|capitalize }}</span>
                                </div>
                            </div>
                        </div>
                        {% if user_role == 'admin' %}
                        <div class="card-footer">
                            <a href="/posts/replace/Photos/{{ today_data.date_str }}/{{ slot }}" class="btn-action btn-replace {% if today_data.photos[slot].status == 'posted' %}disabled{% endif %}"><i class="fas fa-sync-alt"></i> Replace</a>
                            <button class="btn-action btn-edit {% if today_data.photos[slot].status == 'posted' %}disabled{% endif %}" data-content-type="Photos" data-date-str="{{ today_data.date_str }}" data-slot="{{ slot }}" data-filename="{{ today_data.photos[slot].filename }}" data-caption-id="caption-today-photos-{{ slot }}"><i class="fas fa-edit"></i> Edit</button>
                        </div>
                        {% endif %}
                        {% else %}
                        <div class="card-body">
                            <div class="post-image-placeholder"><i class="fas fa-image"></i><span>No photo</span></div>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <!-- Today's Stories -->
            <div class="content-section">
                <div class="content-header stories">
                    <i class="fas fa-circle-notch"></i>
                    <h3>Stories</h3>
                </div>
                <div class="posts-grid">
                    {% for slot, label, icon in [('am', 'Morning', 'sun'), ('pm', 'Evening', 'moon')] %}
                    <div class="post-card story">
                        <div class="card-header {{ slot }}">
                            <i class="fas fa-{{ icon }}"></i>
                            <h4>{{ label }}</h4>
                            {% if today_data.stories[slot] and today_data.stories[slot].exists %}
                            <span class="time-badge">{{ today_data.stories[slot].scheduled_time }}</span>
                            {% endif %}
                        </div>
                        {% if today_data.stories[slot] and today_data.stories[slot].exists %}
                        <div class="card-body">
                            <div class="post-content">
                                {% if today_data.stories[slot].is_video %}
                                <div class="video-container">
                                    <video src="/media/Stories/{{ today_data.stories[slot].filename }}" class="post-video story" muted></video>
                                    <i class="fas fa-play-circle play-icon"></i>
                                </div>
                                {% else %}
                                <img src="/media/Stories/{{ today_data.stories[slot].filename }}" class="post-image story" alt="{{ slot }} Story">
                                {% endif %}
                                <div class="post-details">
                                    <div class="caption-text">{{ today_data.stories[slot].caption_preview or '(No caption)' }}</div>
                                    <span class="status-badge {{ today_data.stories[slot].status }}"><i class="fas fa-{% if today_data.stories[slot].status == 'posted' %}check-circle{% elif today_data.stories[slot].status == 'failed' %}times-circle{% else %}clock{% endif %}"></i> {{ today_data.stories[slot].status|capitalize }}</span>
                                </div>
                            </div>
                        </div>
                        {% if user_role == 'admin' %}
                        <div class="card-footer">
                            <a href="/posts/replace/Stories/{{ today_data.date_str }}/{{ slot }}" class="btn-action btn-replace {% if today_data.stories[slot].status == 'posted' %}disabled{% endif %}"><i class="fas fa-sync-alt"></i> Replace</a>
                        </div>
                        {% endif %}
                        {% else %}
                        <div class="card-body">
                            <div class="post-image-placeholder"><i class="fas fa-circle-notch"></i><span>No story</span></div>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <!-- TOMORROW -->
        <div class="day-section">
            <div class="date-header tomorrow">
                <i class="fas fa-calendar-alt"></i>
                <h2>{{ tomorrow_data.date_display }}</h2>
                <span class="badge">TOMORROW</span>
            </div>
            
            <!-- Tomorrow's Photos -->
            <div class="content-section">
                <div class="content-header photos">
                    <i class="fas fa-image"></i>
                    <h3>Photos</h3>
                </div>
                <div class="posts-grid">
                    {% for slot, label, icon in [('am', 'Morning', 'sun'), ('pm', 'Evening', 'moon')] %}
                    <div class="post-card">
                        <div class="card-header {{ slot }}">
                            <i class="fas fa-{{ icon }}"></i>
                            <h4>{{ label }}</h4>
                            {% if tomorrow_data.photos[slot] and tomorrow_data.photos[slot].exists %}
                            <span class="time-badge">{{ tomorrow_data.photos[slot].scheduled_time }}</span>
                            {% endif %}
                        </div>
                        {% if tomorrow_data.photos[slot] and tomorrow_data.photos[slot].exists %}
                        <div class="card-body">
                            <div class="post-content">
                                <img src="/media/Photos/{{ tomorrow_data.photos[slot].filename }}" class="post-image" alt="{{ slot }} Photo">
                                <div class="post-details">
                                    <div class="caption-container">
                                        <div class="caption-text collapsed" id="caption-tomorrow-photos-{{ slot }}">{{ tomorrow_data.photos[slot].caption }}</div>
                                        {% if tomorrow_data.photos[slot].caption|length > 100 %}
                                        <span class="expand-btn" data-target="caption-tomorrow-photos-{{ slot }}">Show more</span>
                                        {% endif %}
                                    </div>
                                    <span class="status-badge {{ tomorrow_data.photos[slot].status }}"><i class="fas fa-{% if tomorrow_data.photos[slot].status == 'posted' %}check-circle{% elif tomorrow_data.photos[slot].status == 'failed' %}times-circle{% else %}clock{% endif %}"></i> {{ tomorrow_data.photos[slot].status|capitalize }}</span>
                                </div>
                            </div>
                        </div>
                        {% if user_role == 'admin' %}
                        <div class="card-footer">
                            <a href="/posts/replace/Photos/{{ tomorrow_data.date_str }}/{{ slot }}" class="btn-action btn-replace"><i class="fas fa-sync-alt"></i> Replace</a>
                            <button class="btn-action btn-edit" data-content-type="Photos" data-date-str="{{ tomorrow_data.date_str }}" data-slot="{{ slot }}" data-filename="{{ tomorrow_data.photos[slot].filename }}" data-caption-id="caption-tomorrow-photos-{{ slot }}"><i class="fas fa-edit"></i> Edit</button>
                        </div>
                        {% endif %}
                        {% else %}
                        <div class="card-body">
                            <div class="post-image-placeholder"><i class="fas fa-image"></i><span>No photo</span></div>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <!-- Tomorrow's Stories -->
            <div class="content-section">
                <div class="content-header stories">
                    <i class="fas fa-circle-notch"></i>
                    <h3>Stories</h3>
                </div>
                <div class="posts-grid">
                    {% for slot, label, icon in [('am', 'Morning', 'sun'), ('pm', 'Evening', 'moon')] %}
                    <div class="post-card story">
                        <div class="card-header {{ slot }}">
                            <i class="fas fa-{{ icon }}"></i>
                            <h4>{{ label }}</h4>
                            {% if tomorrow_data.stories[slot] and tomorrow_data.stories[slot].exists %}
                            <span class="time-badge">{{ tomorrow_data.stories[slot].scheduled_time }}</span>
                            {% endif %}
                        </div>
                        {% if tomorrow_data.stories[slot] and tomorrow_data.stories[slot].exists %}
                        <div class="card-body">
                            <div class="post-content">
                                {% if tomorrow_data.stories[slot].is_video %}
                                <div class="video-container">
                                    <video src="/media/Stories/{{ tomorrow_data.stories[slot].filename }}" class="post-video story" muted></video>
                                    <i class="fas fa-play-circle play-icon"></i>
                                </div>
                                {% else %}
                                <img src="/media/Stories/{{ tomorrow_data.stories[slot].filename }}" class="post-image story" alt="{{ slot }} Story">
                                {% endif %}
                                <div class="post-details">
                                    <div class="caption-text">{{ tomorrow_data.stories[slot].caption_preview or '(No caption)' }}</div>
                                    <span class="status-badge {{ tomorrow_data.stories[slot].status }}"><i class="fas fa-{% if tomorrow_data.stories[slot].status == 'posted' %}check-circle{% elif tomorrow_data.stories[slot].status == 'failed' %}times-circle{% else %}clock{% endif %}"></i> {{ tomorrow_data.stories[slot].status|capitalize }}</span>
                                </div>
                            </div>
                        </div>
                        {% if user_role == 'admin' %}
                        <div class="card-footer">
                            <a href="/posts/replace/Stories/{{ tomorrow_data.date_str }}/{{ slot }}" class="btn-action btn-replace {% if tomorrow_data.stories[slot].status == 'posted' %}disabled{% endif %}"><i class="fas fa-sync-alt"></i> Replace</a>
                        </div>
                        {% endif %}
                        {% else %}
                        <div class="card-body">
                            <div class="post-image-placeholder"><i class="fas fa-circle-notch"></i><span>No story</span></div>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        {% if last_swap %}<div class="swap-info"><i class="fas fa-info-circle"></i> {{ last_swap }}</div>{% endif %}
    </div>
    
    <!-- Edit Caption Modal -->
    <div class="modal-overlay" id="editModal">
        <div class="modal">
            <h3><i class="fas fa-edit"></i> Edit Caption</h3>
            <img id="modalImage" class="modal-image" src="" alt="Post preview">
            <div class="modal-info">
                <i class="fas fa-info-circle"></i> Edit the caption below. Changes will update both the database and the .txt file.
            </div>
            <form action="/posts/edit-caption" method="POST">
                <input type="hidden" name="content_type" id="modalContentType">
                <input type="hidden" name="date_str" id="modalDateStr">
                <input type="hidden" name="slot" id="modalSlot">
                <textarea name="caption" id="modalCaption" placeholder="Enter caption..."></textarea>
                <div class="modal-actions">
                    <button type="submit" class="btn btn-save"><i class="fas fa-save"></i> Save Caption</button>
                    <button type="button" class="btn btn-cancel" onclick="closeEditModal()"><i class="fas fa-times"></i> Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        // Expand/collapse captions
        document.querySelectorAll('.expand-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var targetId = this.getAttribute('data-target');
                var el = document.getElementById(targetId);
                if (el.classList.contains('collapsed')) {
                    el.classList.remove('collapsed');
                    this.textContent = 'Show less';
                } else {
                    el.classList.add('collapsed');
                    this.textContent = 'Show more';
                }
            });
        });
        
        // Edit buttons
        document.querySelectorAll('.btn-edit').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var contentType = this.getAttribute('data-content-type');
                var dateStr = this.getAttribute('data-date-str');
                var slot = this.getAttribute('data-slot');
                var filename = this.getAttribute('data-filename');
                var captionId = this.getAttribute('data-caption-id');
                var captionEl = document.getElementById(captionId);
                var caption = captionEl ? captionEl.textContent : '';
                
                document.getElementById('modalContentType').value = contentType;
                document.getElementById('modalDateStr').value = dateStr;
                document.getElementById('modalSlot').value = slot;
                document.getElementById('modalCaption').value = caption;
                document.getElementById('modalImage').src = '/media/' + contentType + '/' + filename;
                document.getElementById('editModal').classList.add('active');
            });
        });
        
        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }
        
        // Close modal on click outside
        document.getElementById('editModal').addEventListener('click', function(e) {
            if (e.target === this) closeEditModal();
        });
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeEditModal();
        });
    </script>
</body>
</html>
"""

# =============================================================================
# POST REVIEW HELPER FUNCTIONS
# =============================================================================

def parse_filename_date(filename):
    """Parse MM_DD_YYYY_am/pm from filename"""
    try:
        base = os.path.splitext(filename)[0]
        parts = base.split('_')
        if len(parts) >= 4:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            slot = parts[3].lower()
            return datetime(year, month, day), slot
    except:
        pass
    return None, None

def get_next_posting_day():
    """Get the next day that has posts scheduled"""
    today = datetime.now().date()
    
    for days_ahead in range(0, 60):
        check_date = today + timedelta(days=days_ahead)
        date_str = check_date.strftime("%m_%d_%Y")
        
        am_file = os.path.join(PHOTOS_DIR, f"{date_str}_am.jpg")
        pm_file = os.path.join(PHOTOS_DIR, f"{date_str}_pm.jpg")
        
        if os.path.exists(am_file) or os.path.exists(pm_file):
            if days_ahead == 0:
                try:
                    con = sqlite3.connect(DB_FILE)
                    today_start = datetime.combine(today, datetime.min.time())
                    cur = con.execute("SELECT COUNT(*) FROM media_files WHERE posted_at >= ? AND status = 'posted'", 
                                     (int(today_start.timestamp()),))
                    posted_today = cur.fetchone()[0]
                    con.close()
                    if posted_today >= 2:
                        continue
                except:
                    pass
            return check_date
    
    return today + timedelta(days=1)

def get_content_for_day(target_date, content_dir, content_type):
    """Get AM and PM content info for a specific date and content type"""
    date_str = target_date.strftime("%m_%d_%Y")
    
    result = {
        'am': None,
        'pm': None
    }
    
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    for slot in ['am', 'pm']:
        # Check for both image and video extensions
        file_path = None
        is_video = False
        for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov']:
            test_path = os.path.join(content_dir, f"{date_str}_{slot}{ext}")
            if os.path.exists(test_path):
                file_path = test_path
                is_video = ext.lower() in video_extensions
                break
        
        if file_path:
            filename = os.path.basename(file_path)
            
            # Get caption, scheduled time and status from DATABASE (same source as poster!)
            caption = ""
            scheduled_time = "9:00 AM" if slot == 'am' else "7:00 PM"
            post_status = "pending"
            
            try:
                con = sqlite3.connect(DB_FILE)
                file_pattern = f"%{date_str}_{slot}%"
                row = con.execute(
                    "SELECT scheduled_for, status, caption FROM media_files WHERE file_path LIKE ? AND content_type = ? LIMIT 1",
                    (file_pattern, content_type)
                ).fetchone()
                if row:
                    if row[0]:
                        sched_dt = datetime.fromtimestamp(row[0])
                        scheduled_time = sched_dt.strftime("%I:%M %p").lstrip('0')
                    post_status = row[1] or "pending"
                    caption = row[2] or ""
                con.close()
            except:
                pass
            
            # Fallback: if no caption in DB, read from file
            if not caption:
                caption_path = os.path.join(content_dir, f"{date_str}_{slot}.txt")
                if os.path.exists(caption_path):
                    try:
                        with open(caption_path, 'r', encoding='utf-8') as f:
                            caption = f.read().strip()
                    except:
                        caption = "(No caption)"
            
            result[slot] = {
                'file_path': file_path,
                'filename': filename,
                'caption': caption,
                'caption_preview': caption[:100] + '...' if len(caption) > 100 else caption,
                'exists': True,
                'is_video': is_video,
                'scheduled_time': scheduled_time,
                'status': post_status,
                'content_type': content_type
            }
        else:
            result[slot] = {'exists': False}
    
    return result

def get_post_for_day(target_date):
    """Get Photos and Stories for a specific date"""
    date_str = target_date.strftime("%m_%d_%Y")
    
    result = {
        'date': target_date,
        'date_display': target_date.strftime("%A, %B %d"),
        'date_str': date_str,
        'photos': get_content_for_day(target_date, PHOTOS_DIR, 'Photos'),
        'stories': get_content_for_day(target_date, STORIES_DIR, 'Stories'),
    }
    
    return result

def get_future_posts(content_type, after_date, exclude_date_str=None, exclude_slot=None):
    """Get list of all future posts for swapping"""
    future_posts = []
    
    content_dir = STORIES_DIR if content_type == 'Stories' else PHOTOS_DIR
    
    if not os.path.exists(content_dir):
        return future_posts
    
    for filename in os.listdir(content_dir):
        if not any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov']):
            continue
        
        file_date, slot = parse_filename_date(filename)
        if file_date is None:
            continue
        
        if file_date.date() <= after_date:
            continue
        
        date_str = file_date.strftime("%m_%d_%Y")
        if exclude_date_str and exclude_slot:
            if date_str == exclude_date_str and slot == exclude_slot:
                continue
        
        future_posts.append({
            'date': file_date,
            'date_str': date_str,
            'slot': slot,
            'filename': filename
        })
    
    return future_posts

def swap_posts(content_type, date1_str, slot1, date2_str, slot2):
    """Swap two posts (image and caption)"""
    try:
        content_dir = STORIES_DIR if content_type == 'Stories' else PHOTOS_DIR
        
        # Find the actual files (could be different extensions)
        img1 = img2 = None
        for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov']:
            test1 = os.path.join(content_dir, f"{date1_str}_{slot1}{ext}")
            test2 = os.path.join(content_dir, f"{date2_str}_{slot2}{ext}")
            if os.path.exists(test1):
                img1 = test1
            if os.path.exists(test2):
                img2 = test2
        
        if not img1 or not img2:
            return False, "Could not find files to swap"
        
        ext1 = os.path.splitext(img1)[1]
        ext2 = os.path.splitext(img2)[1]
        
        cap1 = os.path.join(content_dir, f"{date1_str}_{slot1}.txt")
        cap2 = os.path.join(content_dir, f"{date2_str}_{slot2}.txt")
        
        temp_img = os.path.join(content_dir, f"_temp_{ext1}")
        temp_cap = os.path.join(content_dir, "_temp_.txt")
        
        # Swap images (handling different extensions)
        shutil.move(img1, temp_img)
        new_img1 = os.path.join(content_dir, f"{date1_str}_{slot1}{ext2}")
        new_img2 = os.path.join(content_dir, f"{date2_str}_{slot2}{ext1}")
        shutil.move(img2, new_img1)
        shutil.move(temp_img, new_img2)
        
        # Swap captions
        if os.path.exists(cap1) and os.path.exists(cap2):
            shutil.move(cap1, temp_cap)
            shutil.move(cap2, cap1)
            shutil.move(temp_cap, cap2)
        elif os.path.exists(cap1):
            shutil.move(cap1, cap2)
        elif os.path.exists(cap2):
            shutil.move(cap2, cap1)
        
        return True, f"Swapped with {date2_str} {slot2.upper()}"
    except Exception as e:
        return False, str(e)

def replace_post_random(content_type, date_str, slot):
    """Replace a post with a random future post"""
    parts = date_str.split('_')
    target_date = datetime(int(parts[2]), int(parts[0]), int(parts[1])).date()
    
    future_posts = get_future_posts(content_type, target_date, date_str, slot)
    
    if not future_posts:
        return False, f"No future {content_type.lower()} available"
    
    chosen = random.choice(future_posts)
    return swap_posts(content_type, date_str, slot, chosen['date_str'], chosen['slot'])

def update_caption(content_type, date_str, slot, new_caption):
    """Update caption in both database and .txt file"""
    try:
        # Determine content directory
        content_dir = STORIES_DIR if content_type == 'Stories' else PHOTOS_DIR
        
        # Update .txt file
        caption_path = os.path.join(content_dir, f"{date_str}_{slot}.txt")
        with open(caption_path, 'w', encoding='utf-8') as f:
            f.write(new_caption)
        
        # Update database
        con = sqlite3.connect(DB_FILE)
        file_pattern = f"%{date_str}_{slot}%"
        con.execute(
            "UPDATE media_files SET caption = ? WHERE file_path LIKE ? AND content_type = ?",
            (new_caption, file_pattern, content_type)
        )
        con.commit()
        con.close()
        
        return True, "Caption updated successfully"
    except Exception as e:
        return False, str(e)

# =============================================================================
# INSTAGRAM API FUNCTIONS
# =============================================================================

def get_instagram_credentials():
    try:
        con = sqlite3.connect(DB_FILE)
        row = con.execute("SELECT ig_user_id, access_token FROM credentials WHERE platform = 'Instagram' AND is_active = 1 LIMIT 1").fetchone()
        con.close()
        return (row[0], row[1]) if row else (None, None)
    except:
        return None, None

def get_instagram_profile():
    ig_user_id, token = get_instagram_credentials()
    if not ig_user_id: return None
    try:
        resp = requests.get(f"{FB_GRAPH_API}/{ig_user_id}", params={'fields': 'username,name,biography,followers_count,follows_count,media_count,profile_picture_url', 'access_token': token}, timeout=10)
        data = resp.json()
        if 'error' not in data:
            return {'username': data.get('username', 'N/A'), 'name': data.get('name', 'N/A'), 'bio': data.get('biography', ''), 'followers': data.get('followers_count', 0), 'following': data.get('follows_count', 0), 'posts': data.get('media_count', 0), 'avatar': data.get('profile_picture_url', '')}
    except: pass
    return None

def get_instagram_posts(limit=8):
    ig_user_id, token = get_instagram_credentials()
    if not ig_user_id: return []
    try:
        resp = requests.get(f"{FB_GRAPH_API}/{ig_user_id}/media", params={'fields': 'id,caption,media_type,timestamp,like_count,comments_count,permalink,thumbnail_url,media_url', 'limit': limit, 'access_token': token}, timeout=10)
        data = resp.json()
        posts = []
        for post in data.get('data', []):
            posts.append({'id': post.get('id'), 'media_type': post.get('media_type', 'IMAGE'), 'likes': post.get('like_count', 0), 'comments': post.get('comments_count', 0), 'permalink': post.get('permalink', '#'), 'thumbnail': post.get('thumbnail_url') or post.get('media_url', '')})
        return posts
    except: return []

# =============================================================================
# TWITTER API FUNCTIONS (with caching to avoid rate limits)
# =============================================================================

# Twitter cache - stores data in memory and file to survive restarts
TWITTER_CACHE_FILE = os.path.join(PROJECT_ROOT, ".twitter_cache.json")
TWITTER_CACHE_TTL = 21600  # 15 minutes - Twitter free tier limit
_twitter_cache = {"profile": None, "tweets": None, "profile_time": 0, "tweets_time": 0}

def load_twitter_cache():
    """Load Twitter cache from file"""
    global _twitter_cache
    try:
        if os.path.exists(TWITTER_CACHE_FILE):
            with open(TWITTER_CACHE_FILE, 'r') as f:
                _twitter_cache = json.load(f)
    except:
        pass

def save_twitter_cache():
    """Save Twitter cache to file"""
    try:
        with open(TWITTER_CACHE_FILE, 'w') as f:
            json.dump(_twitter_cache, f)
    except:
        pass

# Load cache on startup
load_twitter_cache()

def get_twitter_credentials():
    """Get Twitter API credentials from database"""
    try:
        con = sqlite3.connect(DB_FILE)
        row = con.execute("""
            SELECT twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret 
            FROM credentials WHERE platform = 'Twitter' AND is_active = 1 LIMIT 1
        """).fetchone()
        con.close()
        if row and all(row):
            return {'api_key': row[0], 'api_secret': row[1], 'access_token': row[2], 'access_secret': row[3]}
    except:
        pass
    return None

def get_twitter_profile():
    """Get Twitter profile information using tweepy (with caching)"""
    global _twitter_cache
    
    # Check cache first
    now = datetime.now().timestamp()
    if _twitter_cache.get("profile") and (now - _twitter_cache.get("profile_time", 0)) < TWITTER_CACHE_TTL:
        return _twitter_cache["profile"]
    
    if not TWEEPY_AVAILABLE:
        return _twitter_cache.get("profile")  # Return stale cache if available
    creds = get_twitter_credentials()
    if not creds:
        return _twitter_cache.get("profile")
    
    try:
        client = tweepy.Client(
            consumer_key=creds['api_key'],
            consumer_secret=creds['api_secret'],
            access_token=creds['access_token'],
            access_token_secret=creds['access_secret']
        )
        # Get authenticated user info
        user = client.get_me(user_fields=['profile_image_url', 'description', 'public_metrics', 'username', 'name'])
        if user and user.data:
            u = user.data
            metrics = u.public_metrics or {}
            profile = {
                'username': u.username or 'N/A',
                'name': u.name or 'N/A',
                'bio': u.description or '',
                'followers': metrics.get('followers_count', 0),
                'following': metrics.get('following_count', 0),
                'posts': metrics.get('tweet_count', 0),
                'avatar': (u.profile_image_url or '').replace('_normal', '_400x400')
            }
            # Update cache
            _twitter_cache["profile"] = profile
            _twitter_cache["profile_time"] = now
            save_twitter_cache()
            return profile
    except Exception as e:
        print(f"Twitter profile error: {e}")
        # Return stale cache on error
        if _twitter_cache.get("profile"):
            return _twitter_cache["profile"]
    return None

def get_twitter_recent_tweets(limit=8):
    """Get recent tweets from the authenticated user (with caching)"""
    global _twitter_cache
    
    # Check cache first
    now = datetime.now().timestamp()
    if _twitter_cache.get("tweets") and (now - _twitter_cache.get("tweets_time", 0)) < TWITTER_CACHE_TTL:
        return _twitter_cache["tweets"]
    
    if not TWEEPY_AVAILABLE:
        return _twitter_cache.get("tweets", [])
    creds = get_twitter_credentials()
    if not creds:
        return _twitter_cache.get("tweets", [])
    
    try:
        client = tweepy.Client(
            consumer_key=creds['api_key'],
            consumer_secret=creds['api_secret'],
            access_token=creds['access_token'],
            access_token_secret=creds['access_secret']
        )
        # Get user ID first
        user = client.get_me()
        if not user or not user.data:
            return _twitter_cache.get("tweets", [])
        user_id = user.data.id
        
        # Get recent tweets with metrics
        tweets = client.get_users_tweets(
            user_id, 
            max_results=min(limit, 100),
            tweet_fields=['created_at', 'public_metrics', 'attachments'],
            media_fields=['preview_image_url', 'url'],
            expansions=['attachments.media_keys']
        )
        
        if not tweets or not tweets.data:
            return _twitter_cache.get("tweets", [])
        
        # Build media lookup
        media_lookup = {}
        if tweets.includes and 'media' in tweets.includes:
            for m in tweets.includes['media']:
                media_lookup[m.media_key] = m.url or m.preview_image_url or ''
        
        result = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics or {}
            # Get first media URL if available
            thumbnail = ''
            if tweet.attachments and 'media_keys' in tweet.attachments:
                for mk in tweet.attachments['media_keys']:
                    if mk in media_lookup:
                        thumbnail = media_lookup[mk]
                        break
            
            result.append({
                'id': str(tweet.id),  # Convert to string for JSON
                'text': tweet.text[:100] + '...' if len(tweet.text) > 100 else tweet.text,
                'likes': metrics.get('like_count', 0),
                'retweets': metrics.get('retweet_count', 0),
                'replies': metrics.get('reply_count', 0),
                'permalink': f"https://twitter.com/i/status/{tweet.id}",
                'thumbnail': thumbnail
            })
        
        # Update cache
        _twitter_cache["tweets"] = result
        _twitter_cache["tweets_time"] = now
        save_twitter_cache()
        return result
    except Exception as e:
        print(f"Twitter tweets error: {e}")
        # Return stale cache on error
        if _twitter_cache.get("tweets"):
            return _twitter_cache["tweets"]
    return []


def calculate_engagement(posts, followers):
    if not posts or followers == 0: return None
    total_likes, total_comments = sum(p['likes'] for p in posts), sum(p['comments'] for p in posts)
    post_count = len(posts)
    return {'rate': round(((total_likes + total_comments) / post_count) / followers * 100, 2), 'avg_likes': round(total_likes / post_count, 1), 'avg_comments': round(total_comments / post_count, 1), 'total_likes': total_likes, 'total_comments': total_comments, 'post_count': post_count}

def get_all_comments(limit_posts=5):
    ig_user_id, token = get_instagram_credentials()
    if not ig_user_id: return []
    comments = []
    try:
        resp = requests.get(f"{FB_GRAPH_API}/{ig_user_id}/media", params={'fields': 'id,caption,permalink,timestamp', 'limit': limit_posts, 'access_token': token}, timeout=10)
        posts = resp.json().get('data', [])
        for post in posts:
            resp2 = requests.get(f"{FB_GRAPH_API}/{post['id']}/comments", params={'fields': 'id,text,username,timestamp,hidden,like_count', 'limit': 50, 'access_token': token}, timeout=10)
            for c in resp2.json().get('data', []):
                comments.append({
                    'id': c.get('id'), 'text': c.get('text', ''), 'username': c.get('username', 'unknown'),
                    'timestamp': c.get('timestamp', ''), 'hidden': c.get('hidden', False), 'likes': c.get('like_count', 0),
                    'post_id': post['id'], 'post_caption': (post.get('caption', '')[:30] + '...') if post.get('caption') else 'No caption',
                    'post_url': post.get('permalink', '#')
                })
    except Exception as e: print(f"Error fetching comments: {e}")
    comments.sort(key=lambda x: x['timestamp'], reverse=True)
    return comments[:50]

def hide_comment(comment_id, hide=True):
    _, token = get_instagram_credentials()
    if not token: return False, "No credentials"
    try:
        resp = requests.post(f"{FB_GRAPH_API}/{comment_id}", params={'hide': str(hide).lower(), 'access_token': token}, timeout=10)
        data = resp.json()
        return (True, "Comment hidden" if hide else "Comment unhidden") if data.get('success') else (False, data.get('error', {}).get('message', 'Unknown error'))
    except Exception as e: return False, str(e)

def delete_comment(comment_id):
    _, token = get_instagram_credentials()
    if not token: return False, "No credentials"
    try:
        resp = requests.delete(f"{FB_GRAPH_API}/{comment_id}", params={'access_token': token}, timeout=10)
        data = resp.json()
        return (True, "Comment deleted") if data.get('success') else (False, data.get('error', {}).get('message', 'Unknown error'))
    except Exception as e: return False, str(e)

def send_comment_reply(comment_id, message):
    _, token = get_instagram_credentials()
    if not token: return False, "No credentials"
    try:
        resp = requests.post(f"{FB_GRAPH_API}/{comment_id}/replies", params={'message': message, 'access_token': token}, timeout=10)
        data = resp.json()
        return (True, data.get('id')) if 'id' in data else (False, data.get('error', {}).get('message', 'Unknown error'))
    except Exception as e: return False, str(e)

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_service_status():
    services = [("Media Server", "media_server.py"), ("Cloudflare Tunnel", "cloudflared"), ("Scanner", "scanner.py"), ("Poster", "poster.py"), ("Comment Responder", "comment_responder.py"), ("Dashboard", "dashboard.py")]
    result = []
    for name, search in services:
        try:
            proc = subprocess.run(["pgrep", "-f", search], capture_output=True, text=True)
            pids = [p for p in proc.stdout.strip().split('\n') if p]
            result.append({"name": name, "running": len(pids) > 0, "pid": pids[0] if pids else None})
        except:
            result.append({"name": name, "running": False, "pid": None})
    return result

def get_post_stats():
    stats = {
        "posts_today": 0, "posts_pending": 0, "posts_failed": 0, 
        "photos_24h": 0, "stories_24h": 0, "total_queued": 0, "posts_week": 0,
        # Platform breakdown
        "ig_today": 0, "ig_pending": 0, "ig_failed": 0,
        "twitter_today": 0, "twitter_pending": 0, "twitter_failed": 0
    }
    try:
        con = sqlite3.connect(DB_FILE)
        now = int(datetime.now().timestamp())
        day_ago, week_ago = now - 86400, now - 604800
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
        
        # Overall stats
        stats["posts_today"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?", (today_start,)).fetchone()[0]
        stats["posts_pending"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'pending'").fetchone()[0]
        stats["posts_failed"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'failed'").fetchone()[0]
        stats["photos_24h"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Photos'", (day_ago,)).fetchone()[0]
        stats["stories_24h"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Stories'", (day_ago,)).fetchone()[0]
        stats["total_queued"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status IN ('pending', 'posting')").fetchone()[0]
        stats["posts_week"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?", (week_ago,)).fetchone()[0]
        
        # Instagram breakdown
        stats["ig_today"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND platform = 'Instagram'", (today_start,)).fetchone()[0]
        stats["ig_pending"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'pending' AND platform = 'Instagram'").fetchone()[0]
        stats["ig_failed"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'failed' AND platform = 'Instagram'").fetchone()[0]
        
        # Twitter breakdown
        stats["twitter_today"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND platform = 'Twitter'", (today_start,)).fetchone()[0]
        stats["twitter_pending"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'pending' AND platform = 'Twitter'").fetchone()[0]
        stats["twitter_failed"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'failed' AND platform = 'Twitter'").fetchone()[0]
        
        con.close()
    except Exception as e:
        print(f"Error: {e}")
    return stats

def get_comment_stats():
    stats = {"comments_sent": 0, "comments_pending": 0, "comments_total": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        stats["comments_sent"] = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'sent'").fetchone()[0]
        stats["comments_pending"] = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'pending'").fetchone()[0]
        stats["comments_total"] = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        con.close()
    except:
        pass
    return stats

def get_pending_replies():
    replies = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("SELECT username, comment_text, reply_text, scheduled_at FROM comment_replies WHERE status = 'pending' ORDER BY scheduled_at ASC LIMIT 5").fetchall()
        for row in rows:
            replies.append({"username": row[0], "comment": row[1], "reply": row[2] or "No reply generated", "scheduled": datetime.fromtimestamp(row[3]).strftime("%H:%M:%S") if row[3] else "N/A"})
        con.close()
    except:
        pass
    return replies

def get_recent_activity():
    activity = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("SELECT content_type, file_path, status, posted_at, created_at FROM media_files WHERE status IN ('posted', 'failed') ORDER BY COALESCE(posted_at, created_at) DESC LIMIT 10").fetchall()
        for row in rows:
            timestamp = row[3] or row[4]
            activity.append({"content_type": row[0], "filename": os.path.basename(row[1]), "status": row[2], "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp else "N/A"})
        con.close()
    except:
        pass
    return activity

def get_comment_history(limit=30):
    history = []
    total = 0
    stats = {"sent": 0, "pending": 0, "skipped": 0, "failed": 0, "rejected": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        total = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        rows = con.execute("SELECT status, COUNT(*) FROM comment_replies GROUP BY status").fetchall()
        for row in rows:
            if row[0] in stats:
                stats[row[0]] = row[1]
        rows = con.execute("SELECT username, comment_text, reply_text, status, created_at, replied_at FROM comment_replies ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        for row in rows:
            created = datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d %H:%M") if row[4] else "N/A"
            replied = datetime.fromtimestamp(row[5]).strftime("%H:%M:%S") if row[5] else None
            history.append({"username": row[0], "text": row[1], "reply": row[2], "status": row[3], "created": created, "replied_time": replied})
        con.close()
    except Exception as e:
        print(f"Error getting comment history: {e}")
    return history, total, stats

def get_pending_count():
    try:
        con = sqlite3.connect(DB_FILE)
        count = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'pending'").fetchone()[0]
        con.close()
        return count
    except:
        return 0

def get_pending_replies_for_approval():
    replies = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("""
            SELECT id, username, comment_text, reply_text, scheduled_at, parent_comment_id 
            FROM comment_replies 
            WHERE status = 'pending' 
            ORDER BY scheduled_at ASC 
            LIMIT 20
        """).fetchall()
        now = datetime.now()
        for row in rows:
            scheduled = datetime.fromtimestamp(row[4]) if row[4] else now
            time_diff = scheduled - now
            if time_diff.total_seconds() > 0:
                hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                time_left = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_left = "Soon"
            replies.append({
                "id": row[0], "username": row[1], "comment": row[2], "reply": row[3] or "",
                "scheduled_time": scheduled.strftime("%H:%M:%S"), "time_left": time_left,
                "is_thread": row[5] is not None
            })
        con.close()
    except Exception as e:
        print(f"Error: {e}")
    return replies

def update_reply_status(reply_id, status, new_text=None):
    try:
        con = sqlite3.connect(DB_FILE)
        if new_text:
            con.execute("UPDATE comment_replies SET status = ?, reply_text = ? WHERE id = ?", (status, new_text, reply_id))
        else:
            con.execute("UPDATE comment_replies SET status = ? WHERE id = ?", (status, reply_id))
        con.commit()
        con.close()
        return True
    except Exception as e:
        print(f"Error updating reply: {e}")
        return False

def get_reply_details(reply_id):
    try:
        con = sqlite3.connect(DB_FILE)
        row = con.execute("SELECT comment_id, reply_text FROM comment_replies WHERE id = ?", (reply_id,)).fetchone()
        con.close()
        return row if row else (None, None)
    except:
        return None, None

def mark_reply_sent(reply_id, nyssa_comment_id=None):
    try:
        con = sqlite3.connect(DB_FILE)
        con.execute("UPDATE comment_replies SET status = 'sent', replied_at = ?, nyssa_comment_id = ? WHERE id = ?", 
                   (int(datetime.now().timestamp()), nyssa_comment_id, reply_id))
        con.commit()
        con.close()
        return True
    except:
        return False

# =============================================================================
# ROUTES
# =============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        role = None
        
        if password == ADMIN_PASSWORD:
            role = 'admin'
        elif password == GUEST_PASSWORD:
            role = 'guest'
        
        if role:
            new_token = generate_auth_token()
            add_token(new_token, role)
            resp = make_response(redirect(url_for("dashboard")))
            max_age = COOKIE_MAX_AGE if request.form.get("remember") else None
            resp.set_cookie(COOKIE_NAME, new_token, max_age=max_age, httponly=True, samesite='Lax')
            return resp
        error = "Invalid password"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    token = request.cookies.get(COOKIE_NAME)
    if token:
        remove_token(token)
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie(COOKIE_NAME)
    return resp

@app.route("/")
@requires_auth
def dashboard():
    profile = get_instagram_profile()
    ig_posts = get_instagram_posts(8)
    engagement = calculate_engagement(ig_posts, profile['followers'] if profile else 0)
    comment_history, total_comments, history_stats = get_comment_history(30)
    post_stats, comment_stats = get_post_stats(), get_comment_stats()
    pending_count = get_pending_count()
    
    # Twitter data
    twitter_profile = get_twitter_profile()
    twitter_posts = get_twitter_recent_tweets(8)
    
    return render_template_string(DASHBOARD_HTML, 
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_role=get_user_role(),
        profile=profile, ig_posts=ig_posts, engagement=engagement, services=get_service_status(),
        posts_today=post_stats["posts_today"], posts_pending=post_stats["posts_pending"],
        posts_failed=post_stats["posts_failed"], photos_24h=post_stats["photos_24h"],
        stories_24h=post_stats["stories_24h"], total_queued=post_stats["total_queued"],
        posts_week=post_stats["posts_week"], comments_sent=comment_stats["comments_sent"],
        comments_pending=comment_stats["comments_pending"], comments_total=comment_stats["comments_total"],
        pending_replies=get_pending_replies(), recent_activity=get_recent_activity(),
        comment_history=comment_history, total_comments=total_comments,
        stats_sent=history_stats["sent"], stats_pending=history_stats["pending"],
        stats_skipped=history_stats["skipped"], stats_failed=history_stats.get("failed", 0) + history_stats.get("rejected", 0),
        pending_count=pending_count,
        # Twitter data
        twitter_profile=twitter_profile, twitter_posts=twitter_posts,
        ig_today=post_stats["ig_today"], ig_pending=post_stats["ig_pending"], ig_failed=post_stats["ig_failed"],
        twitter_today=post_stats["twitter_today"], twitter_pending=post_stats["twitter_pending"], twitter_failed=post_stats["twitter_failed"]
    )

@app.route("/approve")
@requires_auth
def approve():
    pending_replies = get_pending_replies_for_approval()
    return render_template_string(APPROVE_HTML,
        pending_replies=pending_replies,
        user_role=get_user_role(),
        message=request.args.get('message'),
        error=request.args.get('error'))

@app.route("/approve/update/<int:reply_id>", methods=["POST"])
@requires_admin
def approve_update(reply_id):
    action = request.form.get("action")
    new_text = request.form.get("reply_text", "").strip()
    
    if action == "approve":
        comment_id, _ = get_reply_details(reply_id)
        if comment_id and new_text:
            success, result = send_comment_reply(comment_id, new_text)
            if success:
                mark_reply_sent(reply_id, result)
                return redirect(url_for('approve', message=f"Reply sent successfully!"))
            else:
                return redirect(url_for('approve', error=f"Failed to send: {result}"))
        return redirect(url_for('approve', error="Missing comment ID or reply text"))
    
    elif action == "edit":
        if update_reply_status(reply_id, 'pending', new_text):
            return redirect(url_for('approve', message="Reply updated! Will send at scheduled time."))
        return redirect(url_for('approve', error="Failed to update reply"))
    
    elif action == "reject":
        if update_reply_status(reply_id, 'rejected'):
            return redirect(url_for('approve', message="Reply rejected and won't be sent"))
        return redirect(url_for('approve', error="Failed to reject reply"))
    
    return redirect(url_for('approve'))

@app.route("/moderation")
@requires_auth
def moderation():
    comments = get_all_comments(10)
    return render_template_string(MODERATION_HTML,
        comments=comments,
        user_role=get_user_role(),
        message=request.args.get('message'),
        error=request.args.get('error'))

@app.route("/moderation/hide/<comment_id>")
@requires_admin
def mod_hide(comment_id):
    success, msg = hide_comment(comment_id, hide=True)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/moderation/unhide/<comment_id>")
@requires_admin
def mod_unhide(comment_id):
    success, msg = hide_comment(comment_id, hide=False)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/moderation/delete/<comment_id>")
@requires_admin
def mod_delete(comment_id):
    success, msg = delete_comment(comment_id)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/api/stats")
@requires_auth
def api_stats():
    profile = get_instagram_profile()
    ig_posts = get_instagram_posts(8)
    return {'profile': profile, 'engagement': calculate_engagement(ig_posts, profile['followers'] if profile else 0), 'posts': get_post_stats(), 'comments': get_comment_stats()}

# =============================================================================
# POST REVIEW ROUTES
# =============================================================================

@app.route("/posts")
@requires_auth
def posts_review():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    today_data = get_post_for_day(today)
    tomorrow_data = get_post_for_day(tomorrow)
    
    return render_template_string(POST_REVIEW_HTML,
        today_data=today_data,
        tomorrow_data=tomorrow_data,
        user_role=get_user_role(),
        message=request.args.get('message'),
        error=request.args.get('error'),
        last_swap=request.args.get('swap'))

@app.route("/posts/replace/<content_type>/<date_str>/<slot>")
@requires_admin
def replace_post(content_type, date_str, slot):
    success, msg = replace_post_random(content_type, date_str, slot)
    if success:
        return redirect(url_for('posts_review', message=f"Replaced {slot.upper()} {content_type[:-1]}!", swap=msg))
    return redirect(url_for('posts_review', error=f"Failed: {msg}"))

@app.route("/posts/edit-caption", methods=["POST"])
@requires_admin
def edit_caption():
    content_type = request.form.get("content_type")
    date_str = request.form.get("date_str")
    slot = request.form.get("slot")
    new_caption = request.form.get("caption", "").strip()
    
    if not all([content_type, date_str, slot, new_caption]):
        return redirect(url_for('posts_review', error="Missing required fields"))
    
    success, msg = update_caption(content_type, date_str, slot, new_caption)
    if success:
        return redirect(url_for('posts_review', message=f"Caption updated for {date_str} {slot.upper()}!"))
    return redirect(url_for('posts_review', error=f"Failed to update caption: {msg}"))

@app.route("/media/<content_type>/<filename>")
@requires_auth
def serve_media(content_type, filename):
    if content_type == 'Stories':
        return send_from_directory(STORIES_DIR, filename)
    else:
        return send_from_directory(PHOTOS_DIR, filename)

if __name__ == "__main__":
    print("Dashboard with auth on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
