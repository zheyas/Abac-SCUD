from database import Database


class Policy:
    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute(
            """SELECT p.*, r.name AS role_name, u.username AS user_name, b.name AS building_name
               FROM policies p
               LEFT JOIN roles r ON p.role_id = r.id
               LEFT JOIN users u ON p.user_id = u.id
               LEFT JOIN buildings b ON p.building_id = b.id
               ORDER BY p.user_id IS NOT NULL DESC, p.id"""
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(policy_id):
        conn = Database.get_conn()
        row = conn.execute("SELECT * FROM policies WHERE id=?", (policy_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_for_user_building(role_id, user_id, building_id):
        conn = Database.get_conn()
        rows = conn.execute(
            """SELECT * FROM policies
               WHERE building_id=? AND is_active=1
                 AND ((user_id IS NOT NULL AND user_id=?) OR (user_id IS NULL AND role_id=?))
               ORDER BY user_id IS NOT NULL DESC,
                        CASE effect WHEN 'deny' THEN 0 ELSE 1 END,
                        id""",
            (building_id, user_id, role_id)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_role_building(role_id, building_id):
        conn = Database.get_conn()
        rows = conn.execute(
            "SELECT * FROM policies WHERE role_id=? AND building_id=? AND user_id IS NULL",
            (role_id, building_id)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(role_id, building_id, days_allowed, time_start, time_end,
               requires_shift_active, user_id=None, name="", effect="allow", is_active=True):
        conn = Database.get_conn()
        cursor = conn.execute(
            """INSERT INTO policies
               (role_id, building_id, days_allowed, time_start, time_end,
                requires_shift_active, user_id, name, effect, is_active)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (role_id, building_id, days_allowed, time_start, time_end,
             requires_shift_active, user_id, name, effect, is_active)
        )
        conn.commit()
        policy_id = cursor.lastrowid
        conn.close()
        return policy_id

    @staticmethod
    def update(policy_id, role_id, building_id, days_allowed, time_start, time_end,
               requires_shift_active, user_id=None, name="", effect="allow", is_active=True):
        conn = Database.get_conn()
        conn.execute(
            """UPDATE policies SET role_id=?, building_id=?, days_allowed=?,
               time_start=?, time_end=?, requires_shift_active=?, user_id=?,
               name=?, effect=?, is_active=? WHERE id=?""",
            (role_id, building_id, days_allowed, time_start, time_end,
             requires_shift_active, user_id, name, effect, is_active, policy_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete(policy_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM policies WHERE id=?", (policy_id,))
        conn.commit()
        conn.close()
