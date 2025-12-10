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
        self.quantity = quantity

    def update_price(self, price: float) -> None:
        self.price = price

    def get_product_info(self) -> Dict[str, Any]:
        return {'name': self.name, 'price': self.price, 'quantity': self.quantity, 'category': self.category}


class Inventory:
    def __init__(self) -> None:
        self.products = []

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
            print(f"Error reading JSON file: {e}")
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file)
        except Exception as e:
            print(f"Error writing to JSON file: {e}")


def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)


def create_inventory() -> Inventory:
    return Inventory()


def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from URL: {e}")
        return []


def main() -> None:
    url = "https://api.example.com/products"
    inventory = create_inventory()

    # Fetch products data from an API
    products_data = fetch_data(url)

    # Add products to inventory
    for product_data in products_data:
        product = create_product(product_data['name'], product_data['price'], product_data['quantity'], product_data['category'])
        inventory.add_product(product)

    # Print total inventory value
    print(f"Total inventory value: ${inventory.get_inventory_value():.2f}")

    # Save inventory to a file
    file_path = 'inventory.json'
    inventory_data = [product.get_product_info() for product in inventory.products]
    FileManager.write_json(file_path, inventory_data)

    # Print products in the "Electronics" category
    electronics_products = inventory.get_products_by_category("Electronics")
    print(f"Electronics products: {electronics_products}")


if __name__ == "__main__":
    main()
