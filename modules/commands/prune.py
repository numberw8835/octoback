import logging
import os
import time
from ..engine import Engine
from ..utils import count_part, format_action, format_summary

logger = logging.getLogger("octoback.prune")

def prune(engine: Engine) -> bool:
    """Remove entries from the index for paths that no longer exist on disk."""
    start_time = time.monotonic()
    missing = [p for p in engine.index if not os.path.exists(p)]

    # Paths on a drive that isn't plugged in are not deleted, just unreachable right now
    paths_to_remove = []
    skipped = 0
    for path in missing:
        if engine.is_on_unplugged_drive(path):
            logger.info(format_action("skipped", path, "drive not plugged in"))
            skipped += 1
        else:
            paths_to_remove.append(path)

    for path in paths_to_remove:
        engine.remove_path_from_index(path, action="deleted")

    saved = engine.save_index() if paths_to_remove else True
    print(format_summary("Prune done", [count_part(len(paths_to_remove), "removed"), count_part(skipped, "skipped")],
                         time.monotonic() - start_time, saved))
    return saved
