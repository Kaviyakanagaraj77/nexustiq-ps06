from collections import defaultdict
from datetime import datetime
from statistics import median
from math import radians, sin, cos, sqrt, atan2


# ============================================================
# CONFIGURATION
# ============================================================

LOOKBACK_DAYS = 14

BURST_WINDOW_DAYS = 7
BURST_MIN_COUNT = 3
BURST_MIN_TOTAL = 100_000.0
BURST_MIN_SINGLE_PAYMENT = 40_000.0

LARGE_TRANSFER_FLOOR = 100_000.0
LARGE_TRANSFER_MEDIAN_MULTIPLE = 6.0

ODD_HOURS_RANGE = range(0, 6)
ODD_HOURS_AMOUNT_MULTIPLE = 1.5

PATTERN_BREAK_MEDIAN_MULTIPLE = 3.0
PATTERN_BREAK_MIN_AMOUNT = 40_000.0

STRUCTURING_MIN_COUNT = 3
STRUCTURING_MIN_AMOUNT = 40_000.0
STRUCTURING_MAX_AMOUNT = 50_000.0
STRUCTURING_WINDOW_DAYS = 5

GEO_DISTANCE_KM = 500.0
GEO_TIME_HOURS = 3.0

DORMANT_GAP_DAYS = 45
DORMANT_AMOUNT_MULTIPLE = 3.0

FREQUENCY_WINDOW_DAYS = 30
FREQUENCY_SPIKE_MULTIPLE = 4.0
FREQUENCY_MIN_HISTORY = 5
FREQUENCY_MIN_CURRENT_COUNT = 4


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_datetime(transaction):
    return datetime.strptime(
        f"{transaction.date} {transaction.time}",
        "%Y-%m-%d %H:%M"
    )


def _median_amount(transactions):
    if not transactions:
        return 0.0

    return median([float(t.amount) for t in transactions])


def _finding(
    rule_id,
    severity,
    title,
    explanation,
    transaction_ids,
    metrics=None
):
    return {
        "rule_id": rule_id,
        "rule_name": title,
        "title": title,
        "severity": severity,
        "explanation": explanation,
        "rationale": explanation,
        "transaction_ids": transaction_ids,
        "metrics": metrics or {},
    }


# ============================================================
# R1 - LARGE TRANSFER
# ============================================================

def rule_large_transfer(debits_sorted: list) -> list:
    findings = []

    if len(debits_sorted) < 3:
        return findings

    for i, transaction in enumerate(debits_sorted):

        history = debits_sorted[:i]

        if len(history) < 3:
            continue

        historical_median = _median_amount(history)

        threshold = max(
            LARGE_TRANSFER_FLOOR,
            historical_median * LARGE_TRANSFER_MEDIAN_MULTIPLE
        )

        if transaction.amount >= threshold:

            findings.append(
                _finding(
                    rule_id="R1",
                    severity="high",
                    title="Unusually large transfer",
                    explanation=(
                        f"Transaction {transaction.id} for "
                        f"₹{transaction.amount:,.2f} exceeds the "
                        f"large-transfer threshold of "
                        f"₹{threshold:,.2f} based on prior activity."
                    ),
                    transaction_ids=[transaction.id],
                    metrics={
                        "transaction_amount": transaction.amount,
                        "historical_median": round(
                            historical_median, 2
                        ),
                        "threshold": round(threshold, 2),
                    },
                )
            )

    return findings


# ============================================================
# R2 - NEW PAYEE BURST
# ============================================================

def rule_new_payee_burst(debits_sorted: list) -> list:
    findings = []

    payee_history = defaultdict(list)

    for transaction in debits_sorted:

        payee = transaction.payee

        previous_transactions = payee_history[payee]

        if previous_transactions:
            payee_history[payee].append(transaction)
            continue

        window_transactions = [
            x
            for x in debits_sorted
            if x.payee == payee
            and 0 <= (
                _parse_date(x.date)
                - _parse_date(transaction.date)
            ).days <= BURST_WINDOW_DAYS
        ]

        if len(window_transactions) >= BURST_MIN_COUNT:

            total = sum(
                x.amount
                for x in window_transactions
            )

            maximum = max(
                x.amount
                for x in window_transactions
            )

            if (
                total >= BURST_MIN_TOTAL
                or maximum >= BURST_MIN_SINGLE_PAYMENT
            ):

                findings.append(
                    _finding(
                        rule_id="R2",
                        severity="high",
                        title="New payee payment burst",
                        explanation=(
                            f"Multiple payments to newly observed payee "
                            f"{payee} occurred within "
                            f"{BURST_WINDOW_DAYS} days, totaling "
                            f"₹{total:,.2f}."
                        ),
                        transaction_ids=[
                            x.id for x in window_transactions
                        ],
                        metrics={
                            "payee": payee,
                            "count": len(window_transactions),
                            "total": round(total, 2),
                            "maximum_payment": round(maximum, 2),
                        },
                    )
                )

        payee_history[payee].append(transaction)

    return findings


