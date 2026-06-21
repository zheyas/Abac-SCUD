from database import Database

class Role:
    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute("SELECT * FROM roles").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(role_id):
        conn = Database.get_conn()
        row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(name):
        conn = Database.get_conn()
        conn.execute("INSERT INTO roles (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()