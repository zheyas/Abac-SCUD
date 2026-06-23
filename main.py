import datetime
import json
import os
import sqlite3
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import Database
from models import User, Building, Policy, Group, AccessEvent
from abac_engine import evaluate_access
from auth import verify_login

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'scud_admin_secret_2025'
Database.init_db()
Database.seed_data()
weather_cache = {}
WEATHER_CACHE_TTL = 600
WEATHER_SSL_CONTEXT = ssl.create_default_context(
    cafile='/etc/ssl/cert.pem' if os.path.exists('/etc/ssl/cert.pem') else None
)

def is_admin():
    user_id = session.get('user_id')
    if not user_id:
        return False
    user = User.get_by_id(user_id)
    return user and user.get('group_id') == 1


def parse_context_datetime(value=None):
    if not value:
        return datetime.datetime.now().astimezone()
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone()


def shift_payload(user, context_datetime=None):
    effective = User.get_effective_shift_status(user, context_datetime)
    return {
        'shift_status': effective,
        'shift_auto': bool(user.get('shift_auto')),
        'shift_days': user.get('shift_days'),
        'shift_start': user.get('shift_start'),
        'shift_end': user.get('shift_end')
    }


def resolve_policy_target(data):
    target_type = data.get('target_type', 'group')
    target_id = int(data.get('target_id') or data.get('group_id') or data.get('role_id'))
    if target_type == 'user':
        user = User.get_by_id(target_id)
        if not user:
            raise ValueError('Пользователь не найден')
        return user['group_id'], user['id']
    if target_type not in ('group', 'role'):
        raise ValueError('Неизвестный тип назначения')
    if not Group.get_by_id(target_id):
        raise ValueError('Группа не найдена')
    return target_id, None


