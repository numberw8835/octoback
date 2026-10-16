# Octoback TODO

## Data safety (do first)

- [ ] **A. `restore` silently overwrites newer files**
  - Example: backup Monday, edit `report.docx` all week, `restore --all` on Friday -> Monday's version is back, no warning.
  - Fix: list files that would be overwritten and ask for confirmation, `-y` to skip (same as `clear` / `vault clean`).
  - Where: `modules/commands/restore.py`

- [ ] **B. Deleted files come back when a folder is restored**
  - Example: track `~/proj`, back up, delete `~/proj/secret.txt`, back up again -> `secret.txt` is still in the Vault and reappears on restore.
  - Fix: after copying a tracked folder, delete files in its Vault copy that no longer exist in the source (Vault = exact mirror).
  - Where: `copy_dir_to` in `modules/utils/utils.py` (or a backup-only step in `modules/commands/backup.py`)

- [ ] **E. No `fsync`, a power cut can lose a backup that reported success**
  - Fix: `f.flush()` + `os.fsync(f.fileno())` before `os.replace(...)`.
  - Where: `copy_file_to` in `modules/utils/utils.py`, `save_index` in `modules/engine.py`

## Correctness

- [ ] **C. Symlinks are silently left out**
  - Example: dotfiles managed by GNU Stow are links -> never backed up. Restoring a tracked symlink writes a regular file over it.
  - Fix: back up the link itself (`os.readlink` / `os.symlink`), or at least print a warning when one is skipped.
  - Where: `copy_dir_to` / `copy_file_to` in `modules/utils/utils.py`

- [ ] **D. Unplugged drive looks like deleted files**
  - Example: files tracked on `/mnt/usb`, drive not mounted, `update --all` or `prune` -> all recorded as "deleted" and dropped from the index.
  - Fix: if the path's parent folder is also missing, warn and skip instead of marking it deleted.
  - Where: `update_path_in_index` in `modules/engine.py`, `modules/commands/prune.py`

## Scripting / cron

- [ ] **F. Exit code is always 0**
  - `check` returns True/False and backup/restore know what failed, but `main()` ignores it -> scripts and cron can't detect failures.
  - Fix: `sys.exit(1)` when something failed.
  - Where: `octoback.py`, plus return values from `backup` / `restore`

- [ ] **G. Two commands at once lose index changes**
  - Example: cron `update --all` while you run `add` -> last save wins, the other's changes are lost (they also share `index.tmp`).
  - Fix: a simple lock file around load/save. Only needed if Octoback runs from cron.
  - Where: `modules/engine.py`

## Known limits (not bugs)

- A renamed file is only detected as "moved" if it stays inside the same folder tree. Otherwise the old path is "deleted" and the new one must be `add`ed.
- A renamed folder is never detected as moved, only as deleted.
- If you track `~` itself, its hash includes `~/Vault` and `~/.octoback`, so `update` / `check` always report it as modified.
