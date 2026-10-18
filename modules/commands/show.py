import json
import logging
import os
from modules.engine import Engine
from ..utils import format_action, format_size, paint, short_path

logger = logging.getLogger("octoback.show")


def show(engine: Engine) -> None:
    """Display what was added: tracked folders (with their size and file count), whole folders and files."""
    if not engine.index and not engine.roots:
        print("Nothing is tracked yet. Start with: octoback add <paths>")
        return

    # Sum up the entries inside each tracked folder
    sizes = {root: 0 for root in engine.roots}
    counts = {root: 0 for root in engine.roots}
    top = []
    for path, meta in engine.index.items():
        root = engine.root_of(path)
        if root:
            sizes[root] += meta.get("size", 0)
            counts[root] += 1
        else:
            obj_type = "whole" if meta.get("type") == "dir" else meta.get("type", "?")
            top.append((obj_type, meta.get("size", 0), path, ""))
    top = [("folder", sizes[r], r, paint(f"  {counts[r]:,} items", "dim")) for r in engine.roots] + top

    print(paint(f"Tracked ({len(top)})", "bold"))
    for obj_type, size, path, note in top:
        print(f"  {obj_type:<6}  {format_size(size):>9}  {short_path(path)}{note}")


def show_index(engine: Engine) -> None:
    """Display every index entry as aligned columns: type, size, hash, path."""
    if not engine.index:
        print("The index is empty.")
        return

    print(paint(f"Index ({len(engine.index)})", "bold"))
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
