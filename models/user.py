from database import Database
import bcrypt
import datetime

class User:
    @staticmethod
    def get_by_username(username):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT u.*, u.role_id AS group_id, r.name AS group_name, r.name AS role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.username=?",
            (username,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_id(user_id):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT u.*, u.role_id AS group_id, r.name AS group_name, r.name AS role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id=?",
            (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute(
            """SELECT u.id, u.username, u.role_id AS group_id, u.role_id,
                      r.name AS group_name, u.shift_status, u.is_active,
                      u.shift_auto, u.shift_days, u.shift_start, u.shift_end
               FROM users u JOIN roles r ON r.id=u.role_id ORDER BY u.id"""
        ).fetchall()
        users = [dict(row) for row in rows]
        grants = conn.execute(
            "SELECT user_id, building_id FROM user_building_access ORDER BY building_id"
        ).fetchall()
        conn.close()
        grants_by_user = {}
        for grant in grants:
            grants_by_user.setdefault(grant["user_id"], []).append(grant["building_id"])
        for user in users:
            user["personal_building_ids"] = grants_by_user.get(user["id"], [])
        return users

    @staticmethod
    def get_personal_building_ids(user_id):
        conn = Database.get_conn()
        rows = conn.execute(
            "SELECT building_id FROM user_building_access WHERE user_id=? ORDER BY building_id",
            (user_id,)
        ).fetchall()
        conn.close()
        return [row["building_id"] for row in rows]

    @staticmethod
    def has_personal_building_access(user_id, building_id):
        conn = Database.get_conn()
        row = conn.execute(
            "SELECT 1 FROM user_building_access WHERE user_id=? AND building_id=?",
            (user_id, building_id)
        ).fetchone()
        conn.close()
        return bool(row)

    @staticmethod
    def set_personal_building_access(user_id, building_ids):
        building_ids = sorted({int(building_id) for building_id in (building_ids or [])})
        conn = Database.get_conn()
        conn.execute("DELETE FROM user_building_access WHERE user_id=?", (user_id,))
        if building_ids:
            existing = {
                row["id"] for row in conn.execute(
                    f"SELECT id FROM buildings WHERE id IN ({','.join('?' for _ in building_ids)})",
                    building_ids
                ).fetchall()
            }
            conn.executemany(
                "INSERT INTO user_building_access (user_id, building_id) VALUES (?,?)",
                [(user_id, building_id) for building_id in building_ids if building_id in existing]
            )
        conn.commit()
        conn.close()

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
    def create(username, password, group_id, shift_auto=False,
               shift_days="Mon,Tue,Wed,Thu,Fri", shift_start="08:00", shift_end="18:00",
               personal_building_ids=None):
        personal_building_ids = sorted({int(value) for value in (personal_building_ids or [])})
        pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = Database.get_conn()
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role_id, shift_auto, shift_days, shift_start, shift_end) VALUES (?,?,?,?,?,?,?)",
            (username, pwd_hash, group_id, shift_auto, shift_days, shift_start, shift_end)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        User.set_personal_building_access(user_id, personal_building_ids)
        return user_id

    @staticmethod
    def update(user_id, username, group_id, is_active, password=None, shift_status=None,
               shift_auto=False, shift_days="Mon,Tue,Wed,Thu,Fri",
               shift_start="08:00", shift_end="18:00", personal_building_ids=None):
        if personal_building_ids is not None:
            personal_building_ids = sorted({int(value) for value in personal_building_ids})
        conn = Database.get_conn()
        if password:
            pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn.execute("UPDATE users SET username=?, role_id=?, is_active=?, password_hash=? WHERE id=?",
                         (username, group_id, is_active, pwd_hash, user_id))
        else:
            conn.execute("UPDATE users SET username=?, role_id=?, is_active=? WHERE id=?",
                         (username, group_id, is_active, user_id))
        if shift_status in ("active", "inactive"):
            conn.execute("UPDATE users SET shift_status=? WHERE id=?", (shift_status, user_id))
        conn.execute(
            "UPDATE users SET shift_auto=?, shift_days=?, shift_start=?, shift_end=? WHERE id=?",
            (shift_auto, shift_days, shift_start, shift_end, user_id)
        )
        conn.commit()
        conn.close()
        if personal_building_ids is not None:
            User.set_personal_building_access(user_id, personal_building_ids)

    @staticmethod
    def delete(user_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM access_events WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM policies WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM user_building_access WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
