from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Transaction:
    tx_id: str
    amount: float
    created_at: datetime
    category: str

    def is_recent(self, hours: int = 24) -> bool:
        ref = datetime.utcnow() - timedelta(hours=hours)
        if self.created_at < ref:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "amount": self.amount,
            "created_at": self.created_at.isoformat(),
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Transaction"]:
        try:
            ts_raw = str(raw.get("created_at", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                tx_id=str(raw.get("tx_id", "")),
                amount=float(raw.get("amount", 0.0)),
                created_at=ts,
                category=str(raw.get("category", "")),
            )
        except Exception:
            return None


@dataclass
class UserAccount:
    user_id: str
    name: str
    balance: float = 0.0
    transactions: List[Transaction] = field(default_factory=list)

    def add_transaction(self, tx: Transaction) -> None:
        self.transactions.append(tx)
        self.balance += tx.amount

    def recent_transactions(self, hours: int = 24) -> List[Transaction]:
        return [t for t in self.transactions if t.is_recent(hours)]

    def spending_by_category(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for t in self.transactions:
            if t.amount < 0:
                totals[t.category] = totals.get(t.category, 0.0) + abs(t.amount)
        return totals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "balance": self.balance,
            "transactions": [t.to_dict() for t in self.transactions],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UserAccount":
        acc = cls(
            user_id=str(raw.get("user_id", "")),
            name=str(raw.get("name", "Unknown")),
            balance=float(raw.get("balance", 0.0)),
        )
        for t_raw in raw.get("transactions", []):
            tx = Transaction.from_dict(t_raw)
            if tx is not None:
                acc.add_transaction(tx)
        return acc


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, user_id: str) -> str:
        return f"{self.base_url}/users/{user_id}/benchmarks.json"

    def fetch_benchmarks(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(user_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except error.URLError:
            return None
        except Exception:
            return None

    def push_summary(self, user_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = f"{self.base_url}/users/{user_id}/summary.json"
        body = json.dumps(summary).encode("utf-8")
        req = request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False


def load_account(path: Path) -> UserAccount:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return UserAccount.from_dict(raw)
    except Exception:
        return UserAccount(user_id="local", name="Local User")


def save_account(path: Path, account: UserAccount) -> None:
    payload = json.dumps(account.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
    except Exception:
        return
    try:
        tmp.replace(path)
    except Exception:
        return


def compute_kpis(account: UserAccount) -> Dict[str, Any]:
    txs = account.transactions
    if not txs:
        return {"tx_count": 0, "avg_amount": 0.0, "spend_30d": 0.0}
    amounts = [t.amount for t in txs]
    avg = sum(amounts) / len(amounts)
    cutoff = datetime.utcnow() - timedelta(days=30)
    spend_30d = sum(abs(t.amount) for t in txs if t.amount < 0 and t.created_at >= cutoff)
    return {"tx_count": len(txs), "avg_amount": avg, "spend_30d": spend_30d}


def simulate_day(account: UserAccount, count: int = 5) -> None:
    categories = ["food", "travel", "rent", "salary", "shopping"]
    for _ in range(count):
        cat = random.choice(categories)
        base = random.uniform(5.0, 100.0)
        amount = -base
        if cat == "salary":
            amount = base * 10
        tx = Transaction(
            tx_id=f"sim-{datetime.utcnow().timestamp()}-{random.randint(1,9999)}",
            amount=amount,
            created_at=datetime.utcnow(),
            category=cat,
        )
        account.add_transaction(tx)


def merge_benchmarks(kpis: Dict[str, Any], remote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not remote:
        return kpis
    merged = dict(kpis)
    for key, value in remote.items():
        if key.startswith("p") or key.endswith("_rank"):
            merged[key] = value
    return merged


def summarize_categories(account: UserAccount) -> List[Dict[str, Any]]:
    totals = account.spending_by_category()
    if not totals:
        return []
    max_spend = max(totals.values())
    result = []
    for cat, val in totals.items():
        share = val / max_spend if max_spend > 0 else 0.0
        result.append({"category": cat, "amount": val, "relative": share})
    return sorted(result, key=lambda x: x["amount"], reverse=True)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    account_path = base / "account.json"
    summary_path = base / "summary.json"

    account = load_account(account_path)
    if not account.transactions:
        simulate_day(account, count=10)

    kpis = compute_kpis(account)
    cat_summary = summarize_categories(account)
    client = AnalyticsClient(base_url=base_url) if base_url else None

    remote = client.fetch_benchmarks(account.user_id) if client else None
    merged = merge_benchmarks(kpis, remote)

    summary = {"user_id": account.user_id, "name": account.name, "kpis": merged, "categories": cat_summary}

    if client:
        client.push_summary(account.user_id, summary)

    save_account(account_path, account)
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
