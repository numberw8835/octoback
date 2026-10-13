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

# TODO: Handle files locked by other processes

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
