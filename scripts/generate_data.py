"""
Generates synthetic customer transaction histories for the fraud desk demo.

Produces data/customers/<customer_id>.json — several months of activity per
customer. Most customers are entirely routine. A couple have a deliberate,
realistic risk pattern woven in, so the investigation assistant has something
real to find (and something real to correctly ignore).

Run once: python scripts/generate_data.py
Output is committed to the repo — the app never regenerates it at runtime.
"""
import json
import os
import random
from datetime import datetime, timedelta


random.seed(42)

OUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "customers"
)

START_DATE = datetime(2025, 3, 1)
END_DATE = datetime(2025, 8, 31)

CHANNELS_DOMESTIC = [
    "UPI",
    "Card-POS",
    "NetBanking",
    "ATM",
]

MERCHANTS = [
    "Big Bazaar Retail",
    "IndianOil Petrol Pump",
    "Zomato",
    "Swiggy",
    "Apollo Pharmacy",
    "BSES Electricity Board",
    "Airtel Postpaid",
    "Amazon Retail",
    "BookMyShow",
    "Local Kirana Store",
    "Café Coffee Day",
    "Uber Trip",
    "Ola Trip",
    "Reliance Digital",
    "Croma Electronics",
]


# ---------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------

def daterange_days(start, end):
    days = (end - start).days
    return [
        start + timedelta(days=i)
        for i in range(days + 1)
    ]


def txn(
    tid,
    date,
    description,
    payee,
    amount,
    channel,
    ttype,
    time=None,
    location=None,
):
    if time is None:
        time = (
            f"{random.randint(7, 21):02d}:"
            f"{random.randint(0, 59):02d}"
        )

    return {
        "id": tid,
        "date": date.strftime("%Y-%m-%d"),
        "time": time,
        "description": description,
        "payee": payee,
        "amount": round(float(amount), 2),
        "channel": channel,
        "type": ttype,
        "location": location,
    }


def make_counter():
    value = [0]

    def counter():
        value[0] += 1
        return value[0]

    return counter


# ---------------------------------------------------------
# ROUTINE CUSTOMER
# ---------------------------------------------------------

def gen_routine_customer(
    cust_id,
    name,
    monthly_income,
    counter,
    home_location="Chennai",
):
    """
    Normal customer activity.

    These customers establish a predictable baseline:
    - salary through NEFT
    - rent through NetBanking
    - regular small UPI/card/ATM purchases
    """

    txns = []

    salary_payee = "Employer Payroll"

    recurring_merchants = random.sample(
        MERCHANTS,
        6
    )

    d = START_DATE

    while d <= END_DATE:

        # Monthly salary
        if d.day == 1:
            txns.append(
                txn(
                    f"{cust_id}-{counter():04d}",
                    d,
                    "Salary credit",
                    salary_payee,
                    monthly_income,
                    "NEFT",
                    "credit",
                    location=home_location,
                )
            )

        # Monthly rent
        if d.day == 3:
            txns.append(
                txn(
                    f"{cust_id}-{counter():04d}",
                    d,
                    "Rent payment",
                    "Landlord - Flat 4B",
                    monthly_income * 0.28,
                    "NetBanking",
                    "debit",
                    location=home_location,
                )
            )

        # Everyday spending
        if (
            d.weekday() in (1, 4, 6)
            and random.random() < 0.85
        ):
            merchant = random.choice(
                recurring_merchants
            )

            amount = round(
                random.uniform(150, 3500),
                2
            )

            channel = random.choice(
                CHANNELS_DOMESTIC
            )

            txns.append(
                txn(
                    f"{cust_id}-{counter():04d}",
                    d,
                    f"Payment to {merchant}",
                    merchant,
                    amount,
                    channel,
                    "debit",
                    location=home_location,
                )
            )

        d += timedelta(days=1)

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    return {
        "customer_id": cust_id,
        "name": name,
        "account_opened": "2021-06-15",
        "transactions": txns,
    }


# ---------------------------------------------------------
# CUSTOMER 1004
# NEW PAYEE BURST
# ---------------------------------------------------------

def gen_new_payee_customer(
    cust_id,
    name,
    monthly_income,
    counter,
):
    base = gen_routine_customer(
        cust_id,
        name,
        monthly_income,
        counter,
    )

    txns = base["transactions"]

    start = datetime(2025, 7, 14)

    payee = "Kavita Enterprises"

    offsets = [
        0,
        1,
        2,
        2,
        4,
        5,
    ]

    amounts = [
        42000,
        38500,
        45000,
        31000,
        47500,
        39900,
    ]

    for offset, amount in zip(
        offsets,
        amounts
    ):
        date = start + timedelta(
            days=offset
        )

        txns.append(
            txn(
                f"{cust_id}-{counter():04d}",
                date,
                f"Transfer to {payee}",
                payee,
                amount,
                "UPI",
                "debit",
                location="Chennai",
            )
        )

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    base["transactions"] = txns

    return base


# ---------------------------------------------------------
# CUSTOMER 1005
# LARGE + ODD HOURS + CHANNEL BREAK
# ---------------------------------------------------------

def gen_large_odd_customer(
    cust_id,
    name,
    monthly_income,
    counter,
):
    base = gen_routine_customer(
        cust_id,
        name,
        monthly_income,
        counter,
    )

    txns = base["transactions"]

    date1 = datetime(2025, 8, 9)

    txns.append(
        txn(
            f"{cust_id}-{counter():04d}",
            date1,
            "International wire transfer",
            "Zenith Trading Ltd (Singapore)",
            312000,
            "Wire",
            "debit",
            time="02:14",
            location="Chennai",
        )
    )

    date2 = datetime(2025, 8, 12)

    txns.append(
        txn(
            f"{cust_id}-{counter():04d}",
            date2,
            "International wire transfer",
            "Zenith Trading Ltd (Singapore)",
            98000,
            "Wire",
            "debit",
            time="03:02",
            location="Chennai",
        )
    )

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    base["transactions"] = txns

    return base