def parse_group_id(data):
    try:
        group_id = int(data.get('group_id', data.get('role_id')))
    except (TypeError, ValueError):
        raise ValueError('Выберите группу')
    if not Group.get_by_id(group_id):
        raise ValueError('Группа не найдена')
    return group_id

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
        shift = shift_payload(user)
        return jsonify({'success': True, 'user': {
            'id': user['id'], 'username': user['username'],
            'group_name': user['group_name'], 'group_id': user['group_id'],
            'role_name': user['group_name'], 'role_id': user['group_id'], **shift
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


@app.route('/api/weather', methods=['GET'])
def api_weather():
    try:
        latitude = float(request.args.get('latitude'))
        longitude = float(request.args.get('longitude'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Некорректные координаты'}), 400
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return jsonify({'error': 'Координаты вне допустимого диапазона'}), 400

    cache_key = (round(latitude, 2), round(longitude, 2))
    cached = weather_cache.get(cache_key)
    if cached and time.monotonic() - cached['stored_at'] < WEATHER_CACHE_TTL:
        return jsonify({**cached['payload'], 'cached': True})

    query = urllib.parse.urlencode({
        'latitude': latitude,
        'longitude': longitude,
        'current': ','.join([
            'temperature_2m', 'apparent_temperature', 'relative_humidity_2m',
            'precipitation', 'rain', 'snowfall', 'weather_code', 'cloud_cover',
            'wind_speed_10m', 'wind_direction_10m', 'is_day'
        ]),
        'timezone': 'auto',
        'forecast_days': 1
    })
    url = f'https://api.open-meteo.com/v1/forecast?{query}'
    try:
        upstream_request = urllib.request.Request(url, headers={'User-Agent': 'SCUD-3D-Map/1.0'})
        with urllib.request.urlopen(upstream_request, timeout=8, context=WEATHER_SSL_CONTEXT) as response:
            data = json.loads(response.read().decode('utf-8'))
        payload = {
            'available': True,
            'latitude': data.get('latitude', latitude),
            'longitude': data.get('longitude', longitude),
            'timezone': data.get('timezone'),
            'current': data.get('current', {}),
            'units': data.get('current_units', {}),
            'updated_at': datetime.datetime.now().astimezone().isoformat()
        }
        weather_cache[cache_key] = {'stored_at': time.monotonic(), 'payload': payload}
        return jsonify(payload)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        if cached:
            return jsonify({**cached['payload'], 'cached': True, 'stale': True})
        return jsonify({'available': False, 'error': 'Погодный сервис временно недоступен', 'details': str(error)}), 502

@app.route('/api/access_status', methods=['POST'])
def api_access_status():
    payload = request.json or {}
    user_id = payload.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    timestamp = payload.get('timestamp')
    try:
        context_datetime = parse_context_datetime(timestamp)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid timestamp'}), 400
    buildings = Building.get_all()
    result = {b['id']: evaluate_access(user, b['id'], context_datetime) for b in buildings}
    return jsonify({'buildings': result, 'user': shift_payload(user, context_datetime)})

@app.route('/api/toggle_shift', methods=['POST'])
def api_toggle_shift():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'no user'}), 400
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'no user'}), 404
    if user.get('shift_auto'):
        return jsonify({'error': 'Смена управляется автоматически по расписанию'}), 409
    new_status = User.toggle_shift(user_id)
    return jsonify({'shift_status': new_status})

@app.route('/api/user_status', methods=['POST'])
def api_user_status():
    payload = request.json or {}
    user_id = payload.get('user_id')
    user = User.get_by_id(user_id)
    if user:
        try:
            context_datetime = parse_context_datetime(payload.get('timestamp'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid timestamp'}), 400
        return jsonify(shift_payload(user, context_datetime))
    return jsonify({'error': 'no user'}), 404


@app.route('/api/entry_attempt', methods=['POST'])
def api_entry_attempt():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Требуется авторизация'}), 401
    payload = request.json or {}
    building_id = payload.get('building_id')
    user = User.get_by_id(user_id)
    building = Building.get_by_id(building_id)
    if not building:
        return jsonify({'error': 'Здание не найдено'}), 404
    try:
        context_datetime = parse_context_datetime(payload.get('timestamp'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid timestamp'}), 400
    decision = evaluate_access(user, building_id, context_datetime)
    event_id = AccessEvent.create(
        user_id, building_id, context_datetime.isoformat(),
        'granted' if decision['access'] else 'denied', decision['reason'],
        decision.get('rule_name'), decision.get('source')
    )
    return jsonify({
        'success': True, 'event_id': event_id, 'building_name': building['name'],
        'username': user['username'], **decision
    })


@app.route('/api/access_events', methods=['GET'])
def api_access_events():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Требуется авторизация'}), 401
    scope_all = request.args.get('scope') == 'all' and is_admin()
    return jsonify(AccessEvent.get_recent(request.args.get('limit', 10), None if scope_all else user_id))

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
    groups = Group.get_all()
    buildings = Building.get_all()
    return render_template('admin_users.html', users=users, groups=groups, buildings=buildings)


@app.route('/admin/groups')
def admin_groups():
    if not is_admin():
        return redirect(url_for('index'))
    return render_template('admin_groups.html', groups=Group.get_all())

@app.route('/admin/policies')
def admin_policies():
    if not is_admin():
        return redirect(url_for('index'))
    policies = Policy.get_all()
    buildings = Building.get_all()
    groups = Group.get_all()
    return render_template('admin_policies.html', policies=policies, buildings=buildings, groups=groups)


@app.route('/admin/events')
def admin_events():
    if not is_admin():
        return redirect(url_for('index'))
    return render_template('admin_events.html', events=AccessEvent.get_recent(100))

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
    try:
        group_id = parse_group_id(data)
        user_id = User.create(
            data['username'], data['password'], group_id, data.get('shift_auto', False),
            data.get('shift_days', 'Mon,Tue,Wed,Thu,Fri'), data.get('shift_start', '08:00'),
            data.get('shift_end', '18:00'), data.get('personal_building_ids', [])
        )
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Пользователь с таким логином уже существует'}), 409
    return jsonify({'success': True, 'id': user_id})

@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
def api_admin_update_user(uid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    if not User.get_by_id(uid):
        return jsonify({'error': 'Пользователь не найден'}), 404
    try:
        group_id = parse_group_id(data)
        User.update(uid, data['username'], group_id, data['is_active'],
                    data.get('password', None), data.get('shift_status'), data.get('shift_auto', False),
                    data.get('shift_days', 'Mon,Tue,Wed,Thu,Fri'), data.get('shift_start', '08:00'),
                    data.get('shift_end', '18:00'), data.get('personal_building_ids'))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Пользователь с таким логином уже существует'}), 409
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def api_admin_delete_user(uid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    User.delete(uid)
    return jsonify({'success': True})


@app.route('/api/admin/groups', methods=['POST'])
def api_admin_create_group():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Укажите название группы'}), 400
    try:
        group_id = Group.create(name, (data.get('description') or '').strip())
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Группа с таким названием уже существует'}), 409
    return jsonify({'success': True, 'id': group_id})


@app.route('/api/admin/groups/<int:gid>', methods=['PUT'])
def api_admin_update_group(gid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    if not Group.get_by_id(gid):
        return jsonify({'error': 'Группа не найдена'}), 404
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Укажите название группы'}), 400
    try:
        Group.update(gid, name, (data.get('description') or '').strip())
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Группа с таким названием уже существует'}), 409
    return jsonify({'success': True})


@app.route('/api/admin/groups/<int:gid>', methods=['DELETE'])
def api_admin_delete_group(gid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    if not Group.get_by_id(gid):
        return jsonify({'error': 'Группа не найдена'}), 404
    if not Group.delete(gid):
        return jsonify({'error': 'Сначала перенесите пользователей в другую группу'}), 409
    return jsonify({'success': True})

@app.route('/api/admin/policies', methods=['POST'])
def api_admin_create_policy():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    try:
        group_id, user_id = resolve_policy_target(data)
    except (TypeError, ValueError) as error:
        return jsonify({'error': str(error)}), 400
    policy_id = Policy.create(
        group_id, data['building_id'], data['days_allowed'], data['time_start'], data['time_end'],
        data.get('requires_shift_active', False), user_id, data.get('name', '').strip(),
        data.get('effect', 'allow'), data.get('is_active', True)
    )
    return jsonify({'success': True, 'id': policy_id})

@app.route('/api/admin/policies/<int:pid>', methods=['PUT'])
def api_admin_update_policy(pid):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    try:
        group_id, user_id = resolve_policy_target(data)
    except (TypeError, ValueError) as error:
        return jsonify({'error': str(error)}), 400
    Policy.update(
        pid, group_id, data['building_id'], data['days_allowed'], data['time_start'], data['time_end'],
        data.get('requires_shift_active', False), user_id, data.get('name', '').strip(),
        data.get('effect', 'allow'), data.get('is_active', True)
    )
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
