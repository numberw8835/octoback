import logging
import os
import time
from typing import List
from modules.engine import Engine
from ..utils import count_part, format_action, format_summary, get_dir_hash_optimized, get_file_hash_optimized, short_path

logger = logging.getLogger("octoback.check")


def check(engine: Engine, input_paths: List[str]) -> bool:
    """Checks whether the file(s) or directory(ies) match their indexed hash."""
    if not input_paths:
        logger.warning("No paths provided to check.")
        return False

    start_time = time.monotonic()
    matches = 0
    problems = 0

    for input_path in input_paths:
        path = os.path.abspath(input_path)

        if not os.path.exists(path):
            logger.warning("Not found on disk: %s", short_path(path))
            problems += 1
            continue

        indexed_entry = engine.index.get(path) or engine.index.get(input_path)
        if not indexed_entry:
            logger.warning("Not tracked: %s", short_path(path))
            problems += 1
            continue

        expected_hash = indexed_entry.get("hash")

        # Form: Directory
        if os.path.isdir(path):
            current_hash = get_dir_hash_optimized(path)
        # Form: File
        elif os.path.isfile(path):
            current_hash = get_file_hash_optimized(path)
        else:
            logger.warning("Not a file or folder: %s", short_path(path))
            problems += 1
            continue

        if current_hash == expected_hash:
            logger.info(format_action("matches", path, current_hash[:8]))
            matches += 1
        else:
            logger.info(format_action("changed", path, f"{current_hash[:8]}, tracked {expected_hash[:8]}"))
            problems += 1

    all_matched = problems == 0
    print(format_summary("Check done", [count_part(matches, "match"), count_part(problems, "differ or missing")],
                         time.monotonic() - start_time, all_matched))
    return all_matched
