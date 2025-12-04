import os
import json
import requests
from typing import List, Dict, Any


class Customer:
    def __init__(self, name: str, email: str, age: int, address: str) -> None:
        self.name = name
        self.email = email
        self.age = age
        self.address = address

    def update_email(self, new_email: str) -> None:
        self.email = new_email

    def get_customer_info(self) -> Dict[str, Any]:
        return {"name": self.name, "email": self.email, "age": self.age, "address": self.address}


class Order:
    def __init__(self, order_id: str, customer: Customer, items: List[str], total_amount: float) -> None:
        self.order_id = order_id
        self.customer = customer
        self.items = items
        self.total_amount = total_amount

    def add_item(self, item: str) -> None:
        self.items.append(item)

    def get_order_summary(self) -> Dict[str, Any]:
        return {"order_id": self.order_id, "customer": self.customer.get_customer_info(), "items": self.items, "total_amount": self.total_amount}


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


def load_customers(file_path: str) -> List[Customer]:
    customers = []
    customer_data = FileManager.read_json(file_path)
    for item in customer_data:
        customer = Customer(item["name"], item["email"], item["age"], item["address"])
        customers.append(customer)
    return customers


def save_customers(customers: List[Customer], file_path: str) -> None:
    customer_data = [customer.get_customer_info() for customer in customers]
    FileManager.write_json(file_path, customer_data)


def create_order(customer: Customer, items: List[str], total_amount: float) -> Order:
    order_id = f"ORD{len(items)}{total_amount}"
    order = Order(order_id, customer, items, total_amount)
    return order


def update_customer_email(customers: List[Customer], name: str, new_email: str) -> bool:
    for customer in customers:
        if customer.name == name:
            customer.update_email(new_email)
            return True
    return False


def fetch_api_data(url: str) -> List[Dict[str, Any]]:
    return APIClient.fetch_data(url)


def main() -> None:
    input_file = "customers.json"
    output_file = "updated_customers.json"
    customers = load_customers(input_file)

    customer = customers[0]  # Take the first customer for an example
    items = ["item1", "item2", "item3"]
    total_amount = 100.0
    order = create_order(customer, items, total_amount)
    print(f"Order created: {order.get_order_summary()}")

    # Update customer's email
    updated = update_customer_email(customers, customer.name, "new_email@example.com")
    if updated:
        print(f"Customer email updated: {customer.get_customer_info()}")
    
    save_customers(customers, output_file)

    # Fetch external data (e.g., from API)
    api_url = "https://api.example.com/data"
    api_data = fetch_api_data(api_url)
    print(f"Fetched data from API: {api_data}")


if __name__ == "__main__":
    main()
