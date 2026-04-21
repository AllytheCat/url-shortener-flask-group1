from flask import Flask, render_template, request, redirect
import random
import string
import sqlite3

app = Flask(__name__)

# Generate short code
def generate_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Create database
def init_db():
    conn = sqlite3.connect("urls.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT NOT NULL UNIQUE
        )
    """)

    conn.commit()
    conn.close()

# Home page
@app.route("/", methods=["GET", "POST"])
def home():
    short_url = None

    if request.method == "POST":
        long_url = request.form["long_url"]
        code = generate_code()

        conn = sqlite3.connect("urls.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO urls (long_url, short_code) VALUES (?, ?)",
            (long_url, code)
        )

        conn.commit()
        conn.close()

        short_url = f"http://127.0.0.1:5000/{code}"

    return render_template("index.html", short_url=short_url)

# Redirect route (THIS MAKES IT WORK)
@app.route("/<code>")
def redirect_url(code):
    conn = sqlite3.connect("urls.db")
    cursor = conn.cursor()

    cursor.execute("SELECT long_url FROM urls WHERE short_code = ?", (code,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return redirect(result[0])
    else:
        return "URL not found"

if __name__ == "__main__":
    init_db()
    app.run(debug=True)