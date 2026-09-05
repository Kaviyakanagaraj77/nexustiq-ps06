"""Plain data structures shared across the rule engine and the API layer."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transaction:
    id: str
    date: str          # YYYY-MM-DD
    time: str          # HH:MM
    description: str
    payee: str
    amount: float
    channel: str
    type: str          # "debit" | "credit"
    location: Optional[str] = None   # transaction initiation location

    @property
    def hour(self) -> int:
        return int(self.time.split(":")[0])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "time": self.time,
            "description": self.description,
            "payee": self.payee,
            "amount": self.amount,
            "channel": self.channel,
            "type": self.type,
            "location": self.location,
        }


@dataclass
class CustomerBaseline:
    """Statistics describing a customer's own normal behaviour, computed
    once per investigation from their own history — never from any other
    customer's data, and never hard-coded."""
    customer_id: str
    debit_median: float
    debit_p90: float
    known_payees: set
    known_channels: set
    typical_hours: set
    transaction_count: int


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    severity: str                 # "high" | "medium" | "low"
    transaction_ids: list = field(default_factory=list)
    rationale: str = ""
    metric: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "transaction_ids": self.transaction_ids,
            "rationale": self.rationale,
            "metric": self.metric,
        }