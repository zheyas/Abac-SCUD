from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import Database
from models import User, Building, Policy, Role
from abac_engine import evaluate_access
from auth import verify_login

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'scud_admin_secret_2025'
Database.init_db()
Database.seed_data()

def is_admin():
    user_id = session.get('user_id')
    if not user_id:
        return False
    user = User.get_by_id(user_id)
    return user and user.get('role_id') == 1

# ------------------- Главная страница (3D карта) -------------------
@app.route('/')
def index():
    return render_template('index.html')

# ------------------- API для 3D-карты -------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    user = verify_login(data.get('username'), data.get('password'))
    if user:
        session['user_id'] = user['id']
        return jsonify({'success': True, 'user': {
            'id': user['id'], 'username': user['username'],
            'role_name': user['role_name'], 'shift_status': user['shift_status'],
            'role_id': user['role_id']
        }})
    return jsonify({'success': False, 'error': 'Неверный логин или пароль'})

@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.clear()
    if request.method == 'GET':
        return redirect(url_for('index'))
    return jsonify({'success': True})

@app.route('/api/buildings', methods=['GET'])
def api_buildings():
    return jsonify(Building.get_all())

@app.route('/api/access_status', methods=['POST'])
def api_access_status():
    payload = request.json or {}
    user_id = payload.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    context_datetime = None
    timestamp = payload.get('timestamp')
    if timestamp:
        try:
            # ISO 8601 приходит из браузера вместе с текущим временем симуляции.
            context_datetime = __import__('datetime').datetime.fromisoformat(
                timestamp.replace('Z', '+00:00')
            ).astimezone()
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid timestamp'}), 400
    buildings = Building.get_all()
    result = {b['id']: evaluate_access(user, b['id'], context_datetime) for b in buildings}
    return jsonify(result)

@app.route('/api/toggle_shift', methods=['POST'])
def api_toggle_shift():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'no user'}), 400
    new_status = User.toggle_shift(user_id)
    return jsonify({'shift_status': new_status})

@app.route('/api/user_status', methods=['POST'])
def api_user_status():
    user_id = request.json.get('user_id')
    user = User.get_by_id(user_id)
    if user:
        return jsonify({'shift_status': user['shift_status']})
    return jsonify({'error': 'no user'}), 404

# ------------------- Административные страницы -------------------
@app.route('/admin')
def admin_dashboard():
    if not is_admin():
        return redirect(url_for('index'))
    return redirect(url_for('admin_buildings'))

@app.route('/admin/buildings')
def admin_buildings():
    if not is_admin():
        return redirect(url_for('index'))
    buildings = Building.get_all()
    return render_template('admin_buildings.html', buildings=buildings)

@app.route('/admin/users')
def admin_users():
    if not is_admin():
        return redirect(url_for('index'))
    users = User.get_all()
    roles = Role.get_all()
    return render_template('admin_users.html', users=users, roles=roles)

@app.route('/admin/policies')
def admin_policies():
    if not is_admin():
        return redirect(url_for('index'))
    policies = Policy.get_all()
    buildings = Building.get_all()
    roles = Role.get_all()
    return render_template('admin_policies.html', policies=policies, buildings=buildings, roles=roles)

# ------------------- API для администрирования (CRUD) -------------------
@app.route('/api/admin/buildings', methods=['POST'])
def api_admin_create_building():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    building_id = Building.create(
        data['name'], data['color_hex'], data['x'], data['y'],
        data['w'], data['h'], data['depth'], data['is_accessible_to_all'],
        data.get('open_days', 'Mon,Tue,Wed,Thu,Fri'), data.get('open_time', '08:00'),
        data.get('close_time', '20:00'), data.get('is_24_hours', False)
    )
    return jsonify({'success': True, 'id': building_id})

@app.route('/api/admin/buildings/<int:bid>', methods=['PUT'])
def api_admin_update_building(bid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    Building.update(bid, data['name'], data['color_hex'], data['x'], data['y'],
                    data['w'], data['h'], data['depth'], data['is_accessible_to_all'],
                    data.get('open_days', 'Mon,Tue,Wed,Thu,Fri'), data.get('open_time', '08:00'),
                    data.get('close_time', '20:00'), data.get('is_24_hours', False))
    return jsonify({'success': True})

@app.route('/api/admin/buildings/<int:bid>', methods=['DELETE'])
def api_admin_delete_building(bid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    Building.delete(bid)
    return jsonify({'success': True})

@app.route('/api/admin/users', methods=['POST'])
def api_admin_create_user():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    User.create(data['username'], data['password'], data['role_id'])
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
def api_admin_update_user(uid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    User.update(uid, data['username'], data['role_id'], data['is_active'],
                data.get('password', None), data.get('shift_status'))
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def api_admin_delete_user(uid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    User.delete(uid)
    return jsonify({'success': True})

@app.route('/api/admin/policies', methods=['POST'])
def api_admin_create_policy():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    Policy.create(data['role_id'], data['building_id'], data['days_allowed'],
                  data['time_start'], data['time_end'], data['requires_shift_active'])
    return jsonify({'success': True})

@app.route('/api/admin/policies/<int:pid>', methods=['PUT'])
def api_admin_update_policy(pid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    Policy.update(pid, data['role_id'], data['building_id'], data['days_allowed'],
                  data['time_start'], data['time_end'], data['requires_shift_active'])
    return jsonify({'success': True})

@app.route('/api/admin/policies/<int:pid>', methods=['DELETE'])
def api_admin_delete_policy(pid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    Policy.delete(pid)
    return jsonify({'success': True})

# ------------------- Запуск -------------------
if __name__ == '__main__':
    print("🌐 Сервер СКУД запущен: http://127.0.0.1:8080/")
    print("🔑 Администратор: admin / admin123")
    app.run(host='127.0.0.1', port=8080, debug=True)
