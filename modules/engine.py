import json
import os
import time
import logging
from .utils.utils import get_dir_hash_optimized, get_file_hash_optimized
DEFAULT_PATH = os.path.expanduser("~/.octoback/octoback-index.json")
DEFAULT_HISTORY_PATH = os.path.expanduser("~/.octoback/octoback-history.jsonl")

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
        self.index = {}
        self._loaded = True

    def load_index(self, path: str = DEFAULT_PATH) -> None:
        """Load the index from a file."""
        try: 
            with open(path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.index = data
                else:
                    logger.error("Index file does not contain a JSON object: %s", path)
                    return
                self._loaded = True
                logger.info("Data loaded successfully!")
        except FileNotFoundError:
            logger.error("File not found: %s", path)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in file: %s", path)

    def save_index(self, path: str = DEFAULT_PATH) -> None:
        """save the index to file atomically."""
        if not self._loaded:
            logger.info("Index not loaded, cannot save!")
            return
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(self.index, f, indent=4)
            os.replace(tmp_path, path)
            logger.info("Data saved to: %s", path)
        except OSError as e:
            logger.error("Error saving index to file: %s", e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def add_path_to_index(self, path: str) -> bool:
        """adds a path to the index"""
        if not os.path.exists(path):
            logger.error("Path does not exist: %s", path)
            return False

        is_hidden = os.path.basename(path).startswith(".")

        if os.path.isdir(path):
            dir_hash = get_dir_hash_optimized(path)
            if not dir_hash:
                logger.error("Failed to hash directory: %s", path)
                return False
            if path in self.index and self.index[path].get("hash") == dir_hash:
                logger.info("No change done!")
                return True
            self.index[path] = {
                "type": "dir",
                "hidden": is_hidden,
                "hash": dir_hash,
                "size": f"{self._calculate_path_size(path)}"
            }
        elif os.path.isfile(path):
            file_hash = get_file_hash_optimized(path)
            if not file_hash:
                logger.error("Failed to hash file: %s", path)
                return False
            if path in self.index and self.index[path].get("hash") == file_hash:
                logger.info("No change done!")
                return True
            ext = os.path.splitext(path)[1].lstrip(".") or None
            self.index[path] = {
                "type": "file",
                "hidden": is_hidden,
                "extension": ext,
                "hash": file_hash,
                "size": f"{self._calculate_path_size(path)}"
            }
        else:
            logger.error("Unknown object type: %s", path)
            return False
        return True

    def _record_history(self, action: str, path: str, origin: str = None):
        """records file lifecycle events to history file"""
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "path": path,
            "origin": origin
        }
        try:
            with open(DEFAULT_HISTORY_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def remove_path_from_index(self, path: str) -> None:
        """removes a path from the index"""
        if path in self.index:
            del self.index[path]
            self._record_history("removed", path)
            logger.info("Removed path: %s", path)
        else:
            logger.warning("Path not found in index: %s", path)

    def update_path_in_index(self, path: str):
        """checks if a path is new, moved, or copied"""
        if not os.path.exists(path):
            logger.error("Path does not exist: %s", path)
            return

        is_dir = os.path.isdir(path)
        path_type = "dir" if is_dir else "file"
        current_hash = get_dir_hash_optimized(path) if is_dir else get_file_hash_optimized(path)
        if not current_hash:
            return

        # Check if path is already in index
        if path in self.index:
            if self.index[path].get("hash") == current_hash:
                logger.info("No change done: %s", path)
                return "unchanged"
            else:
                self.add_path_to_index(path)
                self._record_history("modified", path)
                logger.info("Modified: %s", path)
                return "modified"

        # Path is not in index: check for moved or copied files
        empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        if current_hash != empty_hash:
            matches = [
                p for p, data in self.index.items()
                if p != path and data.get("type") == path_type and data.get("hash") == current_hash
            ]
            for old_path in matches:
                if not os.path.exists(old_path):
                    del self.index[old_path]
                    self.add_path_to_index(path)
                    self._record_history("moved", path, old_path)
                    logger.info("Moved: %s -> %s", old_path, path)
                    return "moved"

            if matches:
                self.add_path_to_index(path)
                self._record_history("copied", path, matches[0])
                logger.info("Copied: %s is copy of %s", path, matches[0])
                return "copied"

        self.add_path_to_index(path)
        self._record_history("new", path)
        return "new"

    def _calculate_path_size(self, path: str):
        """calculate the size of a path"""
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            total_size = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        continue
            return total_size
        except OSError as e:
            logger.error("Error calculating size for %s: %s", path, e)
            return 0