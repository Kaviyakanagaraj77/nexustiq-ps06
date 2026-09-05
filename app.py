"""
NexusTiQ 24 — PS06 Transaction Risk Investigation Assistant

Single entrypoint per the submission rules: `python app.py` starts the
whole application (API + frontend) on port 8000.
"""
import os
import traceback
from flask import Flask, jsonify, send_from_directory, request

from src.data_loader import list_customers, load_customer
from src.report import build_investigation_report

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/customers")
def api_list_customers():
    try:
        return jsonify(list_customers())
    except Exception as e:
        app.logger.error("list_customers failed: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "Could not load customer list."}), 500


@app.get("/api/customers/<customer_id>/transactions")
def api_get_transactions(customer_id):
    record, txns = load_customer(customer_id)
    if record is None:
        return jsonify({"error": f"No customer found with id '{customer_id}'."}), 404
    return jsonify({
        "customer_id": record["customer_id"],
        "name": record["name"],
        "account_opened": record["account_opened"],
        "transactions": [t.to_dict() for t in txns],
    })


@app.post("/api/investigate/<customer_id>")
def api_investigate(customer_id):
    record, txns = load_customer(customer_id)
    if record is None:
        return jsonify({"error": f"No customer found with id '{customer_id}'."}), 404
    if not txns:
        return jsonify({"error": "This customer has no transaction history to review."}), 422
    try:
        report = build_investigation_report(record, txns)
        return jsonify(report)
    except Exception as e:
        app.logger.error("investigation failed for %s: %s\n%s", customer_id, e, traceback.format_exc())
        return jsonify({
            "error": "The investigation could not be completed due to an internal error. "
                     "No report was generated — please retry or escalate manually.",
        }), 500


@app.errorhandler(404)
def not_found(e):
    # Let client-side routing handle unknown paths by falling back to index.html,
    # but keep /api/* returning real JSON 404s (handled above per-route).
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
