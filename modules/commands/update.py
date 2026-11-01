import logging
import os
import time
from collections import Counter
from typing import List
from ..engine import Engine
from ..utils import (
    EMPTY_HASH,
    DualProgressBar,
    ancestors,
    count_part,
    format_action,
    format_summary,
    get_dir_hash_optimized,
    get_file_hash_optimized,
    get_quick_signature,
    is_gone,
    is_inside,
    short_path,
)
from ..utils.utils import get_mount_point

logger = logging.getLogger("octoback.update")


def find_moved_file(engine: Engine, missing_path: str) -> str | None:
    """Looks next to a missing tracked file for an untracked file with the same content."""
    entry = engine.index.get(missing_path)
    if not entry or entry.get("type") != "file":
        return None

    for root, _, files in os.walk(os.path.dirname(missing_path)):
        for name in files:
            candidate = os.path.join(root, name)
            # Compare sizes first so only real candidates get hashed
            if (candidate not in engine.index
                    and os.path.isfile(candidate)
                    and os.path.getsize(candidate) == entry.get("size")
                    and get_file_hash_optimized(candidate) == entry.get("hash")):
                return candidate
    return None


def find_copy_origin(engine: Engine, path: str, path_hash: str, path_type: str) -> str | None:
    """A tracked path with the same content that still exists, if any."""
    for p in engine.paths_with_hash(path_hash):
        if p != path and engine.index[p].get("type") == path_type and os.path.exists(p):
            return p
    return None


