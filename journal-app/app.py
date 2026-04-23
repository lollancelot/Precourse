import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
import anthropic

app = Flask(__name__)
DB = "journal.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                mood TEXT,
                ai_feedback TEXT,
                created_at TEXT NOT NULL
            )
        """)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/entries", methods=["GET"])
def get_entries():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/entries", methods=["POST"])
def create_entry():
    data = request.get_json()
    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    mood = data.get("mood", "")

    if not title or not body:
        return jsonify({"error": "Title and body are required"}), 400

    ai_feedback = None
    api_key = data.get("apiKey") or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": (
                        f"You are a warm, supportive journal companion. "
                        f"The user wrote this journal entry titled '{title}' "
                        f"with mood '{mood}':\n\n{body}\n\n"
                        f"Give a brief (2-3 sentence), empathetic, encouraging response. "
                        f"Be genuine, not generic."
                    )
                }]
            )
            ai_feedback = message.content[0].text
        except Exception:
            ai_feedback = None

    created_at = datetime.utcnow().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO entries (title, body, mood, ai_feedback, created_at) VALUES (?,?,?,?,?)",
            (title, body, mood, ai_feedback, created_at)
        )
        entry_id = cur.lastrowid
        entry = dict(conn.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone())

    return jsonify(entry), 201


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    with get_db() as conn:
        conn.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
