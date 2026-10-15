import logging
import os
import tarfile
from modules.engine import Engine

logger = logging.getLogger("octoback.unzip")


def unzip_vault(engine: Engine) -> bool:
    """
    Decompresses the vault archive (Vault.tar.xz) in-place back into engine.vault_path
    and removes the archive file once extraction succeeds.
    """
    vault_path = engine.vault_path
    archive_path = f"{vault_path}.tar.xz"

    if not os.path.exists(archive_path):
        logger.error("Compressed vault archive does not exist: %s", archive_path)
        return False

    parent_dir = os.path.dirname(vault_path)

    try:
        logger.info("Decompressing vault in-place: %s -> %s", archive_path, parent_dir)
        with tarfile.open(archive_path, "r:xz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=parent_dir, filter="data")
            else:
                tar.extractall(path=parent_dir)

        # Remove the archive file after successful extraction
        os.remove(archive_path)
        logger.info("Vault decompressed successfully to %s", vault_path)
        return True

    except Exception as e:
        logger.error("Failed to decompress vault in-place: %s", e)
        return False
