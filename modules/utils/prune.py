import logging
import os
from typing import List
from ..engine import Engine

logger = logging.getLogger("octoback.prune")

def prune(engine: Engine) -> None: 
    """Remove entries from the index for paths that no longer exist."""
    paths_to_remove = [p for p in engine.index if not os.path.exists(p)]
    
    if not paths_to_remove:
        return
    
    for path in paths_to_remove:
        logger.info("Removing missing path: %s", path)
        engine.remove_path_from_index(path)
    
    engine.save_index()
    logger.info("Pruned %d paths", len(paths_to_remove))
