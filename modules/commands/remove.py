import logging
import os
from typing import List
from ..engine import Engine
from ..utils import is_inside, short_path

logger = logging.getLogger("octoback.remove")

def remove(engine: Engine, input_list: List[str]) -> bool:
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing removed.")
        return False
    ok = True
    for path in input_list:
        if path in engine.roots:
            engine.roots.remove(path)
            for p in [p for p in engine.index if is_inside(p, path)]:
                engine.remove_path_from_index(p)
            continue
        inside = [p for p in engine.index if is_inside(p, path)]
        if path not in engine.index and inside:
            # A subfolder of a tracked folder: untrack everything in it
            for p in inside:
                engine.remove_path_from_index(p)
        else:
            ok = engine.remove_path_from_index(path) and ok
        if engine.root_of(path):
            logger.warning("%s is inside a tracked folder: the next update tracks it again", short_path(path))
    return engine.save_index() and ok