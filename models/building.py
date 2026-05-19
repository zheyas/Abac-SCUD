from database import get_conn

def get_all():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM buildings").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create(name, color_hex, x, y, w, h, depth, is_all):
    conn = get_conn()
    conn.execute("INSERT INTO buildings (name, color_hex, x, y, w, h, depth, is_accessible_to_all) VALUES (?,?,?,?,?,?,?,?)",
                 (name, color_hex, x, y, w, h, depth, is_all))
    conn.commit()
    conn.close()