import logging
import os
import shutil
from typing import List
from ..engine import Engine

logger = logging.getLogger("octoback.prune")

def prune(engine: Engine) -> None: 
    """Remove entries from the index and their copies from the vault for paths that no longer exist."""
    paths_to_remove = [p for p in engine.index if not os.path.exists(p)]
    
    if not paths_to_remove:
        logger.info("Nothing to prune.")
        return
    
    for path in paths_to_remove:
        logger.info("Removing missing path from index: %s", path)
        engine.remove_path_from_index(path)

        # Remove mirrored copy from the Vault
        rel_path = path.lstrip(os.sep)
        vault_item = os.path.join(engine.vault_path, rel_path)

        if os.path.exists(vault_item):
            try:
                if os.path.isdir(vault_item):
                    shutil.rmtree(vault_item)
                else:
                    os.remove(vault_item)
                logger.info("Removed from vault: %s", vault_item)

                # Clean up any now-empty parent directories in vault
                parent = os.path.dirname(vault_item)
                vault_root = os.path.abspath(engine.vault_path)
                while os.path.abspath(parent) != vault_root and os.path.abspath(parent).startswith(vault_root):
                    if os.path.exists(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    else:
                        break
            except OSError as e:
                logger.error("Error removing %s from vault: %s", vault_item, e)
    
    engine.save_index()
    logger.info("Pruned %d paths from index and vault.", len(paths_to_remove))
