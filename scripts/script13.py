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
        # Simulating a web request
        data = [{'product_name': 'Laptop', 'price': 1000, 'quantity': 10, 'category': 'Electronics'}]
        return data
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return []


def main() -> None:
    inventory = create_inventory()
    product1 = create_product("Laptop", 1000, 10, "Electronics")
    product2 = create_product("Phone", 500, 20, "Electronics")
    
    inventory.add_product(product1)
    inventory.add_product(product2)
    
    print("Total inventory value:", inventory.get_inventory_value())
    
    data = fetch_data("https://example.com/api/products")
    for item in data:
        product = create_product(item['product_name'], item['price'], item['quantity'], item['category'])
        inventory.add_product(product)
    
    print("Updated inventory value:", inventory.get_inventory_value())

    # Save to file
    FileManager.write_json("inventory.json", [product.get_product_info() for product in inventory.products])


if __name__ == "__main__":
    main()
