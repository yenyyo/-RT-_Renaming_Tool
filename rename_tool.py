import os, re, stat, logging
from pathlib import Path
from dotenv import load_dotenv
import signal

# ─────────────────────────────────────────────
# PREPARATION: SSHFS MOUNT VARIABLES
# ─────────────────────────────────────────────

# Reads .env in cwd
load_dotenv()

# Remote connection settings
REMOTE_USER = os.environ['REMOTE_USER']
REMOTE_HOST = os.environ['REMOTE_HOST']
REMOTE_PORT = int(os.environ['REMOTE_PORT'])
REMOTE_SERIES_PATH = os.environ['REMOTE_SERIES_PATH']

MOUNT_POINT = Path(os.environ['MOUNT_POINT'])

# Create the local mount directory if it does not exist
os.makedirs(MOUNT_POINT, exist_ok=True)

# Mount the remote series directory via sshfs
# Command: sshfs -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST:$REMOTE_SERIES_PATH $MOUNT_POINT
# Note: Ensure sshfs is installed and SSH key or password auth is set up.

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
# Base directory for the renaming operations, derived from the mount point
BASE_DIR = MOUNT_POINT

# Set to True to skip confirmation prompts and auto-run
AUTO_RUN = os.environ.get('AUTO_RUN', 'False').lower() in ('1','true','yes')

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def pad(n):
    return f"{int(n):02}"

# ─────────────────────────────────────────────
# Gather all rename operations
# ─────────────────────────────────────────────
def gather_operations():
    ops = []  # list of (old_path: Path, new_path: Path)
    logger.info(f"Starting operation gathering in {BASE_DIR}")

    try:
        for season_dir in BASE_DIR.iterdir():
            if not season_dir.is_dir():
                continue

            logger.debug(f"Processing directory: {season_dir.name}")
            m_season = re.search(r'(?:season[\s_]?|s)(\d{1,2})', season_dir.name, re.IGNORECASE)
            if not m_season:
                logger.warning(f"Skipping unknown folder: {season_dir.name}")
                continue

            season = pad(m_season.group(1))
            new_season_dir = BASE_DIR / f"How I Met Your Mother S{season}"

            # Plan episode renames inside the original folder first
            for ep in season_dir.iterdir():
                if not ep.is_file():
                    continue
                try:
                    fname = ep.name
                    logger.debug(f"Examining file: {fname}")
                    m_ep = re.search(r'[sS]\d{2}[eE](\d{2})', fname)
                    if m_ep:
                        ep_no = m_ep.group(1)
                    else:
                        m2 = re.search(r'(\d{1,2})[xX](\d{2})', fname)
                        if m2:
                            ep_no = m2.group(2)
                        else:
                            m3 = re.search(r'[eE](\d{2})', fname)
                            if m3:
                                ep_no = m3.group(1)
                            else:
                                logger.warning(f"Skipping file, no episode found: {fname}")
                                continue
                    ep_no = pad(ep_no)
                    ext = ep.suffix
                    new_ep_name = f"How I Met Your Mother S{season}E{ep_no}{ext}"
                    new_ep_path = new_season_dir / new_ep_name
                    if ep != new_ep_path:
                        ops.append((ep, new_ep_path))
                        logger.info(f"Planned rename: {ep.relative_to(BASE_DIR)} -> {new_ep_path.relative_to(BASE_DIR)}")
                except Exception as e:
                    logger.error(f"Error processing file {ep}: {e}")

            # Plan folder rename if needed after episode ops
            if season_dir != new_season_dir:
                ops.append((season_dir, new_season_dir))
                logger.info(f"Planned folder rename: {season_dir.name} -> {new_season_dir.name}")

    except Exception as e:
        logger.error(f"Failed gathering operations: {e}")
    logger.info(f"Gathering complete: {len(ops)} operations planned")
    return ops

# ─────────────────────────────────────────────
# Preview planned operations
# ─────────────────────────────────────────────
def preview(ops):
    logger.info("Previewing planned operations:")
    print("\nPlanned renames:\n")
    for old, new in ops:
        print(f"  {old.relative_to(BASE_DIR)}  →  {new.relative_to(BASE_DIR)}")
    print(f"\nTotal operations: {len(ops)}\n")

# ─────────────────────────────────────────────
# Prompt for confirmation
# ─────────────────────────────────────────────
def confirm(prompt="Proceed? [y/N]: "):
    resp = input(prompt).strip().lower()
    return resp in ('y', 'yes')

# ─────────────────────────────────────────────
# Apply renames (files first, then directories)
# ─────────────────────────────────────────────
def apply_ops(ops):
    ops_sorted = sorted(ops, key=lambda pair: pair[0].as_posix().count(os.sep), reverse=True)
    executed = []
    for old, new in ops_sorted:
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            os.rename(old, new)
            executed.append((old, new))
            logger.info(f"Renamed: {old.relative_to(BASE_DIR)} -> {new.relative_to(BASE_DIR)}")
        except Exception as e:
            logger.error(f"Failed to rename {old} -> {new}: {e}")
    logger.info("Renaming complete")
    return executed

