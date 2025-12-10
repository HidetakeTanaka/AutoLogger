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
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            print(f"Error writing to file {file_path}: {e}")

def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)

def create_inventory() -> Inventory:
    return Inventory()

def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        # Simulating an HTTP request to fetch data from an API
        data = [{"name": "Product1", "price": 100.0, "quantity": 10, "category": "Category1"},
                {"name": "Product2", "price": 150.0, "quantity": 20, "category": "Category2"}]
        return data
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return []

def main() -> None:
    # Sample file path and API URL
    file_path = 'inventory.json'
    api_url = 'https://api.example.com/products'

    # Create an inventory and fetch data
    inventory = create_inventory()
    products_data = fetch_data(api_url)

    # Add products to inventory
    for product_data in products_data:
        product = create_product(product_data['name'], product_data['price'], product_data['quantity'], product_data['category'])
        inventory.add_product(product)

    # Save the inventory to a file
    FileManager.write_json(file_path, [product.get_product_info() for product in inventory.products])

    # Print the inventory value
    print(f"Total inventory value: ${inventory.get_inventory_value():.2f}")

    # Print products by category
    category = "Category1"
    print(f"Products in {category}: {inventory.get_products_by_category(category)}")

if __name__ == '__main__':
    main()
