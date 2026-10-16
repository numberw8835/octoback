import logging
import os
import shutil
import tarfile
from modules.engine import Engine
from ..utils import DualProgressBar, ProgressReader, sorted_dirs_and_files

logger = logging.getLogger("octoback.zip")


def add_to_archive(tar: tarfile.TarFile, path: str, parent_dir: str, tracker: DualProgressBar) -> None:
    """Adds one entry to the archive, streaming regular files through the progress bar."""
    tarinfo = tar.gettarinfo(path, arcname=os.path.relpath(path, parent_dir))
    if tarinfo is None:
        return  # Sockets and other special files can't be archived
    if tarinfo.isreg():
        tracker.start_file(os.path.basename(path), tarinfo.size)
        with open(path, "rb") as f:
            tar.addfile(tarinfo, ProgressReader(f, tracker.update))
    else:
        tar.addfile(tarinfo)  # Folders and symlinks have no content


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
    parent_dir = os.path.dirname(vault_path)

    # Calculate total bytes in the vault for the progress bar
    total_bytes = 0
    for root, _, files in os.walk(vault_path):
        for f in files:
            try:
                total_bytes += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass

    tracker = DualProgressBar(total_bytes=total_bytes)

    try:
        logger.info("Compressing vault in-place: %s -> %s", vault_path, archive_path)
        # Archive vault contents one entry at a time so the progress bar can follow
        with tarfile.open(tmp_archive, "w:xz", preset=9) as tar:
            for root, dirs, files in sorted_dirs_and_files(os.walk(vault_path)):
                add_to_archive(tar, root, parent_dir, tracker)
                for name in files:
                    add_to_archive(tar, os.path.join(root, name), parent_dir, tracker)
                # Symlinked folders are listed but never walked, so add them as links here
                for name in dirs:
                    if os.path.islink(os.path.join(root, name)):
                        add_to_archive(tar, os.path.join(root, name), parent_dir, tracker)
        tracker.finish()

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
