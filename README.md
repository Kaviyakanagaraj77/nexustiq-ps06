TRACK_ID=PS06

# Ledgerwatch — Transaction Risk Investigation Assistant

A fraud-desk assistant that reviews one customer's transaction history at a
time, runs it against a small set of deterministic risk rules, and produces
an investigation report an analyst can actually act on — cited transactions,
plain-English reasoning, and a priority order, with the judgement of whether
anything happened at all left explicitly to the human investigator.

## What it does

1. **Loads a customer's transaction history** (date, description, payee,
   amount, channel — a few months of activity per customer).
2. **Runs four deterministic rules** over it, each computed only from that
   customer's *own* history, using a look-back baseline so a rule is never
   evaluated against data that includes the anomaly itself:
   - **Unusually large transfer** — a debit far above the customer's own
     median debit size.
   - **Burst of payments to a newly added payee** — three or more payments
     to a payee within days of the first-ever payment to them (the
     classic money-mule / funnel signature).
   - **Odd-hours activity** — a transaction between midnight and 6 AM,
     outside this specific customer's established active hours, above their
     typical amount.
   - **Payment channel this customer has never used before** — e.g. an
     account that has only ever used UPI and card payments suddenly sends
     an international wire.
3. **Passes the rule engine's findings — never raw transactions — to Gemini**
   to turn into a short, investigator-facing narrative and a priority order.
   Gemini is told explicitly which transaction IDs it may reference and is
   forbidden from asserting that fraud occurred.
4. **If the Gemini call fails or no API key is configured**, the report
   still generates from a deterministic template built straight from the
   rule findings — the app degrades gracefully instead of breaking or
   silently doing nothing.
5. **When nothing triggers**, the report says exactly that — a system that
   finds concern in every routine history is as useless as one that finds
   none.

## Why this design

The brief's evaluation criteria reward "a clear separation between LLM
reasoning and deterministic logic." Here that separation is a hard module
boundary: `src/rules.py` contains zero LLM calls and is the *only* place
that decides whether something is risky. `src/llm.py` contains zero risk
logic and can only narrate what `rules.py` already found, grounded in the
exact transaction IDs it's handed. `src/report.py` wires them together.
This also means the rule engine is independently testable and the whole
app still produces a correct, cited report even with zero AI calls.

## Data

No real customer data is used. `scripts/generate_data.py` (seeded, so it's
reproducible) generates five synthetic customers under `data/customers/`:

- **CUST-1001, 1002, 1003** — entirely routine salaries, rent, and everyday
  spending. No anomalies. These exist specifically to prove the assistant
  stays quiet on ordinary histories.
- **CUST-1004** — a routine baseline plus a burst of payments to a payee
  that didn't exist in their history before that week (mule/funnel pattern).
- **CUST-1005** — a routine baseline plus two international wire transfers
  at 2–3 AM through a channel the customer has never used, one of which is
  also a large-transfer outlier. Demonstrates two independent rules firing
  on related but distinct evidence.

The generated JSON is committed under `data/customers/` — the app never
regenerates it at startup.

## How to run

```
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000. Set `GEMINI_API_KEY` in the environment to
get LLM-narrated reports; without it, the app still runs and serves
rule-grounded reports via the deterministic fallback template (visible in
the report's `narrative_source` field).

## Demo suggestions

- **Normal case:** open CUST-1001, 1002, or 1003, run the investigation,
  and show the "nothing flagged" verdict with the ledger underneath it —
  proving the system doesn't cry wolf.
- **Difficult case:** open CUST-1005 and show two distinct findings (large
  transfer + odd-hours/channel break) tied to two different transactions a
  week apart, each cited to its exact ledger row, with a priority order
  explaining which to check first.

## What's deliberately left to the human

The system never states that fraud occurred and never takes action on an
account. It ranks and explains; an investigator decides. This mirrors the
problem statement's explicit instruction that judgement stays with the
investigator.
