import asyncio
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from .connection import DB_PATH


BACKUP_INTERVAL_SECONDS = 60 * 60
BACKUP_RETENTION_HOURS = 48
BACKUP_DIR = Path(__file__).resolve().parent / "backups"
BACKUP_PREFIX = "bot_backup_"
BACKUP_SUFFIX = ".db"
BACKUP_TIMEZONE = ZoneInfo("Asia/Seoul")


def _backup_path(now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(BACKUP_TIMEZONE)).astimezone(BACKUP_TIMEZONE)
    return BACKUP_DIR / f"{BACKUP_PREFIX}{timestamp:%Y%m%d_%H%M%S}_KST{BACKUP_SUFFIX}"


def backup_database() -> Path:
    """Create a consistent SQLite backup and return the backup path."""
    source_path = Path(DB_PATH)
    if not source_path.exists() or source_path.stat().st_size == 0:
        raise FileNotFoundError(f"Database is not ready: {source_path}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination_path = _backup_path()

    try:
        source_uri = f"{source_path.resolve().as_uri()}?mode=ro"
        source = sqlite3.connect(source_uri, uri=True)
        try:
            destination = sqlite3.connect(destination_path)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    except Exception:
        destination_path.unlink(missing_ok=True)
        Path(f"{destination_path}-journal").unlink(missing_ok=True)
        raise

    journal_path = Path(f"{destination_path}-journal")
    if journal_path.exists():
        journal_path.unlink()

    return destination_path


def list_backups() -> list[Path]:
    """Return available backups from newest to oldest."""
    if not BACKUP_DIR.exists():
        return []

    backups = [
        path
        for path in BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
        if path.is_file()
    ]
    return sorted(backups, key=lambda path: path.stat().st_mtime, reverse=True)


def resolve_backup(identifier: str) -> Path:
    """Resolve 'latest' or a backup filename to a safe backup path."""
    if identifier == "latest":
        backups = list_backups()
        if not backups:
            raise FileNotFoundError("No database backups found.")
        return backups[0]

    candidate = BACKUP_DIR / Path(identifier).name
    if not candidate.is_file():
        raise FileNotFoundError(f"Backup not found: {identifier}")

    if candidate.parent.resolve() != BACKUP_DIR.resolve():
        raise ValueError("Invalid backup path.")

    return candidate


def restore_database(identifier: str) -> tuple[Path, Path | None]:
    """Restore DB_PATH from a backup. Returns (restored_from, safety_backup)."""
    backup_path = resolve_backup(identifier)

    safety_backup = None
    source_path = Path(DB_PATH)
    if source_path.exists() and source_path.stat().st_size > 0:
        safety_backup = backup_database()

    try:
        source_uri = f"{backup_path.resolve().as_uri()}?mode=ro"
        source = sqlite3.connect(source_uri, uri=True)
        try:
            destination = sqlite3.connect(DB_PATH)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    except Exception:
        Path(f"{DB_PATH}-journal").unlink(missing_ok=True)
        raise

    return backup_path, safety_backup


def prune_old_backups() -> int:
    """Delete DB backups older than the retention window."""
    if not BACKUP_DIR.exists():
        return 0

    cutoff = datetime.now() - timedelta(hours=BACKUP_RETENTION_HOURS)
    removed = 0

    for path in BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if not path.is_file():
            continue

        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if modified_at <= cutoff:
            path.unlink()
            removed += 1

    return removed


async def database_backup_loop() -> None:
    """Back up the database hourly and keep only the last 48 hours."""
    while True:
        try:
            backup_path = await asyncio.to_thread(backup_database)
            removed = await asyncio.to_thread(prune_old_backups)
            print(f"[DB Backup] Created {backup_path.name}; removed {removed} old backup(s).")
        except Exception as exc:
            print(f"[DB Backup] Failed: {exc}")

        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
