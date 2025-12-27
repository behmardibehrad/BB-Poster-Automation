#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Dashboard for BB-Poster-Automation
Includes Instagram profile stats, post performance, and engagement metrics.
"""
import os, sys, json, sqlite3, subprocess, requests
from datetime import datetime
from flask import Flask, render_template_string

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")
FB_GRAPH_API = "https://graph.facebook.com/v21.0"

app = Flask(__name__)

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
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; font-size: 0.9rem; }
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

        /* Profile Section */
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

        /* Engagement Card */
        .engagement-value { font-size: 2rem; font-weight: bold; color: #4ade80; }
        .engagement-label { color: #888; font-size: 0.8rem; }
        .engagement-detail { color: #aaa; font-size: 0.85rem; margin-top: 5px; }

        /* Posts Grid */
        .posts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .post-card { background: rgba(255,255,255,0.03); border-radius: 10px; overflow: hidden; transition: transform 0.2s; }
        .post-card:hover { transform: scale(1.02); }
        .post-image { width: 100%; aspect-ratio: 1; object-fit: cover; background: #222; }
        .post-image-placeholder { width: 100%; aspect-ratio: 1; background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%); display: flex; align-items: center; justify-content: center; color: #666; font-size: 2rem; }
        .post-stats { padding: 12px; display: flex; justify-content: space-between; align-items: center; }
        .post-stat { display: flex; align-items: center; gap: 5px; color: #aaa; font-size: 0.85rem; }
        .post-stat svg { width: 16px; height: 16px; }
        .post-type { font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; background: rgba(233, 69, 96, 0.2); color: #e94560; }

        /* Activity & Services */
        .activity-item { padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px; font-size: 0.85rem; }
        .activity-time { color: #888; font-size: 0.75rem; }
        .reply-text { color: #4ade80; margin: 5px 0; font-style: italic; }
        .service-status { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
        .service-dot { width: 10px; height: 10px; border-radius: 50%; }
        .service-dot.running { background: #4ade80; }
        .service-dot.stopped { background: #f87171; }

        /* Comment History */
        .comment-list { max-height: 500px; overflow-y: auto; }
        .comment-item { padding: 15px; background: rgba(255,255,255,0.03); border-radius: 10px; margin-bottom: 10px; border-left: 3px solid #e94560; }
        .comment-item.sent { border-left-color: #4ade80; }
        .comment-item.pending { border-left-color: #60a5fa; }
        .comment-item.skipped { border-left-color: #fbbf24; }
        .comment-item.failed { border-left-color: #f87171; }
        .comment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .comment-username { font-weight: bold; color: #e94560; }
        .comment-status { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; }
        .comment-status.sent { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .comment-status.pending { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
        .comment-status.skipped { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .comment-status.failed { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .comment-text { color: #ccc; margin-bottom: 8px; }
        .comment-reply { color: #4ade80; font-style: italic; padding-left: 15px; border-left: 2px solid #4ade80; margin-top: 8px; }
        .comment-time { color: #666; font-size: 0.75rem; margin-top: 8px; }
        .comment-stats { display: flex; gap: 20px; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
        .comment-stat { text-align: center; }
        .comment-stat-num { font-size: 1.5rem; font-weight: bold; color: #e94560; }
        .comment-stat-label { font-size: 0.75rem; color: #888; }

        .refresh-note { text-align: center; color: #666; font-size: 0.8rem; margin-top: 20px; }
        .error-note { color: #f87171; font-size: 0.8rem; text-align: center; padding: 20px; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: #e94560; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌸 Nyssa Bloom Dashboard</h1>
        <p class="subtitle">Last updated: {{ current_time }}</p>

        <!-- Profile & Engagement Row -->
        <div class="grid">
            <div class="card" style="grid-column: span 2;">
                <h2>📸 Instagram Profile</h2>
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
                    <div class="profile-stat">
                        <div class="profile-stat-num">{{ profile.followers }}</div>
                        <div class="profile-stat-label">Followers</div>
                    </div>
                    <div class="profile-stat">
                        <div class="profile-stat-num">{{ profile.following }}</div>
                        <div class="profile-stat-label">Following</div>
                    </div>
                    <div class="profile-stat">
                        <div class="profile-stat-num">{{ profile.posts }}</div>
                        <div class="profile-stat-label">Posts</div>
                    </div>
                </div>
                {% else %}
                <div class="error-note">Could not load Instagram profile</div>
                {% endif %}
            </div>

            <div class="card">
                <h2>📊 Engagement</h2>
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
                {% else %}
                <div class="error-note">Could not calculate engagement</div>
                {% endif %}
            </div>
        </div>

        <!-- Services & System Stats -->
        <div class="grid">
            <div class="card">
                <h2>⚙️ Services Status</h2>
                {% for service in services %}
                <div class="service-status">
                    <div class="service-dot {{ 'running' if service.running else 'stopped' }}"></div>
                    <span>{{ service.name }}</span>
                    <span style="margin-left: auto; color: #888; font-size: 0.8rem;">{{ 'PID ' + service.pid|string if service.running else 'Stopped' }}</span>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <h2>📬 Posts Overview</h2>
                <div class="stat-grid">
                    <div><div class="big-number">{{ posts_today }}</div><div class="big-label">Posted Today</div></div>
                    <div><div class="big-number status-pending">{{ posts_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number status-error">{{ posts_failed }}</div><div class="big-label">Failed</div></div>
                </div>
            </div>
            <div class="card">
                <h2>💬 Comment Responder</h2>
                <div class="stat-grid">
                    <div><div class="big-number status-ok">{{ comments_sent }}</div><div class="big-label">Sent</div></div>
                    <div><div class="big-number status-pending">{{ comments_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number">{{ comments_total }}</div><div class="big-label">Total</div></div>
                </div>
            </div>
        </div>

        <!-- Recent Instagram Posts -->
        <div class="grid">
            <div class="card card-full">
                <h2>📷 Recent Instagram Posts</h2>
                {% if ig_posts %}
                <div class="posts-grid">
                    {% for post in ig_posts %}
                    <a href="{{ post.permalink }}" target="_blank" style="text-decoration: none; color: inherit;">
                        <div class="post-card">
                            {% if post.thumbnail %}
                            <img src="{{ post.thumbnail }}" alt="Post" class="post-image" onerror="this.outerHTML='<div class=post-image-placeholder>{{ post.media_type[0] }}</div>'">
                            {% else %}
                            <div class="post-image-placeholder">{{ post.media_type[0] if post.media_type else '?' }}</div>
                            {% endif %}
                            <div class="post-stats">
                                <div style="display: flex; gap: 15px;">
                                    <div class="post-stat">❤️ {{ post.likes }}</div>
                                    <div class="post-stat">💬 {{ post.comments }}</div>
                                </div>
                                <span class="post-type">{{ post.media_type }}</span>
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
                {% else %}
                <div class="error-note">No posts found</div>
                {% endif %}
            </div>
        </div>

        <!-- Queue & Activity -->
        <div class="grid">
            <div class="card">
                <h2>📅 Queue Statistics</h2>
                <div class="stat-row"><span class="stat-label">Photos Posted (24h)</span><span class="stat-value">{{ photos_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Stories Posted (24h)</span><span class="stat-value">{{ stories_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Total in Queue</span><span class="stat-value status-pending">{{ total_queued }}</span></div>
                <div class="stat-row"><span class="stat-label">Posts This Week</span><span class="stat-value">{{ posts_week }}</span></div>
            </div>
            <div class="card">
                <h2>⏳ Pending Replies</h2>
                {% if pending_replies %}
                    {% for reply in pending_replies %}
                    <div class="activity-item">
                        <div><strong>@{{ reply.username }}</strong>: "{{ reply.comment[:40] }}..."</div>
                        <div class="reply-text">→ {{ reply.reply[:50] }}...</div>
                        <div class="activity-time">Scheduled: {{ reply.scheduled }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="color: #888; text-align: center; padding: 20px;">No pending replies</div>
                {% endif %}
            </div>
            <div class="card">
                <h2>🕐 Recent Activity</h2>
                {% if recent_activity %}
                    {% for activity in recent_activity %}
                    <div class="activity-item">
                        <div><span class="{{ 'status-ok' if activity.status == 'posted' else 'status-error' }}">{{ activity.status|upper }}</span> - {{ activity.content_type }}</div>
                        <div class="activity-time">{{ activity.time }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="color: #888; text-align: center; padding: 20px;">No recent activity</div>
                {% endif %}
            </div>
        </div>

        <!-- Comment History -->
        <div class="grid">
            <div class="card card-full">
                <h2>💬 Comment History (Latest {{ comment_history|length }} of {{ total_comments }})</h2>
                <div class="comment-stats">
                    <div class="comment-stat"><div class="comment-stat-num status-ok">{{ stats_sent }}</div><div class="comment-stat-label">Sent</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-pending">{{ stats_pending }}</div><div class="comment-stat-label">Pending</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-skipped">{{ stats_skipped }}</div><div class="comment-stat-label">Skipped</div></div>
                    <div class="comment-stat"><div class="comment-stat-num status-error">{{ stats_failed }}</div><div class="comment-stat-label">Failed</div></div>
                </div>
                <div class="comment-list">
                    {% for comment in comment_history %}
                    <div class="comment-item {{ comment.status }}">
                        <div class="comment-header">
                            <span class="comment-username">@{{ comment.username }}</span>
                            <span class="comment-status {{ comment.status }}">{{ comment.status }}</span>
                        </div>
                        <div class="comment-text">"{{ comment.text }}"</div>
                        {% if comment.reply %}
                        <div class="comment-reply">{{ comment.reply }}</div>
                        {% endif %}
                        <div class="comment-time">{{ comment.created }}{% if comment.replied_time %} | Replied: {{ comment.replied_time }}{% endif %}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <p class="refresh-note">Auto-refreshes every 60 seconds • <a href="/api/stats" style="color: #e94560;">API</a></p>
    </div>
</body>
</html>
"""


