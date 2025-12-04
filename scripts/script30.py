import os
import requests
import json
from typing import List, Dict, Any


class DataProcessor:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def filter_data(self, threshold: int) -> List[Dict[str, Any]]:
        """Filter data based on a threshold value"""
        return [item for item in self.data if item['value'] > threshold]

    def aggregate_data(self) -> Dict[str, int]:
        """Aggregate data by summing values"""
        aggregation = {}
        for item in self.data:
            key = item['category']
            aggregation[key] = aggregation.get(key, 0) + item['value']
        return aggregation

    def transform_data(self) -> List[Dict[str, Any]]:
        """Transform data by adding a new field"""
        for item in self.data:
            item['value_squared'] = item['value'] ** 2
        return self.data


class FileHandler:
    @staticmethod
    def read_file(file_path: str) -> List[Dict[str, Any]]:
        """Read JSON file and return data"""
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"File {file_path} not found.")
            return []
        except json.JSONDecodeError:
            print(f"Error decoding JSON in file {file_path}.")
            return []

    @staticmethod
    def write_file(file_path: str, data: List[Dict[str, Any]]) -> None:
        """Write data to a JSON file"""
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        except IOError:
            print(f"Error writing to file {file_path}.")


class APIClient:
    @staticmethod
    def fetch_data(url: str) -> List[Dict[str, Any]]:
        """Fetch data from an API"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from API: {e}")
            return []


def process_and_save_data(input_file: str, output_file: str, threshold: int, api_url: str) -> None:
    """Main function to process data from file and API, then save the result"""
    file_data = FileHandler.read_file(input_file)
    if not file_data:
        print("No data to process.")
        return

    api_data = APIClient.fetch_data(api_url)
    combined_data = file_data + api_data

    processor = DataProcessor(combined_data)
    filtered_data = processor.filter_data(threshold)
    transformed_data = processor.transform_data()
    aggregated_data = processor.aggregate_data()

    print(f"Aggregated Data: {aggregated_data}")

    FileHandler.write_file(output_file, transformed_data)


def main() -> None:
    """Run the application"""
    input_file = "data.json"
    output_file = "processed_data.json"
    api_url = "https://api.example.com/data"
    threshold = 50

    process_and_save_data(input_file, output_file, threshold, api_url)


if __name__ == "__main__":
    main()

