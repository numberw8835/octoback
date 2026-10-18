import logging
import os
import time
from typing import List
from ..engine import Engine

from ..utils import DualProgressBar, count_part, format_summary, is_inside, short_path

logger = logging.getLogger("octoback.add")

def add(engine: Engine, input_list: List[str], whole: bool = False) -> bool:
    if len(input_list) == 0:
        logger.error("Nothing provided and therefore nothing added.")
        return False

    start_time = time.monotonic()

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

    tracked = 0
    failed = 0

    def track(p: str):
        nonlocal tracked, failed
        if engine.add_path_to_index(p, tracker=tracker):
            tracked += 1
        else:
            failed += 1

    for path in input_list:
        if os.path.islink(path):
            logger.warning("%s is a symlink: Octoback backs up what it points to, not the link itself", short_path(path))
        if os.path.exists(path):
            if os.path.isdir(path) and not whole:
                engine.add_root(path)
                for p in engine.walk_folder(path):
                    track(p)
            else:
                # The folder replaces any entries inside it (e.g. its files tracked one by one)
                if os.path.isdir(path):
                    for p in [p for p in engine.index if is_inside(p, path) and p != path]:
                        del engine.index[p]
                track(path)
        else:
            logger.error("Not found: %s", short_path(path))
            failed += 1

    tracker.finish()
    saved = engine.save_index()
    ok = saved and failed == 0
    print(format_summary("Add done", [count_part(tracked, "tracked"), count_part(failed, "failed")],
                         time.monotonic() - start_time, ok))
    return ok
