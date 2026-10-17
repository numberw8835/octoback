import logging
import lzma
import os
import tarfile
import time
from modules.engine import Engine
from ..utils import DualProgressBar, ProgressReader, count_part, format_summary, paint, short_path

logger = logging.getLogger("octoback.unzip")


def unzip_vault(engine: Engine) -> bool:
    """
    Decompresses the vault archive (Vault.tar.xz) in-place back into engine.vault_path
    and removes the archive file once extraction succeeds.
    """
    vault_path = engine.vault_path
    archive_path = f"{vault_path}.tar.xz"

    if not os.path.exists(archive_path):
        logger.error("Compressed Vault not found: %s", short_path(archive_path))
        return False

    parent_dir = os.path.dirname(vault_path)

    # The extracted size is unknown until the end, so the total bar follows
    # the compressed bytes read and the file bar follows the bytes extracted
    tracker = DualProgressBar(total_bytes=os.path.getsize(archive_path))
    start_time = time.monotonic()

    try:
        logger.info(paint(f"Decompressing {short_path(archive_path)} ...", "dim"))
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
        print(format_summary("Vault decompressed", [count_part(tracker.files_copied_count, "entries")],
                             time.monotonic() - start_time))
        return True

    except Exception as e:
        logger.error("Could not decompress the Vault: %s", e)
        return False
