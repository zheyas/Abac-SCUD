from database import get_conn

def get_all():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM roles").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create(name):
    conn = get_conn()
    conn.execute("INSERT INTO roles (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()