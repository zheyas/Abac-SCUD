from flask import Flask, request, jsonify, render_template_string
from models.role import get_all as get_roles, create as create_role
from models.building import get_all as get_buildings, create as create_building
from models.policy import get_all as get_policies, create as create_policy
from models.user import create as create_user, toggle_shift

app = Flask(__name__)

ADMIN_HTML = """
<!DOCTYPE html>
<html><head><title>СКУД Админ</title><style>body{font-family:system-ui;max-width:900px;margin:20px auto;}</style></head>
<body>
<h1>🔐 Административная панель СКУД</h1>
<button onclick="loadData()">🔄 Обновить</button>
<div id="data"></div>
<script>
async function loadData(){
    const res = await fetch('/api/data');
    const d = await res.json();
    document.getElementById('data').innerHTML = `
        <h3>Пользователи</h3><pre>${JSON.stringify(d.users,null,2)}</pre>
        <h3>Здания</h3><pre>${JSON.stringify(d.buildings,null,2)}</pre>
        <h3>Политики</h3><pre>${JSON.stringify(d.policies,null,2)}</pre>
    `;
}
loadData();
</script>
</body></html>
"""

@app.route("/")
def admin_ui(): return render_template_string(ADMIN_HTML)

@app.route("/api/data")
def api_data():
    from models.user import get_by_username # импортируем локально для избежания циклов
    # Упрощённый экспорт без паролей
    import sqlite3; conn = sqlite3.connect("abac_scud.db"); conn.row_factory = sqlite3.Row
    users = [dict(u) for u in conn.execute("SELECT id, username, role_id, shift_status FROM users").fetchall()]
    buildings = [dict(b) for b in conn.execute("SELECT * FROM buildings").fetchall()]
    policies = [dict(p) for p in conn.execute("SELECT * FROM policies").fetchall()]
    conn.close()
    return jsonify({"users": users, "buildings": buildings, "policies": policies})

@app.route("/api/user/<int:uid>/toggle", methods=["POST"])
def toggle(uid): return jsonify({"shift": toggle_shift(uid)})

@app.route("/api/policy", methods=["POST"])
def add_policy():
    data = request.json
    create_policy(data["role_id"], data["building_id"], data["days"], data["t_start"], data["t_end"], data["req_shift"])
    return jsonify({"status":"ok"})