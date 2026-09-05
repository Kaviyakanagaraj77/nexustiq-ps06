"""
Deterministic transaction risk rules.

Nothing in this file calls an LLM. Every number here is computed directly
from the customer's own transaction history, and every finding carries the
exact transaction IDs and the arithmetic behind it, so the report layer can
cite it and the LLM layer can narrate it without inventing anything.

Baselines are look-back only: a transaction is compared against what was
already established strictly before it (>= LOOKBACK_DAYS earlier), never
against transactions that happened afterwards, and never against the
transaction currently being evaluated. This avoids the circular trap of
using an anomaly to define what's "normal".
"""
from collections import defaultdict
from datetime import datetime
from statistics import median
from .models import Transaction, Finding

LOOKBACK_DAYS = 14
BURST_WINDOW_DAYS = 7
BURST_MIN_COUNT = 3
LARGE_TRANSFER_FLOOR = 100_000.0       # absolute floor, INR
LARGE_TRANSFER_MEDIAN_MULTIPLE = 6.0
ODD_HOURS_RANGE = range(0, 6)           # 00:00–05:59
ODD_HOURS_AMOUNT_FLOOR_MULTIPLE = 1.5
PATTERN_BREAK_MEDIAN_MULTIPLE = 3.0


def _parse(d: str) -> datetime:
    return datetime.strptime(d, "%Y-%m-%d")


def _debit_baseline_stats(debits: list) -> dict:
    amounts = [t.amount for t in debits] or [0.0]
    return {
        "median": median(amounts),
        "count": len(debits),
    }


def _known_before(txns_sorted: list, cutoff_date: datetime, key_fn) -> set:
    """Values of key_fn(t) seen at least twice, strictly before cutoff_date
    minus LOOKBACK_DAYS — i.e. genuinely established, not a fluke."""
    counts = defaultdict(int)
    for t in txns_sorted:
        if (cutoff_date - _parse(t.date)).days >= LOOKBACK_DAYS:
            counts[key_fn(t)] += 1
    return {k for k, c in counts.items() if c >= 2}


def rule_large_transfer(debits: list, baseline: dict) -> Finding:
    threshold = max(LARGE_TRANSFER_FLOOR, baseline["median"] * LARGE_TRANSFER_MEDIAN_MULTIPLE)
    hits = [t for t in debits if t.amount >= threshold]
    if not hits:
        return None
    return Finding(
        rule_id="LARGE_TRANSFER",
        rule_name="Unusually large transfer",
        severity="high",
        transaction_ids=[t.id for t in hits],
        rationale=(
            f"{len(hits)} debit(s) at or above ₹{threshold:,.0f}, which is "
            f"{LARGE_TRANSFER_MEDIAN_MULTIPLE:.0f}x this customer's own median "
            f"debit of ₹{baseline['median']:,.0f} (floor ₹{LARGE_TRANSFER_FLOOR:,.0f})."
        ),
        metric={"threshold": round(threshold, 2), "customer_median_debit": round(baseline["median"], 2)},
    )


def rule_new_payee_burst(debits_sorted: list) -> list:
    """Flags payees that appear for the first time and receive 3+ payments
    within a short window shortly after — a mule/funnel signature."""
    findings = []
    by_payee = defaultdict(list)
    for t in debits_sorted:
        by_payee[t.payee].append(t)

    for payee, txns in by_payee.items():
        txns = sorted(txns, key=lambda t: t.date)
        first_date = _parse(txns[0].date)
        # window of transactions to this payee within BURST_WINDOW_DAYS of the first
        window = [t for t in txns if (_parse(t.date) - first_date).days <= BURST_WINDOW_DAYS]
        if len(window) >= BURST_MIN_COUNT:
            total = sum(t.amount for t in window)
            findings.append(Finding(
                rule_id="NEW_PAYEE_BURST",
                rule_name="Burst of payments to a newly added payee",
                severity="high",
                transaction_ids=[t.id for t in window],
                rationale=(
                    f"{len(window)} payments totalling ₹{total:,.0f} were sent to "
                    f"'{payee}' within {BURST_WINDOW_DAYS} days of the first-ever "
                    f"payment to that payee, dated {txns[0].date}."
                ),
                metric={"payee": payee, "count": len(window), "total": round(total, 2),
                        "window_days": BURST_WINDOW_DAYS},
            ))
    return findings


