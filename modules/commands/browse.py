import curses
import os
from modules.engine import Engine
from .show import top_items
from ..utils import format_size, short_path

KEYS_UP = (curses.KEY_UP, ord("k"))
KEYS_DOWN = (curses.KEY_DOWN, ord("j"))
KEYS_OPEN = (curses.KEY_ENTER, curses.KEY_RIGHT, 10, 13, ord("l"))
KEYS_BACK = (curses.KEY_BACKSPACE, curses.KEY_LEFT, 8, 127, ord("h"))
KEYS_QUIT = (27, ord("q"))


def children(engine: Engine, folder: str) -> list:
    """(type, size, path, items) for what is directly inside a folder, built from the index"""
    prefix = folder.rstrip(os.sep) + os.sep
    kids = {}
    for path, meta in engine.index.items():
        if not path.startswith(prefix):
            continue
        child = prefix + path[len(prefix):].split(os.sep)[0]
        kid = kids.setdefault(child, ["folder", 0, child, 0])
        if path == child:
            kid[0] = "file" if meta.get("type") == "file" else "whole" if engine.is_whole(child) else "empty"
        kid[1] += meta.get("size", 0)
        kid[3] += 1
    # Folders first, then files, each by name
    return sorted(map(tuple, kids.values()), key=lambda k: (k[0] == "file", k[2].casefold()))


def browse(engine: Engine) -> None:
    curses.wrapper(_run, engine)


def _put(scr, y: int, text: str, width: int, attr: int = 0) -> None:
    try:
        scr.addnstr(y, 0, text.ljust(width), width - 1, attr)
    except curses.error:
        pass  # Text that doesn't fit (e.g. wide characters at the edge)


def _run(scr, engine: Engine) -> None:
    curses.curs_set(0)
    curses.set_escdelay(25)
    stack = []  # (folder, items, selected, offset) of the levels above
    folder, items, sel, off = None, top_items(engine), 0, 0
    message = ""

    while True:
        h, w = scr.getmaxyx()
        rows = max(h - 3, 1)
        sel = max(0, min(sel, len(items) - 1))
        off = max(min(off, sel), sel - rows + 1)

        scr.erase()
        _put(scr, 0, f" Octoback  {short_path(folder) if folder else 'Tracked'}", w, curses.A_BOLD)
        if not items:
            _put(scr, 1, "  (empty)", w, curses.A_DIM)
        for i, (kind, size, path, count) in enumerate(items[off:off + rows]):
            name = short_path(path) if folder is None else os.path.basename(path)
            name += os.sep if kind != "file" else ""
            note = f"  {count:,} item{'s' * (count != 1)}" if kind == "folder" else ""
            attr = curses.A_REVERSE if off + i == sel else curses.A_BOLD if kind != "file" else 0
            _put(scr, 1 + i, f" {kind:<6} {format_size(size):>9}  {name}{note}", w, attr)
        total = sum(item[1] for item in items)
        _put(scr, h - 2, f" {message}", w, curses.A_DIM)
        _put(scr, h - 1, f" {len(items):,} item{'s' * (len(items) != 1)} · {format_size(total)}    ↑↓ move  ⏎ open  ⌫ back  q quit",
             w, curses.A_DIM)
        scr.refresh()

        key = scr.getch()
        message = ""
        if key in KEYS_QUIT:
            return
        elif key in KEYS_UP:
            sel -= 1
        elif key in KEYS_DOWN:
            sel += 1
        elif key == curses.KEY_PPAGE:
            sel -= rows
        elif key == curses.KEY_NPAGE:
            sel += rows
        elif key in (curses.KEY_HOME, ord("g")):
            sel = 0
        elif key in (curses.KEY_END, ord("G")):
            sel = len(items) - 1
        elif key in KEYS_OPEN and items:
            kind, _, path, _ = items[sel]
            if kind == "folder":
                stack.append((folder, items, sel, off))
                folder, items, sel, off = path, children(engine, path), 0, 0
            elif kind == "whole":
                message = "Tracked as one unit: nothing inside it is listed"
        elif key in KEYS_BACK and stack:
            folder, items, sel, off = stack.pop()
