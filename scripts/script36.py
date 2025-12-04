from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


@dataclass
class Account:
    account_id: str
    owner: str
    currency: str
    balance: float

    def can_withdraw(self, amount: float) -> bool:
        if amount <= 0:
            return False
        return self.balance >= amount

    def withdraw(self, amount: float) -> bool:
        if not self.can_withdraw(amount):
            return False
        self.balance -= amount
        return True

    def deposit(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.balance += amount
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "currency": self.currency,
            "balance": self.balance,
        }


@dataclass
class Transaction:
    tx_id: str
    account_id: str
    amount: float
    kind: str
    created_at: datetime

    def is_debit(self) -> bool:
        return self.amount < 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "account_id": self.account_id,
            "amount": self.amount,
            "kind": self.kind,
            "created_at": self.created_at.isoformat(),
        }


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._accounts: Dict[str, Account] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._accounts = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._accounts = {}
            return
        accounts: Dict[str, Account] = {}
        for raw in data.get("accounts", []):
            try:
                aid = str(raw["account_id"])
                owner = str(raw.get("owner", ""))
                currency = str(raw.get("currency", "EUR"))
                balance = float(raw.get("balance", 0.0))
            except (KeyError, ValueError):
                continue
            accounts[aid] = Account(account_id=aid, owner=owner, currency=currency, balance=balance)
        self._accounts = accounts

    def save(self) -> None:
        payload = {"accounts": [a.to_dict() for a in self._accounts.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def get(self, account_id: str) -> Optional[Account]:
        return self._accounts.get(account_id)

    def all(self) -> List[Account]:
        return list(self._accounts.values())


class TransactionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> List[Transaction]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        txs: List[Transaction] = []
        for raw in data.get("transactions", []):
            try:
                tx_id = str(raw["tx_id"])
                account_id = str(raw["account_id"])
                amount = float(raw["amount"])
                kind = str(raw.get("kind", ""))
                created = datetime.fromisoformat(str(raw["created_at"]))
            except (KeyError, ValueError):
                continue
            txs.append(Transaction(tx_id=tx_id, account_id=account_id, amount=amount, kind=kind, created_at=created))
        return txs

    def save(self, txs: List[Transaction]) -> None:
        payload = {"transactions": [t.to_dict() for t in txs]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)


def apply_transactions(accounts: AccountStore, txs: List[Transaction]) -> Tuple[int, int]:
    applied = 0
    rejected = 0
    for tx in txs:
        acc = accounts.get(tx.account_id)
        if acc is None:
            rejected += 1
            continue
        if tx.amount >= 0:
            if acc.deposit(tx.amount):
                applied += 1
            else:
                rejected += 1
        else:
            if acc.withdraw(-tx.amount):
                applied += 1
            else:
                rejected += 1
    return applied, rejected


def summarize_accounts(accounts: List[Account]) -> Dict[str, Any]:
    if not accounts:
        return {"count": 0, "total_balance": 0.0, "avg_balance": 0.0}
    balances = [a.balance for a in accounts]
    total = sum(balances)
    avg = total / len(balances)
    return {"count": len(accounts), "total_balance": total, "avg_balance": avg}


def find_suspicious_transactions(txs: List[Transaction], hours: int = 24, amount_threshold: float = 10000.0) -> List[Transaction]:
    if not txs:
        return []
    now = max(t.created_at for t in txs)
    suspicious: List[Transaction] = []
    for t in txs:
        if t.amount < 0 and -t.amount >= amount_threshold and now - t.created_at <= timedelta(hours=hours):
            suspicious.append(t)
    return suspicious


def export_summary(path: Path, summary: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def export_suspicious(path: Path, txs: List[Transaction]) -> None:
    payload = [t.to_dict() for t in txs]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"transactions": payload}, f, indent=2, ensure_ascii=False)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    base = Path("data")
    accounts_path = base / "accounts.json"
    txs_path = base / "transactions.json"
    summary_path = base / "accounts_summary.json"
    suspicious_path = base / "suspicious.json"
    config_path = base / "bank_config.json"

    accounts = AccountStore(accounts_path)
    accounts.load()

    tx_store = TransactionStore(txs_path)
    txs = tx_store.load()

    if not txs:
        return 1

    applied, rejected = apply_transactions(accounts, txs)
    accounts.save()

    summary = summarize_accounts(accounts.all())
    summary["applied"] = applied
    summary["rejected"] = rejected
    export_summary(summary_path, summary)

    cfg = load_config(config_path)
    threshold = float(cfg.get("suspicious_threshold", 10000.0))
    hours = int(cfg.get("suspicious_window_hours", 24))
    suspicious = find_suspicious_transactions(txs, hours=hours, amount_threshold=threshold)
    export_suspicious(suspicious_path, suspicious)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
