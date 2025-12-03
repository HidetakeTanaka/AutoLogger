from __future__ import annotations

import json
import random
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable


@dataclass
class Product:
    sku: str
    name: str
    price: float
    tags: List[str] = field(default_factory=list)
    updated: datetime = field(default_factory=datetime.utcnow)

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.updated >= datetime.utcnow() - timedelta(days=days)

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "name": self.name,
            "price": self.price,
            "tags": list(self.tags),
            "updated": self.updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            ts_raw = str(raw.get("updated", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                sku=str(raw.get("sku", "")),
                name=str(raw.get("name", "")),
                price=float(raw.get("price", 0.0)),
                tags=list(raw.get("tags", [])),
                updated=ts,
            )
        except Exception:
            return None


@dataclass
class Inventory:
    store_id: str
    products: List[Product] = field(default_factory=list)

    def add_product(self, product: Product) -> None:
        for idx, p in enumerate(self.products):
            if p.sku == product.sku:
                self.products[idx] = product
                return
        self.products.append(product)

    def find(self, query: str) -> List[Product]:
        return [p for p in self.products if p.matches(query)]

    def recent_products(self, days: int = 7) -> List[Product]:
        return [p for p in self.products if p.is_recent(days)]

    def total_value(self) -> float:
        return sum(p.price for p in self.products)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_id": self.store_id,
            "products": [p.to_dict() for p in self.products],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Inventory":
        inv = cls(store_id=str(raw.get("store_id", "unknown")))
        for item in raw.get("products", []):
            prod = Product.from_dict(item)
            if prod is not None:
                inv.add_product(prod)
        return inv


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, sku: str) -> str:
        return f"{self.base_url}/pricing/{sku}"

    def fetch_remote_prices(self, skus: Iterable[str]) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for sku in skus:
            url = self._url(sku)
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8")
                data = json.loads(body)
                price = float(data.get("price", 0.0))
                if price > 0:
                    result[sku] = price
            except (urllib.error.URLError, ValueError, json.JSONDecodeError):
                continue
        return result


def load_inventory(path: Path) -> Inventory:
    if not path.is_file():
        return Inventory(store_id="local")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return Inventory.from_dict(data)
    except Exception:
        return Inventory(store_id="local")


def save_inventory(path: Path, inv: Inventory) -> None:
    payload = inv.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def apply_price_updates(inv: Inventory, prices: Dict[str, float]) -> int:
    updated = 0
    now = datetime.utcnow()
    for p in inv.products:
        if p.sku in prices:
            new_price = prices[p.sku]
            if new_price != p.price:
                p.price = new_price
                p.updated = now
                updated += 1
    return updated


def summarize_inventory(inv: Inventory) -> Dict[str, Any]:
    total = len(inv.products)
    if total == 0:
        return {"store_id": inv.store_id, "total": 0, "avg_price": 0.0, "recent": 0}
    avg_price = inv.total_value() / total
    recent = len(inv.recent_products(7))
    return {
        "store_id": inv.store_id,
        "total": total,
        "avg_price": avg_price,
        "recent": recent,
    }


def pick_random_product(inv: Inventory, cheap_only: bool = False) -> Optional[Product]:
    if not inv.products:
        return None
    candidates = inv.products
    if cheap_only:
        limit = max(p.price for p in inv.products) * 0.5 if inv.products else 0.0
        candidates = [p for p in inv.products if p.price <= limit]
    if not candidates:
        return None
    return random.choice(candidates)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    inv_path = base / "inventory.json"
    inv = load_inventory(inv_path)

    if not base_url:
        prices = {p.sku: p.price for p in inv.products}
    else:
        client = PricingClient(base_url=base_url)
        prices = client.fetch_remote_prices([p.sku for p in inv.products])

    apply_price_updates(inv, prices)
    save_inventory(inv_path, inv)

    summary = summarize_inventory(inv)
    report_path = base / "inventory_report.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1

    _ = pick_random_product(inv, cheap_only=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
