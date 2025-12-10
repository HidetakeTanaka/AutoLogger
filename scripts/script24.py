import os
import json
import requests
from typing import List, Dict, Any


class Student:
    def __init__(self, name: str, age: int, grade: str, subject: str) -> None:
        self.name = name
        self.age = age
        self.grade = grade
        self.subject = subject

    def update_grade(self, grade: str) -> None:
        self.grade = grade

    def get_student_info(self) -> Dict[str, Any]:
        return {"name": self.name, "age": self.age, "grade": self.grade, "subject": self.subject}


class School:
    def __init__(self, name: str) -> None:
        self.name = name
        self.students: List[Student] = []

    def add_student(self, student: Student) -> None:
        self.students.append(student)

    def remove_student(self, name: str) -> bool:
        for student in self.students:
            if student.name == name:
                self.students.remove(student)
                return True
        return False

    def get_school_info(self) -> Dict[str, Any]:
        return {"name": self.name, "students": [student.get_student_info() for student in self.students]}


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


def load_schools(file_path: str) -> List[School]:
    schools = []
    school_data = FileManager.read_json(file_path)
    for item in school_data:
        school = School(item["name"])
        for student_data in item["students"]:
            student = Student(student_data["name"], student_data["age"], student_data["grade"], student_data["subject"])
            school.add_student(student)
        schools.append(school)
    return schools


def save_schools(schools: List[School], file_path: str) -> None:
    school_data = [{"name": school.name, "students": [student.get_student_info() for student in school.students]} for school in schools]
    FileManager.write_json(file_path, school_data)


def create_student(name: str, age: int, grade: str, subject: str) -> Student:
    return Student(name, age, grade, subject)


def fetch_external_data(url: str) -> List[Dict[str, Any]]:
    return APIClient.fetch_data(url)


def main() -> None:
    input_file = "schools.json"
    output_file = "updated_schools.json"
    schools = load_schools(input_file)

    # Add a new student
    new_student = create_student("John Doe", 15, "A", "Math")
    first_school = schools[0]
    first_school.add_student(new_student)

    # Remove a student from a school
    first_school.remove_student("Jane Smith")

    # Save updated school data
    save_schools(schools, output_file)

    # Fetch external data from an API
    api_url = "https://api.example.com/schools"
    api_data = fetch_external_data(api_url)
    print(f"Fetched data from API: {api_data}")


if __name__ == "__main__":
    main()
