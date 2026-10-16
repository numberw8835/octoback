import logging
import os
import shutil
from ..engine import Engine

logger = logging.getLogger("octoback.clear")


def clear_index(engine: Engine, yes_flag: bool = False) -> None:
    """Clears all tracked paths from the index without touching the Vault."""
    total = len(engine.index)
    if total == 0:
        logger.info("Index is already empty.")
        return

    print(f"Warning: This will remove all {total} tracked item(s) from the index.")
    print("The Vault will NOT be touched.")

    if not yes_flag:
        confirm = input("Are you sure you want to clear the entire index? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted.")
            return

    engine.index.clear()
    engine.save_index()
    logger.info("Cleared %d item(s) from index. Index is now empty.", total)


def clear_vault(engine: Engine, yes_flag: bool = False) -> None:
    """Clears all backup files from the Vault without touching the index or PC files."""
    if not os.path.exists(engine.vault_path) or not os.listdir(engine.vault_path):
        logger.info("Vault is already empty.")
        return

    print(f"Warning: This will permanently delete ALL backup files in the Vault ({engine.vault_path}).")
    print("Your PC files and tracking index will NOT be touched.")

    if not yes_flag:
        confirm = input("Are you sure you want to permanently clear the Vault? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted.")
            return

    count = 0
    for item in os.listdir(engine.vault_path):
        item_path = os.path.join(engine.vault_path, item)
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
            count += 1
        except OSError as e:
            logger.error("Failed to remove %s from Vault: %s", item_path, e)

    # Also remove compressed archive if present
    compressed_vault = f"{engine.vault_path}.tar.xz"
    if os.path.exists(compressed_vault):
        try:
            os.remove(compressed_vault)
        except OSError:
            pass

    logger.info("Cleared Vault (%d top-level item(s) removed).", count)
