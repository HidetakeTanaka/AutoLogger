import os
import json
import requests
from typing import List, Dict, Any


class DataAnalyzer:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def filter_by_value(self, threshold: int) -> List[Dict[str, Any]]:
        """Filter the data by a value threshold"""
        return [item for item in self.data if item['value'] >= threshold]

    def group_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by category"""
        grouped = {}
        for item in self.data:
            category = item['category']
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(item)
        return grouped

    def calculate_average(self, category: str) -> float:
        """Calculate the average value for a given category"""
        category_data = [item for item in self.data if item['category'] == category]
        if not category_data:
            return 0.0
        total = sum(item['value'] for item in category_data)
        return total / len(category_data)


class FileManager:
    @staticmethod
    def read_json(file_path: str) -> List[Dict[str, Any]]:
        """Read JSON data from a file"""
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def write_json(file_path: str, data: List[Dict[str, Any]]) -> None:
        """Write JSON data to a file"""
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except IOError:
            pass


class APIHandler:
    @staticmethod
    def fetch_data(url: str) -> List[Dict[str, Any]]:
        """Fetch data from an API"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return []


def process_and_save_data(input_file: str, output_file: str, threshold: int, api_url: str) -> None:
    """Process data from file and API, then save to output"""
    file_data = FileManager.read_json(input_file)
    if not file_data:
        return

    api_data = APIHandler.fetch_data(api_url)
    combined_data = file_data + api_data

    analyzer = DataAnalyzer(combined_data)
    filtered_data = analyzer.filter_by_value(threshold)
    grouped_data = analyzer.group_by_category()

    FileManager.write_json(output_file, filtered_data)


def analyze_category_data(input_file: str, category: str) -> float:
    """Analyze and return the average value of a category"""
    file_data = FileManager.read_json(input_file)
    if not file_data:
        return 0.0

    analyzer = DataAnalyzer(file_data)
    return analyzer.calculate_average(category)


def get_data_from_url(url: str) -> List[Dict[str, Any]]:
    """Get data from the provided URL"""
    return APIHandler.fetch_data(url)


def main() -> None:
    """Run the application"""
    input_file = "data.json"
    output_file = "filtered_data.json"
    api_url = "https://api.example.com/data"
    threshold = 50

    process_and_save_data(input_file, output_file, threshold, api_url)

    category = "category1"
    average_value = analyze_category_data(input_file, category)
    print(f"Average value for {category}: {average_value}")


if __name__ == "__main__":
    main()
