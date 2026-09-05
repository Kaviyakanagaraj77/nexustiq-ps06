"""
LLM narrative layer.

This file NEVER decides what is risky — src/rules.py already did that.
Gemini's only job here is to turn already-established, cited findings into
a clear investigator-facing narrative, and to rank them by what to look at
first. If the model call fails for any reason (no key, network, quota,
malformed response), we fall back to a deterministic template built
straight from the Finding objects, so the app never breaks and never goes
silent just because Gemini is unavailable.
"""
import json
import os
import urllib.request
import urllib.error


def _load_env():
    """Load variables from .env if present without external dependencies."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def _fallback_narrative(findings: list) -> dict:
    """Deterministic, template-based narrative used when Gemini can't be reached."""
    if not findings:
        return {
            "finding_narratives": [],
            "priority_order": [],
            "priority_reasoning": "",
            "overall_summary": "No transaction in this history triggered any of the "
                                "configured risk rules. Nothing here needs an investigator's time.",
            "narrative_source": "fallback_template",
        }
    narratives = []
    for f in findings:
        rationale = f.get("rationale") or f.get("explanation", "")
        narratives.append({
            "rule_id": f["rule_id"],
            "narrative": rationale + f" Transactions: {', '.join(f.get('transaction_ids', []))}.",
        })
    order = [f["rule_id"] for f in sorted(findings, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 99))]
    return {
        "finding_narratives": narratives,
        "priority_order": order,
        "priority_reasoning": "Ordered by rule severity (high before medium before low) "
                               "since the narrative model was unavailable.",
        "overall_summary": f"{len(findings)} finding(s) triggered against this customer's own history. "
                            f"Review in the listed order.",
        "narrative_source": "fallback_template",
    }


def generate_investigation_narrative(customer_id: str, customer_name: str, findings: list) -> dict:
    """
    findings: list of Finding dict results.
    Returns a dict with finding_narratives, priority_order, priority_reasoning,
    overall_summary, and narrative_source ("gemini" or "fallback_template").
    """
    _load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _fallback_narrative(findings)

    payload = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "findings": findings,
    }

    system_instructions = """You are drafting notes for a human fraud investigator at a bank.
You are given a JSON list of findings that a deterministic rule engine already
produced from one customer's transaction history, each with the exact transaction
IDs, a factual rationale, and supporting metrics.

Rules you must follow exactly:
1. Only ever refer to transaction IDs, payees, amounts, dates and channels that
   appear in the JSON you were given. Never invent a transaction, amount, or date.
2. Never state that fraud has occurred, or use the words "fraud", "scam", or
   "confirmed" to describe the customer's activity. You flag and explain; the
   investigator decides.
3. For each finding, write a short (2-3 sentence) plain-English explanation of
   why it stands out, referencing the specific transaction IDs it's based on.
4. Then write a single prioritized list ("what to look at first") ordering the
   findings by how urgently an investigator should look at them, with a one-line
   reason for the ordering.
5. If the findings list is empty, say plainly that nothing in this history stood
   out against the rule set, in one or two sentences — do not manufacture concern.
6. Return ONLY valid JSON matching this shape, nothing else, no markdown fences:
{"finding_narratives": [{"rule_id": "...", "narrative": "..."}], "priority_order": ["rule_id1", "rule_id2"], "priority_reasoning": "...", "overall_summary": "..."}
"""

    body = {
        "system_instruction": {"parts": [{"text": system_instructions}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload)}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }

    try:
        model_name = os.environ.get("GEMINI_MODEL", GEMINI_MODEL)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Safely handle markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response is not a valid JSON object")

        parsed.setdefault("finding_narratives", [])
        parsed.setdefault("priority_order", [])
        parsed.setdefault("priority_reasoning", "")
        parsed.setdefault("overall_summary", "")
        parsed["narrative_source"] = "gemini"
        return parsed
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            KeyError, ValueError, json.JSONDecodeError) as e:
        fallback = _fallback_narrative(findings)
        fallback["narrative_source"] = f"fallback_template (gemini_error: {type(e).__name__})"
        return fallback
