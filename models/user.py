from database import Database
import bcrypt
import datetime

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
        rows = conn.execute(
            "SELECT id, username, role_id, shift_status, is_active, shift_auto, shift_days, shift_start, shift_end FROM users"
        ).fetchall()
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
    def get_effective_shift_status(user, context_datetime=None):
        if not user.get("shift_auto"):
            return user.get("shift_status", "inactive")
        now = context_datetime or datetime.datetime.now().astimezone()
        days = [day.strip() for day in (user.get("shift_days") or "").split(",") if day.strip()]
        try:
            start = datetime.datetime.strptime(user.get("shift_start") or "08:00", "%H:%M").time()
            end = datetime.datetime.strptime(user.get("shift_end") or "18:00", "%H:%M").time()
        except (TypeError, ValueError):
            return "inactive"
        current = now.time().replace(tzinfo=None)

        def allowed(day_name):
            return "All" in days or day_name in days

        if start <= end:
            active = allowed(now.strftime("%a")) and start <= current <= end
        elif current >= start:
            active = allowed(now.strftime("%a"))
        elif current <= end:
            active = allowed((now - datetime.timedelta(days=1)).strftime("%a"))
        else:
            active = False
        return "active" if active else "inactive"

    @staticmethod
    def create(username, password, role_id, shift_auto=False,
               shift_days="Mon,Tue,Wed,Thu,Fri", shift_start="08:00", shift_end="18:00"):
        pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = Database.get_conn()
        conn.execute(
            "INSERT INTO users (username, password_hash, role_id, shift_auto, shift_days, shift_start, shift_end) VALUES (?,?,?,?,?,?,?)",
            (username, pwd_hash, role_id, shift_auto, shift_days, shift_start, shift_end)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update(user_id, username, role_id, is_active, password=None, shift_status=None,
               shift_auto=False, shift_days="Mon,Tue,Wed,Thu,Fri",
               shift_start="08:00", shift_end="18:00"):
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
        conn.execute(
            "UPDATE users SET shift_auto=?, shift_days=?, shift_start=?, shift_end=? WHERE id=?",
            (shift_auto, shift_days, shift_start, shift_end, user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete(user_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM access_events WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM policies WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
