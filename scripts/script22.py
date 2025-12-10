from typing import List, Dict, Any


class Employee:
    def __init__(self, name: str, position: str, salary: float) -> None:
        self.name = name
        self.position = position
        self.salary = salary

    def update_salary(self, salary: float) -> None:
        self.salary = salary

    def get_employee_info(self) -> Dict[str, Any]:
        return {'name': self.name, 'position': self.position, 'salary': self.salary}


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
        return {
            'name': self.name,
            'employees': [employee.get_employee_info() for employee in self.employees]
        }


class Company:
    def __init__(self, name: str) -> None:
        self.name = name
        self.departments: List[Department] = []

    def add_department(self, department: Department) -> None:
        self.departments.append(department)

    def get_company_info(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'departments': [department.get_department_info() for department in self.departments]
        }


def read_json(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON in file {file_path}.")
        return []


def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except IOError:
        print(f"Error writing to file {file_path}.")


def fetch_data(url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return []


def create_employee(name: str, position: str, salary: float) -> Employee:
    return Employee(name, position, salary)


def create_department(name: str) -> Department:
    return Department(name)


def main():
    company = Company('Tech Corp')
    it_department = create_department('IT')
    hr_department = create_department('HR')

    employee1 = create_employee('John Doe', 'Developer', 50000)
    employee2 = create_employee('Jane Smith', 'HR Manager', 60000)

    it_department.add_employee(employee1)
    hr_department.add_employee(employee2)

    company.add_department(it_department)
    company.add_department(hr_department)

    print(company.get_company_info())

    # File handling example
    data = read_json('data.json')
    write_json('output.json', data)

    # Fetch external data
    api_data = fetch_data('https://api.example.com/data')
    print(api_data)


if __name__ == '__main__':
    import json
    import requests
    main()