# ---------------------------------------------------------
# CUSTOMER 1006
# STRUCTURING
# ---------------------------------------------------------

def gen_structuring_customer(
    cust_id,
    name,
    monthly_income,
    counter,
):
    base = gen_routine_customer(
        cust_id,
        name,
        monthly_income,
        counter,
    )

    txns = base["transactions"]

    start = datetime(2025, 8, 5)

    amounts = [
        49000,
        48000,
        47000,
        46000,
    ]

    payees = [
        "Vendor Alpha",
        "Vendor Beta",
        "Vendor Gamma",
        "Vendor Delta",
    ]

    for i, (amount, payee) in enumerate(
        zip(amounts, payees)
    ):
        date = start + timedelta(days=i)

        txns.append(
            txn(
                f"{cust_id}-{counter():04d}",
                date,
                f"Business transfer to {payee}",
                payee,
                amount,
                "NEFT",
                "debit",
                location="Bengaluru",
            )
        )

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    base["transactions"] = txns

    return base


# ---------------------------------------------------------
# CUSTOMER 1007
# GEO-VELOCITY
# ---------------------------------------------------------

def gen_geo_velocity_customer(
    cust_id,
    name,
    monthly_income,
    counter,
):
    base = gen_routine_customer(
        cust_id,
        name,
        monthly_income,
        counter,
        home_location="Chennai",
    )

    txns = base["transactions"]

    first_time = datetime(
        2025,
        8,
        18,
        10,
        15,
    )

    second_time = datetime(
        2025,
        8,
        18,
        12,
        10,
    )

    txns.append(
        txn(
            f"{cust_id}-{counter():04d}",
            first_time,
            "Business payment",
            "Metro Supplies",
            18000,
            "UPI",
            "debit",
            time="10:15",
            location="Chennai",
        )
    )

    txns.append(
        txn(
            f"{cust_id}-{counter():04d}",
            second_time,
            "Business payment",
            "Metro Supplies",
            22000,
            "UPI",
            "debit",
            time="12:10",
            location="Delhi",
        )
    )

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    base["transactions"] = txns

    return base


# ---------------------------------------------------------
# CUSTOMER 1008
# DORMANT REACTIVATION + FREQUENCY SPIKE
# ---------------------------------------------------------

def gen_dormant_customer(
    cust_id,
    name,
    monthly_income,
    counter,
):
    base = gen_routine_customer(
        cust_id,
        name,
        monthly_income,
        counter,
    )

    txns = base["transactions"]

    # Create an explicit long dormant period.
    txns = [
        t
        for t in txns
        if not (
            "2025-06-01"
            <= t["date"]
            <= "2025-07-31"
        )
    ]

    # First transaction after dormancy.
    reactivation_date = datetime(
        2025,
        8,
        5,
    )

    txns.append(
        txn(
            f"{cust_id}-{counter():04d}",
            reactivation_date,
            "Large post-dormancy transfer",
            "Harbor Investments",
            45000,
            "NEFT",
            "debit",
            time="11:20",
            location="Mumbai",
        )
    )

    # Several transactions on one day to create
    # a clear frequency spike.
    spike_date = datetime(
        2025,
        8,
        20,
    )

    spike_amounts = [
        1200,
        1800,
        2400,
        3100,
        2200,
        1600,
    ]

    for i, amount in enumerate(
        spike_amounts
    ):
        txns.append(
            txn(
                f"{cust_id}-{counter():04d}",
                spike_date,
                "Rapid purchase activity",
                f"Merchant {i + 1}",
                amount,
                "UPI",
                "debit",
                time=f"{10 + i:02d}:15",
                location="Mumbai",
            )
        )

    txns.sort(
        key=lambda t: (t["date"], t["time"])
    )

    base["transactions"] = txns

    return base


# ---------------------------------------------------------
# CUSTOMER LIST
# ---------------------------------------------------------

CUSTOMERS = [
    (
        "CUST-1001",
        "Ananya Rao",
        68000,
        gen_routine_customer,
    ),
    (
        "CUST-1002",
        "Vikram Shetty",
        52000,
        gen_routine_customer,
    ),
    (
        "CUST-1003",
        "Farida Sheikh",
        91000,
        gen_routine_customer,
    ),
    (
        "CUST-1004",
        "Ramesh Iyer",
        45000,
        gen_new_payee_customer,
    ),
    (
        "CUST-1005",
        "Neha Kapoor",
        120000,
        gen_large_odd_customer,
    ),
    (
        "CUST-1006",
        "Arjun Mehta",
        75000,
        gen_structuring_customer,
    ),
    (
        "CUST-1007",
        "Priya Nair",
        82000,
        gen_geo_velocity_customer,
    ),
    (
        "CUST-1008",
        "Sanjay Verma",
        95000,
        gen_dormant_customer,
    ),
]


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    os.makedirs(
        OUT_DIR,
        exist_ok=True
    )

    # Remove old customer JSON files first.
    for filename in os.listdir(OUT_DIR):
        if filename.endswith(".json"):
            os.remove(
                os.path.join(
                    OUT_DIR,
                    filename
                )
            )

    for (
        cust_id,
        name,
        income,
        generator,
    ) in CUSTOMERS:

        counter = make_counter()

        record = generator(
            cust_id,
            name,
            income,
            counter,
        )

        path = os.path.join(
            OUT_DIR,
            f"{cust_id}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                record,
                f,
                indent=2,
            )

        print(
            f"wrote {path} "
            f"({len(record['transactions'])} transactions)"
        )


if __name__ == "__main__":
    main()