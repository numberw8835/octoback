import json
import os
import time
import logging
from .utils.utils import get_dir_hash_optimized, get_file_hash_optimized
from .config import CONFIG_FILE, load_config, create_default_config

logger = logging.getLogger("octoback.engine")

class Engine:
    def __init__(self, config_path: str = CONFIG_FILE) -> None:
        self.config_path = config_path
        self.config = load_config(config_path)
        self.index_path = self.config["storage"]["index_path"]
        self.vault_path = self.config["storage"]["vault_path"]
        self.history_path = self.config["storage"]["history_path"]
        self.compression = self.config["settings"]["compression"]
        self.index = {}
        self._loaded = False
        if os.path.exists(self.index_path):
            self.load_index()

    def init(self):
        """Initialize the engine, configuration, and default storage."""
        create_default_config(self.config_path)
        self.config = load_config(self.config_path)
        self.index_path = self.config["storage"]["index_path"]
        self.vault_path = self.config["storage"]["vault_path"]
        self.history_path = self.config["storage"]["history_path"]
        self.compression = self.config["settings"]["compression"]

        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        os.makedirs(self.vault_path, exist_ok=True)
        if not os.path.exists(self.index_path):
            with open(self.index_path, 'w') as f:
                json.dump({}, f)
        self.index = {}
        self._loaded = True

    def load_index(self, path: str | None = None) -> None:
        """Load the index from a file."""
        target = path or self.index_path
        try: 
            with open(target, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.index = data
                else:
                    logger.error("Index file does not contain a JSON object: %s", target)
                    return
                self._loaded = True
                logger.info("Data loaded successfully!")
        except FileNotFoundError:
            logger.error("File not found: %s", target)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in file: %s", target)

    def save_index(self, path: str | None = None) -> None:
        """save the index to file atomically."""
        if not self._loaded:
            logger.info("Index not loaded, cannot save!")
            return
        target = path or self.index_path
        tmp_path = f"{target}.tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(self.index, f, indent=4)
            os.replace(tmp_path, target)
            logger.info("Data saved to: %s", target)
        except OSError as e:
            logger.error("Error saving index to file: %s", e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                    
    def add_path_to_index(self, path: str, tracker=None) -> bool:
        """adds a path to the index"""
        if not os.path.exists(path):
            logger.error("Path does not exist: %s", path)
            return False

        is_hidden = os.path.basename(path).startswith(".")

        if os.path.isdir(path):
            dir_hash = get_dir_hash_optimized(path, tracker=tracker)
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
                "size": self._calculate_path_size(path)
            }
        elif os.path.isfile(path):
            file_hash = get_file_hash_optimized(path, tracker=tracker)
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
                "size": self._calculate_path_size(path)
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
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            with open(self.history_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def remove_path_from_index(self, path: str, action: str = "untracked") -> None:
        """removes a path from the index
        action: "untracked" when the user stops tracking it, "deleted" when it vanished from disk
        """
        if path in self.index:
            del self.index[path]
            self._record_history(action, path)
            logger.info("Removed path: %s", path)
        else:
            logger.warning("Path not found in index: %s", path)

    def update_path_in_index(self, path: str):
        """checks if a path is new, moved, or copied"""
        if not os.path.exists(path):
            if path in self.index:
                del self.index[path]
                self._record_history("deleted", path)
                logger.info("Deleted: %s", path)
                return "deleted"
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

        empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        # Path is not in index: check if a missing entry was moved here (ignoring empty files)
        if current_hash != empty_hash:
            missing_matches = [
                old_p for old_p, data in self.index.items()
                if old_p != path and data.get("type") == path_type and data.get("hash") == current_hash and not os.path.exists(old_p)
            ]
            if missing_matches:
                for old_p in missing_matches:
                    del self.index[old_p]
                    self._record_history("moved", path, old_p)
                    logger.info("Moved: %s -> %s", old_p, path)
                self.add_path_to_index(path)
                return "moved"

        # Check for copied files
        if current_hash != empty_hash:
            copied_matches = [
                p for p, data in self.index.items()
                if p != path and data.get("type") == path_type and data.get("hash") == current_hash and os.path.exists(p)
            ]
            if copied_matches:
                self.add_path_to_index(path)
                self._record_history("copied", path, copied_matches[0])
                logger.info("Copied: %s is copy of %s", path, copied_matches[0])
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