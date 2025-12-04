import os
import json
import requests
from typing import List, Dict, Any


class Product:
    def __init__(self, name: str, price: float, quantity: int, category: str) -> None:
        self.name = name
        self.price = price
        self.quantity = quantity
        self.category = category

    def update_quantity(self, quantity: int) -> None:
        self.quantity += quantity

    def update_price(self, price: float) -> None:
        self.price = price

    def get_product_info(self) -> Dict[str, Any]:
        return {"name": self.name, "price": self.price, "quantity": self.quantity, "category": self.category}


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
        return sum(product.price * product.quantity for product in self.products)

    def get_products_by_category(self, category: str) -> List[Dict[str, Any]]:
        return [product.get_product_info() for product in self.products if product.category == category]


class FileManager:
    @staticmethod
    def read_json(file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except IOError:
            pass


class APIClient:
    @staticmethod
    def fetch_data(url: str) -> List[Dict[str, Any]]:
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return []


def load_inventory(file_path: str) -> Inventory:
    inventory = Inventory()
    product_data = FileManager.read_json(file_path)
    for item in product_data:
        product = Product(item["name"], item["price"], item["quantity"], item["category"])
        inventory.add_product(product)
    return inventory


def save_inventory(inventory: Inventory, file_path: str) -> None:
    product_data = [product.get_product_info() for product in inventory.products]
    FileManager.write_json(file_path, product_data)


def create_order(products: List[Product], quantities: List[int]) -> Dict[str, Any]:
    total_amount = sum(product.price * quantity for product, quantity in zip(products, quantities))
    order = {"products": [product.get_product_info() for product in products], "total_amount": total_amount}
    return order


def fetch_api_data(url: str) -> List[Dict[str, Any]]:
    return APIClient.fetch_data(url)


def main() -> None:
    input_file = "inventory.json"
    output_file = "updated_inventory.json"
    inventory = load_inventory(input_file)

    # Add new product
    new_product = Product("New Product", 20.5, 100, "Electronics")
    inventory.add_product(new_product)

    # Remove product
    inventory.remove_product("Old Product")

    # Save updated inventory
    save_inventory(inventory, output_file)

    # Fetch external data from API
    api_url = "https://api.example.com/products"
    api_data = fetch_api_data(api_url)
    print(f"Fetched data from API: {api_data}")

    # Example order creation
    selected_products = [product for product in inventory.products if product.category == "Electronics"]
    quantities = [2, 3]
    order = create_order(selected_products, quantities)
    print(f"Order created: {order}")


if __name__ == "__main__":
    main()
