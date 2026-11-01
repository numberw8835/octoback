import json
import logging
import os
import shutil
from ..engine import Engine
from ..utils import ancestors, format_action, get_dir_hash_optimized, get_file_hash_optimized, is_gone, paint, short_path

logger = logging.getLogger("octoback.vault")


def get_vault_copy_path(engine: Engine, path: str) -> str:
    """Returns where the backup of a path lives in the Vault (e.g. ~/Vault/home/user/doc.txt)."""
    return os.path.join(engine.vault_path, path.lstrip(os.sep))


def same_backup(first: str, second: str) -> bool:
    """True if two Vault copies hold the same data."""
    if os.path.isfile(first) and os.path.isfile(second):
        if os.path.getsize(first) != os.path.getsize(second):
            return False
        first_hash, second_hash = get_file_hash_optimized(first), get_file_hash_optimized(second)
    elif os.path.isdir(first) and os.path.isdir(second):
        first_hash, second_hash = get_dir_hash_optimized(first), get_dir_hash_optimized(second)
    else:
        return False
    return first_hash != "" and first_hash == second_hash


def is_backed_up(engine: Engine, path: str) -> bool:
    """True if the path is a tracked file and its Vault copy has the hash from the index."""
    entry = engine.index.get(path, {})
    vault_file = get_vault_copy_path(engine, path)
    if entry.get("type") != "file" or not os.path.isfile(vault_file):
        return False
    return get_file_hash_optimized(vault_file) == entry.get("hash")


def clean_vault(engine: Engine, yes_flag: bool = False, remove_deleted: bool = False) -> bool:
    """Uses history to find and remove ghost files from the vault."""
    if not os.path.exists(engine.history_path):
        print("No history found. Vault is clean.")
        return True

    # 1. Replay the history in order, so only the newest event of each path counts
    last = {}     # path -> (event number, action, where it moved to)
    started = {}  # path -> number of the event that put the current file there ("modified" doesn't count)
    with open(engine.history_path, "r", encoding="utf-8") as f:
        for number, line in enumerate(f):
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue  # Not written by Octoback
            path, action, origin = entry["path"], entry.get("action"), entry.get("origin")
            last[path] = (number, action, None)
            if action != "modified":
                started[path] = number
            if action == "moved" and isinstance(origin, str):
                last[origin] = (number, "moved away", path)
                started[origin] = number

    def is_ghost(path: str, owner: str) -> bool:
        """True if the newest event of owner (the path, or a folder above it) makes the path's backup a ghost"""
        number, action, moved_to = last[owner]
        if action == "untracked":
            return True
        if action == "moved away":
            # Only once the new location is backed up too, with this data or a newer version of it
            dest = moved_to if owner == path else os.path.join(moved_to, os.path.relpath(path, owner))
            if same_backup(get_vault_copy_path(engine, path), get_vault_copy_path(engine, dest)):
                return True
            return started.get(dest) == number and is_backed_up(engine, dest)
        # Deleted files only when asked, and never one that is back on disk
        return action in ("deleted", "removed") and remove_deleted and is_gone(path)

    # 2. Collect paths the user untracked, old locations of moved files, and deleted files when asked.
    #    A newer event on a folder above covers the path too, but never beats the path's own reason
    #    to keep its backup: a deleted file (the Vault may hold the only copy), or a move not backed up yet.
    old_paths, kept = set(), set()
    for path in last:
        if not os.path.exists(get_vault_copy_path(engine, path)):
            continue
        owner = path
        for folder in ancestors(path):
            if folder in last and last[folder][0] > last[owner][0]:
                owner = folder
        keeps_own = last[path][1] in ("deleted", "removed", "moved away") and not is_ghost(path, path)
        if keeps_own or not is_ghost(path, owner):
            kept.add(path)
        else:
            old_paths.add(path)

    # 3. Leave out paths still tracked or inside a tracked folder, and folders holding anything tracked or kept
    tracked = set(engine.index)
    holding = {folder for path in [*engine.index, *kept] for folder in ancestors(path)}
    ghost_files = []
    for path in old_paths:
        if path in tracked or path in holding or any(folder in tracked for folder in ancestors(path)):
            continue
        ghost_files.append(get_vault_copy_path(engine, path))
    ghost_files.sort()

    if not ghost_files:
        print("Vault is clean! No ghost files found.")
        return True

    # 4. Show ghost files and ask for confirmation
    print(f"{paint('⚠', 'yellow')} Found {len(ghost_files)} ghost file(s) in the Vault:")
    for gf in ghost_files:
        print(f"    {short_path(gf)}")

    if not yes_flag:
        confirm = input("\nDo you want to permanently delete these from the Vault? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Vault cleaning aborted.")
            return False

    # 5. Delete the ghost files from the Vault (files inside a ghost folder go before the folder itself)
    ok = True
    for gf in reversed(ghost_files):
        try:
            if os.path.isdir(gf):
                shutil.rmtree(gf)
            else:
                os.remove(gf)
            logger.info(format_action("deleted", gf))
        except OSError as e:
            logger.error("Could not delete %s: %s", short_path(gf), e.strerror or e)
            ok = False

    print(f"{paint('✓', 'green')} Vault clean done ({len(ghost_files)} ghost item(s) removed).")
    return ok