def get_instagram_credentials():
    try:
        con = sqlite3.connect(DB_FILE)
        row = con.execute(
            "SELECT ig_user_id, access_token FROM credentials WHERE platform = 'Instagram' AND is_active = 1 LIMIT 1").fetchone()
        con.close()
        if row:
            return row[0], row[1]
    except:
        pass
    return None, None


def get_instagram_profile():
    ig_user_id, token = get_instagram_credentials()
    if not ig_user_id or not token:
        return None
    try:
        resp = requests.get(f"{FB_GRAPH_API}/{ig_user_id}", params={
            'fields': 'username,name,biography,followers_count,follows_count,media_count,profile_picture_url',
            'access_token': token
        }, timeout=10)
        data = resp.json()
        if 'error' not in data:
            return {
                'username': data.get('username', 'N/A'),
                'name': data.get('name', 'N/A'),
                'bio': data.get('biography', ''),
                'followers': data.get('followers_count', 0),
                'following': data.get('follows_count', 0),
                'posts': data.get('media_count', 0),
                'avatar': data.get('profile_picture_url', '')
            }
    except Exception as e:
        print(f"Error fetching profile: {e}")
    return None


def get_instagram_posts(limit=8):
    ig_user_id, token = get_instagram_credentials()
    if not ig_user_id or not token:
        return []
    try:
        resp = requests.get(f"{FB_GRAPH_API}/{ig_user_id}/media", params={
            'fields': 'id,caption,media_type,timestamp,like_count,comments_count,permalink,thumbnail_url,media_url',
            'limit': limit,
            'access_token': token
        }, timeout=10)
        data = resp.json()
        posts = []
        if 'data' in data:
            for post in data['data']:
                thumbnail = post.get('thumbnail_url') or post.get('media_url', '')
                posts.append({
                    'id': post.get('id'),
                    'caption': (post.get('caption', '')[:50] + '...') if post.get('caption') else '',
                    'media_type': post.get('media_type', 'IMAGE'),
                    'timestamp': post.get('timestamp', ''),
                    'likes': post.get('like_count', 0),
                    'comments': post.get('comments_count', 0),
                    'permalink': post.get('permalink', '#'),
                    'thumbnail': thumbnail
                })
        return posts
    except Exception as e:
        print(f"Error fetching posts: {e}")
    return []