# ============================================================
# R3 - ODD HOURS
# ============================================================

def rule_odd_hours(debits_sorted: list) -> list:
    findings = []

    if len(debits_sorted) < 3:
        return findings

    normal_hours = defaultdict(list)

    for transaction in debits_sorted:

        hour = int(transaction.time.split(":")[0])

        if hour not in ODD_HOURS_RANGE:
            normal_hours[transaction.payee].append(
                transaction
            )

    suspicious = []

    for i, transaction in enumerate(debits_sorted):

        hour = int(transaction.time.split(":")[0])

        if hour not in ODD_HOURS_RANGE:
            continue

        history = debits_sorted[:i]

        if len(history) < 3:
            continue

        historical_median = _median_amount(history)

        if historical_median <= 0:
            continue

        if transaction.amount < (
            historical_median * ODD_HOURS_AMOUNT_MULTIPLE
        ):
            continue

        previous_odd_hours = [
            x
            for x in history
            if int(x.time.split(":")[0])
            in ODD_HOURS_RANGE
        ]

        if previous_odd_hours:
            continue

        suspicious.append(transaction)

    if suspicious:

        total = sum(
            x.amount for x in suspicious
        )

        findings.append(
            _finding(
                rule_id="R3",
                severity="medium",
                title="Odd-hours transaction activity",
                explanation=(
                    f"{len(suspicious)} transaction(s) occurred "
                    f"during previously unestablished odd hours, "
                    f"with a combined value of ₹{total:,.2f}."
                ),
                transaction_ids=[
                    x.id for x in suspicious
                ],
                metrics={
                    "count": len(suspicious),
                    "total": round(total, 2),
                },
            )
        )

    return findings


# ============================================================
# R4 - PATTERN BREAK / CHANNEL
# ============================================================

def rule_pattern_break_channel(debits_sorted: list) -> list:
    findings = []

    if len(debits_sorted) < 3:
        return findings

    known_channels = defaultdict(int)

    for transaction in debits_sorted:
        known_channels[transaction.channel] += 1

    suspicious_by_channel = defaultdict(list)

    for i, transaction in enumerate(debits_sorted):

        history = debits_sorted[:i]

        if len(history) < 3:
            continue

        channel_count = sum(
            1
            for x in history
            if x.channel == transaction.channel
        )

        if channel_count >= 2:
            continue

        historical_median = _median_amount(history)

        if historical_median <= 0:
            continue

        if transaction.amount < PATTERN_BREAK_MIN_AMOUNT:
            continue

        if transaction.amount < (
            historical_median * PATTERN_BREAK_MEDIAN_MULTIPLE
        ):
            continue

        suspicious_by_channel[
            transaction.channel
        ].append(transaction)

    for channel, transactions in suspicious_by_channel.items():

        total = sum(
            x.amount for x in transactions
        )

        findings.append(
            _finding(
                rule_id="R4",
                severity="medium",
                title="New or unestablished transaction channel",
                explanation=(
                    f"Transaction activity through {channel} "
                    f"is not established in the customer's prior "
                    f"pattern and involves unusually large amounts "
                    f"totaling ₹{total:,.2f}."
                ),
                transaction_ids=[
                    x.id for x in transactions
                ],
                metrics={
                    "channel": channel,
                    "count": len(transactions),
                    "total": round(total, 2),
                },
            )
        )

    return findings


# ============================================================
# R5 - STRUCTURING / NARROW AMOUNT BAND
# ============================================================

