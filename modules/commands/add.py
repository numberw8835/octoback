import logging
import os
from typing import List
from ..engine import Engine

from ..utils import DualProgressBar

logger = logging.getLogger("octoback.add")

def add(engine: Engine, input_list: List[str], granular: bool = False) -> None: 
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing added.")
        return

    # Calculate total bytes of paths being added
    total_bytes = 0
    for path in input_list:
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

    for path in input_list:
        if os.path.exists(path):
            if os.path.isdir(path) and granular:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        engine.add_path_to_index(full_path, tracker=tracker)
                    # If this folder is empty, index the folder itself
                    if not dirs and not files:
                        engine.add_path_to_index(root, tracker=tracker)
            else:
                engine.add_path_to_index(path, tracker=tracker)
        else:
            logger.error("Path does not exist: %s", path)

    tracker.finish()
    engine.save_index()