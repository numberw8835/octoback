import curses
import os
from collections import Counter
from ..utils import ancestors, format_size, is_inside, paint, short_path
from .browse import KEYS_BACK, KEYS_DOWN, KEYS_OPEN, KEYS_QUIT, KEYS_UP, _put

KEY_SELECT = ord(" ")
KEY_ALL = ord("a")
QUIET = ("same", "in Vault")  # Statuses that need no attention: dimmed, and left out of folder notes


def build_tree(items: dict) -> tuple:
    """
    Groups {path: (kind, size, status)} into folders, starting at the deepest folder that holds everything.
    Returns ({folder: child paths}, {folder: [size, count, Counter of statuses]}, top folder).
    """
    paths = list(items)
    top = os.path.commonpath(paths) if len(paths) > 1 else os.path.dirname(paths[0])
    tree, info = {}, {}
    for path, (kind, size, status) in items.items():
        if path == top:
            continue
        child = path
        for folder in ancestors(path):
            if folder not in tree:
                tree[folder] = set()
                info[folder] = [0, 0, Counter()]
            tree[folder].add(child)
            totals = info[folder]
            totals[0] += size
            totals[1] += 1
            totals[2][status] += 1
            if folder == top:
                break
            child = folder
    return tree, info, top


def pick(items: dict, title: str, action_key: str, action: str) -> list | None:
    """
    Lets the user browse items ({path: (kind, size, status)}) and select some with space.
    Returns the picked paths (a folder stands for everything inside it), or None when they quit.
    """
    try:
        return curses.wrapper(_run, items, title, action_key, action)
    except curses.error as e:
        print(f"{paint('✗', 'red')} Can't show the list in this terminal ({e}): pass paths or --all instead")
        return None


def _shown(text: str) -> str:
    """text curses can draw: undecodable bytes and control characters (like a newline) become placeholders"""
    text = text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return "".join("?" if ord(c) < 32 or ord(c) == 127 else c for c in text)


def _run(scr, items: dict, title: str, action_key: str, action: str) -> list | None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass  # Some terminals can't hide the cursor
    curses.set_escdelay(25)
    tree, info, top = build_tree(items)

    def listing(folder):
        # Folders first, then the rest, each by name
        return sorted(tree.get(folder, ()), key=lambda p: (p not in tree, os.path.basename(p).casefold()))

    def through_folder(path):
        return any(a in selected for a in ancestors(path))

    stack = []  # (folder, rows, selected row, offset) of the levels above
    folder, rows, sel, off = top, listing(top), 0, 0
    selected = set()
    message = ""

    while True:
        h, w = scr.getmaxyx()
        height = max(h - 3, 1)
        sel = max(0, min(sel, len(rows) - 1))
        off = max(min(off, sel), sel - height + 1)

        scr.erase()
        _put(scr, 0, _shown(f" Octoback  {title} · {short_path(folder)}"), w, curses.A_BOLD)
        if not rows:
            _put(scr, 1, "  (empty)", w, curses.A_DIM)
        for i, path in enumerate(rows[off:off + height]):
            picked = path in selected or through_folder(path)
            if path in tree:
                size, count, statuses = info[path]
                if picked:
                    mark = "[x]"
                elif any(is_inside(s, path) for s in selected):
                    mark = "[-]"  # Something inside it is selected
                else:
                    mark = "[ ]"
                name = os.path.basename(path) + os.sep
                notes = "".join(f" · {n:,} {status}" for status, n in sorted(statuses.items()) if status not in QUIET)
                line = f" {mark} folder {format_size(size):>9}  {name}  {count:,} item{'s' * (count != 1)}{notes}"
                attr = curses.A_BOLD
            else:
                kind, size, status = items[path]
                mark = "[x]" if picked else "[ ]"
                name = os.path.basename(path) + (os.sep if kind != "file" else "")
                line = f" {mark} {kind:<6} {format_size(size):>9}  {name}  {status}"
                attr = curses.A_DIM if status in QUIET else 0
            _put(scr, 1 + i, _shown(line), w, curses.A_REVERSE if off + i == sel else attr)
        picked_size = sum(info[p][0] if p in tree else items[p][1] for p in selected)
        _put(scr, h - 2, f" {message}", w, curses.A_DIM)
        _put(scr, h - 1, f" {len(selected):,} selected · {format_size(picked_size)}    "
                         f"space select  a all  ⏎ open  ⌫ back  {action_key} {action}  q quit", w, curses.A_DIM)
        scr.refresh()

        key = scr.getch()
        message = ""
        if key in KEYS_QUIT or key == -1:  # -1: the input was closed, no key will come
            return None
        elif key in KEYS_UP:
            sel -= 1
        elif key in KEYS_DOWN:
            sel += 1
        elif key == curses.KEY_PPAGE:
            sel -= height
        elif key == curses.KEY_NPAGE:
            sel += height
        elif key in (curses.KEY_HOME, ord("g")):
            sel = 0
        elif key in (curses.KEY_END, ord("G")):
            sel = len(rows) - 1
        elif key in KEYS_OPEN and rows:
            if rows[sel] in tree:
                stack.append((folder, rows, sel, off))
                folder, rows, sel, off = rows[sel], listing(rows[sel]), 0, 0
            elif items[rows[sel]][0] == "whole":
                message = "Tracked as one unit: nothing inside it is listed"
        elif key in KEYS_BACK and stack:
            folder, rows, sel, off = stack.pop()
        elif key == KEY_SELECT and rows:
            path = rows[sel]
            if through_folder(path):
                message = "Selected with its folder: unselect the folder to change this"
            elif path in selected:
                selected.discard(path)
            else:
                if path in tree:
                    # The folder now covers what was selected inside it
                    selected.difference_update([s for s in selected if is_inside(s, path)])
                selected.add(path)
            sel += 1
        elif key == KEY_ALL and rows:
            if through_folder(rows[0]):
                message = "This whole folder is already selected"
            elif all(p in selected for p in rows):
                selected.difference_update(rows)
            else:
                selected.difference_update([s for s in selected if is_inside(s, folder)])
                selected.update(rows)
        elif key == ord(action_key):
            # Only what was selected on purpose, so a stray key press never starts anything
            if selected:
                return sorted(selected)
            message = f"Nothing selected: press space on what you want to {action}"
