import json
import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)

NEXUS_TOKEN = os.environ.get("NEXUS_TOKEN", "").strip()
DB_PATH = os.environ.get("NEXUS_DB_PATH", "/tmp/nexus_cloud.db")


def get_db() -> sqlite3.Connection:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            data TEXT NOT NULL,
            received_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def is_authorized(req) -> bool:
    if not NEXUS_TOKEN:
        return True
    auth_header = req.headers.get("Authorization", "")
    return auth_header == f"Bearer {NEXUS_TOKEN}"


@app.route("/", methods=["GET"])
def health():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS cnt FROM memories").fetchone()["cnt"]
    return jsonify(
        {
            "status": "online",
            "service": "nexus-memory-server",
            "auth_enabled": bool(NEXUS_TOKEN),
            "stored_count": count,
        }
    ), 200


@app.route("/api/memory", methods=["POST"])
def receive_memory():
    if not is_authorized(request):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "data" not in payload:
        return jsonify({"error": "Invalid payload: missing 'data'"}), 400

    raw_data = payload["data"]
    data_str = raw_data if isinstance(raw_data, str) else json.dumps(raw_data, ensure_ascii=False)
    client_id = str(payload.get("id", ""))
    received_at = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO memories (client_id, data, received_at) VALUES (?, ?, ?)",
            (client_id, data_str, received_at),
        )
        conn.commit()
        server_seq = cursor.lastrowid

    print(
        f"[NEXUS-CLOUD] Persisted seq={server_seq} client_id={client_id} at={received_at}",
        flush=True,
    )
    return jsonify(
        {
            "status": "stored",
            "id": payload.get("id"),
            "seq": server_seq,
            "received_at": received_at,
        }
    ), 200


@app.route("/api/memory", methods=["GET"])
def list_memories():
    if not is_authorized(request):
        return jsonify({"error": "Unauthorized"}), 401

    limit = min(int(request.args.get("limit", 50)), 200)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT seq, client_id, data, received_at FROM memories ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return jsonify(
        {
            "count": len(rows),
            "items": [dict(r) for r in rows],
        }
    ), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
