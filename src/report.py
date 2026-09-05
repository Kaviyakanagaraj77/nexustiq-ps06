"""Combines the deterministic rule findings with the LLM narrative into the
final investigation report returned by the API."""
from .rules import run_investigation
from .llm import generate_investigation_narrative


def build_investigation_report(customer_record: dict, transactions: list) -> dict:
    findings = run_investigation(transactions)
    findings_dicts = [f.to_dict() for f in findings]

    narrative = generate_investigation_narrative(
        customer_record["customer_id"], customer_record["name"], findings_dicts
    )

    txn_by_id = {t.id: t.to_dict() for t in transactions}
    for f in findings_dicts:
        f["transactions"] = [txn_by_id[tid] for tid in f["transaction_ids"] if tid in txn_by_id]

    return {
        "customer_id": customer_record["customer_id"],
        "customer_name": customer_record["name"],
        "period": {
            "start": min((t.date for t in transactions), default=None),
            "end": max((t.date for t in transactions), default=None),
        },
        "transactions_reviewed": len(transactions),
        "needs_attention": len(findings_dicts) > 0,
        "overall_summary": narrative.get("overall_summary", ""),
        "findings": [
            {
                **f,
                "narrative": next(
                    (n["narrative"] for n in narrative.get("finding_narratives", [])
                     if n["rule_id"] == f["rule_id"]),
                    f["rationale"],
                ),
            }
            for f in findings_dicts
        ],
        "priority_order": narrative.get("priority_order", []),
        "priority_reasoning": narrative.get("priority_reasoning", ""),
        "narrative_source": narrative.get("narrative_source", "fallback_template"),
    }
