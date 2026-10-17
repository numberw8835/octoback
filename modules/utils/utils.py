import logging
import os
import shutil
import sys
import tempfile
import time
from blake3 import blake3
from .style import format_duration, format_size, paint, short_path

logger = logging.getLogger("octoback.utils")

# BLAKE3 hash of no data at all (an empty file or an empty folder)
EMPTY_HASH = blake3().hexdigest()

def get_file_hash_optimized(file_path: str, tracker: "DualProgressBar | None" = None) -> str:
    """returns the BLAKE3 hexdigest of a file, read in chunks of 64MB and hashed on all CPU cores"""
    file_hash = blake3(max_threads=blake3.AUTO)
    try:
        if tracker:
            tracker.start_file(os.path.basename(file_path), os.path.getsize(file_path))
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024 ** 2), b""):
                file_hash.update(chunk)
                if tracker:
                    tracker.update(len(chunk))
        return file_hash.hexdigest()
    except OSError as e:
        logger.error("Could not read %s: %s", short_path(file_path), e.strerror or e)
        return ""

def get_quick_signature(path: str) -> str:
    """
    Cheap fingerprint built only from sizes and modification times, no file contents are read.
    If it is the same as last time, the contents haven't changed and hashing can be skipped.
    """
    try:
        if os.path.isfile(path):
            stat = os.stat(path)
            return f"{stat.st_size}:{stat.st_mtime_ns}"
        signature = blake3()
        for root, dirs, files in sorted_dirs_and_files(os.walk(path)):
            for name in dirs + files:
                entry_path = os.path.join(root, name)
                stat = os.lstat(entry_path)
                rel = os.path.relpath(entry_path, path)
                signature.update(os.fsencode(f"{rel}\0{stat.st_size}:{stat.st_mtime_ns}\n"))
        return signature.hexdigest()
    except OSError:
        return ""  # Unknown signature: never matches, so the path gets hashed

