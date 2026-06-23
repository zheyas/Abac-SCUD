import sqlite3

DB_PATH = "abac_scud.db"

class Database:
    @staticmethod
    def get_conn():
        """Всегда создаёт новое соединение (потокобезопасно)"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def init_db():
        conn = Database.get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role_id INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1, shift_status TEXT DEFAULT 'inactive',
                FOREIGN KEY(role_id) REFERENCES roles(id)
            );
            CREATE TABLE IF NOT EXISTS buildings (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, color_hex TEXT DEFAULT '#888',
                x INTEGER DEFAULT 200, y INTEGER DEFAULT 200, w INTEGER DEFAULT 120,
                h INTEGER DEFAULT 90, depth INTEGER DEFAULT 30, is_accessible_to_all BOOLEAN DEFAULT 0,
                open_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri', open_time TEXT DEFAULT '08:00',
                close_time TEXT DEFAULT '20:00', is_24_hours BOOLEAN DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY, role_id INTEGER NOT NULL, building_id INTEGER NOT NULL,
                days_allowed TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri', time_start TEXT DEFAULT '08:00',
                time_end TEXT DEFAULT '18:00', requires_shift_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(role_id) REFERENCES roles(id), FOREIGN KEY(building_id) REFERENCES buildings(id)
            );
            CREATE TABLE IF NOT EXISTS access_events (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                building_id INTEGER NOT NULL,
                attempted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                context_time TEXT NOT NULL,
                result TEXT NOT NULL,
                reason TEXT NOT NULL,
                rule_name TEXT,
                source TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(building_id) REFERENCES buildings(id)
            );
            CREATE TABLE IF NOT EXISTS user_building_access (
                user_id INTEGER NOT NULL,
                building_id INTEGER NOT NULL,
                granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, building_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(building_id) REFERENCES buildings(id)
            );
        """)
        # Неблокирующая миграция для баз, созданных предыдущей версией приложения.
        building_columns = {row[1] for row in conn.execute("PRAGMA table_info(buildings)").fetchall()}
        migrations = {
            "open_days": "ALTER TABLE buildings ADD COLUMN open_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri'",
            "open_time": "ALTER TABLE buildings ADD COLUMN open_time TEXT DEFAULT '08:00'",
            "close_time": "ALTER TABLE buildings ADD COLUMN close_time TEXT DEFAULT '20:00'",
            "is_24_hours": "ALTER TABLE buildings ADD COLUMN is_24_hours BOOLEAN DEFAULT 0",
        }
        for column, statement in migrations.items():
            if column not in building_columns:
                conn.execute(statement)

        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        user_migrations = {
            "shift_auto": "ALTER TABLE users ADD COLUMN shift_auto BOOLEAN DEFAULT 0",
            "shift_days": "ALTER TABLE users ADD COLUMN shift_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri'",
            "shift_start": "ALTER TABLE users ADD COLUMN shift_start TEXT DEFAULT '08:00'",
            "shift_end": "ALTER TABLE users ADD COLUMN shift_end TEXT DEFAULT '18:00'",
        }
        for column, statement in user_migrations.items():
            if column not in user_columns:
                conn.execute(statement)

        policy_columns = {row[1] for row in conn.execute("PRAGMA table_info(policies)").fetchall()}
        policy_migrations = {
            "user_id": "ALTER TABLE policies ADD COLUMN user_id INTEGER DEFAULT NULL",
            "name": "ALTER TABLE policies ADD COLUMN name TEXT DEFAULT ''",
            "effect": "ALTER TABLE policies ADD COLUMN effect TEXT DEFAULT 'allow'",
            "is_active": "ALTER TABLE policies ADD COLUMN is_active BOOLEAN DEFAULT 1",
        }
        for column, statement in policy_migrations.items():
            if column not in policy_columns:
                conn.execute(statement)

        role_columns = {row[1] for row in conn.execute("PRAGMA table_info(roles)").fetchall()}
        if "description" not in role_columns:
            conn.execute("ALTER TABLE roles ADD COLUMN description TEXT DEFAULT ''")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_access_events_time ON access_events(attempted_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_policies_user_building ON policies(user_id, building_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_building_access_user ON user_building_access(user_id)")
        conn.commit()
        conn.close()

    @staticmethod
    def seed_data():
        import bcrypt
        conn = Database.get_conn()
        role_names = ["Администратор", "Производство", "Охрана", "Инженер", "Гость", "Медслужба"]
        conn.executemany("INSERT OR IGNORE INTO roles (name) VALUES (?)", [(name,) for name in role_names])

        if conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0] == 0:
            buildings = [
                ("Администрация", "#a55d35", 200, 200, 140, 100, 35, False, "Mon,Tue,Wed,Thu,Fri", "08:00", "19:00", False),
                ("Производство", "#7a8c8c", 450, 150, 180, 110, 40, False, "All", "06:00", "23:00", False),
                ("Столовая", "#6a9c78", 750, 250, 130, 90, 30, False, "All", "07:00", "22:00", False),
                ("Бункер", "#5a5e6b", 350, 400, 150, 80, 25, True, "All", "00:00", "23:59", True),
                ("Убежище", "#8b7a6b", 650, 380, 120, 70, 25, True, "All", "00:00", "23:59", True)
            ]
            conn.executemany(
                "INSERT INTO buildings (name, color_hex, x, y, w, h, depth, is_accessible_to_all, open_days, open_time, close_time, is_24_hours) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                buildings)

        schedule_version = conn.execute("SELECT value FROM app_meta WHERE key='building_schedule_version'").fetchone()
        if not schedule_version:
            schedules = {
                "Администрация": ("Mon,Tue,Wed,Thu,Fri", "08:00", "19:00", False),
                "Производство": ("All", "06:00", "23:00", False),
                "Столовая": ("All", "07:00", "22:00", False),
                "Бункер": ("All", "00:00", "23:59", True),
                "Убежище": ("All", "00:00", "23:59", True),
                "Новостройка": ("Mon,Tue,Wed,Thu,Fri,Sat", "07:00", "20:00", False),
            }
            for name, (days, opening, closing, around_clock) in schedules.items():
                conn.execute(
                    "UPDATE buildings SET open_days=?, open_time=?, close_time=?, is_24_hours=? WHERE name=?",
                    (days, opening, closing, around_clock, name)
                )
            conn.execute("INSERT INTO app_meta (key, value) VALUES ('building_schedule_version', '1')")

        roles = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM roles")}
        demo_users = [
            ("admin", "admin123", "Администратор", "active"),
            ("worker", "prod123", "Производство", "inactive"),
            ("guard", "guard123", "Охрана", "active"),
            ("engineer", "engineer123", "Инженер", "active"),
            ("medic", "medic123", "Медслужба", "inactive"),
            ("guest", "guest123", "Гость", "inactive"),
        ]
        for username, password, role_name, shift_status in demo_users:
            if not conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                conn.execute(
                    "INSERT INTO users (username, password_hash, role_id, shift_status) VALUES (?,?,?,?)",
                    (username, password_hash, roles[role_name], shift_status)
                )

        auto_shift_version = conn.execute("SELECT value FROM app_meta WHERE key='auto_shift_version'").fetchone()
        if not auto_shift_version:
            auto_schedules = {
                "worker": ("Mon,Tue,Wed,Thu,Fri", "07:00", "19:00"),
                "guard": ("All", "00:00", "23:59"),
                "engineer": ("Mon,Tue,Wed,Thu,Fri,Sat", "07:00", "21:00"),
            }
            for username, (days, start, end) in auto_schedules.items():
                conn.execute(
                    "UPDATE users SET shift_auto=1, shift_days=?, shift_start=?, shift_end=? WHERE username=?",
                    (days, start, end, username)
                )
            conn.execute("INSERT INTO app_meta (key, value) VALUES ('auto_shift_version', '1')")

        buildings = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM buildings")}
        policy_specs = [
            ("Администратор", "Администрация", "All", "00:00", "23:59", False),
            ("Администратор", "Производство", "All", "00:00", "23:59", False),
            ("Администратор", "Столовая", "All", "00:00", "23:59", False),
            ("Производство", "Производство", "All", "06:00", "23:00", True),
            ("Производство", "Столовая", "All", "07:00", "22:00", False),
            ("Охрана", "Администрация", "All", "00:00", "23:59", True),
            ("Охрана", "Производство", "All", "00:00", "23:59", True),
            ("Инженер", "Производство", "Mon,Tue,Wed,Thu,Fri,Sat", "07:00", "21:00", True),
            ("Инженер", "Администрация", "Mon,Tue,Wed,Thu,Fri", "09:00", "18:00", True),
            ("Инженер", "Новостройка", "Mon,Tue,Wed,Thu,Fri,Sat", "07:00", "20:00", True),
            ("Гость", "Администрация", "Mon,Tue,Wed,Thu,Fri", "10:00", "17:00", False),
            ("Гость", "Столовая", "Mon,Tue,Wed,Thu,Fri", "11:00", "15:00", False),
            ("Медслужба", "Администрация", "All", "00:00", "23:59", False),
            ("Медслужба", "Производство", "All", "00:00", "23:59", False),
        ]
        # Аварийные объекты доступны всем ролям круглосуточно, даже если старую
        # базу пользователь ранее настроил без флага общего доступа.
        policy_specs.extend(
            (role_name, building_name, "All", "00:00", "23:59", False)
            for role_name in role_names
            for building_name in ("Бункер", "Убежище")
        )
        for role_name, building_name, days, start, end, shift in policy_specs:
            if building_name not in buildings:
                continue
            values = (roles[role_name], buildings[building_name], days, start, end, shift)
            exists = conn.execute(
                "SELECT 1 FROM policies WHERE role_id=? AND building_id=? AND days_allowed=? AND time_start=? AND time_end=? AND requires_shift_active=?",
                values
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO policies (role_id, building_id, days_allowed, time_start, time_end, requires_shift_active) VALUES (?,?,?,?,?,?)",
                    values
                )
        conn.execute(
            """UPDATE policies
               SET name = CASE
                   WHEN name IS NULL OR name = '' THEN 'Доступ: ' ||
                       COALESCE((SELECT name FROM roles WHERE roles.id = policies.role_id), 'Группа') ||
                       ' → ' || COALESCE((SELECT name FROM buildings WHERE buildings.id = policies.building_id), 'Объект')
                   ELSE name END"""
        )
        conn.commit()
        conn.close()
