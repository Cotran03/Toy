import asyncio


def get_operation_lock(bot, namespace: str, key: int) -> asyncio.Lock:
    """Return a bot-local lock shared by Cogs for the same operation target."""
    locks = getattr(bot, "_operation_locks", None)
    if locks is None:
        locks = {}
        setattr(bot, "_operation_locks", locks)

    lock_key = (namespace, key)
    lock = locks.get(lock_key)
    if lock is None:
        lock = asyncio.Lock()
        locks[lock_key] = lock
    return lock
