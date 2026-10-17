import logging
import os
import time
from collections import Counter
from typing import List
from ..engine import Engine
from ..utils import DualProgressBar, count_part, format_summary, get_file_hash_optimized

logger = logging.getLogger("octoback.update")


def find_moved_file(engine: Engine, missing_path: str) -> str | None:
    """Looks next to a missing tracked file for an untracked file with the same content."""
    entry = engine.index.get(missing_path)
    if not entry or entry.get("type") != "file":
        return None

    for root, _, files in os.walk(os.path.dirname(missing_path)):
        for name in files:
            candidate = os.path.join(root, name)
            # Compare sizes first so only real candidates get hashed
            if (candidate not in engine.index
                    and os.path.isfile(candidate)
                    and os.path.getsize(candidate) == entry.get("size")
                    and get_file_hash_optimized(candidate) == entry.get("hash")):
                return candidate
    return None


def update(engine: Engine, input_list: List[str] | None = None, all_flag: bool = False, granular: bool = False) -> bool:
    """Updates paths in index (checks for modified, moved, or copied files)."""
    targets = list(engine.index.keys()) if all_flag else (input_list or [])
    if not targets:
        logger.warning("No paths provided to update.")
        return False

    start_time = time.monotonic()

    # Calculate total bytes of existing targets
    total_bytes = 0
    for path in targets:
        if os.path.isfile(path):
            total_bytes += os.path.getsize(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        total_bytes += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass

    tracker = DualProgressBar(total_bytes=total_bytes)

    results = Counter()

    def process(p: str):
        # The engine moves the bars: while hashing, or by skipping paths that didn't change
        results[engine.update_path_in_index(p, tracker=tracker) or "failed"] += 1

    for path in targets:
        if os.path.isdir(path) and granular:
            for root, dirs, files in os.walk(path):
                for f in files:
                    process(os.path.join(root, f))
                if not dirs and not files:
                    process(root)
            prefix = path if path.endswith(os.sep) else path + os.sep
            for k in list(engine.index.keys()):
                if k.startswith(prefix) and not os.path.exists(k):
                    process(k)
        elif os.path.exists(path):
            process(path)
        else:
            moved_to = find_moved_file(engine, path)
            if moved_to:
                process(moved_to)  # Recorded as "moved"
            else:
                process(path)  # Recorded as "deleted"

    tracker.finish()
    ok = engine.save_index() and not results["failed"]
    parts = [count_part(results[action], action) for action in
             ("new", "modified", "moved", "copied", "deleted", "unchanged", "skipped", "failed")]
    print(format_summary("Update done", parts, time.monotonic() - start_time, ok))
    return ok
