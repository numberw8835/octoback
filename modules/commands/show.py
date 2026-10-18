import json
import logging
import os
from modules.engine import Engine
from ..utils import format_action, format_size, paint, short_path

logger = logging.getLogger("octoback.show")


def show(engine: Engine) -> None:
    """Display all tracked paths as aligned columns: type, size, hash, path."""
    if not engine.index and not engine.roots:
        print("Nothing is tracked yet. Start with: octoback add <paths>")
        return

    if engine.roots:
        print(paint(f"Folders ({len(engine.roots)})", "bold"))
        for root in engine.roots:
            print(f"  {short_path(root)}")
        print()

    print(paint(f"Tracked ({len(engine.index)})", "bold"))
    for path, meta in engine.index.items():
        obj_type = meta.get("type", "?")
        size = format_size(meta.get("size", 0))
        hash_val = meta.get("hash", "")[:8]
        print(f"  {obj_type:<4}  {size:>9}  {paint(hash_val, 'dim')}  {short_path(path)}")


def show_history(engine: Engine, limit: int = 20) -> None:
    """Display recorded lifecycle history of tracked paths, coloured by action."""
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

    print(paint(f"History (last {len(display_entries)} of {total})", "bold"))
    for entry in display_entries:
        timestamp = entry.get("time", "unknown time")
        action = entry.get("action", "")
        origin = entry.get("origin")

        if origin and action == "moved":
            note = f"from {short_path(origin)}"
        elif origin and action == "copied":
            note = f"copy of {short_path(origin)}"
        else:
            note = ""

        print(f"  {paint(timestamp, 'dim')}  {format_action(action, entry.get('path', ''), note)}")