# ─────────────────────────────────────────────
# Rollback executed operations
# ─────────────────────────────────────────────
def rollback(executed):
    logger.warning("Starting rollback")
    for old, new in reversed(executed):
        try:
            if new.exists():
                os.rename(new, old)
                logger.info(f"Rolled back: {new.relative_to(BASE_DIR)} -> {old.relative_to(BASE_DIR)}")
        except Exception as e:
            logger.error(f"Failed to rollback {new} -> {old}: {e}")
    logger.warning("Rollback complete")

# ─────────────────────────────────────────────
# Checks for inconsistent files
# ─────────────────────────────────────────────
def check_outliers(ops):
    """
    Detect files in the target directory that don’t match the rename operations
    (e.g. contain PSArips.com.txt, .url, etc.), and prompt to keep or delete them.
    """
    if not ops:
        logger.info("No operations to determine target directory for outlier check.")
        return

    # All ops target the same folder
    directory = os.path.dirname(ops[0].src)
    try:
        all_files = os.listdir(directory)
    except OSError as e:
        logger.error(f"[Outliers] Failed to list directory '{directory}': {e}")
        return

    # Files involved in renaming
    renamed = {os.path.basename(op.src) for op in ops}

    # Heuristic keywords for likely outliers
    keywords = ["PSArips.com", ".url", ".txt", "RARBG", "ReadMe"]
    outliers = [
        f for f in all_files
        if f not in renamed and any(kw in f for kw in keywords)
    ]

    if not outliers:
        logger.info(f"[Outliers] No outlier files detected in '{directory}'.")
        return

    logger.warning(f"[Outliers] Detected {len(outliers)} potential outlier file(s):")
    for f in outliers:
        logger.warning(f"    • {f}")

    # Prompt user
    prompt = (
        "\n[Outliers] What should be done with these files?\n"
        "  1) Keep them\n"
        "  2) Delete them\n"
        "Choice [1/2]: "
    )
    while True:
        choice = input(prompt).strip()
        if choice == "1":
            logger.info("[Outliers] Keeping all outlier files.")
            return
        elif choice == "2":
            for f in outliers:
                path = os.path.join(directory, f)
                try:
                    os.remove(path)
                    logger.info(f"[Outliers] Deleted '{f}'.")
                except OSError as e:
                    logger.error(f"[Outliers] Failed to delete '{f}': {e}")
            return
        else:
            logger.warning("[Outliers] Invalid choice; please enter 1 or 2.")

# ─────────────────────────────────────────────
# Timeout‐aware confirmation
# ─────────────────────────────────────────────
class TimeoutException(Exception):
    pass

def _timeout_handler(signum, frame):
    raise TimeoutException()

def confirm(prompt="Proceed? [y/N]: ", timeout=15):
    """
    Ask the user to confirm. Returns True only if they type 'y' or 'yes'.
    After `timeout` seconds, automatically returns False.
    """
    if AUTO_RUN:
        logger.info(f"[Confirm] AUTO_RUN enabled, skipping prompt: '{prompt.strip()}'")
        return False

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        resp = input(prompt).strip().lower()
        if resp in ("y", "yes"):
            logger.info(f"[Confirm] Received affirmative response.")
            return True
        else:
            logger.info(f"[Confirm] Received negative or empty response.")
            return False
    except TimeoutException:
        logger.warning(f"[Confirm] No response in {timeout}s, defaulting to 'no'.")
        return False
    except KeyboardInterrupt:
        logger.warning("[Confirm] KeyboardInterrupt received, defaulting to 'no'.")
        return False
    finally:
        signal.alarm(0)

# ─────────────────────────────────────────────
# Main routine
# ─────────────────────────────────────────────
def main():
    ops = gather_operations()
    if not ops:
        logger.info("Nothing to rename.")
        return

    check_outliers(ops)

    preview(ops)
    if not confirm("Apply rename operations? [y/N]: "):
        logger.info("User aborted before renaming.")
        return

    try:
        executed = apply_ops(ops)
    except Exception as e:
        logger.error(f"[Main] Fatal error during rename operations: {e}")
        return

    if not executed:
        logger.error("[Main] No rename operations succeeded; nothing to rollback.")
        return

    # Final rollback prompt
    if confirm("Rollback all changes? [y/N]: "):
        try:
            rollback(executed)
            logger.info("[Main] Rollback completed successfully.")
        except Exception as e:
            logger.error(f"[Main] Error during rollback: {e}")
    else:
        logger.info("[Main] Rename operations committed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"[Main] Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
