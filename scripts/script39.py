from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class Product:
    product_id: str
    name: str
    category: str
    price: float
    rating: float

    def is_valid(self) -> bool:
        if self.price < 0:
            return False
        return 0.0 <= self.rating <= 5.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "rating": self.rating,
        }


@dataclass
class Review:
    review_id: str
    product_id: str
    user_id: str
    score: int
    ts: datetime

    def is_recent(self, hours: int = 24) -> bool:
        now = datetime.utcnow()
        return now - self.ts <= timedelta(hours=hours)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "product_id": self.product_id,
            "user_id": self.user_id,
            "score": self.score,
            "ts": self.ts.isoformat(),
        }


@dataclass
class User:
    user_id: str
    country: str
    age: int

    def is_adult(self) -> bool:
        return self.age >= 18

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "country": self.country,
            "age": self.age,
        }


class ProductCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._products: Dict[str, Product] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._products = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._products = {}
            return
        for raw in data.get("products", []):
            try:
                p = Product(
                    product_id=str(raw["product_id"]),
                    name=str(raw.get("name", "")),
                    category=str(raw.get("category", "")),
                    price=float(raw.get("price", 0.0)),
                    rating=float(raw.get("rating", 0.0)),
                )
            except (KeyError, ValueError):
                continue
            if p.is_valid():
                self._products[p.product_id] = p

    def all(self) -> List[Product]:
        return list(self._products.values())

    def get(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)


class ReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> List[Review]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        result: List[Review] = []
        for raw in data.get("reviews", []):
            try:
                ts = datetime.fromisoformat(str(raw["ts"]))
                r = Review(
                    review_id=str(raw["review_id"]),
                    product_id=str(raw["product_id"]),
                    user_id=str(raw["user_id"]),
                    score=int(raw.get("score", 0)),
                    ts=ts,
                )
            except (KeyError, ValueError):
                continue
            result.append(r)
        return result


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def get_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        url = self.base_url + endpoint
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8"))
        except (URLError, HTTPError, json.JSONDecodeError):
            return None


def filter_recent_reviews(reviews: Iterable[Review], hours: int = 48) -> List[Review]:
    now = datetime.utcnow()
    return [r for r in reviews if now - r.ts <= timedelta(hours=hours)]


def group_reviews_by_product(reviews: Iterable[Review]) -> Dict[str, List[Review]]:
    grouped: Dict[str, List[Review]] = {}
    for r in reviews:
        grouped.setdefault(r.product_id, []).append(r)
    return grouped


def compute_average_scores(groups: Dict[str, List[Review]]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for pid, rs in groups.items():
        if not rs:
            result[pid] = 0.0
            continue
        values = [r.score for r in rs]
        result[pid] = sum(values) / len(values)
    return result


def load_users(path: Path) -> Dict[str, User]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    result: Dict[str, User] = {}
    for raw in data.get("users", []):
        try:
            u = User(
                user_id=str(raw["user_id"]),
                country=str(raw.get("country", "unknown")),
                age=int(raw.get("age", 0)),
            )
            result[u.user_id] = u
        except (KeyError, ValueError):
            continue
    return result


def fetch_remote_products(client: ApiClient) -> List[Dict[str, Any]]:
    data = client.get_json("/products")
    if not data:
        return []
    items = data.get("products", [])
    return [dict(it) for it in items]


def select_top_products(scores: Dict[str, float], limit: int = 5) -> List[str]:
    if not scores:
        return []
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in sorted_items[:limit]]


def write_report(path: Path, products: List[Product], scores: Dict[str, float]) -> None:
    payload = []
    for p in products:
        payload.append(
            {
                "product_id": p.product_id,
                "name": p.name,
                "score": scores.get(p.product_id, 0.0),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"report": payload}, f, indent=2, ensure_ascii=False)


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    products_path = base / "products.json"
    reviews_path = base / "reviews.json"
    report_path = base / "report.json"

    catalog = ProductCatalog(products_path)
    catalog.load()
    products = catalog.all()

    review_store = ReviewStore(reviews_path)
    reviews = review_store.load()

    if not products or not reviews:
        return 1

    recent = filter_recent_reviews(reviews, hours=72)
    grouped = group_reviews_by_product(recent)
    scores = compute_average_scores(grouped)

    write_report(report_path, products, scores)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
