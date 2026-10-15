import hashlib
import os

def get_file_hash(file_path: str):
    """returns the hash digest of the file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            sha256_hash.update(f.read())
            result = sha256_hash.hexdigest()
            return result
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return ""

def get_file_hash_optimized(file_path: str) -> str:
    """returns the hexdigest of a file in chunks of 64MB"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024 ** 2), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except OSError as e:
        print(f"Error reading file {file_path}: {e}")
        return ""

class DualProgressBar:
    """Renders dual progress: [total: ▮▮▮ 2% | file_name: ▮▮▮▮▮▮ 24%]"""
    def __init__(self, total_bytes: int, bar_length: int = 15):
        import sys
        self.sys = sys
        self.total_bytes = max(total_bytes, 1)
        self.copied_total_bytes = 0
        self.bar_length = bar_length
        self.current_file = ""
        self.current_file_bytes = 0
        self.current_file_total = 1

    def start_file(self, filename: str, file_size: int):
        self.current_file = filename
        self.current_file_total = max(file_size, 1)
        self.current_file_bytes = 0
        self.render()

    def update(self, chunk_bytes: int):
        self.copied_total_bytes += chunk_bytes
        self.current_file_bytes += chunk_bytes
        self.render()

    def render(self):
        total_pct = min(100, int((self.copied_total_bytes / self.total_bytes) * 100))
        file_pct = min(100, int((self.current_file_bytes / self.current_file_total) * 100))

        total_filled = int(self.bar_length * total_pct // 100)
        file_filled = int(self.bar_length * file_pct // 100)

        total_bar = "▮" * total_filled + " " * (self.bar_length - total_filled)
        file_bar = "▮" * file_filled + " " * (self.bar_length - file_filled)

        # \033[K clears from cursor to end of line, preventing trailing ghost characters
        line = f"\r\033[K[total: {total_bar} {total_pct:>3}% | {self.current_file} : {file_bar} {file_pct:>3}%]"
        self.sys.stdout.write(line)
        self.sys.stdout.flush()

    def finish(self):
        self.sys.stdout.write("\n")
        self.sys.stdout.flush()

def copy_file_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """
    Optimized file copy:
    1. Size check first (O(1)) - skips hashing if sizes differ.
    2. Only hashes if destination exists and sizes match.
    3. Streams in 64MB chunks with atomic temp file rename.
    """
    try:
        dest_file = os.path.join(destination, os.path.basename(source)) if os.path.isdir(destination) else destination

        # Fast path: check if destination exists and is identical
        if os.path.exists(dest_file):
            src_stat = os.stat(source)
            dst_stat = os.stat(dest_file)

            # If sizes match, verify content hash
            if src_stat.st_size == dst_stat.st_size:
                src_hash = get_file_hash_optimized(source)
                dst_hash = get_file_hash_optimized(dest_file)
                if src_hash and src_hash == dst_hash:
                    if tracker:
                        tracker.update(src_stat.st_size)
                    return True  # Identical, skip copying!

        # Need to copy: ensure parent directory exists
        parent_dir = os.path.dirname(dest_file)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Atomic copy in 64MB chunks
        tmp_dest = f"{dest_file}.octoback.tmp"
        chunk_size = 64 * 1024 * 1024

        if tracker:
            tracker.start_file(os.path.basename(source), os.path.getsize(source))

        with open(source, "rb") as src, open(tmp_dest, "wb") as dst:
            for chunk in iter(lambda: src.read(chunk_size), b""):
                dst.write(chunk)
                if tracker:
                    tracker.update(len(chunk))

        os.replace(tmp_dest, dest_file)
        return True

    except OSError as e:
        print(f"Error copying file {source} to {destination}: {e}")
        tmp_dest = f"{dest_file}.octoback.tmp"
        if os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except OSError:
                pass
        return False

def copy_dir_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """
    Optimized directory copy:
    1. Skips entirely if directory hash already matches target.
    2. Otherwise, copies individual files using optimized copy_file_to.
    """
    try:
        target_dir = destination

        # Directory-level fast path: skip if entire directory hash matches
        if os.path.isdir(target_dir):
            src_dir_hash = get_dir_hash_optimized(source)
            dst_dir_hash = get_dir_hash_optimized(target_dir)
            if src_dir_hash and src_dir_hash == dst_dir_hash:
                if tracker:
                    dir_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, files in os.walk(source) for f in files)
                    tracker.update(dir_size)
                return True  # Whole directory is identical, skip!

        # Walk and copy/update files
        for root, dirs, files in sorted_dirs_and_files(os.walk(source)):
            rel_path = os.path.relpath(root, source)
            current_dest = target_dir if rel_path == "." else os.path.join(target_dir, rel_path)
            os.makedirs(current_dest, exist_ok=True)

            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(current_dest, file)
                if not copy_file_to(src_file, dst_file, tracker=tracker):
                    return False

        return True
    except OSError as e:
        print(f"Error copying directory {source} to {destination}: {e}")
        return False

def copy_to(source: str, destination: str, tracker: DualProgressBar | None = None) -> bool:
    """Checks if source is a file or dir, checks hashes, and copies files in 64MB chunks."""
    if not os.path.exists(source):
        print(f"Source not found: {source}")
        return False

    if os.path.isfile(source):
        return copy_file_to(source, destination, tracker=tracker)
    elif os.path.isdir(source):
        return copy_dir_to(source, destination, tracker=tracker)
    else:
        print(f"Unsupported source type: {source}")
        return False

def get_dir_hash_optimized(dir_path: str) -> str:
    """returns a stable hexdigest of a directory's contents"""
    if not os.path.isdir(dir_path):
        print(f"Directory not found: {dir_path}")
        return ""
    sha256_hash = hashlib.sha256()
    try:
        for root, dirs, files in sorted_dirs_and_files(os.walk(dir_path)):
            for name in files:
                file_path = os.path.join(root, name)
                rel = os.path.relpath(file_path, dir_path)
                sha256_hash.update(rel.encode())  # structure matters
                try:
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(64 * 1024 ** 2), b""):
                            sha256_hash.update(chunk)
                except OSError:
                    # Ignore transient or unreadable files inside the directory
                    continue
        return sha256_hash.hexdigest()
    except OSError as e:
        print(f"Error accessing directory {dir_path}: {e}")
        return ""

def sorted_dirs_and_files(walk):
    """generator that yields (root, sorted(dirs), sorted(files))"""
    for root, dirs, files in walk:
        dirs.sort()
        files.sort()
        yield root, dirs, files
