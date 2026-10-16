import logging
import os
import shutil
import tarfile
from modules.engine import Engine

logger = logging.getLogger("octoback.zip")


def zip_vault(engine: Engine) -> bool:
    """
    Compresses the vault directory in-place into Vault.tar.xz (using max LZMA2 preset 9)
    and removes the uncompressed directory once successfully archived.
    """
    vault_path = engine.vault_path
    if not os.path.exists(vault_path):
        logger.error("Vault directory does not exist: %s", vault_path)
        return False

    archive_path = f"{vault_path}.tar.xz"
    tmp_archive = f"{archive_path}.tmp"

    try:
        logger.info("Compressing vault in-place: %s -> %s", vault_path, archive_path)
        # Archive vault contents
        with tarfile.open(tmp_archive, "w:xz", preset=9) as tar:
            tar.add(vault_path, arcname=os.path.basename(vault_path))

        # Safely move temporary archive to final archive path
        os.replace(tmp_archive, archive_path)

        # Remove the uncompressed vault directory
        shutil.rmtree(vault_path)
        logger.info("Vault compressed successfully into %s", archive_path)
        return True

    except Exception as e:
        logger.error("Failed to compress vault in-place: %s", e)
        if os.path.exists(tmp_archive):
            try:
                os.remove(tmp_archive)
            except OSError:
                pass
        return False
