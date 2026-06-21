from database import Database
import bcrypt

class User:
    @staticmethod
    def get_by_username(username):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.username=?",
            (username,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_id(user_id):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id=?",
            (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute("SELECT id, username, role_id, shift_status, is_active FROM users").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def toggle_shift(user_id):
        conn = Database.get_conn()
        curr = conn.execute("SELECT shift_status FROM users WHERE id=?", (user_id,)).fetchone()
        new_status = "inactive" if curr["shift_status"] == "active" else "active"
        conn.execute("UPDATE users SET shift_status=? WHERE id=?", (new_status, user_id))
        conn.commit()
        conn.close()
        return new_status

    @staticmethod
    def create(username, password, role_id):
        pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = Database.get_conn()
        conn.execute("INSERT INTO users (username, password_hash, role_id) VALUES (?,?,?)",
                     (username, pwd_hash, role_id))
        conn.commit()
        conn.close()

    @staticmethod
    def update(user_id, username, role_id, is_active, password=None, shift_status=None):
        conn = Database.get_conn()
        if password:
            pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn.execute("UPDATE users SET username=?, role_id=?, is_active=?, password_hash=? WHERE id=?",
                         (username, role_id, is_active, pwd_hash, user_id))
        else:
            conn.execute("UPDATE users SET username=?, role_id=?, is_active=? WHERE id=?",
                         (username, role_id, is_active, user_id))
        if shift_status in ("active", "inactive"):
            conn.execute("UPDATE users SET shift_status=? WHERE id=?", (shift_status, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(user_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
