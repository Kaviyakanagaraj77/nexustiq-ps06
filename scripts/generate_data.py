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

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "customers")
START_DATE = datetime(2025, 3, 1)
END_DATE = datetime(2025, 8, 31)

CHANNELS_DOMESTIC = ["UPI", "Card-POS", "NetBanking", "ATM"]
MERCHANTS = [
    "Big Bazaar Retail", "IndianOil Petrol Pump", "Zomato", "Swiggy",
    "Apollo Pharmacy", "BSES Electricity Board", "Airtel Postpaid",
    "Amazon Retail", "BookMyShow", "Local Kirana Store", "Café Coffee Day",
    "Uber Trip", "Ola Trip", "Reliance Digital", "Croma Electronics",
]


def daterange_days(start, end):
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def txn(tid, date, description, payee, amount, channel, ttype):
    return {
        "id": tid,
        "date": date.strftime("%Y-%m-%d"),
        "time": f"{random.randint(7, 21):02d}:{random.randint(0, 59):02d}",
        "description": description,
        "payee": payee,
        "amount": round(amount, 2),
        "channel": channel,
        "type": ttype,
    }


def gen_routine_customer(cust_id, name, monthly_income, counter):
    """A customer with an unremarkable, repeating pattern. No anomalies."""
    txns = []
    d = START_DATE
    salary_payee = "Employer Payroll"
    recurring_merchants = random.sample(MERCHANTS, 6)
    while d <= END_DATE:
        # monthly salary credit around the 1st
        if d.day == 1:
            txns.append(txn(f"{cust_id}-{counter():04d}", d, "Salary credit",
                             salary_payee, monthly_income, "NEFT", "credit"))
        # rent/utility debit around the 3rd
        if d.day == 3:
            txns.append(txn(f"{cust_id}-{counter():04d}", d, "Rent payment",
                             "Landlord - Flat 4B", monthly_income * 0.28,
                             "NetBanking", "debit"))
        # a handful of everyday spends per week
        if d.weekday() in (1, 4, 6) and random.random() < 0.85:
            merchant = random.choice(recurring_merchants)
            amt = round(random.uniform(150, 3500), 2)
            txns.append(txn(f"{cust_id}-{counter():04d}", d, f"Payment to {merchant}",
                             merchant, amt, random.choice(CHANNELS_DOMESTIC), "debit"))
        d += timedelta(days=1)
    txns.sort(key=lambda t: (t["date"], t["time"]))
    return {
        "customer_id": cust_id,
        "name": name,
        "account_opened": "2021-06-15",
        "transactions": txns,
    }


def gen_mule_pattern_customer(cust_id, name, monthly_income, counter):
    """
    Routine baseline, then a burst of payments to a brand-new payee over a
    short window — classic money-mule / romance-scam funnel signature.
    """
    base = gen_routine_customer(cust_id, name, monthly_income, counter)
    txns = base["transactions"]

    burst_start = datetime(2025, 7, 14)
    new_payee = "Kavita Enterprises"
    offsets = [0, 1, 2, 2, 4, 5]
    amounts = [42000, 38500, 45000, 31000, 47500, 39900]
    for off, amt in zip(offsets, amounts):
        d = burst_start + timedelta(days=off)
        txns.append(txn(f"{cust_id}-{counter():04d}", d,
                         f"Transfer to {new_payee}", new_payee, amt, "UPI", "debit"))

    txns.sort(key=lambda t: (t["date"], t["time"]))
    base["transactions"] = txns
    return base


def gen_odd_hours_customer(cust_id, name, monthly_income, counter):
    """
    Routine daytime customer who never uses wire transfers, then makes one
    large international wire at 2 AM — a channel deviation + odd-hours
    combination worth a closer look.
    """
    base = gen_routine_customer(cust_id, name, monthly_income, counter)
    txns = base["transactions"]

    d = datetime(2025, 8, 9)
    t = {
        "id": f"{cust_id}-{counter():04d}",
        "date": d.strftime("%Y-%m-%d"),
        "time": "02:14",
        "description": "International wire transfer",
        "payee": "Zenith Trading Ltd (Singapore)",
        "amount": 312000.00,
        "channel": "Wire",
        "type": "debit",
    }
    txns.append(t)

    # a second, smaller odd-hours wire three days later to the same new payee
    d2 = d + timedelta(days=3)
    t2 = {
        "id": f"{cust_id}-{counter():04d}",
        "date": d2.strftime("%Y-%m-%d"),
        "time": "03:02",
        "description": "International wire transfer",
        "payee": "Zenith Trading Ltd (Singapore)",
        "amount": 98000.00,
        "channel": "Wire",
        "type": "debit",
    }
    txns.append(t2)

    txns.sort(key=lambda t: (t["date"], t["time"]))
    base["transactions"] = txns
    return base


def make_counter():
    n = [0]

    def counter():
        n[0] += 1
        return n[0]
    return counter


CUSTOMERS = [
    ("CUST-1001", "Ananya Rao", 68000, gen_routine_customer),
    ("CUST-1002", "Vikram Shetty", 52000, gen_routine_customer),
    ("CUST-1003", "Farida Sheikh", 91000, gen_routine_customer),
    ("CUST-1004", "Ramesh Iyer", 45000, gen_mule_pattern_customer),
    ("CUST-1005", "Neha Kapoor", 120000, gen_odd_hours_customer),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for cust_id, name, income, generator in CUSTOMERS:
        counter = make_counter()
        record = generator(cust_id, name, income, counter)
        path = os.path.join(OUT_DIR, f"{cust_id}.json")
        with open(path, "w") as f:
            json.dump(record, f, indent=2)
        print(f"wrote {path} ({len(record['transactions'])} transactions)")


if __name__ == "__main__":
    main()
