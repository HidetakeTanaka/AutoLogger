from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class Product:
    product_id: str
    name: str
    category: str
    price: float
    updated_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.updated_at >= cutoff:
            return True
        return False

    def matches_category(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.category.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            ts_raw = raw.get("updated_at") or ""
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                product_id=str(raw.get("product_id", "")),
                name=str(raw.get("name", "")),
                category=str(raw.get("category", "")),
                price=float(raw.get("price", 0.0)),
                updated_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class CustomerPrefs:
    customer_id: str
    favorite_categories: List[str]
    max_budget: float
    updated_at: datetime

    def needs_refresh(self, days: int = 7) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "favorite_categories": list(self.favorite_categories),
            "max_budget": self.max_budget,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["CustomerPrefs"]:
        try:
            ts_raw = raw.get("updated_at") or ""
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                customer_id=str(raw.get("customer_id", "")),
                favorite_categories=list(raw.get("favorite_categories", [])),
                max_budget=float(raw.get("max_budget", 0.0)),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class InventoryState:
    customer_id: str
    products: List[Product] = field(default_factory=list)
    prefs: Optional[CustomerPrefs] = None

    def add_product(self, product: Product) -> None:
        for i, p in enumerate(self.products):
            if p.product_id == product.product_id:
                self.products[i] = product
                return
        self.products.append(product)

    def filter_for_customer(self) -> List[Product]:
        if not self.prefs:
            return [p for p in self.products if p.price >= 0]
        fav = {c.lower() for c in self.prefs.favorite_categories}
        results: List[Product] = []
        for p in self.products:
            if p.price > self.prefs.max_budget:
                continue
            if not fav or p.category.lower() in fav:
                results.append(p)
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "prefs": self.prefs.to_dict() if self.prefs else None,
            "products": [p.to_dict() for p in self.products],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "InventoryState":
        state = cls(customer_id=str(raw.get("customer_id", "local")))
        p_raw = raw.get("prefs")
        if p_raw:
            prefs = CustomerPrefs.from_dict(p_raw)
            if prefs:
                state.prefs = prefs
        for pr in raw.get("products", []):
            prod = Product.from_dict(pr)
            if prod:
                state.products.append(prod)
        return state


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_remote_price(self, product_id: str) -> Optional[float]:
        url = self._url(f"price/{product_id}")
        if not url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            parsed = json.loads(data.decode("utf-8"))
            value = parsed.get("price")
            return float(value) if value is not None else None
        except (error.URLError, error.HTTPError, ValueError, KeyError):
            return None


def load_inventory(path: Path) -> InventoryState:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return InventoryState.from_dict(raw)
    except FileNotFoundError:
        return InventoryState(customer_id="local")
    except Exception:
        return InventoryState(customer_id="local")


def save_inventory(path: Path, state: InventoryState) -> None:
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_category_stats(state: InventoryState) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for p in state.products:
        totals[p.category] = totals.get(p.category, 0.0) + p.price
        counts[p.category] = counts.get(p.category, 0) + 1
    if not totals:
        return {}
    return {k: totals[k] / counts[k] for k in totals}


def suggest_bundle(state: InventoryState, budget: float) -> List[Product]:
    available = sorted(state.products, key=lambda p: p.price)
    bundle: List[Product] = []
    remaining = budget
    for p in available:
        if p.price <= 0 or p.price > remaining:
            continue
        bundle.append(p)
        remaining -= p.price
        if remaining <= 0:
            break
    return bundle


def simulate_purchases(state: InventoryState, sessions: int = 5) -> int:
    if not state.products:
        return 0
    purchases = 0
    i = 0
    while i < sessions:
        basket_size = random.randint(1, min(3, len(state.products)))
        chosen = random.sample(state.products, basket_size)
        if sum(p.price for p in chosen) > 0:
            purchases += 1
        i += 1
    return purchases


def summarize_inventory(state: InventoryState, client: Optional[PricingClient]) -> Dict[str, Any]:
    if client:
        for p in state.products:
            new_price = client.fetch_remote_price(p.product_id)
            if new_price is not None and new_price > 0:
                p.price = new_price
    stats = compute_category_stats(state)
    filtered = state.filter_for_customer()
    recent = [p for p in state.products if p.is_recent()]
    return {
        "customer_id": state.customer_id,
        "total_products": len(state.products),
        "filtered_products": len(filtered),
        "recent_products": len(recent),
        "category_avg_price": stats,
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    state_path = base / "inventory.json"
    state = load_inventory(state_path)
    client = PricingClient(base_url=base_url) if base_url else None
    if not state.products:
        now = datetime.utcnow()
        for i in range(5):
            p = Product(
                product_id=f"p{i+1}",
                name=f"Product {i+1}",
                category="general" if i % 2 == 0 else "special",
                price=10.0 + i * 2,
                updated_at=now - timedelta(hours=i),
                tags=["demo"],
            )
            state.add_product(p)
    purchases = simulate_purchases(state)
    summary = summarize_inventory(state, client)
    summary["simulated_purchases"] = purchases
    save_inventory(state_path, state)
    summary_path = base / "inventory_summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
