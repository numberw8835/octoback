import logging
import os
import shutil
import tarfile
import time
from modules.engine import Engine
from ..utils import DualProgressBar, ProgressReader, format_size, format_summary, paint, short_path, sorted_dirs_and_files

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
        logger.error("Vault not found: %s", short_path(vault_path))
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
    start_time = time.monotonic()

    try:
        logger.info(paint(f"Compressing {short_path(vault_path)} into {os.path.basename(archive_path)} ...", "dim"))
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
        sizes = f"{format_size(total_bytes)} → {format_size(os.path.getsize(archive_path))}"
        print(format_summary("Vault compressed", [sizes], time.monotonic() - start_time))
        return True

    except KeyboardInterrupt:
        # Don't leave a half-written archive behind, then let main() report the kill
        tracker.finish()
        if os.path.exists(tmp_archive):
            try:
                os.remove(tmp_archive)
            except OSError:
                pass
        raise
    except Exception as e:
        logger.error("Could not compress the Vault: %s", e)
        if os.path.exists(tmp_archive):
            try:
                os.remove(tmp_archive)
            except OSError:
                pass
        return False
