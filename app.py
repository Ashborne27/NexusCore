import os
from flask import Flask, jsonify, request

app = Flask(__name__)

NEXUS_TOKEN = os.environ.get("NEXUS_TOKEN", "")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "service": "nexus-memory-server"}), 200


@app.route("/api/memory", methods=["POST"])
def receive_memory():
    if NEXUS_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {NEXUS_TOKEN}":
            return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload or "data" not in payload:
        return jsonify({"error": "Invalid payload: missing 'data'"}), 400

    print(
        f"[NEXUS-CLOUD] Reçu id={payload.get('id')} len={len(str(payload['data']))}",
        flush=True,
    )
    return jsonify({"status": "stored", "id": payload.get("id")}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
