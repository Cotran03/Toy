import asyncio
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .secondary_warn import (
    SECONDARY_WARN_DB_LOCK,
    SECONDARY_WARN_DB_PATH,
    init_secondary_warn_db,
)


BACKUP_INTERVAL_SECONDS = 60 * 60
BACKUP_RETENTION_HOURS = 48
BACKUP_DIR = Path(__file__).resolve().parent / "secondary_backups"
BACKUP_PREFIX = "secondary_warn_backup_"
BACKUP_SUFFIX = ".db"
BACKUP_TIMEZONE = ZoneInfo("Asia/Seoul")


def _backup_path(now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(BACKUP_TIMEZONE)).astimezone(BACKUP_TIMEZONE)
    return BACKUP_DIR / f"{BACKUP_PREFIX}{timestamp:%Y%m%d_%H%M%S}_KST{BACKUP_SUFFIX}"


def backup_secondary_database() -> Path:
    with SECONDARY_WARN_DB_LOCK:
        source_path = Path(SECONDARY_WARN_DB_PATH)
        if not source_path.exists() or source_path.stat().st_size == 0:
            raise FileNotFoundError(f"Secondary database is not ready: {source_path}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        destination_path = _backup_path()
        try:
            source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
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

        Path(f"{destination_path}-journal").unlink(missing_ok=True)
        return destination_path


def list_secondary_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    backups = [
        path
        for path in BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
        if path.is_file()
    ]
    return sorted(backups, key=lambda path: path.stat().st_mtime, reverse=True)


def resolve_secondary_backup(identifier: str) -> Path:
    if identifier == "latest":
        backups = list_secondary_backups()
        if not backups:
            raise FileNotFoundError("No secondary database backups found.")
        return backups[0]

    candidate = BACKUP_DIR / Path(identifier).name
    if not candidate.is_file() or candidate.parent.resolve() != BACKUP_DIR.resolve():
        raise FileNotFoundError(f"Secondary backup not found: {identifier}")
    return candidate


def restore_secondary_database(identifier: str) -> tuple[Path, Path | None]:
    with SECONDARY_WARN_DB_LOCK:
        backup_path = resolve_secondary_backup(identifier)
        source_path = Path(SECONDARY_WARN_DB_PATH)
        safety_backup = None
        if source_path.exists() and source_path.stat().st_size > 0:
            safety_backup = backup_secondary_database()

        try:
            source = sqlite3.connect(f"{backup_path.resolve().as_uri()}?mode=ro", uri=True)
            try:
                destination = sqlite3.connect(SECONDARY_WARN_DB_PATH)
                try:
                    source.backup(destination)
                finally:
                    destination.close()
            finally:
                source.close()
        except Exception:
            Path(f"{SECONDARY_WARN_DB_PATH}-journal").unlink(missing_ok=True)
            raise

        init_secondary_warn_db()
        return backup_path, safety_backup


def prune_old_secondary_backups() -> int:
    if not BACKUP_DIR.exists():
        return 0

    cutoff = datetime.now(BACKUP_TIMEZONE) - timedelta(hours=BACKUP_RETENTION_HOURS)
    removed = 0
    for path in BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, BACKUP_TIMEZONE)
        if modified_at <= cutoff:
            path.unlink()
            removed += 1
    return removed


async def secondary_database_backup_loop(
    is_paused: Callable[[], bool] | None = None,
    on_failure: Callable[[Exception], Awaitable[None]] | None = None,
) -> None:
    while True:
        if is_paused is not None and is_paused():
            await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
            continue

        try:
            backup_path = await asyncio.to_thread(backup_secondary_database)
            removed = await asyncio.to_thread(prune_old_secondary_backups)
            print(f"[Secondary DB Backup] Created {backup_path.name}; removed {removed} old backup(s).")
        except Exception as exc:
            print(f"[Secondary DB Backup] Failed: {exc}")
            if on_failure is not None:
                await on_failure(exc)

        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
