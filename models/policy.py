from database import get_conn

def get_all():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM policies").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_by_role_building(role_id, building_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM policies WHERE role_id=? AND building_id=?", (role_id, building_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create(role_id, building_id, days, t_start, t_end, req_shift):
    conn = get_conn()
    conn.execute("INSERT INTO policies (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active) VALUES (?,?,?,?,?,?)",
                 (role_id, building_id, days, t_start, t_end, req_shift))
    conn.commit()
    conn.close()
