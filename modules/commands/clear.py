import logging
import os
import shutil
from ..engine import Engine
from ..utils import paint, short_path

logger = logging.getLogger("octoback.clear")


def clear_index(engine: Engine, yes_flag: bool = False) -> bool:
    """Clears all tracked paths from the index without touching the Vault."""
    total = len(engine.index)
    if total == 0 and not engine.roots:
        print("Index is already empty.")
        return True

    print(f"{paint('⚠', 'yellow')} This will remove all {total} tracked item(s) from the index.")
    print(paint("  The Vault will NOT be touched.", "dim"))

    if not yes_flag:
        confirm = input("Are you sure you want to clear the entire index? (yes/no): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted.")
            return False

    engine.index.clear()
    engine.roots.clear()
    if not engine.save_index():
        return False
    print(f"{paint('✓', 'green')} Cleared {total} item(s) from the index.")
    return True


def clear_vault(engine: Engine, yes_flag: bool = False) -> bool:
    """Clears all backup files from the Vault without touching the index or PC files."""
    compressed_vault = f"{engine.vault_path}.tar.xz"
    has_files = os.path.isdir(engine.vault_path) and len(os.listdir(engine.vault_path)) > 0
    has_archive = os.path.exists(compressed_vault)
    if not has_files and not has_archive:
        print("Vault is already empty.")
        return True

    print(f"{paint('⚠', 'yellow')} This will permanently delete ALL backups in the Vault ({short_path(engine.vault_path)}).")
    print(paint("  Your files and the tracking index will NOT be touched.", "dim"))

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
                logger.error("Could not remove %s: %s", short_path(item_path), e.strerror or e)
                ok = False

    # Also remove compressed archive if present
    if has_archive:
        try:
            os.remove(compressed_vault)
            count += 1
        except OSError as e:
            logger.error("Could not remove %s: %s", short_path(compressed_vault), e.strerror or e)
            ok = False

    print(f"{paint('✓', 'green')} Cleared the Vault ({count} top-level item(s) removed).")
    return ok
