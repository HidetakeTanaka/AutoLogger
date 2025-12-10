import json
from typing import List, Dict, Any

class Product:
    def __init__(self, name: str, price: float, quantity: int, category: str) -> None:
        self.name = name
        self.price = price
        self.quantity = quantity
        self.category = category

    def update_quantity(self, quantity: int) -> None:
        self.quantity = quantity

    def update_price(self, price: float) -> None:
        self.price = price

    def get_product_info(self) -> Dict[str, Any]:
        return {'name': self.name, 'price': self.price, 'quantity': self.quantity, 'category': self.category}


class Inventory:
    def __init__(self) -> None:
        self.products: List[Product] = []

    def add_product(self, product: Product) -> None:
        self.products.append(product)

    def remove_product(self, name: str) -> bool:
        for product in self.products:
            if product.name == name:
                self.products.remove(product)
                return True
        return False

    def get_inventory_value(self) -> float:
        return sum((product.price * product.quantity for product in self.products))

    def get_products_by_category(self, category: str) -> List[Dict[str, Any]]:
        return [product.get_product_info() for product in self.products if product.category == category]


class FileManager:
    @staticmethod
    def read_json(file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            pass


def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)


def create_inventory() -> Inventory:
    return Inventory()


def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        # Simulate a fetch operation
        return [{"name": "Product1", "price": 10.0, "quantity": 5, "category": "Category1"}]
    except Exception as e:
        return []


def main() -> None:
    inventory = create_inventory()
    product1 = create_product("Product1", 10.0, 5, "Category1")
    product2 = create_product("Product2", 15.0, 10, "Category2")

    inventory.add_product(product1)
    inventory.add_product(product2)

    print(f"Total Inventory Value: {inventory.get_inventory_value()}")

    products_in_category1 = inventory.get_products_by_category("Category1")
    print(f"Products in Category1: {products_in_category1}")

    # File operations
    file_path = "inventory_data.json"
    data_to_write = [{"name": product1.name, "price": product1.price}]
    FileManager.write_json(file_path, data_to_write)

    data_from_file = FileManager.read_json(file_path)
    print(f"Data from file: {data_from_file}")

    # Fetch data
    url = "http://example.com/products"
    fetched_data = fetch_data(url)
    print(f"Fetched data: {fetched_data}")
