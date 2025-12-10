import os
import json
import requests
from typing import List, Dict, Any


class Product:
    def __init__(self, name: str, category: str, price: float, stock: int) -> None:
        self.name = name
        self.category = category
        self.price = price
        self.stock = stock

    def update_stock(self, quantity: int) -> None:
        self.stock += quantity

    def update_price(self, new_price: float) -> None:
        self.price = new_price

    def get_product_info(self) -> Dict[str, Any]:
        return {"name": self.name, "category": self.category, "price": self.price, "stock": self.stock}


class Inventory:
    def __init__(self) -> None:
        self.products = []

    def add_product(self, product: Product) -> None:
        self.products.append(product)

    def remove_product(self, product_name: str) -> bool:
        for product in self.products:
            if product.name == product_name:
                self.products.remove(product)
                return True
        return False

    def get_inventory_value(self) -> float:
        return sum(product.price * product.stock for product in self.products)

    def filter_by_category(self, category: str) -> List[Dict[str, Any]]:
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
        product = Product(item["name"], item["category"], item["price"], item["stock"])
        inventory.add_product(product)
    return inventory


def save_inventory(inventory: Inventory, file_path: str) -> None:
    product_data = [product.get_product_info() for product in inventory.products]
    FileManager.write_json(file_path, product_data)


def process_inventory(input_file: str, output_file: str, category: str) -> None:
    inventory = load_inventory(input_file)
    filtered_products = inventory.filter_by_category(category)
    total_value = inventory.get_inventory_value()
    print(f"Total inventory value: ${total_value:.2f}")
    print(f"Filtered products in category '{category}': {filtered_products}")
    save_inventory(inventory, output_file)


def update_product_prices(inventory: Inventory, price_increase_percentage: float) -> None:
    for product in inventory.products:
        new_price = product.price * (1 + price_increase_percentage / 100)
        product.update_price(new_price)


def fetch_api_data(url: str) -> List[Dict[str, Any]]:
    return APIClient.fetch_data(url)


def main() -> None:
    input_file = "inventory.json"
    output_file = "updated_inventory.json"
    category = "Electronics"
    
    process_inventory(input_file, output_file, category)
    
    api_url = "https://api.example.com/products"
    api_data = fetch_api_data(api_url)
    print(f"Fetched API data: {api_data}")


if __name__ == "__main__":
    main()
