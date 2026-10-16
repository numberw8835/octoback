import argparse
import logging
import os
import sys
from modules.engine import Engine
from modules.utils.add import add
from modules.utils.backup import backup
from modules.utils.check import check
from modules.utils.prune import prune
from modules.utils.remove import remove
from modules.utils.restore import restore
from modules.utils.show import show
from modules.utils.unzip import unzip_vault
from modules.utils.update import update
from modules.utils.zip import zip_vault

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
    subparsers.add_parser("show", help="List all tracked paths in the index")

    # zip (compress Vault in-place)
    subparsers.add_parser("zip", help="Compress the Vault directory in-place")

    # unzip (decompress Vault in-place)
    subparsers.add_parser("unzip", help="Decompress the Vault archive in-place")

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

    # Check if Octoback has been initialized
    if not engine._loaded and not os.path.exists(engine.index_path):
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
    if args.command in ("backup", "restore") and os.path.exists(compressed_vault):
        print("Error: The Vault is currently compressed (Vault.tar.xz).")
        print("Please run `octoback unzip` first before running backup or restore.")
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
        show(engine)
    elif args.command == "zip":
        zip_vault(engine)
    elif args.command == "unzip":
        unzip_vault(engine)


if __name__ == "__main__":
    main()
