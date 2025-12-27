#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Dashboard with Login & Comment Approval - BB-Poster-Automation
"""
import os, sys, json, sqlite3, subprocess, requests, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, make_response

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")
FB_GRAPH_API = "https://graph.facebook.com/v21.0"

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ============== CHANGE THIS PASSWORD ==============
DASHBOARD_PASSWORD = "ThisIsaBadPassword.2025!" 
# ==================================================

COOKIE_NAME = "nyssa_auth"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days

def generate_auth_token():
    return secrets.token_hex(32)

AUTH_TOKEN = generate_auth_token()

def is_authenticated():
    return request.cookies.get(COOKIE_NAME) == AUTH_TOKEN

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
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
        <h1>?? Nyssa Dashboard</h1>
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
        <h1>?? Nyssa Bloom Dashboard</h1>
        <p class="subtitle">Last updated: {{ current_time }}</p>
        
        <div class="nav">
            <a href="/" class="active">?? Dashboard</a>
            <a href="/approve">? Approve Replies {% if pending_count > 0 %}<span class="badge">{{ pending_count }}</span>{% endif %}</a>
            <a href="/moderation">??? Moderation</a>
        </div>
        
        <div class="grid">
            <div class="card" style="grid-column: span 2;">
                <h2>?? Instagram Profile</h2>
                {% if profile %}
                <div class="profile-card">
                    <img src="{{ profile.avatar }}" alt="Profile" class="profile-avatar" onerror="this.style.display='none'">
                    <div class="profile-info">
                        <div class="profile-name">{{ profile.name }}</div>
                        <div class="profile-username">@{{ profile.username }}</div>
                        <div class="profile-bio">{{ profile.bio }}</div>
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
                <h2>?? Engagement</h2>
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
                <h2>?? Services Status</h2>
                {% for service in services %}
                <div class="service-status">
                    <div class="service-dot {{ 'running' if service.running else 'stopped' }}"></div>
                    <span>{{ service.name }}</span>
                    <span style="margin-left: auto; color: #888; font-size: 0.8rem;">{{ 'PID ' + service.pid|string if service.running else 'Stopped' }}</span>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <h2>?? Posts Overview</h2>
                <div class="stat-grid">
                    <div><div class="big-number">{{ posts_today }}</div><div class="big-label">Posted Today</div></div>
                    <div><div class="big-number status-pending">{{ posts_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number status-error">{{ posts_failed }}</div><div class="big-label">Failed</div></div>
                </div>
            </div>
            <div class="card">
                <h2>?? Comment Responder</h2>
                <div class="stat-grid">
                    <div><div class="big-number status-ok">{{ comments_sent }}</div><div class="big-label">Sent</div></div>
                    <div><div class="big-number status-pending">{{ comments_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number">{{ comments_total }}</div><div class="big-label">Total</div></div>
                </div>
            </div>
        </div>
        <div class="grid">
            <div class="card card-full">
                <h2>?? Recent Instagram Posts</h2>
                {% if ig_posts %}
                <div class="posts-grid">
                    {% for post in ig_posts %}
                    <a href="{{ post.permalink }}" target="_blank" style="text-decoration: none; color: inherit;">
                        <div class="post-card">
                            {% if post.thumbnail %}<img src="{{ post.thumbnail }}" alt="Post" class="post-image">{% else %}<div class="post-image-placeholder">{{ post.media_type[0] if post.media_type else '?' }}</div>{% endif %}
                            <div class="post-stats">
                                <div style="display: flex; gap: 15px;"><div class="post-stat">?? {{ post.likes }}</div><div class="post-stat">?? {{ post.comments }}</div></div>
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
            <div class="card">
                <h2>?? Queue Statistics</h2>
                <div class="stat-row"><span class="stat-label">Photos Posted (24h)</span><span class="stat-value">{{ photos_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Stories Posted (24h)</span><span class="stat-value">{{ stories_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Total in Queue</span><span class="stat-value status-pending">{{ total_queued }}</span></div>
                <div class="stat-row"><span class="stat-label">Posts This Week</span><span class="stat-value">{{ posts_week }}</span></div>
            </div>
            <div class="card">
                <h2>? Pending Replies</h2>
                {% if pending_replies %}{% for reply in pending_replies %}
                <div class="activity-item">
                    <div><strong>@{{ reply.username }}</strong>: "{{ reply.comment[:40] }}..."</div>
                    <div class="reply-text">? {{ reply.reply[:50] }}...</div>
                    <div class="activity-time">Scheduled: {{ reply.scheduled }} <a href="/approve" style="color: #e94560; margin-left: 10px;">Review ?</a></div>
                </div>
                {% endfor %}{% else %}<div style="color: #888; text-align: center; padding: 20px;">No pending replies</div>{% endif %}
            </div>
            <div class="card">
                <h2>?? Recent Activity</h2>
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
                <h2>?? Comment History (Latest {{ comment_history|length }} of {{ total_comments }})</h2>
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
        <h1>? Approve Replies</h1>
        <p class="subtitle">Review and approve Nyssa's AI-generated responses</p>
        
        <div class="nav">
            <a href="/">?? Dashboard</a>
            <a href="/approve" class="active">? Approve Replies</a>
            <a href="/moderation">??? Moderation</a>
        </div>
        
        {% if message %}<div class="message success">? {{ message }}</div>{% endif %}
        {% if error %}<div class="message error">? {{ error }}</div>{% endif %}
        
        <div class="info-box">
            ?? Replies will be sent automatically at their scheduled time if not reviewed. Edit or reject to change.
        </div>
        
        {% if pending_replies %}
            {% for reply in pending_replies %}
            <div class="pending-card">
                <div class="pending-header">
                    <div class="pending-user">@{{ reply.username }}</div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span class="pending-time">Scheduled: {{ reply.scheduled_time }}</span>
                        <span class="countdown">?? {{ reply.time_left }}</span>
                    </div>
                </div>
                
                {% if reply.is_thread %}<div class="thread-indicator">?? Thread Reply (responding to their reply)</div>{% endif %}
                
                <div class="original-comment">
                    <div class="original-label">Their Comment</div>
                    <div class="original-text">"{{ reply.comment }}"</div>
                </div>
                
                <form action="/approve/update/{{ reply.id }}" method="POST">
                    <div class="reply-section">
                        <div class="reply-label">Nyssa's Response <span>AI Generated</span></div>
                        <textarea name="reply_text" class="reply-textarea">{{ reply.reply }}</textarea>
                    </div>
                    
                    <div class="actions">
                        <button type="submit" name="action" value="approve" class="btn btn-approve">? Approve & Send Now</button>
                        <button type="submit" name="action" value="edit" class="btn btn-edit">?? Save Edit</button>
                        <button type="submit" name="action" value="reject" class="btn btn-reject">? Reject</button>
                    </div>
                </form>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty">
                <div class="empty-icon">?</div>
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
        <h1>??? Comment Moderation</h1>
        <p class="subtitle">Manage comments on your posts</p>
        
        <div class="nav">
            <a href="/">?? Dashboard</a>
            <a href="/approve">? Approve Replies</a>
            <a href="/moderation" class="active">??? Moderation</a>
        </div>
        
        {% if message %}<div class="message success">? {{ message }}</div>{% endif %}
        {% if error %}<div class="message error">? {{ error }}</div>{% endif %}
        
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
                        <span class="likes">?? {{ comment.likes }}</span> • 
                        {{ comment.timestamp[:10] if comment.timestamp else 'Unknown' }}
                    </div>
                </div>
                <div class="comment-text">"{{ comment.text }}"</div>
                <div class="comment-post">On post: <a href="{{ comment.post_url }}" target="_blank">{{ comment.post_caption }}</a></div>
                <div class="comment-actions">
                    {% if comment.hidden %}
                    <a href="/moderation/unhide/{{ comment.id }}" class="btn btn-unhide">??? Unhide</a>
                    {% else %}
                    <a href="/moderation/hide/{{ comment.id }}" class="btn btn-hide">?? Hide</a>
                    {% endif %}
                    <a href="/moderation/delete/{{ comment.id }}" class="btn btn-delete" onclick="return confirm('Delete this comment permanently?')">??? Delete</a>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty">No comments found on recent posts</div>
        {% endif %}
    </div>
</body>
</html>
"""

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
        if 'id' in data:
            return True, data['id']
        return False, data.get('error', {}).get('message', 'Unknown error')
    except Exception as e: return False, str(e)

