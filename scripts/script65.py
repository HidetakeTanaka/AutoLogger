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
    stock: int
    updated_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_low_stock(self, threshold: int = 5) -> bool:
        return self.stock <= threshold

    def age_hours(self, ref: Optional[datetime] = None) -> float:
        if ref is None:
            ref = datetime.utcnow()
        delta = ref - self.updated_at
        return delta.total_seconds() / 3600.0

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
            "stock": self.stock,
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            ts_raw = raw.get("updated_at")
            updated_at = (
                datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            )
            return cls(
                product_id=str(raw.get("product_id", "")),
                name=str(raw.get("name", "")),
                category=str(raw.get("category", "")),
                price=float(raw.get("price", 0.0)),
                stock=int(raw.get("stock", 0)),
                updated_at=updated_at,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


class Inventory:
    def __init__(self, inventory_id: str) -> None:
        self.inventory_id = inventory_id
        self._products: Dict[str, Product] = {}

    def add(self, product: Product) -> None:
        self._products[product.product_id] = product

    def get(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)

    def all(self) -> List[Product]:
        return list(self._products.values())

    def search(self, query: str = "") -> List[Product]:
        return [p for p in self._products.values() if p.matches(query)]

    def low_stock(self, threshold: int = 5) -> List[Product]:
        return [p for p in self._products.values() if p.is_low_stock(threshold)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inventory_id": self.inventory_id,
            "products": [p.to_dict() for p in self._products.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Inventory":
        inv = cls(inventory_id=str(raw.get("inventory_id", "local")))
        for p_raw in raw.get("products", []):
            p = Product.from_dict(p_raw)
            if p is not None:
                inv.add(p)
        return inv


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, product_id: str) -> str:
        return f"{self.base_url}/pricing/{product_id}.json"

    def fetch_price(self, product_id: str) -> Optional[float]:
        url = self._url(product_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            data = json.loads(body.decode("utf-8"))
            if "price" not in data:
                return None
            return float(data["price"])
        except (error.URLError, ValueError, KeyError):
            return None


def load_inventory(path: Path) -> Inventory:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Inventory.from_dict(raw)
    except Exception:
        return Inventory(inventory_id="local")


def save_inventory(path: Path, inv: Inventory) -> None:
    payload = inv.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def compute_summary(inv: Inventory) -> Dict[str, Any]:
    products = inv.all()
    if not products:
        return {"count": 0, "avg_price": 0.0, "low_stock": 0}
    total_price = sum(p.price for p in products)
    low = sum(1 for p in products if p.is_low_stock())
    return {
        "count": len(products),
        "avg_price": total_price / len(products),
        "low_stock": low,
    }


def update_prices(inv: Inventory, client: PricingClient) -> int:
    updated = 0
    for product in inv.all():
        new_price = client.fetch_price(product.product_id)
        if new_price is not None and new_price != product.price:
            product.price = new_price
            product.updated_at = datetime.utcnow()
            updated += 1
    return updated


def simulate_sales(inv: Inventory, rounds: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    products = inv.all()
    if not products:
        return history
    for step in range(rounds):
        p = random.choice(products)
        sold = random.randint(0, 3)
        if sold > 0 and p.stock > 0:
            p.stock = max(0, p.stock - sold)
        history.append({"round": step, "product_id": p.product_id, "sold": sold})
    return history


def restock_low(inv: Inventory, min_stock: int = 5, target_stock: int = 10) -> int:
    count = 0
    for product in inv.low_stock(min_stock):
        if product.stock < target_stock:
            product.stock = target_stock
            product.updated_at = datetime.utcnow()
            count += 1
    return count


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    inv_path = base / "inventory.json"
    summary_path = base / "inventory_summary.json"

    inv = load_inventory(inv_path)
    client = PricingClient(base_url=base_url) if base_url else PricingClient("http://localhost:8000")

    simulate_sales(inv, rounds=5)
    restock_low(inv)
    updated = update_prices(inv, client)
    summary = compute_summary(inv)
    summary["prices_updated"] = updated

    save_inventory(inv_path, inv)
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
