import logging
import os
import time
from typing import List
from modules.engine import Engine
from ..utils import DualProgressBar, copy_to, count_part, format_size, format_summary, paint, short_path

logger = logging.getLogger("octoback.restore")


def is_different(vault_file: str, dest_file: str) -> bool:
    """True if dest_file exists and doesn't look like the Vault copy (size or modification time differ)."""
    if not os.path.isfile(dest_file):
        return False
    vault_stat = os.stat(vault_file)
    dest_stat = os.stat(dest_file)
    return vault_stat.st_size != dest_stat.st_size or vault_stat.st_mtime_ns != dest_stat.st_mtime_ns


def find_files_to_overwrite(vault_path: str, dest_path: str) -> List[str]:
    """Lists your existing files that restoring vault_path would replace."""
    if os.path.isfile(vault_path):
        return [dest_path] if is_different(vault_path, dest_path) else []

    overwritten = []
    for root, _, files in os.walk(vault_path):
        for name in files:
            vault_file = os.path.join(root, name)
            dest_file = os.path.join(dest_path, os.path.relpath(vault_file, vault_path))
            if is_different(vault_file, dest_file):
                overwritten.append(dest_file)
    return overwritten


def restore(engine: Engine, input_list: List[str], all_flag: bool = False, yes_flag: bool = False) -> bool:
    # Step 1: Decide what paths to restore
    if all_flag:
        targets = list(engine.index.keys())
    else:
        targets = input_list

    if not targets:
        logger.warning("No targets specified for restore.")
        return False

    start_time = time.monotonic()

    # Step 2: Build pairs of (vault_source, destination_target) using mirrored paths
    restore_pairs = []
    for original_path in targets:
        # Items were mirrored under engine.vault_path:
        # e.g. /home/user/doc.txt was stored at ~/Vault/home/user/doc.txt
        rel_path = original_path.lstrip(os.sep)
        vault_path = os.path.join(engine.vault_path, rel_path)

        if not os.path.exists(vault_path):
            logger.warning("Not in the Vault, skipped: %s", short_path(original_path))
            continue

        restore_pairs.append((vault_path, original_path))

    if not restore_pairs:
        logger.warning("Nothing to restore: none of these are in the Vault.")
        return False

    # Step 3: Ask before replacing any of your existing files that differ from the Vault copy
    overwritten = []
    for vault_path, dest_path in restore_pairs:
        overwritten += find_files_to_overwrite(vault_path, dest_path)

    if overwritten and not yes_flag:
        print(f"{paint('⚠', 'yellow')} Restoring will overwrite {len(overwritten)} existing file(s) that differ from the Vault:")
        for path in overwritten[:20]:
            print(f"    {short_path(path)}")
        if len(overwritten) > 20:
            print(paint(f"    ... and {len(overwritten) - 20} more", "dim"))
        confirm = input("\nDo you want to overwrite them with the Vault copies? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Restore aborted. Nothing was changed.")
            return False

    # Step 4: Calculate total bytes across all vault items to restore
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

    # Step 5: Create the progress tracker with the total bytes
    tracker = DualProgressBar(total_bytes=total_bytes)

    # Step 6: Restore each item from vault back to its destination
    failed = []
    for vault_path, dest_path in restore_pairs:
        parent_dir = os.path.dirname(dest_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        if not copy_to(vault_path, dest_path, tracker=tracker):
            failed.append(dest_path)

    # Step 7: Clear the progress bar
    tracker.finish()

    # Step 8: List items that were not fully restored, then the summary
    for path in failed:
        logger.warning("Not fully restored: %s", short_path(path))
    restored = tracker.copied_count
    parts = [count_part(restored, "restored") + (f" ({format_size(tracker.read_bytes)})" if restored else ""),
             count_part(tracker.skipped_count, "unchanged"), count_part(len(failed), "failed")]
    print(format_summary("Restore done", parts, time.monotonic() - start_time, not failed))
    return not failed
