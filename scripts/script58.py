from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Product:
    product_id: str
    name: str
    category: str
    price: float
    tags: List[str] = field(default_factory=list)

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.name.lower() or q in self.category.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional[Product]:
        try:
            return cls(
                product_id=str(raw.get("product_id", "")),
                name=str(raw.get("name", "")),
                category=str(raw.get("category", "")),
                price=float(raw.get("price", 0.0)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class Order:
    order_id: str
    created_at: datetime
    items: List[Product] = field(default_factory=list)
    status: str = "pending"

    def total_value(self) -> float:
        return sum(p.price for p in self.items)

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.created_at >= datetime.utcnow() - timedelta(days=days)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "items": [p.to_dict() for p in self.items],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional[Order]:
        try:
            created = datetime.fromisoformat(str(raw.get("created_at")))
            items_raw = raw.get("items", [])
            items: List[Product] = []
            for it in items_raw:
                p = Product.from_dict(it)
                if p:
                    items.append(p)
            return cls(
                order_id=str(raw.get("order_id", "")),
                created_at=created,
                items=items,
                status=str(raw.get("status", "pending")),
            )
        except Exception:
            return None


class OrderBook:
    def __init__(self, book_id: str) -> None:
        self.book_id = book_id
        self._orders: Dict[str, Order] = {}

    def add(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def all(self) -> List[Order]:
        return list(self._orders.values())

    def open_orders(self) -> List[Order]:
        return [o for o in self._orders.values() if o.status != "completed"]

    def search_by_product(self, query: str) -> List[Order]:
        result: List[Order] = []
        for o in self._orders.values():
            if any(p.matches(query) for p in o.items):
                result.append(o)
        return sorted(result, key=lambda o: o.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "orders": [o.to_dict() for o in self._orders.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> OrderBook:
        ob = cls(book_id=str(raw.get("book_id", "local")))
        for item in raw.get("orders", []):
            o = Order.from_dict(item)
            if o:
                ob.add(o)
        return ob


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, book_id: str) -> str:
        return f"{self.base_url}/orders/{book_id}.json"

    def fetch_orders(self, book_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(book_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (error.URLError, OSError, ValueError):
            return None

    def push_summary(self, book_id: str, summary: Dict[str, Any]) -> bool:
        url = self._url(book_id)
        body = json.dumps(summary).encode("utf-8")
        try:
            req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (error.URLError, OSError):
            return False


def load_order_book(path: Path) -> OrderBook:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return OrderBook.from_dict(raw)
    except FileNotFoundError:
        return OrderBook(book_id="local")
    except Exception:
        return OrderBook(book_id="local")


def save_order_book(path: Path, book: OrderBook) -> None:
    payload = json.dumps(book.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def summarize_orders(book: OrderBook) -> Dict[str, Any]:
    orders = book.all()
    if not orders:
        return {"count": 0, "open": 0, "total_value": 0.0}
    count = len(orders)
    open_count = len([o for o in orders if o.status != "completed"])
    total_value = sum(o.total_value() for o in orders)
    return {"count": count, "open": open_count, "total_value": total_value}


def filter_large_orders(book: OrderBook, threshold: float = 100.0) -> List[Order]:
    result: List[Order] = []
    for o in book.all():
        if o.total_value() >= threshold:
            result.append(o)
    return result


def merge_remote_orders(book: OrderBook, remote_data: Optional[Dict[str, Any]]) -> int:
    if not remote_data:
        return 0
    remote = OrderBook.from_dict(remote_data)
    added = 0
    for o in remote.all():
        if book.get(o.order_id) is None:
            book.add(o)
            added += 1
    return added


def simulate_processing(book: OrderBook, steps: int = 3) -> None:
    step = 0
    while step < steps:
        open_orders = book.open_orders()
        if not open_orders:
            return
        for o in open_orders:
            if random.random() < 0.4:
                o.status = "completed"
        step += 1


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    book_path = base / "orders.json"
    report_path = base / "orders_report.json"

    book = load_order_book(book_path)

    if base_url:
        client = ApiClient(base_url=base_url)
        remote = client.fetch_orders(book.book_id)
        merge_remote_orders(book, remote)

    simulate_processing(book)
    summary = summarize_orders(book)

    try:
        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_order_book(book_path, book)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
