import sqlite3, time

def init_db():
    conn = sqlite3.connect('logs/posted.sqlite')
    conn.execute("CREATE TABLE IF NOT EXISTS posted (platform TEXT, account TEXT, image TEXT, ts INTEGER)")
    conn.commit()
    return conn

def already_posted(conn, platform, image):
    return conn.execute("SELECT 1 FROM posted WHERE platform=? AND image=?", (platform, image)).fetchone() is not None

def mark_posted(conn, platform, account, image):
    conn.execute("INSERT INTO posted VALUES (?, ?, ?, ?)", (platform, account, image, int(time.time())))
    conn.commit()