def calculate_engagement(posts, followers):
    if not posts or followers == 0:
        return None
    total_likes = sum(p['likes'] for p in posts)
    total_comments = sum(p['comments'] for p in posts)
    post_count = len(posts)
    avg_likes = total_likes / post_count if post_count > 0 else 0
    avg_comments = total_comments / post_count if post_count > 0 else 0
    engagement_rate = ((total_likes + total_comments) / post_count) / followers * 100 if post_count > 0 else 0
    return {
        'rate': round(engagement_rate, 2),
        'avg_likes': round(avg_likes, 1),
        'avg_comments': round(avg_comments, 1),
        'total_likes': total_likes,
        'total_comments': total_comments,
        'post_count': post_count
    }


def get_service_status():
    services = [("Media Server", "media_server.py"), ("Cloudflare Tunnel", "cloudflared"), ("Scanner", "scanner.py"),
                ("Poster", "poster.py"), ("Comment Responder", "comment_responder.py"), ("Dashboard", "dashboard.py")]
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
    stats = {"posts_today": 0, "posts_pending": 0, "posts_failed": 0, "photos_24h": 0, "stories_24h": 0,
             "total_queued": 0, "posts_week": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        now = int(datetime.now().timestamp())
        day_ago, week_ago = now - 86400, now - 604800
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
        stats["posts_today"] = \
        con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?",
                    (today_start,)).fetchone()[0]
        stats["posts_pending"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'pending'").fetchone()[0]
        stats["posts_failed"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'failed'").fetchone()[0]
        stats["photos_24h"] = con.execute(
            "SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Photos'",
            (day_ago,)).fetchone()[0]
        stats["stories_24h"] = con.execute(
            "SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ? AND content_type = 'Stories'",
            (day_ago,)).fetchone()[0]
        stats["total_queued"] = \
        con.execute("SELECT COUNT(*) FROM media_files WHERE status IN ('pending', 'posting')").fetchone()[0]
        stats["posts_week"] = con.execute("SELECT COUNT(*) FROM media_files WHERE status = 'posted' AND posted_at >= ?",
                                          (week_ago,)).fetchone()[0]
        con.close()
    except Exception as e:
        print(f"Error: {e}")
    return stats


def get_comment_stats():
    stats = {"comments_sent": 0, "comments_pending": 0, "comments_total": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        stats["comments_sent"] = con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'sent'").fetchone()[0]
        stats["comments_pending"] = \
        con.execute("SELECT COUNT(*) FROM comment_replies WHERE status = 'pending'").fetchone()[0]
        stats["comments_total"] = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        con.close()
    except:
        pass
    return stats


def get_pending_replies():
    replies = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute(
            "SELECT username, comment_text, reply_text, scheduled_at FROM comment_replies WHERE status = 'pending' ORDER BY scheduled_at ASC LIMIT 5").fetchall()
        for row in rows:
            replies.append({"username": row[0], "comment": row[1] or "", "reply": row[2] or "Generating...",
                            "scheduled": datetime.fromtimestamp(row[3]).strftime("%H:%M:%S") if row[3] else "N/A"})
        con.close()
    except:
        pass
    return replies


def get_recent_activity():
    activity = []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute(
            "SELECT content_type, file_path, status, posted_at, created_at FROM media_files WHERE status IN ('posted', 'failed') ORDER BY COALESCE(posted_at, created_at) DESC LIMIT 10").fetchall()
        for row in rows:
            timestamp = row[3] or row[4]
            activity.append({"content_type": row[0], "filename": os.path.basename(row[1]), "status": row[2],
                             "time": datetime.fromtimestamp(timestamp).strftime(
                                 "%Y-%m-%d %H:%M") if timestamp else "N/A"})
        con.close()
    except:
        pass
    return activity


def get_comment_history(limit=30):
    history, total, stats = [], 0, {"sent": 0, "pending": 0, "skipped": 0, "failed": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        total = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        rows = con.execute("SELECT status, COUNT(*) FROM comment_replies GROUP BY status").fetchall()
        for row in rows:
            if row[0] in stats:
                stats[row[0]] = row[1]
        rows = con.execute(
            "SELECT username, comment_text, reply_text, status, created_at, replied_at FROM comment_replies ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
        for row in rows:
            created = datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d %H:%M") if row[4] else "N/A"
            replied = datetime.fromtimestamp(row[5]).strftime("%H:%M:%S") if row[5] else None
            history.append(
                {"username": row[0] or "unknown", "text": row[1] or "", "reply": row[2], "status": row[3] or "unknown",
                 "created": created, "replied_time": replied})
        con.close()
    except Exception as e:
        print(f"Error getting comment history: {e}")
    return history, total, stats


@app.route("/")
def dashboard():
    profile = get_instagram_profile()
    ig_posts = get_instagram_posts(8)
    engagement = calculate_engagement(ig_posts, profile['followers'] if profile else 0)
    services = get_service_status()
    post_stats = get_post_stats()
    comment_stats = get_comment_stats()
    comment_history, total_comments, history_stats = get_comment_history(30)
    return render_template_string(DASHBOARD_HTML,
                                  current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  profile=profile, ig_posts=ig_posts, engagement=engagement, services=services,
                                  posts_today=post_stats["posts_today"], posts_pending=post_stats["posts_pending"],
                                  posts_failed=post_stats["posts_failed"], photos_24h=post_stats["photos_24h"],
                                  stories_24h=post_stats["stories_24h"], total_queued=post_stats["total_queued"],
                                  posts_week=post_stats["posts_week"], comments_sent=comment_stats["comments_sent"],
                                  comments_pending=comment_stats["comments_pending"],
                                  comments_total=comment_stats["comments_total"],
                                  pending_replies=get_pending_replies(), recent_activity=get_recent_activity(),
                                  comment_history=comment_history, total_comments=total_comments,
                                  stats_sent=history_stats["sent"], stats_pending=history_stats["pending"],
                                  stats_skipped=history_stats["skipped"], stats_failed=history_stats["failed"])


@app.route("/api/stats")
def api_stats():
    profile = get_instagram_profile()
    ig_posts = get_instagram_posts(8)
    engagement = calculate_engagement(ig_posts, profile['followers'] if profile else 0)
    return {'profile': profile, 'engagement': engagement, 'posts': get_post_stats(), 'comments': get_comment_stats(),
            'timestamp': datetime.now().isoformat()}


if __name__ == "__main__":
    print("Starting enhanced dashboard on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
