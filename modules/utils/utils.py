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
        return None

def get_file_hash_optimized(file_path: str):
    "returns the hexdigest of a file but, it does it in chunks of 64MB"
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024 ** 2), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None

def get_dir_hash_optimized(dir_path: str) -> str | None:
    """returns a stable hexdigest of a directory's contents"""
    sha256_hash = hashlib.sha256()
    try:
        for root, dirs, files in sorted_dirs_and_files(os.walk(dir_path)):
            for name in files:
                file_path = os.path.join(root, name)
                rel = os.path.relpath(file_path, dir_path)
                sha256_hash.update(rel.encode())  # structure matters
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(64 * 1024 ** 2), b""):
                        sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        print(f"Directory not found: {dir_path}")
        return None

def sorted_dirs_and_files(walk):
    """generator that yields (root, sorted(dirs), sorted(files))"""
    for root, dirs, files in walk:
        dirs.sort()
        files.sort()
        yield root, dirs, files
