from src.rules import run_investigation
from src.llm import generate_investigation_narrative


def build_investigation_report(customer, transactions):
    # Run deterministic risk rules
    findings = run_investigation(transactions)

    # findings are already dictionaries
    findings_dicts = findings

    customer_id = customer["customer_id"]
    customer_name = customer["name"]
    account_opened = customer["account_opened"]

    # Generate investigator-facing narrative
    narrative_result = generate_investigation_narrative(
        customer_id=customer_id,
        customer_name=customer_name,
        findings=findings_dicts
    )

    # Calculate review period start and end from transaction dates
    dates = [t.date for t in transactions] if transactions else []
    review_start = min(dates) if dates else None
    review_end = max(dates) if dates else None

    # Map narratives and cited transactions onto each finding for frontend rendering
    narrative_map = {
        fn["rule_id"]: fn["narrative"]
        for fn in narrative_result.get("finding_narratives", [])
    }
    txn_map = {t.id: t.to_dict() for t in transactions}

    report_findings = []
    for f in findings_dicts:
        cited_txns = [
            txn_map[tid] for tid in f.get("transaction_ids", []) if tid in txn_map
        ]
        rule_name = f.get("rule_name") or f.get("title", f["rule_id"])
        rationale = f.get("rationale") or f.get("explanation", "")
        narrative = narrative_map.get(f["rule_id"], rationale)

        report_findings.append({
            "rule_id": f["rule_id"],
            "rule_name": rule_name,
            "title": rule_name,
            "severity": f["severity"],
            "rationale": rationale,
            "explanation": rationale,
            "transaction_ids": f.get("transaction_ids", []),
            "metrics": f.get("metrics", {}),
            "narrative": narrative,
            "transactions": cited_txns,
        })

    # Final report
    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "account_opened": account_opened,
        "review_period": {
            "start": review_start,
            "end": review_end
        },
        "needs_attention": len(findings_dicts) > 0,
        "attention_required": len(findings_dicts) > 0,
        "findings": report_findings,
        "finding_narratives": narrative_result.get(
            "finding_narratives", []
        ),
        "priority_order": narrative_result.get(
            "priority_order", []
        ),
        "priority_reasoning": narrative_result.get(
            "priority_reasoning", ""
        ),
        "overall_summary": narrative_result.get(
            "overall_summary", ""
        ),
        "narrative_source": narrative_result.get(
            "narrative_source", "fallback_template"
        )
    }