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


def show_history(engine: Engine, limit: int = 20) -> None:
    """Display recorded lifecycle history of tracked paths."""
    import json
    import os

    if not os.path.exists(engine.history_path):
        print("No history recorded yet.")
        return

    entries = []
    with open(engine.history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("History log is empty.")
        return

    total = len(entries)
    display_entries = entries[-limit:] if limit > 0 else entries

    print(f"\nOctoback History (showing {len(display_entries)} of {total} event(s)):")
    print("-" * 75)
    for entry in display_entries:
        timestamp = entry.get("time", "Unknown time")
        action = entry.get("action", "").upper().ljust(9)
        path = entry.get("path", "")
        origin = entry.get("origin")

        if origin and action.strip() == "MOVED":
            details = f"{origin} -> {path}"
        elif origin and action.strip() == "COPIED":
            details = f"{path} (copy of {origin})"
        else:
            details = path

        print(f"[{timestamp}] [{action}] {details}")
    print("-" * 75)
