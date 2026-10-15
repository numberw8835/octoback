import logging
import os
from typing import List
from ..engine import Engine
from .utils import DualProgressBar

logger = logging.getLogger("octoback.update")


def update(engine: Engine, input_list: List[str] | None = None, all_flag: bool = False) -> None:
    """Updates paths in index (checks for modified, moved, or copied files)."""
    if all_flag:
        targets = list(engine.index.keys())
    else:
        targets = input_list or []

    if not targets:
        logger.warning("No paths provided to update.")
        return

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

    for path in targets:
        if os.path.exists(path):
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        engine.update_path_in_index(full_path)
                    if not dirs and not files:
                        engine.update_path_in_index(root)
            else:
                engine.update_path_in_index(path)
        else:
            logger.warning("Path does not exist on disk: %s", path)

    tracker.finish()
    engine.save_index()
