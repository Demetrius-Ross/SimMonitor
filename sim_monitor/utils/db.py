import sqlite3, time, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "sim_monitor.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS simulators (
        sim_id INTEGER PRIMARY KEY,
        motion_state INTEGER,
        ramp_state INTEGER,
        last_update_ts INTEGER,
        online INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS active_motion (
        sim_id INTEGER PRIMARY KEY,
        start_ts INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS motion_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sim_id INTEGER,
        start_ts INTEGER,
        end_ts INTEGER,
        duration_sec INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_status (
        id INTEGER PRIMARY KEY CHECK(id=1),
        receiver_online INTEGER,
        last_seen INTEGER
    )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO system_status (id, receiver_online, last_seen)
        VALUES (1, 0, 0)
    """)

    conn.commit()
    conn.close()
