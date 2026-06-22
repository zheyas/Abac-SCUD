from database import Database

class Building:
    @staticmethod
    def get_all():
        conn = Database.get_conn()
        rows = conn.execute("SELECT * FROM buildings").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(building_id):
        conn = Database.get_conn()
        row = conn.execute("SELECT * FROM buildings WHERE id=?", (building_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(name, color_hex, x, y, w, h, depth, is_all,
               open_days="Mon,Tue,Wed,Thu,Fri", open_time="08:00",
               close_time="20:00", is_24_hours=False):
        conn = Database.get_conn()
        conn.execute(
            "INSERT INTO buildings (name, color_hex, x, y, w, h, depth, is_accessible_to_all, open_days, open_time, close_time, is_24_hours) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, color_hex, x, y, w, h, depth, is_all, open_days, open_time, close_time, is_24_hours))
        conn.commit()
        building_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return building_id

    @staticmethod
    def update(building_id, name, color_hex, x, y, w, h, depth, is_all,
               open_days="Mon,Tue,Wed,Thu,Fri", open_time="08:00",
               close_time="20:00", is_24_hours=False):
        conn = Database.get_conn()
        conn.execute(
            "UPDATE buildings SET name=?, color_hex=?, x=?, y=?, w=?, h=?, depth=?, is_accessible_to_all=?, open_days=?, open_time=?, close_time=?, is_24_hours=? WHERE id=?",
            (name, color_hex, x, y, w, h, depth, is_all, open_days, open_time, close_time, is_24_hours, building_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(building_id):
        conn = Database.get_conn()
        conn.execute("DELETE FROM access_events WHERE building_id=?", (building_id,))
        conn.execute("DELETE FROM policies WHERE building_id=?", (building_id,))
        conn.execute("DELETE FROM buildings WHERE id=?", (building_id,))
        conn.commit()
        conn.close()
