#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, sqlite3, subprocess
from datetime import datetime
from flask import Flask, render_template_string, request

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>BB-Poster Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2rem; color: #e94560; }
        .subtitle { text-align: center; color: #888; margin-top: -20px; margin-bottom: 30px; font-size: 0.9rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .card h2 { font-size: 1rem; color: #e94560; margin-bottom: 15px; }
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
        .activity-item { padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px; font-size: 0.85rem; }
        .activity-time { color: #888; font-size: 0.75rem; }
        .reply-text { color: #4ade80; margin: 5px 0; font-style: italic; }
        .service-status { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
        .service-dot { width: 10px; height: 10px; border-radius: 50%; }
        .service-dot.running { background: #4ade80; }
        .service-dot.stopped { background: #f87171; }
        .refresh-note { text-align: center; color: #666; font-size: 0.8rem; margin-top: 20px; }
        
        /* Comment History Styles */
        .comment-list { max-height: 600px; overflow-y: auto; }
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
        .load-more { text-align: center; margin-top: 15px; }
        .load-more a { color: #e94560; text-decoration: none; padding: 10px 20px; border: 1px solid #e94560; border-radius: 5px; }
        .load-more a:hover { background: #e94560; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>BB-Poster Dashboard</h1>
        <p class="subtitle">Nyssa Bloom Automation - Last updated: {{ current_time }}</p>
        <div class="grid">
            <div class="card">
                <h2>Services Status</h2>
                {% for service in services %}
                <div class="service-status">
                    <div class="service-dot {{ 'running' if service.running else 'stopped' }}"></div>
                    <span>{{ service.name }}</span>
                    <span style="margin-left: auto; color: #888; font-size: 0.8rem;">{{ 'PID ' + service.pid|string if service.running else 'Stopped' }}</span>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <h2>Posts Overview</h2>
                <div class="stat-grid">
                    <div><div class="big-number">{{ posts_today }}</div><div class="big-label">Posted Today</div></div>
                    <div><div class="big-number status-pending">{{ posts_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number status-error">{{ posts_failed }}</div><div class="big-label">Failed</div></div>
                </div>
            </div>
            <div class="card">
                <h2>Comment Responder</h2>
                <div class="stat-grid">
                    <div><div class="big-number status-ok">{{ comments_sent }}</div><div class="big-label">Sent (All Time)</div></div>
                    <div><div class="big-number status-pending">{{ comments_pending }}</div><div class="big-label">Pending</div></div>
                    <div><div class="big-number">{{ comments_total }}</div><div class="big-label">Total</div></div>
                </div>
            </div>
        </div>
        <div class="grid">
            <div class="card">
                <h2>Post Statistics</h2>
                <div class="stat-row"><span class="stat-label">Photos Posted (24h)</span><span class="stat-value">{{ photos_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Stories Posted (24h)</span><span class="stat-value">{{ stories_24h }}</span></div>
                <div class="stat-row"><span class="stat-label">Total in Queue</span><span class="stat-value">{{ total_queued }}</span></div>
                <div class="stat-row"><span class="stat-label">Posts This Week</span><span class="stat-value">{{ posts_week }}</span></div>
            </div>
            <div class="card">
                <h2>Pending Replies</h2>
                {% if pending_replies %}
                    {% for reply in pending_replies %}
                    <div class="activity-item">
                        <div><strong>@{{ reply.username }}</strong>: "{{ reply.comment[:50] }}"</div>
                        <div class="reply-text">-> {{ reply.reply[:60] }}...</div>
                        <div class="activity-time">Scheduled: {{ reply.scheduled }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="color: #888; text-align: center; padding: 20px;">No pending replies</div>
                {% endif %}
            </div>
            <div class="card">
                <h2>Recent Activity</h2>
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
        
        <!-- Comment History Section -->
        <div class="grid">
            <div class="card card-full">
                <h2>Comment History (Latest {{ comment_history|length }} of {{ total_comments }})</h2>
                <div class="comment-stats">
                    <div class="comment-stat">
                        <div class="comment-stat-num status-ok">{{ stats_sent }}</div>
                        <div class="comment-stat-label">Sent</div>
                    </div>
                    <div class="comment-stat">
                        <div class="comment-stat-num status-pending">{{ stats_pending }}</div>
                        <div class="comment-stat-label">Pending</div>
                    </div>
                    <div class="comment-stat">
                        <div class="comment-stat-num status-skipped">{{ stats_skipped }}</div>
                        <div class="comment-stat-label">Skipped</div>
                    </div>
                    <div class="comment-stat">
                        <div class="comment-stat-num status-error">{{ stats_failed }}</div>
                        <div class="comment-stat-label">Failed</div>
                    </div>
                </div>
                <div class="comment-list">
                    {% if comment_history %}
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
                            <div class="comment-time">
                                {{ comment.created }} 
                                {% if comment.replied_time %} | Replied: {{ comment.replied_time }}{% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="color: #888; text-align: center; padding: 40px;">No comments yet</div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <p class="refresh-note">Auto-refreshes every 60 seconds</p>
    </div>
</body>
</html>
"""

def get_service_status():
    services = [("Media Server", "media_server.py"), ("Cloudflare Tunnel", "cloudflared"), ("Scanner", "scanner.py"), ("Poster", "poster.py"), ("Comment Responder", "comment_responder.py")]
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

def get_comment_history(limit=50):
    """Get comment history with replies."""
    history = []
    total = 0
    stats = {"sent": 0, "pending": 0, "skipped": 0, "failed": 0}
    try:
        con = sqlite3.connect(DB_FILE)
        
        # Get total count
        total = con.execute("SELECT COUNT(*) FROM comment_replies").fetchone()[0]
        
        # Get stats by status
        rows = con.execute("SELECT status, COUNT(*) FROM comment_replies GROUP BY status").fetchall()
        for row in rows:
            if row[0] in stats:
                stats[row[0]] = row[1]
        
        # Get latest comments
        rows = con.execute("""
            SELECT username, comment_text, reply_text, status, created_at, replied_at 
            FROM comment_replies 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        
        for row in rows:
            created = datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d %H:%M") if row[4] else "N/A"
            replied = datetime.fromtimestamp(row[5]).strftime("%H:%M:%S") if row[5] else None
            history.append({
                "username": row[0],
                "text": row[1],
                "reply": row[2],
                "status": row[3],
                "created": created,
                "replied_time": replied
            })
        con.close()
    except Exception as e:
        print(f"Error getting comment history: {e}")
    return history, total, stats

@app.route("/")
def dashboard():
    services = get_service_status()
    post_stats = get_post_stats()
    comment_stats = get_comment_stats()
    comment_history, total_comments, history_stats = get_comment_history(50)
    
    return render_template_string(DASHBOARD_HTML, 
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        services=services, 
        posts_today=post_stats["posts_today"], 
        posts_pending=post_stats["posts_pending"],
        posts_failed=post_stats["posts_failed"], 
        photos_24h=post_stats["photos_24h"], 
        stories_24h=post_stats["stories_24h"],
        total_queued=post_stats["total_queued"], 
        posts_week=post_stats["posts_week"], 
        comments_sent=comment_stats["comments_sent"],
        comments_pending=comment_stats["comments_pending"], 
        comments_total=comment_stats["comments_total"],
        pending_replies=get_pending_replies(), 
        recent_activity=get_recent_activity(),
        comment_history=comment_history,
        total_comments=total_comments,
        stats_sent=history_stats["sent"],
        stats_pending=history_stats["pending"],
        stats_skipped=history_stats["skipped"],
        stats_failed=history_stats["failed"]
    )

if __name__ == "__main__":
    print("Starting dashboard on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)