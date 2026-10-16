import logging
from modules.engine import Engine

logger = logging.getLogger("octoback.show")


def show(engine: Engine) -> None:
    """Display all tracked paths and their index info."""
    if not engine.index:
        print("Index is empty. No paths currently tracked.")
        return

    print(f"\nTracked Paths ({len(engine.index)} items):")
    print("-" * 70)
    for path, meta in engine.index.items():
        obj_type = meta.get("type", "unknown")
        size = meta.get("size", "0")
        hash_val = meta.get("hash", "")[:8]
        print(f"[{obj_type:<4}] {path} ({size} bytes, hash: {hash_val}...)")
    print("-" * 70)
