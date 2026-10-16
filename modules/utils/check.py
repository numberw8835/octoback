import logging
import os
from typing import List
from modules.engine import Engine
from .utils import get_dir_hash_optimized, get_file_hash_optimized

logger = logging.getLogger("octoback.check")


def check(engine: Engine, input_paths: List[str]) -> bool:
    """Checks whether the file(s) or directory(ies) match their indexed hash."""
    if not input_paths:
        logger.warning("No paths provided to check.")
        return False

    all_matched = True

    for input_path in input_paths:
        path = os.path.abspath(input_path)

        if not os.path.exists(path):
            logger.warning("Path does not exist on disk: %s", path)
            all_matched = False
            continue

        indexed_entry = engine.index.get(path) or engine.index.get(input_path)
        if not indexed_entry:
            logger.info("Path not found in index: %s", input_path)
            all_matched = False
            continue

        expected_hash = indexed_entry.get("hash")

        # Form: Directory
        if os.path.isdir(path):
            current_hash = get_dir_hash_optimized(path)
        # Form: File
        elif os.path.isfile(path):
            current_hash = get_file_hash_optimized(path)
        else:
            logger.warning("Unsupported path type: %s", path)
            all_matched = False
            continue

        if current_hash == expected_hash:
            logger.info("%s: Hash matches (%s)", input_path, current_hash)
        else:
            logger.info(
                "%s: Hash mismatch (current: %s, indexed: %s)",
                input_path,
                current_hash,
                expected_hash,
            )
            all_matched = False

    return all_matched
