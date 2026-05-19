import sqlite3
import os

DB_PATH = "abac_scud.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 1, shift_status TEXT DEFAULT 'inactive',
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, color_hex TEXT DEFAULT '#888',
            x INTEGER DEFAULT 50, y INTEGER DEFAULT 50, w INTEGER DEFAULT 120,
            h INTEGER DEFAULT 90, depth INTEGER DEFAULT 30, is_accessible_to_all BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY, role_id INTEGER NOT NULL, building_id INTEGER NOT NULL,
            days_allowed TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri', time_start TEXT DEFAULT '08:00',
            time_end TEXT DEFAULT '18:00', requires_shift_active BOOLEAN DEFAULT 1,
            FOREIGN KEY(role_id) REFERENCES roles(id), FOREIGN KEY(building_id) REFERENCES buildings(id)
        );
    """)
    conn.commit()
    conn.close()


def seed_data():
    conn = get_conn()
    if conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0:
        conn.executemany("INSERT INTO roles (name) VALUES (?)", [("Администратор",), ("Производство",), ("Охрана",)])
        conn.commit()

        buildings = [
            ("Администрация", "#3498db", 200, 200, 140, 100, 35, False),
            ("Производство", "#e67e22", 450, 150, 180, 110, 40, False),
            ("Столовая", "#2ecc71", 750, 250, 130, 90, 30, False),
            ("Бункер", "#7f8c8d", 350, 400, 150, 80, 25, True),
            ("Убежище", "#95a5a6", 650, 380, 120, 70, 25, True)
        ]
        conn.executemany(
            "INSERT INTO buildings (name, color_hex, x, y, w, h, depth, is_accessible_to_all) VALUES (?,?,?,?,?,?,?,?)",
            buildings)
        conn.commit()

        policies = [
            (1, 1, "Mon,Tue,Wed,Thu,Fri", "09:00", "18:00", True),
            (2, 2, "Mon,Tue,Wed,Thu,Fri,Sat,Sun", "07:00", "23:00", True),
            (2, 3, "All", "00:00", "23:59", False),
            (1, 3, "All", "07:00", "22:00", False)
        ]
        conn.executemany(
            "INSERT INTO policies (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active) VALUES (?,?,?,?,?,?)",
            policies)
        conn.commit()

        import bcrypt
        pwd_admin = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        pwd_prod = bcrypt.hashpw("prod123".encode(), bcrypt.gensalt()).decode()
        conn.executemany("INSERT INTO users (username, password_hash, role_id, shift_status) VALUES (?,?,?,?)",
                         [("admin", pwd_admin, 1, "active"), ("worker", pwd_prod, 2, "inactive")])
        conn.commit()
    conn.close()