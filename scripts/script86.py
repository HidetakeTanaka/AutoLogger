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
    sku: str
    name: str
    price: float
    quantity: int
    tags: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_low_stock(self, threshold: int = 5) -> bool:
        return self.quantity <= threshold

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.sku.lower() or q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "tags": list(self.tags),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                sku=str(raw.get("sku", "")),
                name=str(raw.get("name", "")),
                price=float(raw.get("price", 0.0)),
                quantity=int(raw.get("quantity", 0)),
                tags=list(raw.get("tags", [])),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class Inventory:
    store_id: str
    products: Dict[str, Product] = field(default_factory=dict)

    def add_product(self, product: Product) -> None:
        self.products[product.sku] = product

    def search(self, query: str = "") -> List[Product]:
        return [p for p in self.products.values() if p.matches(query)]

    def total_value(self) -> float:
        return sum(p.price * p.quantity for p in self.products.values())

    def low_stock(self, threshold: int = 5) -> List[Product]:
        return [p for p in self.products.values() if p.is_low_stock(threshold)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_id": self.store_id,
            "products": [p.to_dict() for p in self.products.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Inventory":
        inv = cls(store_id=str(raw.get("store_id", "local")))
        for item in raw.get("products", []):
            prod = Product.from_dict(item)
            if prod:
                inv.add_product(prod)
        return inv


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_tax_rate(self, country: str) -> Optional[float]:
        if not self.base_url:
            return None
        url = self._url(f"tax?country={country}")
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            value = parsed.get("rate")
            return float(value) if value is not None else None
        except (error.URLError, ValueError, KeyError):
            return None


def load_inventory(path: Path) -> Inventory:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return Inventory.from_dict(raw)
    except FileNotFoundError:
        return Inventory(store_id="local")
    except Exception:
        return Inventory(store_id="local")


def save_inventory(path: Path, inv: Inventory) -> None:
    payload = json.dumps(inv.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def apply_markdown(inv: Inventory, tag: str, pct: float) -> int:
    affected = 0
    for p in inv.products.values():
        if tag in p.tags:
            p.price = max(0.0, p.price * (1 - pct))
            p.updated_at = datetime.utcnow()
            affected += 1
    return affected


def compute_daily_projection(inv: Inventory, hours: int = 24) -> float:
    if not inv.products:
        return 0.0
    now = datetime.utcnow()
    total = 0.0
    for p in inv.products.values():
        age = (now - p.updated_at).total_seconds() / 3600
        factor = 1.0 if age <= hours else 0.5
        total += p.price * p.quantity * factor
    return total


def simulate_sales(inv: Inventory, days: int = 3) -> int:
    if days <= 0:
        return 0
    sold = 0
    for _ in range(days):
        for p in list(inv.products.values()):
            if p.quantity <= 0:
                continue
            qty = random.randint(0, min(3, p.quantity))
            p.quantity -= qty
            sold += qty
            p.updated_at = datetime.utcnow() - timedelta(hours=random.randint(0, 12))
    return sold


def summarize_inventory(inv: Inventory, tax_rate: Optional[float]) -> Dict[str, Any]:
    base_value = inv.total_value()
    if tax_rate is None:
        return {
            "store_id": inv.store_id,
            "value": base_value,
            "value_with_tax": None,
            "low_stock": len(inv.low_stock()),
        }
    taxed = base_value * (1 + tax_rate)
    return {
        "store_id": inv.store_id,
        "value": base_value,
        "value_with_tax": taxed,
        "low_stock": len(inv.low_stock()),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store_path = base / "inventory.json"
    inv = load_inventory(store_path)

    if not inv.products:
        for i in range(5):
            p = Product(
                sku=f"SKU{i+1}",
                name=f"Sample {i+1}",
                price=10.0 + i,
                quantity=10 + 2 * i,
                tags=["demo", "starter"] if i % 2 == 0 else ["demo"],
            )
            inv.add_product(p)

    simulate_sales(inv, days=2)
    apply_markdown(inv, "starter", 0.1)

    client = PricingClient(base_url=base_url)
    tax_rate = client.fetch_tax_rate("US") if base_url else None
    summary = summarize_inventory(inv, tax_rate)

    summary_path = base / "summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1

    save_inventory(store_path, inv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
