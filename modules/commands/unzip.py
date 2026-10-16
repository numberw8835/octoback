import logging
import lzma
import os
import tarfile
from modules.engine import Engine
from ..utils import DualProgressBar, ProgressReader

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

    # The extracted size is unknown until the end, so the total bar follows
    # the compressed bytes read and the file bar follows the bytes extracted
    tracker = DualProgressBar(total_bytes=os.path.getsize(archive_path))

    try:
        logger.info("Decompressing vault in-place: %s -> %s", archive_path, parent_dir)
        with open(archive_path, "rb") as raw, \
                lzma.open(ProgressReader(raw, tracker.update_total)) as xz, \
                tarfile.open(fileobj=ProgressReader(xz, tracker.update_file), mode="r:") as tar:
            for member in tar:
                tracker.start_file(os.path.basename(member.name), member.size)
                if hasattr(tarfile, "data_filter"):
                    tar.extract(member, path=parent_dir, filter="data")
                else:
                    tar.extract(member, path=parent_dir)
        tracker.finish()

        # Remove the archive file after successful extraction
        os.remove(archive_path)
        logger.info("Vault decompressed successfully to %s", vault_path)
        return True

    except Exception as e:
        logger.error("Failed to decompress vault in-place: %s", e)
        return False