class DualProgressBar:
    """Renders one line: ━━━━━━━━━━────────── 48%  2.1 GB / 4.4 GB  120 MB/s  ETA 19s  big.bin 70%"""
    def __init__(self, total_bytes: int, bar_length: int = 20):
        self.total_bytes = max(total_bytes, 1)
        self.copied_total_bytes = 0  # Done so far, including files skipped as up to date
        self.read_bytes = 0          # Actually read from disk, used for the speed
        self.bar_length = bar_length
        self.current_file = ""
        self.current_file_bytes = 0
        self.current_file_total = 1
        self.files_copied_count = 0  # Files started (hashed, copied or extracted)
        self.copied_count = 0        # Files copied successfully, for backup/restore summaries
        self.skipped_count = 0
        self.start_time = time.monotonic()
        self.last_render = 0.0
        self.enabled = sys.stdout.isatty()  # No bar when output goes to a file or a pipe

    def scanning(self, item_name: str):
        """Shows which file is being compared (same size, different modification time)."""
        self.current_file = f"comparing {self.shorten_filename(item_name)}"
        self.render()

    def shorten_filename(self, filename: str) -> str:
        """Truncate long filenames to 25 characters (e.g., "Very_Long_Filename...mp3")"""
        max_name_len = 25
        if len(filename) <= max_name_len:
            return filename
        name, ext = os.path.splitext(filename)
        available = max_name_len - len(ext) - 3
        if available > 0:
            return f"{name[:available]}...{ext}"
        return f"{filename[:max_name_len - 3]}..."

    def start_file(self, filename: str, file_size: int):
        self.current_file = self.shorten_filename(filename)
        self.current_file_total = max(file_size, 1)
        self.current_file_bytes = 0
        self.files_copied_count += 1
        self.render()

    def skip_file(self, filename: str, file_size: int):
        """Count a file or folder that was already up to date, so the total bar still moves."""
        self.current_file = self.shorten_filename(filename)
        self.current_file_total = max(file_size, 1)
        self.current_file_bytes = file_size
        self.copied_total_bytes += file_size
        self.skipped_count += 1
        self.render()

    def update(self, chunk_bytes: int):
        self.copied_total_bytes += chunk_bytes
        self.current_file_bytes += chunk_bytes
        self.read_bytes += chunk_bytes
        self.render()

    def update_total(self, chunk_bytes: int):
        """Advance only the total bar (when total and file are measured differently, e.g. unzip)."""
        self.copied_total_bytes += chunk_bytes
        self.read_bytes += chunk_bytes
        self.render()

    def update_file(self, chunk_bytes: int):
        """Advance only the file bar."""
        self.current_file_bytes += chunk_bytes
        self.render()

    def render(self):
        # Redraw at most 10 times a second, so thousands of small files don't flood the terminal
        now = time.monotonic()
        if not self.enabled or now - self.last_render < 0.1:
            return
        self.last_render = now

        total_pct = min(100, self.copied_total_bytes * 100 // self.total_bytes)
        file_pct = min(100, self.current_file_bytes * 100 // self.current_file_total)
        filled = self.bar_length * total_pct // 100
        bar = paint("━" * filled, "teal") + paint("─" * (self.bar_length - filled), "dim")

        done = min(self.copied_total_bytes, self.total_bytes)
        text = f" {total_pct:>3}%  {format_size(done)} / {format_size(self.total_bytes)}"
        elapsed = now - self.start_time
        if elapsed > 1 and self.read_bytes:
            speed = self.read_bytes / elapsed
            text += f"  {format_size(speed)}/s  ETA {format_duration((self.total_bytes - done) / speed)}"
        text += f"  {self.current_file} {file_pct}%"

        # Keep it on one line: cut the text to the terminal width
        width = shutil.get_terminal_size().columns - self.bar_length - 1
        sys.stdout.write(f"\r\033[K{bar}{text[:width]}")
        sys.stdout.flush()

    def finish(self):
        """Clears the bar, so the command's summary line can take its place."""
        if self.enabled:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

class ProgressReader:
    """Wraps an open file and reports the size of every read to on_read (e.g. tracker.update)."""
    def __init__(self, f, on_read):
        self.f = f
        self.on_read = on_read

    def read(self, size: int = -1) -> bytes:
        data = self.f.read(size)
        self.on_read(len(data))
        return data

    def __getattr__(self, name):
        # Everything else (seek, tell, close...) goes straight to the real file
        return getattr(self.f, name)

def copy_file_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """
    Optimized file copy:
    1. Same size and modification time - already up to date, nothing is read.
    2. Same size but different time - compares content hashes before copying.
    3. Streams in 64MB chunks with atomic temp file rename.
    """
    tmp_dest = None
    try:
        dest_file = os.path.join(destination, os.path.basename(source)) if os.path.isdir(destination) else destination

        # Fast path: check if destination exists and is identical
        if os.path.exists(dest_file):
            src_stat = os.stat(source)
            dst_stat = os.stat(dest_file)

            if src_stat.st_size == dst_stat.st_size:
                # Copies keep the source modification time, so a match means nothing changed
                if src_stat.st_mtime_ns == dst_stat.st_mtime_ns:
                    if tracker:
                        tracker.skip_file(os.path.basename(source), src_stat.st_size)
                    return True

                # Times differ (e.g. a drive with coarse timestamps): verify content hash
                if tracker:
                    tracker.scanning(os.path.basename(source))
                src_hash = get_file_hash_optimized(source)
                dst_hash = get_file_hash_optimized(dest_file)
                if src_hash and src_hash == dst_hash:
                    shutil.copystat(source, dest_file)  # Sync the time so next run takes the fast path
                    if tracker:
                        tracker.skip_file(os.path.basename(source), src_stat.st_size)
                    return True  # Identical, skip copying!

        # Need to copy: ensure parent directory exists
        parent_dir = os.path.dirname(dest_file)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Atomic copy in 64MB chunks through a short, unique temp file in the same folder
        fd, tmp_dest = tempfile.mkstemp(dir=parent_dir, prefix=".octoback-", suffix=".tmp")

        chunk_size = 64 * 1024 * 1024

        if tracker:
            tracker.start_file(os.path.basename(source), os.path.getsize(source))

        with os.fdopen(fd, "wb") as dst, open(source, "rb") as src:
            for chunk in iter(lambda: src.read(chunk_size), b""):
                dst.write(chunk)
                if tracker:
                    tracker.update(len(chunk))
            # Force the data onto the disk, so a power cut can't leave an empty backup
            dst.flush()
            os.fsync(dst.fileno())

        # Keep permissions and timestamps (e.g. 600 on ssh keys, +x on scripts)
        shutil.copystat(source, tmp_dest)
        os.replace(tmp_dest, dest_file)
        sync_folder(parent_dir)
        if tracker:
            tracker.copied_count += 1
        return True

    except OSError as e:
        logger.error("Could not copy %s: %s", short_path(source), e.strerror or e)
        if tmp_dest and os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except OSError:
                pass
        return False

def copy_dir_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """
    Optimized directory copy:
    copies individual files using copy_file_to, which skips files that are already up to date.
    """
    try:
        target_dir = destination
        os.makedirs(target_dir, exist_ok=True)

        # Walk and copy/update files, keep going on errors and report at the end
        all_copied = True
        for root, dirs, files in sorted_dirs_and_files(os.walk(source)):
            # Never walk into the destination itself (e.g. backing up ~ while the Vault is ~/Vault)
            dirs[:] = [d for d in dirs if not is_inside(target_dir, os.path.join(root, d))]

            rel_path = os.path.relpath(root, source)
            current_dest = target_dir if rel_path == "." else os.path.join(target_dir, rel_path)
            os.makedirs(current_dest, exist_ok=True)

            for file in files:
                src_file = os.path.join(root, file)
                # Skip symlinks or non-regular files to prevent infinite loops/issues
                if os.path.islink(src_file) or not os.path.isfile(src_file):
                    continue
                dst_file = os.path.join(current_dest, file)
                if not copy_file_to(src_file, dst_file, tracker=tracker):
                    all_copied = False

        return all_copied
    except OSError as e:
        logger.error("Could not copy %s: %s", short_path(source), e.strerror or e)
        return False

def copy_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """Checks if source is a file or dir, checks hashes, and copies files in 64MB chunks."""
    if not os.path.exists(source):
        logger.error("Not found: %s", short_path(source))
        return False

    if os.path.isfile(source):
        return copy_file_to(source, destination, tracker=tracker)
    elif os.path.isdir(source):
        return copy_dir_to(source, destination, tracker=tracker)
    else:
        logger.error("Not a file or folder: %s", short_path(source))
        return False

def get_dir_hash_optimized(dir_path: str, tracker: "DualProgressBar | None" = None) -> str:
    """returns a stable hexdigest of a directory's structure and contents"""
    if not os.path.isdir(dir_path):
        logger.error("Folder not found: %s", short_path(dir_path))
        return ""
    dir_hash = blake3()
    try:
        # One line per entry: "sub/" for a folder, "sub/b.txt\0<file hash>" for a file
        for root, dirs, files in sorted_dirs_and_files(os.walk(dir_path)):
            for name in dirs:
                rel = os.path.relpath(os.path.join(root, name), dir_path)
                dir_hash.update(os.fsencode(f"{rel}/\n"))
            for name in files:
                file_path = os.path.join(root, name)
                # Skip symlinks to prevent infinite loops
                if os.path.islink(file_path) or not os.path.isfile(file_path):
                    continue
                file_hash = get_file_hash_optimized(file_path, tracker=tracker)
                if not file_hash:
                    return ""  # Unreadable file: fail instead of pretending it matches
                rel = os.path.relpath(file_path, dir_path)
                dir_hash.update(os.fsencode(f"{rel}\0{file_hash}\n"))
        return dir_hash.hexdigest()
    except OSError as e:
        logger.error("Could not read %s: %s", short_path(dir_path), e.strerror or e)
        return ""

def get_mount_point(path: str) -> str:
    """returns the mount point (drive) a path lives on, e.g. / or /run/media/user/Data"""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path

def sync_folder(folder: str) -> None:
    """Force a rename inside folder onto the disk, so it survives a power cut"""
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def is_inside(path: str, folder: str) -> bool:
    """True if path is the folder itself or somewhere inside it"""
    return path == folder or path.startswith(folder + os.sep)

def sorted_dirs_and_files(walk):
    """generator that yields (root, sorted(dirs), sorted(files))"""
    for root, dirs, files in walk:
        dirs.sort()
        files.sort()
        yield root, dirs, files