# =============================================================================
# LOCAL DATA FUNCTIONS
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
    stats = {"posts_today": 0, "posts_pending": 0, "posts_failed": 0, "photos_24h": 0, "stories_24h": 0, "total_queued": 0, "posts_week": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        now = int(datetime.now().timestamp())
        day_ago, week_ago = now - 86400, now - 604800
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
        stats["posts_today"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?", (today_start,)).fetchone()[0]
        stats["posts_pending"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'pending'").fetchone()[0]
        stats["posts_failed"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'failed'").fetchone()[0]
        stats["photos_24h"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Photos'", (day_ago,)).fetchone()[0]
        stats["stories_24h"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Stories'", (day_ago,)).fetchone()[0]
        stats["total_queued"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status IN ('pending', 'posting')").fetchone()[0]
        stats["posts_week"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?", (week_ago,)).fetchone()[0]
        con.close()
    except: pass
    return stats

def get_comment_stats():
    stats = {"comments_sent": 0, "comments_pending": 0, "comments_total": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        stats["comments_sent"] = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'sent'").fetchone()[0]
        stats["comments_pending"] = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'pending'").fetchone()[0]
        stats["comments_total"] = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        con.close()
    except: pass
    return stats

def get_pending_replies_for_approval():
    replies = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("""
            SELECT id, username, comment_text, reply_text, scheduled_at, parent_comment_id 
            FROM comment_replies 
            WHERE status = 'pending' 
            ORDER BY scheduled_at ASC
        """).fetchall()
        now = datetime.now().timestamp()
        for row in rows:
            scheduled_ts = row[4] if row[4] else now + 3600
            scheduled_dt = datetime.fromtimestamp(scheduled_ts)
            time_left_sec = max(0, scheduled_ts - now)
            if time_left_sec > 3600:
                time_left = f"{int(time_left_sec // 3600)}h {int((time_left_sec % 3600) // 60)}m"
            elif time_left_sec > 60:
                time_left = f"{int(time_left_sec // 60)}m"
            else:
                time_left = f"{int(time_left_sec)}s"
            replies.append({
                "id": row[0],
                "username": row[1],
                "comment": row[2] or "",
                "reply": row[3] or "",
                "scheduled_time": scheduled_dt.strftime("%H:%M:%S"),
                "time_left": time_left,
                "is_thread": row[5] is not None
            })
        con.close()
    except Exception as e:
        print(f"Error getting pending replies: {e}")
    return replies

def get_pending_replies():
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("SELECT username, comment_text, reply_text, scheduled_at FROM comment_replies WHERE status = 'pending' ORDER BY scheduled_at ASC LIMIT 5").fetchall()
        con.close()
        return [{"username": r[0], "comment": r[1] or "", "reply": r[2] or "...", "scheduled": datetime.fromtimestamp(r[3]).strftime("%H:%M:%S") if r[3] else "N/A"} for r in rows]
    except: return []

def get_pending_count():
    try:
        con = sqlite3.connect(DB_FILE)
        count = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'pending'").fetchone()[0]
        con.close()
        return count
    except: return 0

def get_recent_activity():
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute("SELECT content_type, file_path, status, posted_at, created_at FROM media_files WHERE status IN ('posted', 'failed') ORDER BY COALESCE(posted_at, created_at) DESC LIMIT 10").fetchall()
        con.close()
        return [{"content_type": r[0], "filename": os.path.basename(r[1]), "status": r[2], "time": datetime.fromtimestamp(r[3] or r[4]).strftime("%Y-%m-%d %H:%M") if (r[3] or r[4]) else "N/A"} for r in rows]
    except: return []

def get_comment_history(limit=30):
    history, total, stats = [], 0, {"sent": 0, "pending": 0, "skipped": 0, "failed": 0, "rejected": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        total = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        for row in con.execute("SELECT status, COUNT(*) FROM comment_replies GROUP BY status").fetchall():
            if row[0] in stats: stats[row[0]] = row[1]
        for row in con.execute("SELECT username, comment_text, reply_text, status, created_at, replied_at FROM comment_replies ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall():
            history.append({"username": row[0] or "unknown", "text": row[1] or "", "reply": row[2], "status": row[3] or "unknown", "created": datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d %H:%M") if row[4] else "N/A", "replied_time": datetime.fromtimestamp(row[5]).strftime("%H:%M:%S") if row[5] else None})
        con.close()
    except: pass
    return history, total, stats

def update_reply_status(reply_id, status, new_text=None):
    try:
        con = sqlite3.connect(DB_FILE)
        if new_text is not None:
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
    global AUTH_TOKEN
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            AUTH_TOKEN = generate_auth_token()
            resp = make_response(redirect(url_for("dashboard")))
            max_age = COOKIE_MAX_AGE if request.form.get("remember") else None
            resp.set_cookie(COOKIE_NAME, AUTH_TOKEN, max_age=max_age, httponly=True, samesite='Lax')
            return resp
        error = "Invalid password"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
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
    return render_template_string(DASHBOARD_HTML, 
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        pending_count=pending_count)

@app.route("/approve")
@requires_auth
def approve():
    pending_replies = get_pending_replies_for_approval()
    return render_template_string(APPROVE_HTML,
        pending_replies=pending_replies,
        message=request.args.get('message'),
        error=request.args.get('error'))

@app.route("/approve/update/<int:reply_id>", methods=["POST"])
@requires_auth
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
        message=request.args.get('message'),
        error=request.args.get('error'))

@app.route("/moderation/hide/<comment_id>")
@requires_auth
def mod_hide(comment_id):
    success, msg = hide_comment(comment_id, hide=True)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/moderation/unhide/<comment_id>")
@requires_auth
def mod_unhide(comment_id):
    success, msg = hide_comment(comment_id, hide=False)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/moderation/delete/<comment_id>")
@requires_auth
def mod_delete(comment_id):
    success, msg = delete_comment(comment_id)
    return redirect(url_for('moderation', message=msg if success else None, error=None if success else msg))

@app.route("/api/stats")
@requires_auth
def api_stats():
    profile = get_instagram_profile()
    ig_posts = get_instagram_posts(8)
    return {'profile': profile, 'engagement': calculate_engagement(ig_posts, profile['followers'] if profile else 0), 'posts': get_post_stats(), 'comments': get_comment_stats()}

if __name__ == "__main__":
    print("Dashboard with auth on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
