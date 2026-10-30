import logging
import os
import time
from collections import Counter
from typing import List
from ..engine import Engine
from ..utils import (
    EMPTY_HASH,
    DualProgressBar,
    count_part,
    format_action,
    format_summary,
    get_dir_hash_optimized,
    get_file_hash_optimized,
    get_quick_signature,
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
        if target in engine.roots or (os.path.isdir(target) and engine.index.get(target, {}).get("type") != "dir"):
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
        else:
            # Missing individual target: check if it moved nearby
            if target in engine.index:
                scope_index_paths.add(target)
            candidate = find_moved_file(engine, target)
            if candidate:
                disk_files.append(candidate)

    # Deduplicate disk_files while preserving order
    seen = set()
    disk_files = [f for f in disk_files if not (f in seen or seen.add(f))]

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

    # Step 2: Separate missing paths from unplugged drive paths
    active_missing = []
    for path in scope_index_paths:
        if not os.path.exists(path):
            if engine.is_on_unplugged_drive(path):
                logger.info(format_action("skipped", path, "drive not plugged in"))
                results["skipped"] += 1
            else:
                active_missing.append(path)

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

        # Check if path is already in index
        if path in engine.index:
            if engine.index[path].get("hash") == current_hash:
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
    for new_path, new_hash, signature, path_type in appeared:
        matched_old = None
        if new_hash != EMPTY_HASH:
            candidates = [
                old_p for old_p in active_missing
                if engine.index[old_p].get("hash") == new_hash and engine.index[old_p].get("type") == path_type
            ]
            if candidates:
                # Pick the single closest candidate by path proximity and filename
                matched_old = max(
                    candidates,
                    key=lambda old: (
                        len(os.path.commonpath([new_path, old])),
                        os.path.basename(new_path) == os.path.basename(old),
                        old,
                    ),
                )

        if matched_old:
            active_missing.remove(matched_old)
            del engine.index[matched_old]
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            engine._record_history("moved", new_path, matched_old)
            logger.info(format_action("moved", new_path, f"from {short_path(matched_old)}"))
            results["moved"] += 1
        elif new_hash != EMPTY_HASH and any(
            p != new_path and engine.index[p].get("type") == path_type and os.path.exists(p)
            for p in engine.paths_with_hash(new_hash)
        ):
            copied_matches = [
                p for p in engine.paths_with_hash(new_hash)
                if p != new_path and engine.index[p].get("type") == path_type and os.path.exists(p)
            ]
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            origin = copied_matches[0]
            engine._record_history("copied", new_path, origin)
            logger.info(format_action("copied", new_path, f"copy of {short_path(origin)}"))
            results["copied"] += 1
        else:
            engine.add_path_to_index(new_path, path_hash=new_hash, signature=signature)
            engine._record_history("new", new_path)
            logger.info(format_action("new", new_path))
            results["new"] += 1

    # Step 5: Leftover missing files are confirmed deleted
    for old_path in active_missing:
        del engine.index[old_path]
        engine._record_history("deleted", old_path)
        logger.info(format_action("deleted", old_path))
        results["deleted"] += 1

    tracker.finish()
    ok = engine.save_index() and not results["failed"]
    parts = [count_part(results[action], action) for action in
             ("new", "modified", "moved", "copied", "deleted", "unchanged", "skipped", "failed")]
    print(format_summary("Update done", parts, time.monotonic() - start_time, ok))
    return ok
