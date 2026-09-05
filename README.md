# Ledgerwatch — Transaction Risk Investigation Assistant

## NexusTiQ24 · PS06

Ledgerwatch is a transaction risk investigation assistant designed to help investigators review a customer's transaction history and identify activity that may require attention.

The system combines deterministic risk detection with Gemini-generated investigation narratives while keeping transaction evidence grounded in the customer's supplied transaction history.

---

## Problem Statement

Investigators may need to review months of transaction activity to identify unusual patterns such as:

- Unusually large transfers
- Bursts involving newly added payees
- Activity during unusual hours
- Transactions that break an established customer pattern
- Multiple transactions within a short period
- Geographic transaction velocity
- Activity following a dormant period
- Sudden transaction-frequency increases

Manually identifying these patterns across a large transaction history can be time-consuming.

Ledgerwatch provides a structured investigation workflow that highlights potentially relevant activity and shows the exact transactions supporting each finding.

---

## Solution

Ledgerwatch follows this investigation pipeline:

```text
Customer Transaction History
            ↓
Deterministic Risk Engine
            ↓
Evidence-Based Findings
            ↓
Gemini Investigation Narrative
            ↓
Investigator Dashboard