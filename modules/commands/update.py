import logging
import os
from typing import List
from ..engine import Engine
from ..utils import DualProgressBar

logger = logging.getLogger("octoback.update")


def update(engine: Engine, input_list: List[str] | None = None, all_flag: bool = False, granular: bool = False) -> None:
    """Updates paths in index (checks for modified, moved, or copied files)."""
    targets = list(engine.index.keys()) if all_flag else (input_list or [])
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

    def process(p: str):
        try:
            size = os.path.getsize(p) if os.path.isfile(p) else 0
        except OSError:
            size = 0
        tracker.start_file(os.path.basename(p), size)
        engine.update_path_in_index(p)
        tracker.update(size)

    for path in targets:
        if os.path.isdir(path) and granular:
            for root, dirs, files in os.walk(path):
                for f in files:
                    process(os.path.join(root, f))
                if not dirs and not files:
                    process(root)
            prefix = path if path.endswith(os.sep) else path + os.sep
            for k in list(engine.index.keys()):
                if k.startswith(prefix) and not os.path.exists(k):
                    engine.update_path_in_index(k)
        elif os.path.exists(path):
            process(path)
        else:
            parent = os.path.dirname(path)
            if os.path.isdir(parent):
                for root, dirs, files in os.walk(parent):
                    for f in files:
                        process(os.path.join(root, f))
                    if not dirs and not files:
                        process(root)
            engine.update_path_in_index(path)

    tracker.finish()
    engine.save_index()
