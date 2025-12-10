from typing import List, Dict, Any
import requests
import json

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
            print(f"Error reading file: {e}")
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            print(f"Error writing file: {e}")


def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)


def create_inventory() -> Inventory:
    return Inventory()


def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def main() -> None:
    inventory = create_inventory()

    # Fetch product data
    url = 'https://api.example.com/products'
    products_data = fetch_data(url)

    for product_data in products_data:
        product = create_product(
            product_data['name'],
            product_data['price'],
            product_data['quantity'],
            product_data['category']
        )
        inventory.add_product(product)

    print(f"Total inventory value: {inventory.get_inventory_value()}")

    # Get products by category
    category = 'Electronics'
    electronics = inventory.get_products_by_category(category)
    print(f"Products in category {category}: {electronics}")

    # Save inventory to file
    file_path = 'inventory.json'
    FileManager.write_json(file_path, [product.get_product_info() for product in inventory.products])

    # Read inventory from file
    saved_inventory = FileManager.read_json(file_path)
    print(f"Saved inventory: {saved_inventory}")


if __name__ == "__main__":
    main()
