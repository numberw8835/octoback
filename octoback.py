import argparse
import logging
import os
import sys
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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
    p_add.add_argument("-g", "--granular", action="store_true", help="Add directory contents individually")

    # update
    p_update = subparsers.add_parser("update", help="Update tracked paths in index (check modified/moved/copied)")
    p_update.add_argument("paths", nargs="*", default=[], help="Specific paths to update")
    p_update.add_argument("--all", dest="all_flag", action="store_true", help="Update all indexed items")
    p_update.add_argument("-g", "--granular", action="store_true", help="Update directory contents individually")

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

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore items from the vault")
    p_restore.add_argument("paths", nargs="*", default=[], help="Specific paths to restore")
    p_restore.add_argument("--all", dest="all_flag", action="store_true", help="Restore all indexed items")

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


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    engine = Engine()

    if args.command == "init":
        engine.init()
        print("Octoback initialized successfully.")
        return

    # Stop if the index is missing or could not be loaded
    if not engine._loaded:
        if os.path.exists(engine.index_path):
            print(f"Error: The index file is corrupted: {engine.index_path}")
            print("Fix it by hand, or delete it and run `octoback init` (this resets tracking).")
        else:
            print("Error: Octoback has not been initialized yet.")
            print("Please run `octoback init` first.")
        sys.exit(1)

    # Normalize input paths to absolute paths directly at the CLI level
    if hasattr(args, "paths") and args.paths:
        args.paths = [os.path.abspath(p) for p in args.paths]
    if hasattr(args, "path") and args.path:
        args.path = os.path.abspath(args.path)

    # Check if Vault is currently compressed
    compressed_vault = f"{engine.vault_path}.tar.xz"
    if args.command in ("backup", "restore", "vault") and os.path.exists(compressed_vault):
        print("Error: The Vault is currently compressed (Vault.tar.xz).")
        print(f"Please run `octoback unzip` first before running {args.command}.")
        sys.exit(1)

    if args.command == "add":
        add(engine, args.paths, granular=args.granular)
    elif args.command == "update":
        update(engine, args.paths, all_flag=args.all_flag, granular=args.granular)
    elif args.command == "remove":
        remove(engine, args.paths)
    elif args.command == "check":
        check(engine, args.paths)
    elif args.command == "backup":
        backup(engine, args.paths, all_flag=args.all_flag)
    elif args.command == "restore":
        restore(engine, args.paths, all_flag=args.all_flag)
    elif args.command == "prune":
        prune(engine)
    elif args.command == "show":
        if args.target == "history":
            show_history(engine, limit=args.limit)
        else:
            show(engine)
    elif args.command == "zip":
        zip_vault(engine)
    elif args.command == "unzip":
        unzip_vault(engine)
    elif args.command == "vault":
        if args.vault_action == "clean":
            clean_vault(engine, yes_flag=args.yes)
        else:
            parser.parse_args(["vault", "--help"])
    elif args.command == "clear":
        if args.clear_target == "index":
            clear_index(engine, yes_flag=args.yes)
        elif args.clear_target == "vault":
            clear_vault(engine, yes_flag=args.yes)
        else:
            parser.parse_args(["clear", "--help"])


if __name__ == "__main__":
    main()
