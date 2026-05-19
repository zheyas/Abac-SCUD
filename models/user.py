from database import get_conn
import bcrypt

def get_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def toggle_shift(user_id):
    conn = get_conn()
    curr = conn.execute("SELECT shift_status FROM users WHERE id=?", (user_id,)).fetchone()
    new_status = "inactive" if curr["shift_status"] == "active" else "active"
    conn.execute("UPDATE users SET shift_status=? WHERE id=?", (new_status, user_id))
    conn.commit()
    conn.close()
    return new_status

def create(username, password, role_id):
    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    conn.execute("INSERT INTO users (username, password_hash, role_id) VALUES (?,?,?)", (username, pwd_hash, role_id))
    conn.commit()
    conn.close()