import logging
import os
from typing import List
from ..engine import Engine

logger = logging.getLogger("octoback.add")

def add(engine: Engine, input_list: List[str]) -> None: 
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing added.")
        return
    for path in input_list:
        if os.path.exists(path):
            engine.add_path_to_index(path)
        else:
            logger.error("Path does not exist: %s", path)
    engine.save_index()