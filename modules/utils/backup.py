import logging
import os
from typing import List
from modules.engine import Engine
from .utils import DualProgressBar, copy_to

logger = logging.getLogger("octoback.backup")


def backup(engine: Engine, input: List[str], all_flag: bool = False):
    # Step 1: Decide what paths to backup
    if all_flag:
        targets = list(engine.index.keys())
    else:
        targets = input

    if not targets:
        logger.warning("No targets specified for backup.")
        return

    # Step 2: Calculate total bytes for the entire backup
    total_bytes = 0
    for path in targets:
        if os.path.isfile(path):
            total_bytes += os.path.getsize(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        total_bytes += os.path.getsize(file_path)
                    except OSError:
                        pass

    # Step 3: Create the progress tracker with the total bytes
    tracker = DualProgressBar(total_bytes=total_bytes)

    # Step 4: Ensure the vault directory exists
    os.makedirs(engine.vault_path, exist_ok=True)

    # Step 5: Copy each target into the vault
    for path in targets:
        if not os.path.exists(path):
            logger.warning("Target does not exist: %s", path)
            continue

        copy_to(path, engine.vault_path, tracker=tracker)

    # Step 6: Print a final newline after finishing all files
    tracker.finish()
