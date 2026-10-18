import json
import os
import time
import logging
from .utils.utils import EMPTY_HASH, get_dir_hash_optimized, get_file_hash_optimized, get_mount_point, get_quick_signature, is_inside, sync_folder
from .utils.style import format_action, short_path
from .config import CONFIG_FILE, load_config, create_default_config

logger = logging.getLogger("octoback.engine")

class Engine:
    def __init__(self, config_path: str = CONFIG_FILE) -> None:
        self.config_path = config_path
        self.config = load_config(config_path)
        self.index_path = self.config["storage"]["index_path"]
        self.roots_path = self.config["storage"]["roots_path"]
        self.vault_path = self.config["storage"]["vault_path"]
        self.history_path = self.config["storage"]["history_path"]
        self.compression = self.config["settings"]["compression"]
        self.index = {}
        self.roots = []  # Folders tracked file by file
        self._loaded = False
        if os.path.exists(self.index_path):
            self.load_index()

    def init(self):
        """Initialize the engine, configuration, and default storage."""
        create_default_config(self.config_path)
        self.config = load_config(self.config_path)
        self.index_path = self.config["storage"]["index_path"]
        self.roots_path = self.config["storage"]["roots_path"]
        self.vault_path = self.config["storage"]["vault_path"]
        self.history_path = self.config["storage"]["history_path"]
        self.compression = self.config["settings"]["compression"]

        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        os.makedirs(self.vault_path, exist_ok=True)
        if not os.path.exists(self.index_path):
            with open(self.index_path, 'w') as f:
                json.dump({}, f)
        self.index = {}
        self.roots = []
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
                    logger.debug("Index file does not contain a JSON object: %s", target)
                    return
                self._loaded = True
                logger.debug("Index loaded: %s", target)
            if os.path.exists(self.roots_path):
                with open(self.roots_path, 'r') as f:
                    self.roots = json.load(f)
        except FileNotFoundError:
            logger.debug("Index file not found: %s", target)
        except json.JSONDecodeError:
            logger.debug("Invalid JSON in index file: %s", target)

    def save_index(self, path: str | None = None) -> bool:
        """save the index and tracked folders to file atomically."""
        if not self._loaded:
            logger.error("Index not loaded, cannot save")
            return False
        return self._write_json(path or self.index_path, self.index) and self._write_json(self.roots_path, self.roots)

    def _write_json(self, target: str, data) -> bool:
        tmp_path = f"{target}.tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=4)
                # Force the data onto the disk, so a power cut can't leave an empty file
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
            sync_folder(os.path.dirname(target))
            logger.debug("Saved: %s", target)
            return True
        except OSError as e:
            logger.error("Could not save %s: %s", short_path(target), e.strerror or e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False

    def root_of(self, path: str) -> str | None:
        """the tracked folder path is in, if any"""
        return next((r for r in self.roots if is_inside(path, r)), None)

    def add_root(self, path: str) -> None:
        """tracks a folder file by file, replacing tracked folders inside it"""
        if not self.root_of(path):
            self.roots = [r for r in self.roots if not is_inside(r, path)] + [path]


    def add_path_to_index(self, path: str, tracker=None, path_hash: str = "", signature: str = "") -> bool:
        """adds a path to the index
        path_hash / signature: pass them when already computed, so the files aren't read twice
        """
        if not os.path.exists(path):
            logger.error("Not found: %s", short_path(path))
            return False

        is_hidden = os.path.basename(path).startswith(".")
        # Take the signature before hashing, so a change made during hashing is caught next time
        signature = signature or get_quick_signature(path)

        if os.path.isdir(path):
            dir_hash = path_hash or get_dir_hash_optimized(path, tracker=tracker)
            if not dir_hash:
                logger.error("Could not hash %s", short_path(path))
                return False
            if path in self.index and self.index[path].get("hash") == dir_hash:
                self.index[path]["signature"] = signature
                logger.debug("Unchanged: %s", path)
                return True
            self.index[path] = {
                "type": "dir",
                "hidden": is_hidden,
                "hash": dir_hash,
                "signature": signature,
                "size": self._calculate_path_size(path),
                "mount": get_mount_point(path)
            }
        elif os.path.isfile(path):
            file_hash = path_hash or get_file_hash_optimized(path, tracker=tracker)
            if not file_hash:
                logger.error("Could not hash %s", short_path(path))
                return False
            if path in self.index and self.index[path].get("hash") == file_hash:
                self.index[path]["signature"] = signature
                logger.debug("Unchanged: %s", path)
                return True
            ext = os.path.splitext(path)[1].lstrip(".") or None
            self.index[path] = {
                "type": "file",
                "hidden": is_hidden,
                "extension": ext,
                "hash": file_hash,
                "signature": signature,
                "size": self._calculate_path_size(path),
                "mount": get_mount_point(path)
            }
        else:
            logger.error("Not a file or folder: %s", short_path(path))
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

    def remove_path_from_index(self, path: str, action: str = "untracked") -> bool:
        """removes a path from the index
        action: "untracked" when the user stops tracking it, "deleted" when it vanished from disk
        """
        if path in self.index:
            del self.index[path]
            self._record_history(action, path)
            logger.info(format_action(action, path))
            return True
        logger.warning("Not tracked: %s", short_path(path))
        return False

    def is_on_unplugged_drive(self, path: str) -> bool:
        """True if the path was tracked on a drive that isn't mounted right now"""
        mount = self.index.get(path, {}).get("mount")
        return bool(mount) and not os.path.ismount(mount)

    def update_path_in_index(self, path: str, tracker=None):
        """checks if a path is new, moved, or copied"""
        if not os.path.exists(path):
            if self.is_on_unplugged_drive(path):
                logger.info(format_action("skipped", path, "drive not plugged in"))
                return "skipped"
            if path in self.index:
                del self.index[path]
                self._record_history("deleted", path)
                logger.info(format_action("deleted", path))
                return "deleted"
            logger.error("Not found: %s", short_path(path))
            return

        is_dir = os.path.isdir(path)
        path_type = "dir" if is_dir else "file"

        # Remember which drive the path lives on (older entries don't have it yet)
        if path in self.index:
            self.index[path]["mount"] = get_mount_point(path)

        # Fast path: same sizes and modification times as last time, no need to read the contents
        signature = get_quick_signature(path)
        if signature and path in self.index and self.index[path].get("signature") == signature:
            if tracker:
                tracker.skip_file(os.path.basename(path), self.index[path].get("size", 0))
            logger.info(format_action("unchanged", path))
            return "unchanged"

        if is_dir:
            current_hash = get_dir_hash_optimized(path, tracker=tracker)
        else:
            current_hash = get_file_hash_optimized(path, tracker=tracker)
        if not current_hash:
            return

        # Check if path is already in index
        if path in self.index:
            if self.index[path].get("hash") == current_hash:
                # Touched but not changed: remember the new signature so it isn't hashed again
                self.index[path]["signature"] = signature
                logger.info(format_action("unchanged", path))
                return "unchanged"
            else:
                self.add_path_to_index(path, path_hash=current_hash, signature=signature)
                self._record_history("modified", path)
                logger.info(format_action("modified", path))
                return "modified"

        # Path is not in index: check if a missing entry was moved here (ignoring empty files)
        if current_hash != EMPTY_HASH:
            missing_matches = [
                old_p for old_p, data in self.index.items()
                if old_p != path and data.get("type") == path_type and data.get("hash") == current_hash and not os.path.exists(old_p)
            ]
            if missing_matches:
                for old_p in missing_matches:
                    del self.index[old_p]
                    self._record_history("moved", path, old_p)
                    logger.info(format_action("moved", path, f"from {short_path(old_p)}"))
                self.add_path_to_index(path, path_hash=current_hash, signature=signature)
                return "moved"

        # Check for copied files
        if current_hash != EMPTY_HASH:
            copied_matches = [
                p for p, data in self.index.items()
                if p != path and data.get("type") == path_type and data.get("hash") == current_hash and os.path.exists(p)
            ]
            if copied_matches:
                self.add_path_to_index(path, path_hash=current_hash, signature=signature)
                self._record_history("copied", path, copied_matches[0])
                logger.info(format_action("copied", path, f"copy of {short_path(copied_matches[0])}"))
                return "copied"

        self.add_path_to_index(path, path_hash=current_hash, signature=signature)
        self._record_history("new", path)
        logger.info(format_action("new", path))
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
            logger.error("Could not measure %s: %s", short_path(path), e.strerror or e)
            return 0