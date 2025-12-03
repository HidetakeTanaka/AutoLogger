from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class Product:
    product_id: str
    name: str
    base_price: float
    tags: List[str] = field(default_factory=list)
    active: bool = True

    def is_discountable(self, now: Optional[datetime] = None) -> bool:
        if not self.active:
            return False
        if now is None:
            return True
        if now.weekday() in (5, 6):
            return True
        return "promo" in (t.lower() for t in self.tags)

    def matches_query(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.product_id.lower():
            return True
        if q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "base_price": self.base_price,
            "tags": list(self.tags),
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            pid = str(raw.get("product_id", "")).strip()
            if not pid:
                return None
            name = str(raw.get("name", "")).strip()
            price = float(raw.get("base_price", 0.0))
            tags = list(raw.get("tags", []))
            active = bool(raw.get("active", True))
            return cls(product_id=pid, name=name, base_price=price, tags=tags, active=active)
        except Exception:
            return None


@dataclass
class CartItem:
    product: Product
    quantity: int = 1

    def subtotal(self) -> float:
        if self.quantity <= 0:
            return 0.0
        return self.product.base_price * self.quantity


@dataclass
class Cart:
    items: List[CartItem] = field(default_factory=list)

    def add(self, product: Product, quantity: int = 1) -> None:
        if quantity <= 0:
            return
        for item in self.items:
            if item.product.product_id == product.product_id:
                item.quantity += quantity
                return
        self.items.append(CartItem(product=product, quantity=quantity))

    def total_quantity(self) -> int:
        return sum(i.quantity for i in self.items)

    def total_price(self) -> float:
        return sum(i.subtotal() for i in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [
                {"product": i.product.to_dict(), "quantity": i.quantity}
                for i in self.items
            ]
        }


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, product_id: str) -> str:
        return f"{self.base_url}/price/{product_id}"

    def fetch_price(self, product_id: str) -> Optional[float]:
        url = self._url(product_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except error.URLError:
            return None
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        value = data.get("price")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def load_products(path: Path) -> Dict[str, Product]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    result: Dict[str, Product] = {}
    for raw in data if isinstance(data, list) else data.get("products", []):
        prod = Product.from_dict(raw)
        if prod is not None:
            result[prod.product_id] = prod
    return result


def save_cart(path: Path, cart: Cart) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(cart.to_dict(), f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def apply_discounts(products: Iterable[Product], now: Optional[datetime] = None) -> Dict[str, float]:
    discounts: Dict[str, float] = {}
    for p in products:
        if not p.active:
            discounts[p.product_id] = 0.0
            continue
        if p.is_discountable(now):
            if "clearance" in (t.lower() for t in p.tags):
                discounts[p.product_id] = 0.4
            else:
                discounts[p.product_id] = 0.1
        else:
            discounts[p.product_id] = 0.0
    return discounts


def compute_cart_total(cart: Cart, discounts: Dict[str, float]) -> float:
    total = 0.0
    for item in cart.items:
        rate = discounts.get(item.product.product_id, 0.0)
        price = item.product.base_price * (1.0 - rate)
        if price < 0:
            price = 0.0
        total += price * item.quantity
    return total


def sync_remote_prices(products: Dict[str, Product], client: PricingClient, max_updates: int = 10) -> int:
    updated = 0
    for p in products.values():
        if updated >= max_updates:
            break
        remote = client.fetch_price(p.product_id)
        if remote is None:
            continue
        if abs(remote - p.base_price) > 0.01:
            p.base_price = remote
            updated += 1
    return updated


def summarize_cart(cart: Cart, discounts: Dict[str, float]) -> Dict[str, Any]:
    total_before = cart.total_price()
    total_after = compute_cart_total(cart, discounts)
    if total_before <= 0:
        savings_rate = 0.0
    else:
        savings_rate = (total_before - total_after) / total_before
    return {
        "items": cart.total_quantity(),
        "total_before": total_before,
        "total_after": total_after,
        "savings_rate": savings_rate,
    }


def main(base_dir: str = "data", base_url: str = "") -> int:
    base = Path(base_dir)
    products_path = base / "products.json"
    cart_path = base / "cart.json"
    products = load_products(products_path)
    if not products:
        return 1
    cart = Cart()
    i = 0
    for prod in products.values():
        qty = 1 if i % 2 == 0 else 2
        cart.add(prod, qty)
        i += 1
        if i >= 5:
            break
    client = PricingClient(base_url=base_url or "https://example.com/api")
    sync_remote_prices(products, client)
    discounts = apply_discounts(products.values())
    summary = summarize_cart(cart, discounts)
    save_cart(cart_path, cart)
    if summary["items"] == 0:
        return 1
    return 0
