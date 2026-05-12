# ──────────────────────────────────────────────
#  db/database.py  |  SQLite3 연동
# ──────────────────────────────────────────────
import sqlite3
import os
from datetime import date, datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """봇 시작 시 한 번 호출 — 테이블 없으면 생성, 컬럼 없으면 추가."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id              INTEGER PRIMARY KEY,
                balance              INTEGER NOT NULL DEFAULT 0,
                post_count           INTEGER NOT NULL DEFAULT 0,
                end_count            INTEGER NOT NULL DEFAULT 0,
                promote_count        INTEGER NOT NULL DEFAULT 0,
                total_promote_count  INTEGER NOT NULL DEFAULT 0,
                last_reward_date     TEXT,
                last_promote_date    TEXT,
                is_banned            INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 기존 DB에 컬럼이 없는 경우 추가 (DB 유지한 채로 업데이트 시 대응)
        migrations = [
            "ALTER TABLE users ADD COLUMN is_banned            INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN promote_count        INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_promote_date    TEXT",
            "ALTER TABLE users ADD COLUMN end_count            INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN total_promote_count  INTEGER NOT NULL DEFAULT 0",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # 이미 있으면 무시

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                reason    TEXT,
                warned_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        conn.commit()
    print("[DB] 초기화 완료")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_user(user_id: int) -> sqlite3.Row | None:
    """유저 행 반환. 없으면 None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def ensure_user(user_id: int) -> None:
    """유저가 없으면 기본값으로 생성. 모든 명령어 진입 시 호출."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Balance (재화)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_balance(user_id: int) -> int:
    """재화 조회. 유저 없으면 0."""
    user = get_user(user_id)
    return user["balance"] if user else 0


def add_balance(user_id: int, amount: int) -> int:
    """재화 추가. 변경 후 잔액 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()
    return get_balance(user_id)


def deduct_balance(user_id: int, amount: int) -> int:
    """재화 차감. 0 미만으로 내려가지 않음. 변경 후 잔액 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()
    return get_balance(user_id)


def set_balance(user_id: int, amount: int) -> int:
    """재화 직접 설정 (관리자용). 변경 후 잔액 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = MAX(0, ?) WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()
    return get_balance(user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Reward (일일 보상)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def can_claim_reward(user_id: int) -> bool:
    """오늘 /reward를 아직 사용하지 않았으면 True."""
    user = get_user(user_id)
    if not user or not user["last_reward_date"]:
        return True
    return user["last_reward_date"] != str(date.today())


def set_reward_claimed(user_id: int) -> None:
    """오늘 날짜로 last_reward_date 갱신."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_reward_date = ? WHERE user_id = ?",
            (str(date.today()), user_id)
        )
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Post Count (생성한 포스트 수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_post_count(user_id: int) -> int:
    """생성한 포스트 수 조회."""
    user = get_user(user_id)
    return user["post_count"] if user else 0


def increment_post_count(user_id: int) -> int:
    """포스트 수 1 증가. 변경 후 포스트 수 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET post_count = post_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
    return get_post_count(user_id)


def get_end_count(user_id: int) -> int:
    """종료한 포스트 수 조회."""
    user = get_user(user_id)
    return user["end_count"] if user else 0


def increment_end_count(user_id: int) -> int:
    """종료한 포스트 수 1 증가. 변경 후 종료 수 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET end_count = end_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
    return get_end_count(user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ban
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def set_banned(user_id: int, banned: bool) -> None:
    """유저의 ban 상태 설정."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if banned else 0, user_id)
        )
        conn.commit()


def is_banned(user_id: int) -> bool:
    """유저가 ban 상태인지 확인."""
    user = get_user(user_id)
    return bool(user["is_banned"]) if user else False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Promote (홍보 횟수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_promote_info(user_id: int) -> tuple[int, str | None]:
    """오늘 홍보 횟수 반환. 날짜가 바뀌었으면 0으로 처리."""
    ensure_user(user_id)
    user = get_user(user_id)
    last_date = user["last_promote_date"]
    today = str(date.today())
    if last_date != today:
        return 0, last_date
    return user["promote_count"], last_date


def get_total_promote_count(user_id: int) -> int:
    """전체 홍보 사용 수 조회."""
    user = get_user(user_id)
    return user["total_promote_count"] if user else 0


def increment_promote(user_id: int) -> int:
    """홍보 횟수 1 증가. 날짜가 바뀌었으면 1로 초기화. 변경 후 오늘 횟수 반환."""
    ensure_user(user_id)
    today = str(date.today())
    current_count, last_date = get_promote_info(user_id)

    new_count = 1 if last_date != today else current_count + 1

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET promote_count = ?, total_promote_count = total_promote_count + 1, last_promote_date = ? WHERE user_id = ?",
            (new_count, today, user_id)
        )
        conn.commit()
    return new_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Warnings (경고)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_warnings(user_id: int) -> list[sqlite3.Row]:
    """유효한 경고 목록 반환 (30일 이내)."""
    cutoff = datetime.now() - timedelta(days=30)
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM warnings WHERE user_id = ? AND warned_at > ? ORDER BY warned_at DESC",
            (user_id, cutoff.isoformat())
        ).fetchall()


def get_warning_count(user_id: int) -> int:
    """유효한 경고 횟수 반환 (30일 이내)."""
    return len(get_warnings(user_id))


def add_warning(user_id: int, reason: str = "") -> int:
    """경고 추가. 변경 후 총 경고 횟수 반환."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
            (user_id, reason)
        )
        conn.commit()
    return get_warning_count(user_id)


def remove_warning(user_id: int) -> int:
    """가장 최근 경고 1건 삭제 (warnoff용). 변경 후 총 경고 횟수 반환."""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM warnings WHERE id = (
                SELECT id FROM warnings WHERE user_id = ? ORDER BY warned_at DESC LIMIT 1
            )
        """, (user_id,))
        conn.commit()
    return get_warning_count(user_id)


def clear_warnings(user_id: int) -> None:
    """유저의 모든 경고 삭제 (관리자용)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
        conn.commit()


def expire_old_warnings() -> list[tuple[int, int]]:
    """
    30일 지난 경고 전체 삭제. ban 상태인 유저는 제외.
    삭제된 경고를 유저별로 집계해 [(user_id, count), ...] 반환.
    """
    cutoff = datetime.now() - timedelta(days=30)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT w.user_id, COUNT(*) as cnt
            FROM warnings w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.warned_at <= ?
              AND (u.is_banned IS NULL OR u.is_banned = 0)
            GROUP BY w.user_id
        """, (cutoff.isoformat(),)).fetchall()

        conn.execute("""
            DELETE FROM warnings
            WHERE warned_at <= ?
              AND user_id IN (
                  SELECT user_id FROM users WHERE is_banned = 0
              )
        """, (cutoff.isoformat(),))
        conn.commit()
    return [(row["user_id"], row["cnt"]) for row in rows]