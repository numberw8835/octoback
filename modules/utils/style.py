import logging
import os
import sys

# Colour only when both outputs are terminals, and never when NO_COLOR is set (https://no-color.org)
USE_COLOR = sys.stdout.isatty() and sys.stderr.isatty() and "NO_COLOR" not in os.environ

# ANSI colour codes; teal and purple come from the logo
COLORS = {"green": "32", "yellow": "33", "red": "31", "dim": "2", "bold": "1", "teal": "38;5;43", "purple": "38;5;99"}

# Symbol and colour for every action shown in update, check, prune and history
ACTION_STYLES = {
    "new": ("✓", "green"),
    "modified": ("✓", "yellow"),
    "moved": ("✓", "purple"),
    "copied": ("✓", "teal"),
    "deleted": ("✓", "red"),
    "removed": ("✓", "red"),  # Old history name for "deleted"
    "untracked": ("✓", "dim"),
    "unchanged": ("·", "dim"),
    "matches": ("✓", "green"),
    "changed": ("✗", "red"),
    "skipped": ("⚠", "yellow"),
    "failed": ("✗", "red"),
}


def paint(text: str, color: str) -> str:
    """Wraps text in an ANSI colour (plain text when colours are off)."""
    return f"\033[{COLORS[color]}m{text}\033[0m" if USE_COLOR else text


def format_size(num_bytes: float) -> str:
    """14952512 -> '14.3 MB'"""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """75 -> '1m 15s'"""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"


def short_path(path: str) -> str:
    """/home/user/Documents -> ~/Documents"""
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def format_action(action: str, path: str, note: str = "") -> str:
    """One coloured line per path: '✓ Modified   ~/Projects  (note)'"""
    symbol, color = ACTION_STYLES.get(action, ("·", "dim"))
    line = f"{paint(symbol, color)} {paint(action.capitalize().ljust(10), color)} {short_path(path)}"
    return f"{line}  {paint(f'({note})', 'dim')}" if note else line


def count_part(count: int, label: str) -> str:
    """'1,204 unchanged', or '' when the count is zero (hidden in summaries)"""
    return f"{count:,} {label}" if count else ""


def format_summary(title: str, parts: list, seconds: float, ok: bool = True) -> str:
    """Last line of a command: '✓ Backup done · 3 copied (1.2 GB) · 1,204 unchanged · 12s'"""
    symbol = paint("✓", "green") if ok else paint("✗", "red")
    details = " · ".join([part for part in parts if part] + [format_duration(seconds)])
    return f"{symbol} {title} {paint('· ' + details, 'dim')}"


def format_header() -> str:
    """'octoback · track, back up, get it back' in the logo colours"""
    return f"{paint('octoback', 'teal')} {paint('· track, back up, get it back', 'purple')}"


class SymbolFormatter(logging.Formatter):
    """Info lines print as they are; warnings and errors get a coloured symbol."""
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            message = f"{paint('✗', 'red')} {message}"
        elif record.levelno >= logging.WARNING:
            message = f"{paint('⚠', 'yellow')} {message}"
        # In a terminal, clear the progress bar line first so messages don't get glued to it
        return ("\r\033[K" if sys.stderr.isatty() else "") + message


def setup_logging() -> None:
    """Sends all messages through SymbolFormatter (debug messages stay hidden)."""
    handler = logging.StreamHandler()
    handler.setFormatter(SymbolFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
