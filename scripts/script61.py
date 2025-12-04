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
    price: float
    tags: List[str] = field(default_factory=list)

    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "price": self.price,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            return cls(
                product_id=str(raw.get("product_id", "")),
                name=str(raw.get("name", "")),
                price=float(raw.get("price", 0.0)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class CartItem:
    product: Product
    quantity: int = 1

    def line_total(self) -> float:
        return self.product.price * self.quantity


class Cart:
    def __init__(self, cart_id: str) -> None:
        self.cart_id = cart_id
        self.created_at = datetime.utcnow()
        self.items: Dict[str, CartItem] = {}

    def add(self, product: Product, quantity: int = 1) -> None:
        if product.product_id in self.items:
            self.items[product.product_id].quantity += quantity
        else:
            self.items[product.product_id] = CartItem(product=product, quantity=quantity)

    def remove(self, product_id: str) -> None:
        if product_id in self.items:
            del self.items[product_id]

    def total(self) -> float:
        return sum(item.line_total() for item in self.items.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cart_id": self.cart_id,
            "created_at": self.created_at.isoformat(),
            "items": [
                {
                    "product": it.product.to_dict(),
                    "quantity": it.quantity,
                }
                for it in self.items.values()
            ],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Cart":
        cart = cls(cart_id=str(raw.get("cart_id", "local")))
        items_raw = raw.get("items", [])
        for row in items_raw:
            p_raw = row.get("product", {})
            product = Product.from_dict(p_raw)
            if product is None:
                continue
            qty = int(row.get("quantity", 1))
            cart.add(product, qty)
        return cart


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, product_id: str) -> str:
        return f"{self.base_url}/pricing/{product_id}.json"

    def fetch_price(self, product_id: str) -> Optional[float]:
        if not self.base_url:
            return None
        url = self._url(product_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return float(data.get("price"))
        except (error.URLError, ValueError, KeyError, json.JSONDecodeError):
            return None


def load_cart(path: Path) -> Cart:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Cart.from_dict(raw)
    except Exception:
        return Cart(cart_id="local")


def save_cart(path: Path, cart: Cart) -> None:
    payload = json.dumps(cart.to_dict(), indent=2)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def apply_discounts(cart: Cart, now: Optional[datetime] = None) -> float:
    if now is None:
        now = datetime.utcnow()
    total = cart.total()
    if not cart.items:
        return 0.0
    if now - cart.created_at > timedelta(hours=24):
        return total * 0.9
    if len(cart.items) >= 5:
        return total * 0.95
    return total


def pick_best_deal(carts: List[Cart]) -> Optional[Cart]:
    if not carts:
        return None
    best = None
    best_value = float("inf")
    for c in carts:
        value = apply_discounts(c)
        if value < best_value:
            best_value = value
            best = c
    return best


def update_prices_from_remote(cart: Cart, client: PricingClient) -> int:
    updated = 0
    for item in cart.items.values():
        new_price = client.fetch_price(item.product.product_id)
        if new_price is None:
            continue
        if new_price != item.product.price:
            item.product.price = new_price
            updated += 1
    return updated


def simulate_cart(cart: Cart, steps: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for step in range(steps):
        if not cart.items:
            break
        product_id = random.choice(list(cart.items.keys()))
        action = random.choice(["add", "remove"])
        if action == "add":
            cart.items[product_id].quantity += 1
        else:
            cart.items[product_id].quantity -= 1
            if cart.items[product_id].quantity <= 0:
                cart.remove(product_id)
        history.append(
            {
                "step": step,
                "action": action,
                "product_id": product_id,
                "total": cart.total(),
            }
        )
    return history


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    cart_path = base / "cart.json"

    cart = load_cart(cart_path)
    if not cart.items:
        sample = Product("p1", "Sample Widget", 10.0, ["sample", "widget"])
        cart.add(sample, 2)

    client = PricingClient(base_url=base_url) if base_url else PricingClient("", 5)
    update_prices_from_remote(cart, client)

    total_before = cart.total()
    total_after = apply_discounts(cart)
    simulate_cart(cart, steps=5)

    summary = {
        "cart_id": cart.cart_id,
        "total_before": total_before,
        "total_after": total_after,
        "item_count": sum(i.quantity for i in cart.items.values()),
    }
    try:
        save_cart(cart_path, cart)
        summary_path = base / "cart_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
