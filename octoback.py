import argparse
import fcntl
import os
import sys
import time
from modules.config import CONFIG_DIR
from modules.engine import Engine
from modules.commands.add import add
from modules.commands.backup import backup
from modules.commands.check import check
from modules.commands.clear import clear_index, clear_vault
from modules.commands.prune import prune
from modules.commands.remove import remove
from modules.commands.restore import restore
from modules.commands.show import show, show_history
from modules.commands.unzip import unzip_vault
from modules.commands.update import update
from modules.commands.vault import clean_vault
from modules.commands.zip import zip_vault
from modules.utils.style import format_header, paint, setup_logging, short_path

setup_logging()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="octoback",
        description="Octoback - High-performance local file backup and tracking tool.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize Octoback storage and configuration")

    # add
    p_add = subparsers.add_parser("add", help="Add files or directories to tracking index")
    p_add.add_argument("paths", nargs="+", help="Paths to add")
    p_add.add_argument("-w", "--whole", action="store_true", help="Track a folder as one unit")

    # update
    p_update = subparsers.add_parser("update", help="Update tracked paths in index (check modified/moved/copied)")
    p_update.add_argument("paths", nargs="*", default=[], help="Specific paths to update")
    p_update.add_argument("--all", dest="all_flag", action="store_true", help="Update all indexed items")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove paths from tracking index")
    p_remove.add_argument("paths", nargs="+", help="Paths to remove")

    # check
    p_check = subparsers.add_parser("check", help="Verify if paths match their indexed hash")
    p_check.add_argument("paths", nargs="+", help="Paths to check")

    # backup
    p_backup = subparsers.add_parser("backup", help="Backup tracked items to the vault")
    p_backup.add_argument("paths", nargs="*", default=[], help="Specific paths to backup")
    p_backup.add_argument("--all", dest="all_flag", action="store_true", help="Backup all indexed items")
    p_backup.add_argument("-u", "--update", dest="update_first", action="store_true", help="Update the index first")

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore items from the vault")
    p_restore.add_argument("paths", nargs="*", default=[], help="Specific paths to restore")
    p_restore.add_argument("--all", dest="all_flag", action="store_true", help="Restore all indexed items")
    p_restore.add_argument("-y", "--yes", action="store_true", help="Overwrite existing files without asking")

    # prune
    subparsers.add_parser("prune", help="Remove non-existent paths from the index")

    # show
    p_show = subparsers.add_parser("show", help="Display tracked paths or change history")
    p_show.add_argument("target", nargs="?", choices=["history"], help="Optional target: 'history' to display change history")
    p_show.add_argument("-n", "--limit", type=int, default=20, help="Number of history events to display (default: 20, 0 for all)")

    # zip (compress Vault in-place)
    subparsers.add_parser("zip", help="Compress the Vault directory in-place")

    # unzip (decompress Vault in-place)
    subparsers.add_parser("unzip", help="Decompress the Vault archive in-place")

    # vault
    p_vault = subparsers.add_parser("vault", help="Vault maintenance and cleanup commands")
    vault_subparsers = p_vault.add_subparsers(dest="vault_action", help="Vault action")
    p_vclean = vault_subparsers.add_parser("clean", help="Remove ghost files from the Vault using history")
    p_vclean.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # clear
    p_clear = subparsers.add_parser("clear", help="Clear tracking data or Vault backups")
    clear_subparsers = p_clear.add_subparsers(dest="clear_target", help="Clear target")
    p_cindex = clear_subparsers.add_parser("index", help="Clear all tracked items from the index (Vault is NOT touched)")
    p_cindex.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_cvault = clear_subparsers.add_parser("vault", help="Clear all backup files in the Vault (Index and PC files NOT touched)")
    p_cvault.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    return parser


def is_vault_available(vault_path: str) -> bool:
    """True if the Vault folder (or its compressed archive) is there."""
    return os.path.isdir(vault_path) or os.path.exists(f"{vault_path}.tar.xz")


def wait_for_vault(vault_path: str) -> None:
    """Waits until the Vault shows up, e.g. when it lives on a drive that isn't plugged in yet."""
    if is_vault_available(vault_path):
        return
    print(f"{paint('⚠', 'yellow')} Waiting for the Vault at {short_path(vault_path)} ...")
    print(paint("  Plug in the drive (or run `octoback init` to create it). Press Ctrl+C to cancel.", "dim"))
    try:
        while not is_vault_available(vault_path):
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{paint('✗', 'red')} Cancelled.")
        sys.exit(1)
    print(f"{paint('✓', 'green')} Vault found, continuing.")


