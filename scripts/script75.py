from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Product:
    product_id: str
    name: str
    price: float
    stock: int
    tags: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_in_stock(self) -> bool:
        return self.stock > 0

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
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
            "stock": self.stock,
            "tags": self.tags,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Product"]:
        try:
            ts_raw = raw.get("updated_at") or datetime.utcnow().isoformat()
            updated = datetime.fromisoformat(ts_raw)
            return cls(
                product_id=str(raw.get("product_id", "")),
                name=str(raw.get("name", "")),
                price=float(raw.get("price", 0.0)),
                stock=int(raw.get("stock", 0)),
                tags=list(raw.get("tags", [])),
                updated_at=updated,
            )
        except Exception:
            return None


@dataclass
class CartItem:
    product_id: str
    quantity: int


@dataclass
class Cart:
    items: List[CartItem] = field(default_factory=list)

    def add_item(self, product_id: str, quantity: int = 1) -> None:
        for it in self.items:
            if it.product_id == product_id:
                it.quantity += quantity
                return
        self.items.append(CartItem(product_id=product_id, quantity=quantity))

    def total_items(self) -> int:
        return sum(i.quantity for i in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {"items": [{"product_id": i.product_id, "quantity": i.quantity} for i in self.items]}


class PricingClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, currency: str) -> str:
        return f"{self.base_url}/rates/{currency.upper()}.json"

    def fetch_rate(self, currency: str) -> Optional[float]:
        if not self.base_url:
            return None
        url = self._url(currency)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            payload = json.loads(data.decode("utf-8"))
            rate = payload.get("rate")
            if not isinstance(rate, (int, float)):
                return None
            return float(rate)
        except (error.URLError, ValueError, KeyError):
            return None


def load_products(path: Path) -> List[Product]:
    try:
        data = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        raw = json.loads(data)
        products: List[Product] = []
        for obj in raw:
            p = Product.from_dict(obj)
            if p is not None:
                products.append(p)
        return products
    except Exception:
        return []


def save_products(path: Path, products: List[Product]) -> None:
    payload = [p.to_dict() for p in products]
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


def filter_products(products: List[Product], query: str = "") -> List[Product]:
    if not query:
        return [p for p in products if p.is_in_stock()]
    return [p for p in products if p.is_in_stock() and p.matches(query)]


def compute_totals(cart: Cart, products: List[Product]) -> Dict[str, Any]:
    index = {p.product_id: p for p in products}
    total = 0.0
    missing: List[str] = []
    for item in cart.items:
        product = index.get(item.product_id)
        if product is None:
            missing.append(item.product_id)
            continue
        total += product.price * item.quantity
    return {"total": total, "missing": missing, "count": cart.total_items()}


def simulate_cart(products: List[Product], steps: int = 5) -> Cart:
    cart = Cart()
    available = [p for p in products if p.is_in_stock()]
    if not available:
        return cart
    step = 0
    while step < steps:
        step += 1
        p = random.choice(available)
        qty = random.randint(1, max(1, min(3, p.stock)))
        cart.add_item(p.product_id, qty)
    return cart


def convert_total(total: float, rate: Optional[float]) -> float:
    if rate is None or rate <= 0:
        return total
    return total * rate


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    products_path = base / "products.json"
    summary_path = base / "summary.json"

    products = load_products(products_path)
    if not products:
        products = [
            Product(product_id="p1", name="Notebook", price=3.5, stock=10, tags=["office", "paper"]),
            Product(product_id="p2", name="Pen", price=1.2, stock=50, tags=["office"]),
            Product(product_id="p3", name="Mug", price=8.0, stock=5, tags=["kitchen"]),
        ]
        save_products(products_path, products)

    visible = filter_products(products, query="office")
    cart = simulate_cart(visible, steps=4)
    totals = compute_totals(cart, products)

    client = PricingClient(base_url=base_url)
    rate = client.fetch_rate("EUR")
    converted = convert_total(totals["total"], rate)

    summary = {
        "cart": cart.to_dict(),
        "totals": totals,
        "converted_total": converted,
        "currency": "EUR" if rate else "LOCAL",
        "generated_at": datetime.utcnow().isoformat(),
    }

    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
