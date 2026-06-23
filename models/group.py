from database import Database


class Group:
    """Группа доступа. Для обратной совместимости хранится в таблице roles."""

    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute(
            """SELECT r.id, r.name, COALESCE(r.description, '') AS description,
                      (SELECT COUNT(*) FROM users u WHERE u.role_id=r.id) AS member_count,
                      (SELECT COUNT(DISTINCT p.building_id) FROM policies p
                       WHERE p.role_id=r.id AND p.user_id IS NULL
                         AND p.is_active=1 AND p.effect='allow') AS access_count
               FROM roles r ORDER BY r.id"""
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(group_id):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT id, name, COALESCE(description, '') AS description FROM roles WHERE id=?",
            (group_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(name, description=''):
        conn = Database.get_conn()
        cursor = conn.execute("INSERT INTO roles (name, description) VALUES (?,?)", (name, description))
        conn.commit()
        group_id = cursor.lastrowid
        conn.close()
        return group_id

    @staticmethod
    def update(group_id, name, description=''):
        conn = Database.get_conn()
        conn.execute("UPDATE roles SET name=?, description=? WHERE id=?", (name, description, group_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(group_id):
        conn = Database.get_conn()
        members = conn.execute("SELECT COUNT(*) FROM users WHERE role_id=?", (group_id,)).fetchone()[0]
        if members:
            conn.close()
            return False
        conn.execute("DELETE FROM policies WHERE role_id=?", (group_id,))
        conn.execute("DELETE FROM roles WHERE id=?", (group_id,))
        conn.commit()
        conn.close()
        return True