def rule_structuring(debits_sorted: list) -> list:
    findings = []

    qualifying = [
        t
        for t in debits_sorted
        if STRUCTURING_MIN_AMOUNT
        <= t.amount
        <= STRUCTURING_MAX_AMOUNT
    ]

    covered_ids = set()

    for i, transaction in enumerate(qualifying):

        if transaction.id in covered_ids:
            continue

        start_date = _parse_date(transaction.date)

        window = [
            x
            for x in qualifying
            if 0 <= (
                _parse_date(x.date) - start_date
            ).days <= STRUCTURING_WINDOW_DAYS
        ]

        if len(window) < STRUCTURING_MIN_COUNT:
            continue

        transaction_ids = [
            x.id for x in window
        ]

        total = sum(
            x.amount for x in window
        )

        findings.append(
            _finding(
                rule_id="R5",
                severity="high",
                title="Narrow amount-band transaction pattern",
                explanation=(
                    f"{len(window)} transactions fall within the "
                    f"₹{STRUCTURING_MIN_AMOUNT:,.0f}-₹"
                    f"{STRUCTURING_MAX_AMOUNT:,.0f} range within "
                    f"{STRUCTURING_WINDOW_DAYS} days, totaling "
                    f"₹{total:,.2f}."
                ),
                transaction_ids=transaction_ids,
                metrics={
                    "count": len(window),
                    "total": round(total, 2),
                    "minimum_amount": min(
                        x.amount for x in window
                    ),
                    "maximum_amount": max(
                        x.amount for x in window
                    ),
                },
            )
        )

        covered_ids.update(transaction_ids)

    return findings


# ============================================================
# R6 - GEO VELOCITY
# ============================================================

CITY_COORDINATES = {
    "Chennai": (13.0827, 80.2707),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bengaluru": (12.9716, 77.5946),
    "Kolkata": (22.5726, 88.3639),
    "Hyderabad": (17.3850, 78.4867),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Singapore": (1.3521, 103.8198),
}


def _distance_km(location_a, location_b):

    if (
        location_a not in CITY_COORDINATES
        or location_b not in CITY_COORDINATES
    ):
        return None

    lat1, lon1 = CITY_COORDINATES[location_a]
    lat2, lon2 = CITY_COORDINATES[location_b]

    earth_radius = 6371.0

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        +
        cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


def rule_geo_velocity(debits_sorted: list) -> list:
    findings = []

    for previous, current in zip(
        debits_sorted,
        debits_sorted[1:]
    ):

        if not previous.location or not current.location:
            continue

        distance = _distance_km(
            previous.location,
            current.location
        )

        if distance is None:
            continue

        previous_dt = _parse_datetime(previous)
        current_dt = _parse_datetime(current)

        hours = (
            current_dt - previous_dt
        ).total_seconds() / 3600

        if hours <= 0:
            continue

        if (
            distance > GEO_DISTANCE_KM
            and hours <= GEO_TIME_HOURS
        ):

            findings.append(
                _finding(
                    rule_id="R6",
                    severity="high",
                    title="Geographic velocity anomaly",
                    explanation=(
                        f"Transaction activity moved from "
                        f"{previous.location} to "
                        f"{current.location}, approximately "
                        f"{distance:,.0f} km apart in "
                        f"{hours:.2f} hours."
                    ),
                    transaction_ids=[
                        previous.id,
                        current.id,
                    ],
                    metrics={
                        "distance_km": round(
                            distance, 2
                        ),
                        "time_hours": round(
                            hours, 2
                        ),
                        "from": previous.location,
                        "to": current.location,
                    },
                )
            )

    return findings


# ============================================================
# R7 - DORMANT REACTIVATION
# ============================================================

