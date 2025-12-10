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
        return {
            'name': self.name,
            'price': self.price,
            'quantity': self.quantity,
            'category': self.category
        }

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
        except Exception as e:
            print(f"Error writing to file: {e}")

def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)

def create_inventory() -> Inventory:
    return Inventory()

def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return []

def main() -> None:
    # Create inventory and products
    inventory = create_inventory()
    product1 = create_product("Laptop", 1000, 5, "Electronics")
    product2 = create_product("Smartphone", 500, 10, "Electronics")
    
    # Add products to inventory
    inventory.add_product(product1)
    inventory.add_product(product2)

    # Print inventory value
    print(f"Inventory Value: ${inventory.get_inventory_value():.2f}")

    # Fetch products data from API
    url = "https://api.example.com/products"
    products_data = fetch_data(url)

    # Add fetched products to inventory
    for product_data in products_data:
        product = create_product(
            product_data['name'],
            product_data['price'],
            product_data['quantity'],
            product_data['category']
        )
        inventory.add_product(product)

    # Print all products in "Electronics" category
    electronics = inventory.get_products_by_category("Electronics")
    print("Electronics products:", electronics)

    # Write the inventory data to a JSON file
    inventory_data = [product.get_product_info() for product in inventory.products]
    FileManager.write_json("inventory.json", inventory_data)

if __name__ == "__main__":
    main()
