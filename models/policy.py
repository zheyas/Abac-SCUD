from database import Database

class Policy:
    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute("SELECT * FROM policies").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(policy_id):
        conn = Database.get_conn()
        row = conn.execute("SELECT * FROM policies WHERE id=?", (policy_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_role_building(role_id, building_id):
        conn = Database.get_conn()
        rows = conn.execute("SELECT * FROM policies WHERE role_id=? AND building_id=?",
                            (role_id, building_id)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def create(role_id, building_id, days_allowed, time_start, time_end, requires_shift_active):
        conn = Database.get_conn()
        conn.execute(
            "INSERT INTO policies (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active) VALUES (?,?,?,?,?,?)",
            (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active))
        conn.commit()
        conn.close()

    @staticmethod
    def update(policy_id, role_id, building_id, days_allowed, time_start, time_end, requires_shift_active):
        conn = Database.get_conn()
        conn.execute(
            "UPDATE policies SET role_id=?, building_id=?, days_allowed=?, time_start=?, time_end=?, requires_shift_active=? WHERE id=?",
            (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active, policy_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(policy_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM policies WHERE id=?", (policy_id,))
        conn.commit()
        conn.close()
