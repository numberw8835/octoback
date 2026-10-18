# Octoback TODO

## Automation & Daemon

- [ ] **Systemd user service and timer for periodic tracking (`octoback update --all`)**
  - Provide systemd user unit files (`octoback-update.service` and `octoback-update.timer`) so users can enable background tracking with `systemctl --user enable --now octoback-update.timer`.
  - Runs `octoback update --all` on a configurable interval (e.g., every 30m or 1h) to keep index hashes and lifecycle states up to date.
  - Can be installed automatically via `install.sh` or an `octoback daemon install` command.

## Known limits (not bugs)

- A file inside a folder tracked file by file can't be untracked on its own: the next `update` finds it again. Untrack the whole folder, or track it with `add -w`. (An ignore list would fix this.)
- A folder that was added before tracked folders existed (old `add -g`) isn't remembered. Run `octoback add <folder>` once more to register it.
- A renamed file is only detected as "moved" if it stays inside the same folder tree. Otherwise the old path is "deleted" and the new one must be `add`ed.
- A renamed folder is never detected as moved, only as deleted.
- If you track `~` itself, its hash includes `~/Vault` and `~/.octoback`, so `update` / `check` always report it as modified.
- Backups are never deleted automatically: a file deleted from a tracked folder stays in the Vault and comes back on restore. This is on purpose, so an accidental delete can't wipe the only copy. Removing things from the Vault is always a deliberate step (`vault clean`, `clear vault`).
- Symlinks are not backed up. Inside tracked folders they are skipped and counted in the backup summary ("N symlinks skipped"). Adding a path that is itself a symlink prints a warning: Octoback backs up what it points to, so a restore writes a regular file where the link was.
