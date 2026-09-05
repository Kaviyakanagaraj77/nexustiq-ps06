"""Loads customer transaction histories from data/customers/*.json.

This is the only place that touches the filesystem for transaction data.
No network calls, no external DB — per the hackathon's local-only rule.
"""
import json
import os
from .models import Transaction

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "customers")


def list_customers() -> list:
    """Returns lightweight summaries for the customer picker in the UI."""
    summaries = []
    if not os.path.isdir(DATA_DIR):
        return summaries
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(DATA_DIR, fname)) as f:
            record = json.load(f)
        dates = [t["date"] for t in record["transactions"]]
        summaries.append({
            "customer_id": record["customer_id"],
            "name": record["name"],
            "account_opened": record["account_opened"],
            "transaction_count": len(record["transactions"]),
            "period_start": min(dates) if dates else None,
            "period_end": max(dates) if dates else None,
        })
    return summaries


def load_customer(customer_id: str):
    """Returns (record_dict, [Transaction, ...]) or (None, None) if missing."""
    path = os.path.join(DATA_DIR, f"{customer_id}.json")
    if not os.path.isfile(path):
        return None, None
    with open(path) as f:
        record = json.load(f)
    txns = [Transaction(**t) for t in record["transactions"]]
    return record, txns
