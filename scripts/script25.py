import os
import json
import requests
from typing import List, Dict, Any


class Employee:
    def __init__(self, name: str, position: str, salary: float, department: str) -> None:
        self.name = name
        self.position = position
        self.salary = salary
        self.department = department

    def update_salary(self, salary: float) -> None:
        self.salary = salary

    def get_employee_info(self) -> Dict[str, Any]:
        return {"name": self.name, "position": self.position, "salary": self.salary, "department": self.department}


class Department:
    def __init__(self, name: str) -> None:
        self.name = name
        self.employees: List[Employee] = []

    def add_employee(self, employee: Employee) -> None:
        self.employees.append(employee)

    def remove_employee(self, name: str) -> bool:
        for employee in self.employees:
            if employee.name == name:
                self.employees.remove(employee)
                return True
        return False

    def get_department_info(self) -> Dict[str, Any]:
        return {"name": self.name, "employees": [emp.get_employee_info() for emp in self.employees]}


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


def load_departments(file_path: str) -> List[Department]:
    departments = []
    department_data = FileManager.read_json(file_path)
    for item in department_data:
        department = Department(item["name"])
        for emp in item["employees"]:
            employee = Employee(emp["name"], emp["position"], emp["salary"], emp["department"])
            department.add_employee(employee)
        departments.append(department)
    return departments


def save_departments(departments: List[Department], file_path: str) -> None:
    department_data = [{"name": dept.name, "employees": [emp.get_employee_info() for emp in dept.employees]} for dept in departments]
    FileManager.write_json(file_path, department_data)


def create_employee(name: str, position: str, salary: float, department: str) -> Employee:
    return Employee(name, position, salary, department)


def fetch_external_data(url: str) -> List[Dict[str, Any]]:
    return APIClient.fetch_data(url)


def main() -> None:
    input_file = "departments.json"
    output_file = "updated_departments.json"
    departments = load_departments(input_file)

    # Add new employee to a department
    new_employee = create_employee("John Doe", "Software Engineer", 60000, "IT")
    it_department = next((dept for dept in departments if dept.name == "IT"), None)
    if it_department:
        it_department.add_employee(new_employee)

    # Remove an employee from a department
    it_department.remove_employee("Jane Smith")

    # Save updated departments
    save_departments(departments, output_file)

    # Fetch external data from API
    api_url = "https://api.example.com/employees"
    api_data = fetch_external_data(api_url)
    print(f"Fetched data from API: {api_data}")


if __name__ == "__main__":
    main()
