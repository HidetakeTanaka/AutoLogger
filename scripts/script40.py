from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime


@dataclass
class Item:
    item_id: str
    name: str
    category: str
    price: float
    stock: int = 0

    def is_in_stock(self, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False
        return self.stock >= quantity

    def reserve(self, quantity: int) -> bool:
        if not self.is_in_stock(quantity):
            return False
        self.stock -= quantity
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "stock": self.stock,
        }


@dataclass
class OrderLine:
    item_id: str
    quantity: int

    def total(self, item: Item) -> float:
        if self.quantity <= 0:
            return 0.0
        return item.price * self.quantity


@dataclass
class Order:
    order_id: str
    customer_id: str
    created_at: datetime
    lines: List[OrderLine] = field(default_factory=list)
    status: str = "pending"

    def total_amount(self, items: Dict[str, Item]) -> float:
        total = 0.0
        for line in self.lines:
            item = items.get(line.item_id)
            if item is None:
                continue
            total += line.total(item)
        return total

    def is_open(self) -> bool:
        return self.status in {"pending", "processing"}


@dataclass
class Inventory:
    items: Dict[str, Item] = field(default_factory=dict)

    def add_item(self, item: Item) -> None:
        self.items[item.item_id] = item

    def get(self, item_id: str) -> Optional[Item]:
        return self.items.get(item_id)

    def all(self) -> List[Item]:
        return list(self.items.values())

    def to_dict(self) -> Dict[str, Any]:
        return {"items": [i.to_dict() for i in self.items.values()]}


class OrderProcessor:
    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory

    def can_fulfil(self, order: Order) -> bool:
        for line in order.lines:
            item = self.inventory.get(line.item_id)
            if item is None or not item.is_in_stock(line.quantity):
                return False
        return True

    def apply_order(self, order: Order) -> bool:
        if not order.is_open():
            return False
        if not self.can_fulfil(order):
            order.status = "rejected"
            return False
        for line in order.lines:
            item = self.inventory.get(line.item_id)
            if item is None:
                order.status = "rejected"
                return False
            if not item.reserve(line.quantity):
                order.status = "rejected"
                return False
        order.status = "completed"
        return True


def load_inventory(path: Path) -> Inventory:
    if not path.exists():
        return Inventory()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return Inventory()
    inv = Inventory()
    for raw in data.get("items", []):
        try:
            item = Item(
                item_id=str(raw["item_id"]),
                name=str(raw.get("name", "")),
                category=str(raw.get("category", "")),
                price=float(raw.get("price", 0.0)),
                stock=int(raw.get("stock", 0)),
            )
        except (KeyError, ValueError):
            continue
        inv.add_item(item)
    return inv


def load_orders(path: Path) -> List[Order]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    result: List[Order] = []
    for raw in data.get("orders", []):
        try:
            order_id = str(raw["order_id"])
            customer_id = str(raw.get("customer_id", ""))
            created_at = datetime.fromisoformat(str(raw["created_at"]))
            lines: List[OrderLine] = []
            for lr in raw.get("lines", []):
                item_id = str(lr["item_id"])
                quantity = int(lr.get("quantity", 0))
                lines.append(OrderLine(item_id=item_id, quantity=quantity))
        except (KeyError, ValueError):
            continue
        result.append(Order(order_id=order_id, customer_id=customer_id, created_at=created_at, lines=lines))
    return result


def save_inventory(path: Path, inventory: Inventory) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(inventory.to_dict(), f, indent=2, ensure_ascii=False)


def summarize_orders(orders: Iterable[Order], inventory: Inventory) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_orders": 0,
        "completed": 0,
        "rejected": 0,
        "pending": 0,
        "revenue": 0.0,
    }
    for order in orders:
        summary["total_orders"] += 1
        if order.status in summary:
            summary[order.status] += 1
        summary["revenue"] += order.total_amount(inventory.items)
    return summary


def find_high_value_orders(orders: Iterable[Order], inventory: Inventory, threshold: float) -> List[Tuple[str, float]]:
    result: List[Tuple[str, float]] = []
    for order in orders:
        amount = order.total_amount(inventory.items)
        if amount >= threshold:
            result.append((order.order_id, amount))
    return result


def group_orders_by_customer(orders: Iterable[Order]) -> Dict[str, List[Order]]:
    grouped: Dict[str, List[Order]] = {}
    for o in orders:
        grouped.setdefault(o.customer_id, []).append(o)
    return grouped


def export_report(path: Path, summary: Dict[str, Any], high_value: List[Tuple[str, float]]) -> None:
    payload = {
        "summary": summary,
        "high_value_orders": [{"order_id": oid, "amount": amt} for oid, amt in high_value],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    inv_path = base / "inventory.json"
    orders_path = base / "orders.json"
    report_path = base / "order_report.json"
    config_path = base / "order_config.json"

    inventory = load_inventory(inv_path)
    orders = load_orders(orders_path)
    if not orders:
        return 1

    processor = OrderProcessor(inventory)
    for order in orders:
        if not order.is_open():
            continue
        processor.apply_order(order)

    save_inventory(inv_path, inventory)

    cfg = load_config(config_path)
    threshold = float(cfg.get("high_value_threshold", 500.0))
    summary = summarize_orders(orders, inventory)
    high_value = find_high_value_orders(orders, inventory, threshold=threshold)
    export_report(report_path, summary, high_value)

    groups = group_orders_by_customer(orders)
    # simple loop to touch groups for state handling
    count = 0
    for _cid, customer_orders in groups.items():
        if not customer_orders:
            continue
        count += 1
        if count > 1000:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
