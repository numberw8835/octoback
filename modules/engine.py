import json
import os
from utils.utils import get_dir_hash_optimized, get_file_hash_optimized
from pprint import pprint

class Engine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = False
        return cls._instance

    def __init__(self) -> None:
        if self._lock:
            return
        self._lock = True
        self.index = {}

    def load_index(self, path: str) -> None:
        """Load the index from a file."""
        try: 
            with open(path, 'r') as f:
                data = json.load(f)
                self.index = data
        except FileNotFoundError:
            print(f"File not found: {path}")
        except json.JSONDecodeError:
            print(f"Invalid JSON in file: {path}")

    def save_index(self, path: str) -> None:
        """save the index to file."""
        try:
            with open(path, 'w') as f:
                json.dump(self.index, f, indent=4)
        except IOError as e:
            print(f"Error saving index to file: {e}")

    def add_path_to_index(self, path: str):
        """adds a path to the index"""

        if path in self.index:
            print("No change done!")
            return
        if os.path.isdir(path):
            self.index[path] = {
                "type": "dir",
                "hash": get_dir_hash_optimized(path),
                "size": f"{self._calculate_path_size(path)} B"
            }
        elif os.path.isfile(path):
            self.index[path] = {
                "type": "file",
                "hash": get_file_hash_optimized(path),
                "size": f"{self._calculate_path_size(path)} B"
            }
        else:
            print(f"Path not found or not a file or directory: {path}")



    def _calculate_path_size(self, path: str):
        """calculate the size of a path"""
        if os.path.isfile(path):
            return os.path.getsize(path)
        total_size = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)

        return total_size