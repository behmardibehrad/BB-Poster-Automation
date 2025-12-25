#!/usr/bin/env python3
import os
import time
import secrets
import mimetypes
import sqlite3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.expanduser("~/BB-Poster-Automation/media_root")
DB_FILE  = os.path.expanduser("~/BB-Poster-Automation/media_tokens/tokens.sqlite3")

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _ensure_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
          CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            rel   TEXT NOT NULL,
            exp   INTEGER NOT NULL,
            uses  INTEGER NOT NULL,
            max_uses INTEGER NOT NULL
          )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_tokens_exp ON tokens(exp)")
        con.commit()

def _cleanup_db(con):
    now = int(time.time())
    con.execute("DELETE FROM tokens WHERE exp <= ? OR uses >= max_uses", (now,))

def _safe_abs_path(rel_path: str) -> str:
    rel_path = rel_path.lstrip("/")
    base = os.path.abspath(BASE_DIR)
    abs_path = os.path.abspath(os.path.join(base, rel_path))
    if not abs_path.startswith(base + os.sep):
        raise ValueError("Path escapes BASE_DIR")
    return abs_path

def mint(rel_path: str, ttl_seconds: int = 900, max_uses: int = 25) -> str:
    _ensure_db()
    abs_path = _safe_abs_path(rel_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(abs_path)

    token = secrets.token_urlsafe(24)
    exp = int(time.time()) + int(ttl_seconds)

    with sqlite3.connect(DB_FILE) as con:
        _cleanup_db(con)
        con.execute(
            "INSERT INTO tokens(token, rel, exp, uses, max_uses) VALUES(?,?,?,?,?)",
            (token, rel_path.lstrip("/"), exp, 0, int(max_uses)),
        )
        con.commit()
    return token

def revoke(token: str) -> bool:
    _ensure_db()
    with sqlite3.connect(DB_FILE) as con:
        cur = con.execute("DELETE FROM tokens WHERE token = ?", (token,))
        con.commit()
        return cur.rowcount > 0

def _lookup_token(con, token: str):
    _cleanup_db(con)
    cur = con.execute("SELECT rel, exp, uses, max_uses FROM tokens WHERE token = ?", (token,))
    return cur.fetchone()

def _increment_use(con, token: str):
    # Atomic increment; token will be cleaned up on the next lookup if max exceeded.
    con.execute("UPDATE tokens SET uses = uses + 1 WHERE token = ?", (token,))

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._serve(head_only=True)

    def do_GET(self):
        self._serve(head_only=False)

    def _serve(self, head_only: bool):
        u = urlparse(self.path)
        parts = u.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "m":
            self.send_response(404); self.end_headers(); return

        token = parts[1]
        _ensure_db()

        with sqlite3.connect(DB_FILE) as con:
            row = _lookup_token(con, token)
            if not row:
                self.send_response(404); self.end_headers(); return

            rel, _exp, _uses, _max_uses = row
            try:
                abs_path = _safe_abs_path(rel)
            except ValueError:
                # If somehow bad data got in, invalidate the token.
                con.execute("DELETE FROM tokens WHERE token = ?", (token,))
                con.commit()
                self.send_response(404); self.end_headers(); return

            if not os.path.isfile(abs_path):
                con.execute("DELETE FROM tokens WHERE token = ?", (token,))
                con.commit()
                self.send_response(404); self.end_headers(); return

            # Only consume uses on GET (not HEAD)
            if not head_only:
                _increment_use(con, token)
                con.commit()

        ctype, _ = mimetypes.guess_type(abs_path)
        if not ctype:
            ctype = "application/octet-stream"

        file_size = os.path.getsize(abs_path)
        range_header = self.headers.get("Range")

        def send_no_cache():
            for k, v in NO_CACHE_HEADERS.items():
                self.send_header(k, v)

        try:
            with open(abs_path, "rb") as f:
                if range_header and range_header.startswith("bytes="):
                    spec = range_header.replace("bytes=", "").strip()
                    start_s, end_s = (spec.split("-", 1) + [""])[:2]
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else (file_size - 1)
                    start = max(0, min(start, file_size - 1))
                    end = max(start, min(end, file_size - 1))
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    send_no_cache()
                    self.end_headers()

                    if not head_only:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return

                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                send_no_cache()
                self.end_headers()
                if not head_only:
                    self.wfile.write(f.read())
        except BrokenPipeError:
            pass

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--mint", help="Mint token for rel path under BASE_DIR (e.g. 'ffindex.jpeg')")
    ap.add_argument("--ttl", type=int, default=900)
    ap.add_argument("--max-uses", type=int, default=200)
    ap.add_argument("--revoke", help="Revoke a token immediately")
    args = ap.parse_args()

    if args.mint:
        print(mint(args.mint, ttl_seconds=args.ttl, max_uses=args.max_uses))
        return
    if args.revoke:
        print("revoked" if revoke(args.revoke) else "not_found")
        return

    _ensure_db()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port} (BASE_DIR={BASE_DIR}, DB={DB_FILE})")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