def rule_odd_hours(debits_sorted: list) -> list:
    findings = []
    for t in debits_sorted:
        if t.hour not in ODD_HOURS_RANGE:
            continue
        cutoff = _parse(t.date)
        typical_hours = _known_before(debits_sorted, cutoff, key_fn=lambda x: x.hour)
        median_amt = median([x.amount for x in debits_sorted if x.id != t.id] or [0.0])
        if t.hour in typical_hours:
            continue  # this hour is actually normal for this customer
        if t.amount < median_amt * ODD_HOURS_AMOUNT_FLOOR_MULTIPLE:
            continue  # small odd-hours spend isn't worth an investigator's time
        findings.append(Finding(
            rule_id="ODD_HOURS",
            rule_name="Odd-hours activity outside this customer's pattern",
            severity="medium",
            transaction_ids=[t.id],
            rationale=(
                f"Transaction at {t.time} on {t.date} (₹{t.amount:,.0f}) falls between "
                f"midnight and 6 AM, an hour this customer has no established history of "
                f"transacting in, and the amount exceeds their typical debit size."
            ),
            metric={"hour": t.hour, "amount": t.amount, "customer_median_debit": round(median_amt, 2)},
        ))
    return findings


def rule_pattern_break_channel(debits_sorted: list) -> list:
    findings = []
    for t in debits_sorted:
        cutoff = _parse(t.date)
        known_channels = _known_before(debits_sorted, cutoff, key_fn=lambda x: x.channel)
        if not known_channels:
            continue  # not enough history yet to call anything a break
        if t.channel in known_channels:
            continue
        median_amt = median([x.amount for x in debits_sorted if x.id != t.id] or [0.0])
        if t.amount < median_amt * PATTERN_BREAK_MEDIAN_MULTIPLE:
            continue
        findings.append(Finding(
            rule_id="CHANNEL_PATTERN_BREAK",
            rule_name="Payment channel this customer has never used before",
            severity="medium",
            transaction_ids=[t.id],
            rationale=(
                f"This customer's established channels are {sorted(known_channels)}, but "
                f"this ₹{t.amount:,.0f} transaction on {t.date} went through '{t.channel}', "
                f"a channel with no prior history for this account, at "
                f"{PATTERN_BREAK_MEDIAN_MULTIPLE:.0f}x their typical debit size."
            ),
            metric={"channel": t.channel, "known_channels": sorted(known_channels), "amount": t.amount},
        ))
    return findings


def run_investigation(transactions: list) -> list:
    """Runs every rule over one customer's history and returns the raw
    Finding objects, deduplicated by (rule_id, transaction set)."""
    debits_sorted = sorted([t for t in transactions if t.type == "debit"], key=lambda t: (t.date, t.time))
    baseline = _debit_baseline_stats(debits_sorted)

    findings = []
    lt = rule_large_transfer(debits_sorted, baseline)
    if lt:
        findings.append(lt)
    findings.extend(rule_new_payee_burst(debits_sorted))
    findings.extend(rule_odd_hours(debits_sorted))
    findings.extend(rule_pattern_break_channel(debits_sorted))

    # Merge findings that share every transaction ID with a higher-severity
    # one, so a burst that's already flagged as a large-transfer set doesn't
    # show up twice with the same evidence.
    seen_txn_sets = []
    merged = []
    for f in sorted(findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity]):
        key = frozenset(f.transaction_ids)
        if key in seen_txn_sets:
            continue
        seen_txn_sets.append(key)
        merged.append(f)
    return merged