def wait_for_index_lock():
    """
    Locks ~/.octoback/octoback.lock until this command ends, waiting if another command holds it,
    so two commands never overwrite each other's index changes. Linux frees the lock on exit or crash.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lock_file = open(os.path.join(CONFIG_DIR, "octoback.lock"), "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"{paint('⚠', 'yellow')} Waiting for another octoback command to finish ...")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        except KeyboardInterrupt:
            print(f"\n{paint('✗', 'red')} Cancelled.")
            sys.exit(1)
    return lock_file  # Keep it open: closing the file would release the lock


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        print(format_header() + "\n")
        parser.print_help()
        sys.exit(0)

    # Commands that change the index wait for any other one to finish, before loading the index
    if args.command in ("add", "update", "remove", "prune") or getattr(args, "clear_target", None) == "index":
        index_lock = wait_for_index_lock()

    engine = Engine()

    if args.command == "init":
        engine.init()
        print(format_header())
        print(f"{paint('✓', 'green')} Initialized")
        print(paint(f"  Vault: {short_path(engine.vault_path)}", "dim"))
        print(paint(f"  Index: {short_path(engine.index_path)}", "dim"))
        return

    # Stop if the index is missing or could not be loaded
    if not engine._loaded:
        if os.path.exists(engine.index_path):
            print(f"{paint('✗', 'red')} The index file is corrupted: {short_path(engine.index_path)}")
            print(paint("  Fix it by hand, or delete it and run `octoback init` (this resets tracking).", "dim"))
        else:
            print(f"{paint('✗', 'red')} Octoback has not been initialized yet.")
            print(paint("  Run `octoback init` first.", "dim"))
        sys.exit(1)

    # Normalize input paths to absolute paths directly at the CLI level
    if hasattr(args, "paths") and args.paths:
        args.paths = [os.path.abspath(p) for p in args.paths]
    if hasattr(args, "path") and args.path:
        args.path = os.path.abspath(args.path)

    # Commands that touch the Vault wait for it (e.g. an external drive that isn't mounted yet)
    if args.command in ("backup", "restore", "zip", "unzip", "vault") or getattr(args, "clear_target", None) == "vault":
        wait_for_vault(engine.vault_path)

    # Check if Vault is currently compressed
    compressed_vault = f"{engine.vault_path}.tar.xz"
    if args.command in ("backup", "restore", "vault") and os.path.exists(compressed_vault):
        print(f"{paint('✗', 'red')} The Vault is currently compressed (Vault.tar.xz).")
        print(paint(f"  Run `octoback unzip` first before running {args.command}.", "dim"))
        sys.exit(1)

    # Every command returns False when something failed, so scripts and cron can tell (exit code 1)
    ok = True
    if args.command == "add":
        ok = add(engine, args.paths, whole=args.whole)
    elif args.command == "update":
        ok = update(engine, args.paths, all_flag=args.all_flag)
    elif args.command == "remove":
        ok = remove(engine, args.paths)
    elif args.command == "check":
        ok = check(engine, args.paths)
    elif args.command == "backup":
        ok = backup(engine, args.paths, all_flag=args.all_flag, update_first=args.update_first)
    elif args.command == "restore":
        ok = restore(engine, args.paths, all_flag=args.all_flag, yes_flag=args.yes)
    elif args.command == "prune":
        ok = prune(engine)
    elif args.command == "show":
        if args.target == "history":
            show_history(engine, limit=args.limit)
        else:
            show(engine)
    elif args.command == "zip":
        ok = zip_vault(engine)
    elif args.command == "unzip":
        ok = unzip_vault(engine)
    elif args.command == "vault":
        if args.vault_action == "clean":
            ok = clean_vault(engine, yes_flag=args.yes)
        else:
            parser.parse_args(["vault", "--help"])
    elif args.command == "clear":
        if args.clear_target == "index":
            ok = clear_index(engine, yes_flag=args.yes)
        elif args.clear_target == "vault":
            ok = clear_vault(engine, yes_flag=args.yes)
        else:
            parser.parse_args(["clear", "--help"])

    if ok is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
