from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Transaction:
    tx_id: str
    amount: float
    currency: str
    category: str
    occurred_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_large(self, threshold: float = 500.0) -> bool:
        return abs(self.amount) >= threshold

    def matches_category(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q == self.category.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "amount": self.amount,
            "currency": self.currency,
            "category": self.category,
            "occurred_at": self.occurred_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Transaction"]:
        try:
            ts_raw = raw.get("occurred_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                tx_id=str(raw.get("tx_id", "")),
                amount=float(raw.get("amount", 0.0)),
                currency=str(raw.get("currency", "USD")),
                category=str(raw.get("category", "other")),
                occurred_at=ts,
                tags=list(raw.get("tags", [])),
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

    def category_total(self, category: str) -> float:
        return sum(t.amount for t in self.transactions if t.category == category)

    def monthly_total(self, year: int, month: int) -> float:
        return sum(
            t.amount
            for t in self.transactions
            if t.occurred_at.year == year and t.occurred_at.month == month
        )

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
        for r in raw.get("transactions", []):
            tx = Transaction.from_dict(r)
            if tx:
                state.add_transaction(tx)
        return state


class BudgetClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_exchange_rate(self, currency: str) -> Optional[float]:
        url = self._url(f"fx?base={currency}")
        if not url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            value = parsed.get("rate")
            return float(value) if value is not None else None
        except (error.URLError, ValueError, json.JSONDecodeError):
            return None

    def push_summary(self, summary: Dict[str, Any]) -> bool:
        url = self._url("summary")
        if not url:
            return False
        body = json.dumps(summary).encode("utf-8")
        try:
            req = request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False


def load_state(path: Path) -> BudgetState:
    if not path.exists():
        return BudgetState(user_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return BudgetState.from_dict(raw)
    except (OSError, json.JSONDecodeError):
        return BudgetState(user_id="local")


def save_state(path: Path, state: BudgetState) -> None:
    payload = json.dumps(state.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return


def compute_stats(state: BudgetState) -> Dict[str, Any]:
    if not state.transactions:
        return {"count": 0, "total": 0.0, "by_category": {}}
    by_cat: Dict[str, float] = {}
    for t in state.transactions:
        by_cat[t.category] = by_cat.get(t.category, 0.0) + t.amount
    total = sum(by_cat.values())
    return {"count": len(state.transactions), "total": total, "by_category": by_cat}


def simulate_month(state: BudgetState, days: int = 30) -> int:
    created = 0
    today = date.today()
    cats = ["food", "rent", "transport", "entertainment", "other"]
    for i in range(days):
        d = today - timedelta(days=i)
        for _ in range(random.randint(0, 3)):
            amt = round(random.uniform(-80, -5), 2)
            cat = random.choice(cats)
            tx = Transaction(
                tx_id=f"sim-{d.isoformat()}-{created}",
                amount=amt,
                currency=state.base_currency,
                category=cat,
                occurred_at=datetime.combine(d, datetime.min.time()),
                tags=[cat],
            )
            state.add_transaction(tx)
            created += 1
    return created


def summarize_state(state: BudgetState, rate: Optional[float]) -> Dict[str, Any]:
    stats = compute_stats(state)
    large = [t.to_dict() for t in state.transactions if t.is_large()]
    converted_total: Optional[float]
    if rate is None:
        converted_total = None
    else:
        converted_total = stats["total"] * rate
    return {
        "user_id": state.user_id,
        "base_currency": state.base_currency,
        "count": stats["count"],
        "total": stats["total"],
        "converted_total": converted_total,
        "large_transactions": large,
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    state_path = base / "budget_state.json"
    state = load_state(state_path)
    simulate_month(state, days=7)
    client = BudgetClient(base_url=base_url)
    fx_rate = client.fetch_exchange_rate(state.base_currency) if base_url else None
    summary = summarize_state(state, fx_rate)
    save_state(state_path, state)
    summary_path = base / "budget_summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1
    if base_url:
        ok = client.push_summary(summary)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
