import logging
import os
import time
from typing import List
from modules.engine import Engine
from .pick import pick
from .restore import is_different
from .update import update
from ..utils import DualProgressBar, ancestors, copy_to, count_part, format_size, format_summary, is_gone, paint, short_path

logger = logging.getLogger("octoback.backup")


def backup_items(engine: Engine) -> dict:
    """Lists what backup can copy: tracked path -> (kind, size, status compared with the Vault)."""
    items = {}
    for path, meta in engine.index.items():
        vault_copy = os.path.join(engine.vault_path, path.lstrip(os.sep))
        if meta.get("type") == "file":
            kind = "file"
        else:
            kind = "whole" if engine.is_whole(path) else "empty"

        if not os.path.exists(path):
            status = "missing" if is_gone(path) else "can't read"
        elif not os.path.lexists(vault_copy):
            status = "new"
        elif kind != "file":
            status = "in Vault"
        elif os.path.isfile(vault_copy) and not is_different(path, vault_copy):
            status = "same"
        else:
            status = "changed"
        items[path] = (kind, meta.get("size", 0), status)
    return items


def pick_backup(engine: Engine) -> List[str] | None:
    """Lets the user pick tracked paths to back up from a list. None when nothing was picked."""
    print(paint("Reading the index ...", "dim"))
    items = backup_items(engine)
    if not items:
        print("Nothing is tracked yet. Start with: octoback add <paths>")
        return None
    picked = pick(items, "Back up", "b", "back up")
    if not picked:
        print("Nothing backed up.")
        return None
    # A picked folder means the tracked paths inside it, not the untracked files next to them
    picked = set(picked)
    return sorted(p for p in items if p in picked or any(folder in picked for folder in ancestors(p)))


def backup(engine: Engine, input: List[str], all_flag: bool = False, update_first: bool = False) -> bool:
    # Step 0: Optionally update the index first
    updated = update(engine, input, all_flag=all_flag) if update_first else True

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
            try:
                total_bytes += os.path.getsize(path)
            except OSError:
                pass
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
    try:
        for path in targets:
            if not os.path.exists(path):
                if is_gone(path):
                    logger.warning("Not found, skipped: %s", short_path(path))
                else:
                    logger.error("Could not read %s", short_path(path))  # e.g. inside a folder without permission
                    failed.append(path)
                continue

            # Strip leading '/' so os.path.join preserves engine.vault_path:
            # e.g. /home/user/doc.txt -> ~/Vault/home/user/doc.txt
            rel_path = path.lstrip(os.sep)
            dest_vault_path = os.path.join(engine.vault_path, rel_path)

            if not copy_to(source=path, destination=dest_vault_path, tracker=tracker, vault_root=engine.vault_path):
                failed.append(path)
    except KeyboardInterrupt:
        tracker.finish()  # Clear the bar, then let main() report the kill
        raise

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
    return not failed and updated
