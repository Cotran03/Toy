# Imports
from contextlib import contextmanager
import os
import sqlite3
import threading
from collections.abc import Iterator

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")
DB_LOCK = threading.RLock()


@contextmanager
def database_lock() -> Iterator[None]:
    with DB_LOCK:
        yield


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    with database_lock():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()
