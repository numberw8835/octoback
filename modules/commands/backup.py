import logging
import os
import time
from typing import List
from modules.engine import Engine
from ..utils import DualProgressBar, copy_to, count_part, format_size, format_summary, short_path

logger = logging.getLogger("octoback.backup")


def backup(engine: Engine, input: List[str], all_flag: bool = False) -> bool:
    # Step 1: Decide what paths to backup
    if all_flag:
        targets = list(engine.index.keys())
    else:
        targets = input

    if not targets:
        logger.warning("No targets specified for backup.")
        return False

    start_time = time.monotonic()

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

    # Step 5: Copy each target into the vault, mirroring its full path structure
    failed = []
    for path in targets:
        if not os.path.exists(path):
            logger.warning("Not found, skipped: %s", short_path(path))
            continue

        # Strip leading '/' so os.path.join preserves engine.vault_path:
        # e.g. /home/user/doc.txt -> ~/Vault/home/user/doc.txt
        rel_path = path.lstrip(os.sep)
        dest_vault_path = os.path.join(engine.vault_path, rel_path)

        if not copy_to(source=path, destination=dest_vault_path, tracker=tracker):
            failed.append(path)

    # Step 6: Clear the progress bar
    tracker.finish()

    # Step 7: List items that were not fully backed up, then the summary
    for path in failed:
        logger.warning("Not fully backed up: %s", short_path(path))
    copied = tracker.copied_count
    parts = [count_part(copied, "copied") + (f" ({format_size(tracker.read_bytes)})" if copied else ""),
             count_part(tracker.skipped_count, "unchanged"), count_part(len(failed), "failed"),
             count_part(tracker.symlinks_skipped, "symlinks skipped")]
    print(format_summary("Backup done", parts, time.monotonic() - start_time, not failed))
    return not failed
