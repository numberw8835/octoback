import logging
import os
from typing import List
from ..engine import Engine

logger = logging.getLogger("octoback.remove")

def remove(engine: Engine, input_list: List[str]) -> bool:
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing removed.")
        return False
    ok = True
    for path in input_list:
        ok = engine.remove_path_from_index(path) and ok
    return engine.save_index() and ok