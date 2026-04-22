"""
URL Shortener Web App
COMP318 – Group Project
Fully commented version for team understanding
"""

import sqlite3
from datetime import datetime
import hashlib
import string
import random
from urllib.parse import urlparse
import io

from flask import (
    Flask, render_template, request,
    redirect, url_for, abort, send_file
)

import qrcode  # For generating QR codes

app = Flask(__name__)
DB = "urls.db"  # SQLite database file


# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------

def get_db():
    """
    Opens a connection to the SQLite database.
    row_factory allows us to access columns by name.
    """
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates the database tables if they do not exist.
    This runs automatically when the app starts.
    """
    conn = get_db()
    cur = conn.cursor()

    # Table storing each shortened URL
    cur.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            click_count INTEGER DEFAULT 0
        );
    """)

    # Table storing click analytics
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_id INTEGER NOT NULL,
            clicked_at TEXT NOT NULL,
            referrer TEXT,
            FOREIGN KEY (url_id) REFERENCES urls(id)
        );
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------

def is_valid_url(url: str) -> bool:
    """
    Basic URL validation using urlparse.
    Ensures the URL starts with http:// or https://
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc
    except:
        return False


def short_code_exists(code: str) -> bool:
    """
    Checks if a short code already exists in the database.
    Prevents duplicates.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM urls WHERE short_code = ?", (code,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def generate_short_code(original_url: str, length: int = 6) -> str:
    """
    Generates a unique short code using hashing + randomness.
    Ensures low chance of collisions.
    """
    base = hashlib.sha256(original_url.encode("utf-8")).hexdigest()
    chars = string.ascii_letters + string.digits

    # Try deterministic seeds first
    for i in range(5):
        seed = base[i * 8:(i + 1) * 8]
        random.seed(seed)
        code = "".join(random.choice(chars) for _ in range(length))
        if not short_code_exists(code):
            return code

    # Fallback: fully random
    while True:
        code = "".join(random.choice(chars) for _ in range(length))
        if not short_code_exists(code):
            return code


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Home page:
    - Accepts long URL input
    - Optional custom short code
    - Displays dashboard of all URLs
    """
    conn = get_db()
    cur = conn.cursor()

    short_url = None
    error = None
    success = None

    if request.method == "POST":
        long_url = request.form.get("long_url", "").strip()
        custom_code = request.form.get("custom_code", "").strip()

        # Validate URL
        if not long_url:
            error = "Please enter a URL."
        elif not is_valid_url(long_url):
            error = "Invalid URL. Must start with http:// or https://"
        elif custom_code and short_code_exists(custom_code):
            error = "Custom short code is already taken."
        else:
            # If no custom code, check if URL already exists
            if not custom_code:
                cur.execute("SELECT short_code FROM urls WHERE original_url = ?", (long_url,))
                row = cur.fetchone()
            else:
                row = None

            if row:
                # Reuse existing short code
                code = row["short_code"]
            else:
                # Create new short code
                code = custom_code if custom_code else generate_short_code(long_url)
                cur.execute("""
                    INSERT INTO urls (original_url, short_code, created_at)
                    VALUES (?, ?, ?)
                """, (long_url, code, datetime.utcnow().isoformat()))
                conn.commit()

            short_url = url_for("redirect_short", code=code, _external=True)
            success = "Short URL created successfully."

    # Load dashboard data
    cur.execute("SELECT * FROM urls ORDER BY created_at DESC")
    urls = cur.fetchall()
    conn.close()

    return render_template("index.html",
                           short_url=short_url,
                           error=error,
                           success=success,
                           urls=urls)


@app.route("/s/<code>")
def redirect_short(code):
    """
    Redirect route:
    - Looks up the original URL
    - Logs click analytics
    - Redirects user
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM urls WHERE short_code = ?", (code,))
    row = cur.fetchone()

    if not row:
        conn.close()
        abort(404)

    url_id = row["id"]
    original_url = row["original_url"]

    # Update click count
    cur.execute("UPDATE urls SET click_count = click_count + 1 WHERE id = ?", (url_id,))

    # Log click event
    cur.execute("""
        INSERT INTO clicks (url_id, clicked_at, referrer)
        VALUES (?, ?, ?)
    """, (url_id, datetime.utcnow().isoformat(), request.referrer))

    conn.commit()
    conn.close()

    return redirect(original_url)


@app.route("/stats/<code>")
def stats(code):
    """
    Stats page:
    - Shows total clicks
    - Shows click history (timestamp + referrer)
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM urls WHERE short_code = ?", (code,))
    url_row = cur.fetchone()

    if not url_row:
        conn.close()
        abort(404)

    cur.execute("SELECT * FROM clicks WHERE url_id = ? ORDER BY clicked_at DESC", (url_row["id"],))
    clicks = cur.fetchall()

    conn.close()

    return render_template("stats.html", url=url_row, clicks=clicks)


@app.route("/qr/<code>")
def qr(code):
    """
    Generates a QR code for the short URL.
    Returns a PNG image.
    """
    short_url = url_for("redirect_short", code=code, _external=True)
    img = qrcode.make(short_url)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    init_db()  # Create tables if needed
    app.run(debug=True)
