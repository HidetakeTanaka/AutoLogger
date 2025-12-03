from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import random
import urllib.request
import urllib.error


@dataclass
class Order:
    order_id: str
    customer_id: str
    total: float
    created_at: datetime
    items: Dict[str, int]

    def is_recent(self, hours: int = 24) -> bool:
        ref = datetime.utcnow() - timedelta(hours=hours)
        return self.created_at >= ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "total": self.total,
            "created_at": self.created_at.isoformat(),
            "items": self.items,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Order"]:
        try:
            created_raw = raw.get("created_at") or ""
            created = datetime.fromisoformat(created_raw) if created_raw else datetime.utcnow()
            return cls(
                order_id=str(raw.get("order_id", "")),
                customer_id=str(raw.get("customer_id", "")),
                total=float(raw.get("total", 0.0)),
                created_at=created,
                items=dict(raw.get("items", {})),
            )
        except Exception:
            return None


@dataclass
class Customer:
    customer_id: str
    name: str
    joined_at: datetime
    tags: List[str] = field(default_factory=list)
    orders: List[Order] = field(default_factory=list)

    def add_order(self, order: Order) -> None:
        if order.customer_id != self.customer_id:
            return
        self.orders.append(order)

    def lifetime_value(self) -> float:
        return sum(o.total for o in self.orders)

    def matches(self, query: str) -> bool:
        q = query.lower()
        if q in self.name.lower() or q in self.customer_id.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "joined_at": self.joined_at.isoformat(),
            "tags": list(self.tags),
            "orders": [o.to_dict() for o in self.orders],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Customer":
        joined_raw = raw.get("joined_at") or ""
        try:
            joined = datetime.fromisoformat(joined_raw) if joined_raw else datetime.utcnow()
        except Exception:
            joined = datetime.utcnow()
        customer = cls(
            customer_id=str(raw.get("customer_id", "")),
            name=str(raw.get("name", "")),
            joined_at=joined,
            tags=list(raw.get("tags", [])),
        )
        for o_raw in raw.get("orders", []):
            order = Order.from_dict(o_raw)
            if order is not None:
                customer.orders.append(order)
        return customer


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_benchmarks(self) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url("benchmarks.json")
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

    def push_summary(self, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url("summary")
        body = json.dumps(summary).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except urllib.error.URLError:
            return False


def load_customers(path: Path) -> List[Customer]:
    try:
        data = path.read_text(encoding="utf-8")
        raw = json.loads(data)
        result: List[Customer] = []
        for c_raw in raw.get("customers", []):
            result.append(Customer.from_dict(c_raw))
        return result
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def save_customers(path: Path, customers: List[Customer]) -> None:
    payload = {"customers": [c.to_dict() for c in customers]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def compute_kpis(customers: List[Customer]) -> Dict[str, Any]:
    if not customers:
        return {"count": 0, "avg_ltv": 0.0, "active": 0}
    ltvs = [c.lifetime_value() for c in customers]
    active = sum(1 for v in ltvs if v > 0)
    return {
        "count": len(customers),
        "avg_ltv": sum(ltvs) / len(ltvs),
        "active": active,
    }


def simulate_orders(customers: List[Customer], days: int = 3) -> List[Order]:
    history: List[Order] = []
    if not customers:
        return history
    day = 0
    while day < days:
        for c in customers:
            if random.random() < 0.5:
                items = {f"sku-{random.randint(1,5)}": random.randint(1, 3)}
                total = sum(q * random.uniform(10, 50) for q in items.values())
                order = Order(
                    order_id=f"sim-{day}-{c.customer_id}",
                    customer_id=c.customer_id,
                    total=round(total, 2),
                    created_at=datetime.utcnow() - timedelta(days=(days - day)),
                    items=items,
                )
                c.add_order(order)
                history.append(order)
        day += 1
    return history


def apply_discounts(customers: List[Customer], threshold: float = 200.0, pct: float = 0.1) -> int:
    updated = 0
    for c in customers:
        for o in c.orders:
            if o.total >= threshold:
                o.total = round(o.total * (1.0 - pct), 2)
                updated += 1
    return updated


def merge_remote_benchmarks(summary: Dict[str, Any], remote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not remote:
        return summary
    result = dict(summary)
    for k, v in remote.items():
        if isinstance(v, (int, float)) and isinstance(result.get(k), (int, float)):
            result[k] = (result[k] + v) / 2
        elif k not in result:
            result[k] = v
    return result


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    customers_path = base / "customers.json"
    summary_path = base / "summary.json"

    customers = load_customers(customers_path)
    if not customers:
        customers = [
            Customer(customer_id="u1", name="Alice", joined_at=datetime.utcnow()),
            Customer(customer_id="u2", name="Bob", joined_at=datetime.utcnow()),
        ]

    simulate_orders(customers, days=5)
    apply_discounts(customers)

    kpis = compute_kpis(customers)
    client = AnalyticsClient(base_url=base_url)
    remote = client.fetch_benchmarks()
    merged = merge_remote_benchmarks(kpis, remote)

    try:
        client.push_summary(merged)
    except Exception:
        pass

    save_customers(customers_path, customers)
    try:
        summary_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    except OSError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
