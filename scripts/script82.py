from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Transaction:
    tx_id: str
    amount: float
    currency: str
    category: str
    occurred_at: datetime
    note: str = ""

    def is_income(self) -> bool:
        return self.amount > 0

    def matches_category(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.category.lower():
            return True
        return q in self.note.lower()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "amount": self.amount,
            "currency": self.currency,
            "category": self.category,
            "occurred_at": self.occurred_at.isoformat(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Transaction"]:
        try:
            ts_raw = str(raw.get("occurred_at", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                tx_id=str(raw.get("tx_id", "")),
                amount=float(raw.get("amount", 0.0)),
                currency=str(raw.get("currency", "USD")),
                category=str(raw.get("category", "")),
                occurred_at=ts,
                note=str(raw.get("note", "")),
            )
        except Exception:
            return None


@dataclass
class BudgetState:
    user_id: str
    base_currency: str = "USD"
    transactions: List[Transaction] = field(default_factory=list)

    def add_transaction(self, tx: Transaction) -> None:
        self.transactions.append(tx)

    def balance(self, currency: Optional[str] = None) -> float:
        cur = currency or self.base_currency
        total = 0.0
        for tx in self.transactions:
            if tx.currency == cur:
                total += tx.amount
        return total

    def by_category(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for tx in self.transactions:
            result[tx.category] = result.get(tx.category, 0.0) + tx.amount
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "base_currency": self.base_currency,
            "transactions": [t.to_dict() for t in self.transactions],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "BudgetState":
        state = cls(
            user_id=str(raw.get("user_id", "local")),
            base_currency=str(raw.get("base_currency", "USD")),
        )
        for item in raw.get("transactions", []):
            tx = Transaction.from_dict(item)
            if tx is not None:
                state.add_transaction(tx)
        return state


class RateClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, base: str) -> str:
        return f"{self.base_url}/latest?base={base}"

    def fetch_rates(self, base: str) -> Optional[Dict[str, float]]:
        if not self.base_url:
            return None
        url = self._url(base)
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            rates = parsed.get("rates")
            return rates if isinstance(rates, dict) else None
        except (urllib.error.URLError, ValueError, KeyError):
            return None


def load_budget(path: Path) -> BudgetState:
    if not path.exists():
        return BudgetState(user_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return BudgetState.from_dict(raw)
    except Exception:
        return BudgetState(user_id="local")


def save_budget(path: Path, budget: BudgetState) -> None:
    payload = json.dumps(budget.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_monthly_summary(
    budget: BudgetState, year: int, month: int
) -> Dict[str, Any]:
    selected = [
        t for t in budget.transactions if t.occurred_at.year == year and t.occurred_at.month == month
    ]
    if not selected:
        return {
            "year": year,
            "month": month,
            "count": 0,
            "income": 0.0,
            "expense": 0.0,
        }
    income = sum(t.amount for t in selected if t.amount > 0)
    expense = sum(-t.amount for t in selected if t.amount < 0)
    return {
        "year": year,
        "month": month,
        "count": len(selected),
        "income": income,
        "expense": expense,
    }


def apply_exchange_rates(
    budget: BudgetState, rates: Optional[Dict[str, float]], target: str
) -> BudgetState:
    if rates is None:
        return budget
    converted = BudgetState(user_id=budget.user_id, base_currency=target)
    for tx in budget.transactions:
        if tx.currency == target:
            factor = 1.0
        else:
            factor = rates.get(tx.currency, 0.0)
        if factor <= 0:
            converted.add_transaction(tx)
            continue
        new_tx = Transaction(
            tx_id=tx.tx_id,
            amount=tx.amount / factor,
            currency=target,
            category=tx.category,
            occurred_at=tx.occurred_at,
            note=tx.note,
        )
        converted.add_transaction(new_tx)
    return converted


def simulate_spending(budget: BudgetState, daily_limit: float = 50.0, days: int = 7) -> int:
    spent_days = 0
    for _ in range(days):
        today_spent = 0.0
        while today_spent < daily_limit:
            amount = -random.uniform(5.0, 20.0)
            today_spent -= amount
            tx = Transaction(
                tx_id=f"sim-{spent_days}-{today_spent:.2f}",
                amount=amount,
                currency=budget.base_currency,
                category="simulated",
                occurred_at=datetime.utcnow(),
            )
            budget.add_transaction(tx)
            if today_spent >= daily_limit:
                break
        spent_days += 1
    return spent_days


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    store_path = base / "budget.json"
    summary_path = base / "summary.json"
    budget = load_budget(store_path)
    if not budget.transactions:
        simulate_spending(budget, daily_limit=40.0, days=3)
    client = RateClient(base_url=base_url) if base_url else None
    rates = client.fetch_rates(budget.base_currency) if client else None
    if rates:
        budget = apply_exchange_rates(budget, rates, budget.base_currency)
    today = date.today()
    summary = compute_monthly_summary(budget, today.year, today.month)
    try:
        save_budget(store_path, budget)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
