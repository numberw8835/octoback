<p align="center">
  <img src="assets/logo_clean.png" alt="Octoback logo" width="160">
</p>

<h1 align="center">Octoback</h1>

<p align="center">
  <b>Track your files. Back them up. Get them back.</b><br>
  A small, local backup tool for the command line.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-7b5cff?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-linux-2ee6c5?style=flat-square" alt="Linux">
</p>

---

## Why Octoback

- **Hash-based tracking.** Every file and folder is fingerprinted with BLAKE3, so Octoback knows exactly what changed.
- **Fast on repeat runs.** Files whose size and modification time haven't changed are skipped without being read.
- **Knows what happened.** It can tell whether a file was *modified*, *moved*, *copied*, *deleted* or is *new*, and keeps a history of it.
- **Plain-folder Vault.** Backups are ordinary files that mirror your real paths. No proprietary format, nothing to unlock.
- **Only copies what changed.** Identical files are skipped, and new ones are written atomically so a failed copy never leaves half a file.
- **Keeps permissions.** Restored files come back with their original mode and timestamps.
- **Compress when idle.** Pack the whole Vault into a single `.tar.xz` and unpack it when you need it.

## Install

Requires Python 3.10+ and `gcc`. The installer compiles Octoback into a single executable with [Nuitka](https://nuitka.net) and puts it in `~/.local/bin`:

```bash
git clone https://github.com/numberw8835/octoback.git
cd octoback
./install.sh
octoback init
```

Build tools are installed into `build/venv`, so your system Python is left untouched. To install somewhere else, set `INSTALL_DIR`, e.g. `INSTALL_DIR=/usr/local/bin ./install.sh`. To update, pull and run `./install.sh` again.

<details>
<summary>Run from source instead</summary>

```bash
pip install pyyaml blake3
python3 octoback.py init
```
</details>

## Quick start

```bash
octoback init                      # create config, index and ~/Vault
octoback add ~/Documents ~/.zshrc  # start tracking
octoback backup --all              # copy everything into the Vault
octoback update --all              # later: detect what changed
octoback restore ~/.zshrc          # bring a file back from the Vault
```

## Commands

| Command | What it does |
|---|---|
| `init` | Create the config, the index and the Vault |
| `add <paths> [-g]` | Start tracking paths (`-g` tracks each file in a folder on its own) |
| `update [<paths>] [--all] [-g]` | Detect modified / moved / copied / deleted / new files |
| `remove <paths>` | Stop tracking paths (the Vault is not touched) |
| `check <paths>` | Verify paths still match their tracked hash (always reads the full contents) |
| `backup [<paths>] [--all]` | Copy items into the Vault |
| `restore [<paths>] [--all]` | Copy items back from the Vault |
| `prune` | Drop paths that no longer exist from the index |
| `show` | List tracked paths |
| `show history [-n N]` | Show the last N lifecycle events (`0` for all) |
| `zip` / `unzip` | Compress / decompress the Vault in place |
| `vault clean [-y]` | Remove backups of untracked files and old locations of moved files |
| `clear index [-y]` | Forget every tracked path (the Vault is not touched) |
| `clear vault [-y]` | Delete every backup (the index and your files are not touched) |

## How it works

The **Vault** mirrors the full path of everything you back up:

```
/home/you/Documents/report.pdf  ->  ~/Vault/home/you/Documents/report.pdf
```

The **index** stores a BLAKE3 hash, type and size for each tracked path, plus a quick signature built from sizes and modification times. When the signature hasn't changed, `update` and `backup` skip the path without reading it, which makes repeat runs on large folders nearly instant.

The **history** records every lifecycle event:

```
[2026-10-16 21:07:21] [MOVED    ] ~/docs/a.txt -> ~/docs/a2.txt
[2026-10-16 21:07:22] [UNTRACKED] ~/proj
[2026-10-16 21:07:23] [DELETED  ] ~/thesis
```

`vault clean` uses this history carefully. It only removes backups of paths you **untracked** yourself, and old copies of **moved** files once the new location is backed up. Backups of **deleted** files are always kept, since the Vault may hold the only copy.

## Configuration

Everything lives in `~/.octoback/`:

```yaml
# ~/.octoback/octoback-config.yaml
storage:
  vault_path: ~/Vault
  index_path: ~/.octoback/octoback-index.json
  history_path: ~/.octoback/octoback-history.jsonl
```

Point `vault_path` at an external drive to keep your backups off your main disk.

## Project layout

```
octoback.py            CLI entry point
modules/
  engine.py            index, history and change detection
  config.py            config loading
  commands/            one file per command
  utils/               hashing, copying, progress bar
```

See [TODO.md](TODO.md) for planned improvements.
