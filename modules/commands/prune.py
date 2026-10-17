import logging
import os
from ..engine import Engine

logger = logging.getLogger("octoback.prune")

def prune(engine: Engine) -> bool:
    """Remove entries from the index for paths that no longer exist on disk."""
    missing = [p for p in engine.index if not os.path.exists(p)]

    # Paths on a drive that isn't plugged in are not deleted, just unreachable right now
    paths_to_remove = []
    for path in missing:
        if engine.is_on_unplugged_drive(path):
            logger.warning("Skipped (drive not plugged in): %s", path)
        else:
            paths_to_remove.append(path)

    if not paths_to_remove:
        logger.info("Nothing to prune.")
        return True
    
    for path in paths_to_remove:
        logger.info("Removing missing path from index: %s", path)
        engine.remove_path_from_index(path, action="deleted")

    logger.info("Pruned %d paths from index.", len(paths_to_remove))
    return engine.save_index()
