import json
import logging
import os
import shutil
from ..engine import Engine

logger = logging.getLogger("octoback.vault")


def clean_vault(engine: Engine, yes_flag: bool = False) -> None:
    """Uses history to find and remove ghost files from the vault."""
    if not os.path.exists(engine.history_path):
        logger.info("No history found. Vault is clean.")
        return

    # 1. Collect all paths that were marked as removed or moved in history
    old_paths = set()
    with open(engine.history_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                action = entry.get("action")
                if action == "removed" and entry.get("path"):
                    old_paths.add(entry["path"])
                elif action == "moved" and entry.get("origin"):
                    old_paths.add(entry["origin"])
            except json.JSONDecodeError:
                continue

    # 2. Check which of those old paths still linger in the Vault and are not in index
    ghost_files = []
    for path in old_paths:
        if path not in engine.index:
            rel_path = path.lstrip(os.sep)
            vault_file = os.path.join(engine.vault_path, rel_path)
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
