from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from urllib import request, error


@dataclass
class Transaction:
    tx_id: str
    account_id: str
    amount: float
    category: str
    ts: datetime
    meta: Dict[str, Any] = field(default_factory=dict)

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.ts >= datetime.utcnow() - timedelta(days=days)

    def is_large(self, threshold: float = 1000.0) -> bool:
        if threshold <= 0:
            return False
        return abs(self.amount) >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "account_id": self.account_id,
            "amount": self.amount,
            "category": self.category,
            "ts": self.ts.isoformat(),
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Transaction"]:
        try:
            ts_raw = raw.get("ts")
            if not ts_raw:
                return None
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                tx_id=str(raw.get("tx_id", "")),
                account_id=str(raw.get("account_id", "")),
                amount=float(raw.get("amount", 0.0)),
                category=str(raw.get("category", "")),
                ts=ts,
                meta=dict(raw.get("meta", {})),
            )
        except Exception:
            return None


@dataclass
class Account:
    account_id: str
    owner: str
    currency: str = "USD"
    transactions: List[Transaction] = field(default_factory=list)

    def add_transaction(self, tx: Transaction) -> None:
        if tx.account_id != self.account_id:
            return
        self.transactions.append(tx)

    def balance(self) -> float:
        return sum(t.amount for t in self.transactions)

    def recent_spending(self, days: int = 7) -> float:
        recent = [t for t in self.transactions if t.is_recent(days) and t.amount < 0]
        return -sum(t.amount for t in recent)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "currency": self.currency,
            "transactions": [t.to_dict() for t in self.transactions],
        }


class BudgetClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, account_id: str) -> str:
        return f"{self.base_url}/budget/{account_id}"

    def fetch_limits(self, account_id: str) -> Dict[str, float]:
        if not self.base_url:
            return {}
        url = self._url(account_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                return {}
            return {str(k): float(v) for k, v in data.items()}
        except (error.URLError, ValueError, TypeError):
            return {}


def load_transactions(path: Path) -> List[Transaction]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw_items = json.load(f)
    except Exception:
        return []
    if not isinstance(raw_items, list):
        return []
    result: List[Transaction] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        tx = Transaction.from_dict(raw)
        if tx is not None:
            result.append(tx)
    return result


def save_transactions(path: Path, txs: Iterable[Transaction]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = [t.to_dict() for t in txs]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def group_by_category(txs: Iterable[Transaction]) -> Dict[str, List[Transaction]]:
    groups: Dict[str, List[Transaction]] = {}
    for tx in txs:
        groups.setdefault(tx.category or "uncategorized", []).append(tx)
    return groups


def summarize_account(account: Account) -> Dict[str, Any]:
    groups = group_by_category(account.transactions)
    category_totals: Dict[str, float] = {
        cat: sum(t.amount for t in items) for cat, items in groups.items()
    }
    return {
        "account_id": account.account_id,
        "owner": account.owner,
        "currency": account.currency,
        "balance": account.balance(),
        "categories": category_totals,
    }


def detect_overspend(
    account: Account, limits: Dict[str, float]
) -> Dict[str, float]:
    if not limits:
        return {}
    groups = group_by_category(account.transactions)
    overspend: Dict[str, float] = {}
    for cat, items in groups.items():
        spent = -sum(t.amount for t in items if t.amount < 0)
        limit = float(limits.get(cat, 0.0))
        if limit > 0 and spent > limit:
            overspend[cat] = spent - limit
    return overspend


def filter_large_transactions(
    txs: Iterable[Transaction], threshold: float = 1000.0
) -> List[Transaction]:
    result = [t for t in txs if t.is_large(threshold)]
    if not result:
        return []
    return sorted(result, key=lambda t: abs(t.amount), reverse=True)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    tx_path = base / "transactions.json"
    account_info_path = base / "account.json"

    txs = load_transactions(tx_path)
    if not txs:
        return 1

    try:
        with account_info_path.open("r", encoding="utf-8") as f:
            info = json.load(f)
    except Exception:
        info = {"account_id": "unknown", "owner": "unknown", "currency": "USD"}

    account = Account(
        account_id=str(info.get("account_id", "unknown")),
        owner=str(info.get("owner", "unknown")),
        currency=str(info.get("currency", "USD")),
    )
    for tx in txs:
        account.add_transaction(tx)

    client = BudgetClient(base_url=base_url, timeout=5) if base_url else BudgetClient("", 5)
    limits = client.fetch_limits(account.account_id)
    summary = summarize_account(account)
    overspend = detect_overspend(account, limits)
    large_txs = filter_large_transactions(account.transactions, threshold=500.0)

    report = {
        "summary": summary,
        "overspend": overspend,
        "large_transactions": [t.to_dict() for t in large_txs],
    }
    report_path = base / "report.json"
    try:
        base.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
