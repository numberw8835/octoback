# Octoback TODO

## Correctness

- [ ] **C. Symlinks are silently left out**
  - Example: dotfiles managed by GNU Stow are links -> never backed up. Restoring a tracked symlink writes a regular file over it.
  - Fix: back up the link itself (`os.readlink` / `os.symlink`), or at least print a warning when one is skipped.
  - Where: `copy_dir_to` / `copy_file_to` in `modules/utils/utils.py`

## Scripting / cron

- [ ] **G. Two commands at once lose index changes**
  - Example: cron `update --all` while you run `add` -> last save wins, the other's changes are lost (they also share `index.tmp`).
  - Fix: a simple lock file around load/save. Only needed if Octoback runs from cron.
  - Where: `modules/engine.py`

## Known limits (not bugs)

- A renamed file is only detected as "moved" if it stays inside the same folder tree. Otherwise the old path is "deleted" and the new one must be `add`ed.
- A renamed folder is never detected as moved, only as deleted.
- If you track `~` itself, its hash includes `~/Vault` and `~/.octoback`, so `update` / `check` always report it as modified.
- Backups are never deleted automatically: a file deleted from a tracked folder stays in the Vault and comes back on restore. This is on purpose, so an accidental delete can't wipe the only copy. Removing things from the Vault is always a deliberate step (`vault clean`, `clear vault`).
