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
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file)
        except Exception as e:
            pass

def create_product(name: str, price: float, quantity: int, category: str) -> Product:
    return Product(name, price, quantity, category)

def create_inventory() -> Inventory:
    return Inventory()

def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url)
        return response.json()
    except Exception as e:
        return []

def main() -> None:
    product1 = create_product('Laptop', 1200.0, 10, 'Electronics')
    product2 = create_product('Smartphone', 800.0, 15, 'Electronics')
    inventory = create_inventory()

    inventory.add_product(product1)
    inventory.add_product(product2)

    print(f'Total Inventory Value: {inventory.get_inventory_value()}')

    electronics = inventory.get_products_by_category('Electronics')
    print(f'Electronics: {electronics}')

    file_path = 'inventory.json'
    FileManager.write_json(file_path, [product1.get_product_info(), product2.get_product_info()])
    data = FileManager.read_json(file_path)
    print(f'Read data: {data}')
