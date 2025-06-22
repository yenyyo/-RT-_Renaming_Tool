# Document Renaming Tool

A Python utility to bulk-rename your **TV Series files** into a clean, consistent format:

- **Season folders** → `Series_name S0x`
- **Episode files**   → `Series_name S0xE0y.ext`

---

## 📋 Overview

1. **Mount** the remote series directory via SSHFS to a local path.
2. **Scan** the mounted folder for season directories (e.g. `SEASON.01`, `S01`, etc.) and episode files.
3. **Plan** a series of rename operations (folders first in preview, then files, then folders).
4. **Preview** the planned changes and ask for your confirmation.
5. **Execute** the renames in a depth-aware order (files before their parent folders).
6. **Rollback** option to undo all changes in one step, if needed.

---

## ⚙️ Requirements

- **Python 3.7+**
- **sshfs** (to mount the remote share locally)
- **SSH key or password** configured for the remote server
- **Python standard library**: `os`, `re`, `pathlib`, `logging`
- **Additional dependency**: `python-dotenv` (install with `pip install python-dotenv`)

---

## 🔧 Setup & Usage

1. **Create a config file** named `.env` in the project root (add `.env` to `.gitignore`):
   ```ini
   REMOTE_USER=your.user
   REMOTE_HOST=your.remote.host
   REMOTE_PORT=31422
   REMOTE_SERIES_PATH=/path/to/series/folder
   MOUNT_POINT=/home/your.user/mnt/series
   AUTO_RUN=False
   ```

2. **Mount** the remote directory:
   ```bash
   mkdir -p "$MOUNT_POINT"
   sshfs -p "$REMOTE_PORT" "$REMOTE_USER"@"$REMOTE_HOST":"$REMOTE_SERIES_PATH" "$MOUNT_POINT"
   ```

3. **Install dependencies**:
   ```bash
   pip install python-dotenv
   ```

4. **Run** the script:
   ```bash
   python rename_tool.py
   ```

5. **Review** the preview of planned renames. Type `y` to apply, or any other key to abort.

6. **(Optional)** After renaming completes, you’ll be prompted for a rollback. Type `y` to revert all changes.

---

## 🔄 Dry-Run & Auto-Run

- **Dry-Run** (default): previews changes and waits for confirmation.
- **Auto-Run**: set `AUTO_RUN=True` in your `.env` or environment to skip confirmations and immediately apply (then still prompts for rollback).

---

## 🛠️ Troubleshooting

- **FileNotFoundError**: Ensure the remote path is correctly mounted under `MOUNT_POINT` and that the directory names match.
- **Permissions**: Verify SSHFS mount permissions allow renaming (read/write).
- **Unknown folders**: If season directories aren’t detected, adjust the regex patterns in `gather_operations()` to match your naming scheme.

---

