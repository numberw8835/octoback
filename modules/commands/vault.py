import json
import logging
import os
import shutil
from ..engine import Engine
from ..utils import is_inside

logger = logging.getLogger("octoback.vault")


def get_vault_copy_path(engine: Engine, path: str) -> str:
    """Returns where the backup of a path lives in the Vault (e.g. ~/Vault/home/user/doc.txt)."""
    return os.path.join(engine.vault_path, path.lstrip(os.sep))


def is_still_tracked(engine: Engine, path: str) -> bool:
    """True if the path, a folder above it, or something inside it is still in the index."""
    return any(is_inside(path, tracked) or is_inside(tracked, path) for tracked in engine.index)


def clean_vault(engine: Engine, yes_flag: bool = False) -> None:
    """Uses history to find and remove ghost files from the vault."""
    if not os.path.exists(engine.history_path):
        logger.info("No history found. Vault is clean.")
        return

    # 1. Collect paths the user untracked, and old locations of moved files.
    #    "deleted" (and old "removed") entries are kept: the Vault may hold the only copy.
    old_paths = set()
    with open(engine.history_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                action = entry.get("action")
                if action == "untracked" and entry.get("path"):
                    old_paths.add(entry["path"])
                elif action == "moved" and entry.get("origin"):
                    # Only drop the old copy once the new location is backed up too
                    if os.path.exists(get_vault_copy_path(engine, entry.get("path", ""))):
                        old_paths.add(entry["origin"])
            except json.JSONDecodeError:
                continue

    # 2. Check which of those old paths still linger in the Vault and are not tracked anymore
    ghost_files = []
    for path in old_paths:
        if not is_still_tracked(engine, path):
            vault_file = get_vault_copy_path(engine, path)
            if os.path.exists(vault_file):
                ghost_files.append(vault_file)

    if not ghost_files:
        logger.info("Vault is clean! No ghost files found.")
        return

    # 3. Show ghost files and ask for confirmation
    print(f"\nFound {len(ghost_files)} ghost file(s) in Vault:")
    for gf in ghost_files:
        print(f"  - {gf}")

    if not yes_flag:
        confirm = input("\nDo you want to permanently delete these from the Vault? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Vault cleaning aborted.")
            return

    # 4. Delete the ghost files from the Vault
    for gf in ghost_files:
        try:
            if os.path.isdir(gf):
                shutil.rmtree(gf)
            else:
                os.remove(gf)
            logger.info("Removed: %s", gf)
        except OSError as e:
            logger.error("Failed to delete %s: %s", gf, e)

    logger.info("Vault clean complete! Removed %d ghost item(s).", len(ghost_files))
