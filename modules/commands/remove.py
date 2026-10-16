import logging
import os
from typing import List
from ..engine import Engine

logger = logging.getLogger("octoback.remove")

def remove(engine: Engine, input_list: List[str]) -> None: 
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing removed.")
        return
    for path in input_list:
        engine.remove_path_from_index(path)
    engine.save_index()