def update(engine: Engine, input_list: List[str] | None = None, all_flag: bool = False) -> bool:
    """Updates paths in index using two-phase reconciliation (checks modified, moved, copied, deleted)."""
    # Tracked folders are walked, so new files in them are found
    targets = engine.roots + [p for p in engine.index if not engine.root_of(p)] if all_flag else (input_list or [])
    if not targets:
        logger.warning("No paths provided to update.")
        return False

    start_time = time.monotonic()

    # Step 1: Collect all disk files and index paths within the scope of update targets
    disk_files = []
    scope_index_paths = set()

    for target in targets:
        target = os.path.abspath(target)
        root = engine.root_of(target)
        # Folders are walked file by file, except folders added as one unit (-w, also when empty)
        added_whole = engine.is_whole(target) or (not root and engine.index.get(target, {}).get("type") == "dir")
        if target in engine.roots or (os.path.isdir(target) and not added_whole):
            if os.path.isdir(target):
                for p in engine.walk_folder(target):
                    disk_files.append(p)
            prefix = target if target.endswith(os.sep) else target + os.sep
            for k in engine.index:
                if k.startswith(prefix) or k == target:
                    scope_index_paths.add(k)
        elif os.path.exists(target):
            disk_files.append(target)
            if target in engine.index:
                scope_index_paths.add(target)
        elif root and target not in engine.index and os.path.isdir(root):
            # A missing subfolder of a tracked folder may have been renamed: check the whole tracked folder
            disk_files.extend(engine.walk_folder(root))
            scope_index_paths.update(k for k in engine.index if is_inside(k, root))
        else:
            # Missing target: it, or what was tracked inside it, may have moved nearby
            scope_index_paths.update(k for k in engine.index if is_inside(k, target))
            candidate = find_moved_file(engine, target)
            if candidate:
                disk_files.append(candidate)

    # Deduplicate disk_files while preserving order
    on_disk = set()
    disk_files = [f for f in disk_files if not (f in on_disk or on_disk.add(f))]

    # Calculate total bytes of existing targets for progress bar
    total_bytes = 0
    for p in disk_files:
        try:
            if os.path.isfile(p):
                total_bytes += os.path.getsize(p)
        except OSError:
            pass

    tracker = DualProgressBar(total_bytes=total_bytes)
    results = Counter()

    # Step 2: Take missing paths out of the index until they are matched (moved) or confirmed deleted
    active_missing = {}  # path -> its old index entry
    for path in scope_index_paths:
        entry = engine.index[path]
        if not os.path.exists(path):
            if engine.is_on_unplugged_drive(path):
                logger.info(format_action("skipped", path, "drive not plugged in"))
                results["skipped"] += 1
            elif not is_gone(path):
                logger.info(format_action("skipped", path, "can't be read"))  # e.g. inside a folder without permission
                results["skipped"] += 1
            else:
                active_missing[path] = engine.index.pop(path)
        elif entry.get("type") == "file" and os.path.isdir(path):
            # A file replaced by a folder: the file is gone (or moved), and the folder's contents are new
            active_missing[path] = engine.index.pop(path)
            if not engine.root_of(path):
                engine.add_root(path)  # It was tracked on its own: keep tracking the folder
        elif entry.get("type") == "dir" and entry.get("hash") == EMPTY_HASH and engine.root_of(path):
            # An empty folder: walk_folder lists it only while it is empty. Once it has files, those are tracked.
            if path not in on_disk:
                del engine.index[path]

    # Step 3: Check disk files (unchanged, modified, or appeared candidates)
    appeared = []  # (path, hash, signature, path_type)

    for path in disk_files:
        is_dir = os.path.isdir(path)
        path_type = "dir" if is_dir else "file"

        # Update mount point
        if path in engine.index:
            engine.index[path]["mount"] = get_mount_point(path)

        # Fast path: same sizes and modification times as last time
        signature = get_quick_signature(path)
        if signature and path in engine.index and engine.index[path].get("signature") == signature:
            if tracker:
                tracker.skip_file(os.path.basename(path), engine.index[path].get("size", 0))
            logger.debug(format_action("unchanged", path))
            results["unchanged"] += 1
            continue

        if is_dir:
            current_hash = get_dir_hash_optimized(path, tracker=tracker)
        else:
            current_hash = get_file_hash_optimized(path, tracker=tracker)

        if not current_hash:
            results["failed"] += 1
            continue

        # Check if path is already in index (compare the type too: an empty folder and an empty file share a hash)
        if path in engine.index:
            if engine.index[path].get("hash") == current_hash and engine.index[path].get("type") == path_type:
                engine.index[path]["signature"] = signature
                logger.debug(format_action("unchanged", path))
                results["unchanged"] += 1
            else:
                engine.add_path_to_index(path, path_hash=current_hash, signature=signature)
                engine._record_history("modified", path)
                logger.info(format_action("modified", path))
                results["modified"] += 1
        else:
            appeared.append((path, current_hash, signature, path_type))

    # Step 4: Reconcile appeared files with missing files 1-to-1 (exact rename detection)
    # Missing paths by content and folder, so the closest one is found by walking up from the new path
    by_folder = {}  # (hash, type, folder) -> missing paths inside that folder
    by_name = {}    # (hash, type, file name) -> missing paths with that name
    for old_p, entry in active_missing.items():
        old_hash, old_type = entry.get("hash"), entry.get("type")
        for folder in [old_p, *ancestors(old_p)]:
            by_folder.setdefault((old_hash, old_type, folder), set()).add(old_p)
        by_name.setdefault((old_hash, old_type, os.path.basename(old_p)), set()).add(old_p)

    for new_path, new_hash, signature, path_type in appeared:
        # Pick the single closest candidate: deepest shared folder, then same file name, then by path
        matched_old = None
        if new_hash != EMPTY_HASH:
            for folder in [new_path, *ancestors(new_path)]:
                near = by_folder.get((new_hash, path_type, folder))
                if near:
                    same_name = near & by_name.get((new_hash, path_type, os.path.basename(new_path)), set())
                    matched_old = max(same_name or near)
                    break

        copied_from = None
        if not matched_old and new_hash != EMPTY_HASH:
            copied_from = find_copy_origin(engine, new_path, new_hash, path_type)

        if matched_old:
            del active_missing[matched_old]
            for folder in [matched_old, *ancestors(matched_old)]:
                by_folder[(new_hash, path_type, folder)].discard(matched_old)
            by_name[(new_hash, path_type, os.path.basename(matched_old))].discard(matched_old)
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            engine._record_history("moved", new_path, matched_old)
            logger.info(format_action("moved", new_path, f"from {short_path(matched_old)}"))
            results["moved"] += 1
        elif copied_from:
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            engine._record_history("copied", new_path, copied_from)
            logger.info(format_action("copied", new_path, f"copy of {short_path(copied_from)}"))
            results["copied"] += 1
        else:
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            engine._record_history("new", new_path)
            logger.info(format_action("new", new_path))
            results["new"] += 1

    # Step 5: Leftover missing files are confirmed deleted
    for old_path in sorted(active_missing):
        note = "replaced by a folder" if os.path.isdir(old_path) else ""
        engine._record_history("deleted", old_path)
        logger.info(format_action("deleted", old_path, note))
        results["deleted"] += 1

    tracker.finish()
    ok = engine.save_index() and not results["failed"]
    parts = [count_part(results[action], action) for action in
             ("new", "modified", "moved", "copied", "deleted", "unchanged", "skipped", "failed")]
    print(format_summary("Update done", parts, time.monotonic() - start_time, ok))
    return ok
