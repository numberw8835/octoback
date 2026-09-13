import hashlib

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
    "returns the hexdigest of a file but, it does it in chunks of 4MB"
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4194304), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None