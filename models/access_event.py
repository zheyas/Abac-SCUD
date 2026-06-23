from database import Database


class AccessEvent:
    @staticmethod
    def create(user_id, building_id, context_time, result, reason, rule_name=None, source=None):
        conn = Database.get_conn()
        cursor = conn.execute(
            """INSERT INTO access_events
               (user_id, building_id, context_time, result, reason, rule_name, source)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, building_id, context_time, result, reason, rule_name, source)
        )
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        return event_id

    @staticmethod
    def get_recent(limit=20, user_id=None):
        conn = Database.get_conn()
        query = """SELECT e.*, u.username, b.name AS building_name
                   FROM access_events e
                   JOIN users u ON e.user_id = u.id
                   JOIN buildings b ON e.building_id = b.id"""
        params = []
        if user_id is not None:
            query += " WHERE e.user_id=?"
            params.append(user_id)
        query += " ORDER BY e.id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
