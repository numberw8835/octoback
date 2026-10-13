import json
import os
import logging
from .utils.utils import get_dir_hash_optimized, get_file_hash_optimized
DEFAULT_PATH = os.path.expanduser("~/.octoback/octoback-index.json")

logger = logging.getLogger("octoback.engine")

class Engine:
    def __init__(self) -> None:
        self.index = {}
        self._loaded = False

    def init(self):
        """Initialize the engine."""
        base = os.path.expanduser("~/.octoback")
        if not os.path.exists(base):
            os.makedirs(base)
        if not os.path.exists(DEFAULT_PATH):
            with open(DEFAULT_PATH, 'w') as f:
                json.dump({}, f)

    def load_index(self, path: str = DEFAULT_PATH) -> None:
        """Load the index from a file."""
        try: 
            with open(path, 'r') as f:
                data = json.load(f)
                self.index = data
                self._loaded = True
                logger.info("Data loaded successfully!")
        except FileNotFoundError:
            logger.error("File not found: %s", path)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in file: %s", path)

    def save_index(self, path: str = DEFAULT_PATH) -> None:
        """save the index to file."""
        if not self._loaded:
            logger.info("Index not loaded, cannot save!")
            return
        try:
            with open(path, 'w') as f:
                json.dump(self.index, f, indent=4)
                logger.info("Data saved to: %s", path)
        except IOError as e:
            logger.error("Error saving index to file: %s", e)

    # TODO: Add error handling for hash computation failures
    # TODO: Check if hash is None before adding to index
    # TODO: Handle race conditions (file deleted between check and hash)
    # TODO: Consider returning bool to indicate success

    def add_path_to_index(self, path: str) -> bool:
        """adds a path to the index"""
        if path in self.index:
            logger.info("No change done!")
        elif os.path.isdir(path):
            self.index[path] = {
                "type": "dir",
                "hash": get_dir_hash_optimized(path),
                "size": f"{self._calculate_path_size(path)}"
            }
        elif os.path.isfile(path):
            self.index[path] = {
                "type": "file",
                "hash": get_file_hash_optimized(path),
                "size": f"{self._calculate_path_size(path)}"
            }
        else:
            logger.error("Unknow object type: %s", path)
            return False
        return True

    def remove_path_from_index(self, path: str) -> None:
        """removes a path from the index"""
        if path in self.index:
            del self.index[path]
            logger.info("Removed path: %s", path)
        else:
            logger.warning("Path not found in index: %s", path)

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