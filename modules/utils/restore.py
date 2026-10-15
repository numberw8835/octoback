import logging
import os
from typing import List
from modules.engine import Engine
from .utils import DualProgressBar, copy_to

logger = logging.getLogger("octoback.restore")


def restore(engine: Engine, input: List[str], all_flag: bool = False):
    # Step 1: Decide what paths to restore
    if all_flag:
        targets = list(engine.index.keys())
    else:
        targets = input

    if not targets:
        logger.warning("No targets specified for restore.")
        return

    # Step 2: Build pairs of (vault_source, destination_target) and check they exist in vault
    restore_pairs = []
    for original_path in targets:
        item_name = os.path.basename(original_path.rstrip(os.sep))
        vault_path = os.path.join(engine.vault_path, item_name)

        if not os.path.exists(vault_path):
            logger.warning("Item not found in vault: %s", vault_path)
            continue

        restore_pairs.append((vault_path, original_path))

    if not restore_pairs:
        logger.warning("No valid items found in vault to restore.")
        return

    # Step 3: Calculate total bytes across all vault items to restore
    total_bytes = 0
    for vault_path, _ in restore_pairs:
        if os.path.isfile(vault_path):
            total_bytes += os.path.getsize(vault_path)
        elif os.path.isdir(vault_path):
            for root, dirs, files in os.walk(vault_path):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        total_bytes += os.path.getsize(file_path)
                    except OSError:
                        pass

    # Step 4: Create the progress tracker with the total bytes
    tracker = DualProgressBar(total_bytes=total_bytes)

    # Step 5: Restore each item from vault back to its destination
    for vault_path, dest_path in restore_pairs:
        parent_dir = os.path.dirname(dest_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        copy_to(vault_path, dest_path, tracker=tracker)

    # Step 6: Print a final newline after finishing all files
    tracker.finish()
