import logging
import os
import shutil
from ..engine import Engine

logger = logging.getLogger("octoback.clear")


def clear_index(engine: Engine, yes_flag: bool = False) -> bool:
    """Clears all tracked paths from the index without touching the Vault."""
    total = len(engine.index)
    if total == 0:
        logger.info("Index is already empty.")
        return True

    print(f"Warning: This will remove all {total} tracked item(s) from the index.")
    print("The Vault will NOT be touched.")

    if not yes_flag:
        confirm = input("Are you sure you want to clear the entire index? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted.")
            return False

    engine.index.clear()
    logger.info("Cleared %d item(s) from index. Index is now empty.", total)
    return engine.save_index()


def clear_vault(engine: Engine, yes_flag: bool = False) -> bool:
    """Clears all backup files from the Vault without touching the index or PC files."""
    compressed_vault = f"{engine.vault_path}.tar.xz"
    has_files = os.path.isdir(engine.vault_path) and len(os.listdir(engine.vault_path)) > 0
    has_archive = os.path.exists(compressed_vault)
    if not has_files and not has_archive:
        logger.info("Vault is already empty.")
        return True

    print(f"Warning: This will permanently delete ALL backup files in the Vault ({engine.vault_path}).")
    print("Your PC files and tracking index will NOT be touched.")

    if not yes_flag:
        confirm = input("Are you sure you want to permanently clear the Vault? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted.")
            return False

    count = 0
    ok = True
    if has_files:
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
                ok = False

    # Also remove compressed archive if present
    if has_archive:
        try:
            os.remove(compressed_vault)
            count += 1
        except OSError as e:
            logger.error("Failed to remove %s: %s", compressed_vault, e)
            ok = False

    logger.info("Cleared Vault (%d top-level item(s) removed).", count)
    return ok
