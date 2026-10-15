import logging
import os
from modules.engine import Engine
from .utils import get_dir_hash_optimized, get_file_hash_optimized

logger = logging.getLogger("octoback.check")

def check(engine: Engine, input_path: str) -> bool:
    """Checks whether the file/directory at input_path matches its indexed hash."""
    path = os.path.abspath(input_path)

    if not os.path.exists(path):
        logger.warning("Path does not exist on disk: %s", path)
        return False

    indexed_entry = engine.index.get(path) or engine.index.get(input_path)
    if not indexed_entry:
        logger.info("Path not found in index: %s", input_path)
        return False

    expected_hash = indexed_entry.get("hash")

    # Form: Directory
    if os.path.isdir(path):
        current_hash = get_dir_hash_optimized(path)
    # Form: File
    elif os.path.isfile(path):
        current_hash = get_file_hash_optimized(path)
    else:
        logger.warning("Unsupported path type: %s", path)
        return False

    if current_hash == expected_hash:
        logger.info("%s: Hash matches (%s)", input_path, current_hash)
        return True
    else:
        logger.info(
            "%s: Hash mismatch (current: %s, indexed: %s)",
            input_path,
            current_hash,
            expected_hash,
        )
        return False