def rule_dormant_reactivation(debits_sorted: list) -> list:
    findings = []

    if len(debits_sorted) < 4:
        return findings

    for i in range(1, len(debits_sorted)):

        current = debits_sorted[i]

        previous = debits_sorted[i - 1]

        gap_days = (
            _parse_date(current.date)
            - _parse_date(previous.date)
        ).days

        # Check for a genuine dormant period
        if gap_days < DORMANT_GAP_DAYS:
            continue

        # Transactions before the dormant period
        history = debits_sorted[:i]

        if len(history) < 3:
            continue

        customer_median = _median_amount(history)

        if customer_median <= 0:
            continue

        # Current transaction must be significantly larger
        if current.amount < (
            customer_median * DORMANT_AMOUNT_MULTIPLE
        ):
            continue

        findings.append(
            _finding(
                rule_id="R7",
                severity="medium",
                title="Dormant account reactivation",
                explanation=(
                    f"Transaction {current.id} occurred after "
                    f"a {gap_days}-day gap in debit activity and "
                    f"is {current.amount / customer_median:.1f}x "
                    f"the historical median debit amount."
                ),
                transaction_ids=[
                    current.id
                ],
                metrics={
                    "gap_days": gap_days,
                    "transaction_amount": current.amount,
                    "historical_median": round(
                        customer_median,
                        2
                    ),
                    "amount_multiple": round(
                        current.amount / customer_median,
                        2
                    ),
                },
            )
        )

    return findings


# ============================================================
# R8 - FREQUENCY SPIKE
# ============================================================

def rule_frequency_spike(debits_sorted: list) -> list:
    findings = []

    if len(debits_sorted) < 10:
        return findings

    dates = [
        _parse_date(t.date)
        for t in debits_sorted
    ]

    for i, transaction in enumerate(debits_sorted):

        current_date = _parse_date(transaction.date)

        window_start = (
            current_date
            - __import__("datetime").timedelta(
                days=FREQUENCY_WINDOW_DAYS
            )
        )

        history = [
            t
            for t in debits_sorted[:i]
            if window_start
            <= _parse_date(t.date)
            < current_date
        ]

        if len(history) < FREQUENCY_MIN_HISTORY:
            continue

        current_day_transactions = [
            t
            for t in debits_sorted
            if _parse_date(t.date) == current_date
        ]

        current_count = len(current_day_transactions)

        if current_count < FREQUENCY_MIN_CURRENT_COUNT:
            continue

        days_with_history = max(
            (
                current_date - window_start
            ).days,
            1
        )

        historical_average = (
            len(history)
            / days_with_history
        )

        if historical_average <= 0:
            continue

        if current_count < (
            historical_average
            * FREQUENCY_SPIKE_MULTIPLE
        ):
            continue

        transaction_ids = [
            t.id
            for t in current_day_transactions
        ]

        total = sum(
            t.amount
            for t in current_day_transactions
        )

        findings.append(
            _finding(
                rule_id="R8",
                severity="low",
                title="Transaction frequency spike",
                explanation=(
                    f"{current_count} debit transactions occurred "
                    f"on {current_date}, compared with a trailing "
                    f"average of {historical_average:.2f} transactions "
                    f"per day."
                ),
                transaction_ids=transaction_ids,
                metrics={
                    "current_count": current_count,
                    "historical_average": round(
                        historical_average,
                        2
                    ),
                    "total": round(total, 2),
                },
            )
        )

        break

    return findings


# ============================================================
# MAIN INVESTIGATION ENGINE
# ============================================================

def run_investigation(transactions: list) -> list:

    debits = [
        t
        for t in transactions
        if t.type.lower() == "debit"
    ]

    debits_sorted = sorted(
        debits,
        key=lambda t: _parse_datetime(t)
    )

    findings = []

    findings.extend(
        rule_large_transfer(debits_sorted)
    )

    findings.extend(
        rule_new_payee_burst(debits_sorted)
    )

    findings.extend(
        rule_odd_hours(debits_sorted)
    )

    findings.extend(
        rule_pattern_break_channel(debits_sorted)
    )

    findings.extend(
        rule_structuring(debits_sorted)
    )

    findings.extend(
        rule_geo_velocity(debits_sorted)
    )

    findings.extend(
        rule_dormant_reactivation(debits_sorted)
    )

    findings.extend(
        rule_frequency_spike(debits_sorted)
    )

    severity_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    findings.sort(
        key=lambda finding: (
            severity_order.get(
                finding["severity"],
                99
            ),
            finding["rule_id"]
        )
    )

    # Remove exact duplicate findings
    unique_findings = []

    seen = set()

    for finding in findings:

        key = (
            finding["rule_id"],
            frozenset(
                finding["transaction_ids"]
            )
        )

        if key in seen:
            continue

        seen.add(key)

        unique_findings.append(finding)

    return unique_findings