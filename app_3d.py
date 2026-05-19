import sqlite3
import threading
import time
import datetime
import json
from flask import Flask, render_template_string, request, jsonify, session
import bcrypt

# ---------- База данных (без изменений) ----------
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
            ("Администрация", "#a55d35", 200, 200, 140, 100, 35, False),  # кирпичный цвет
            ("Производство", "#7a8c8c", 450, 150, 180, 110, 40, False),  # индустриальный
            ("Столовая", "#6a9c78", 750, 250, 130, 90, 30, False),  # светлая зелень
            ("Бункер", "#5a5e6b", 350, 400, 150, 80, 25, True),  # бетон
            ("Убежище", "#8b7a6b", 650, 380, 120, 70, 25, True)  # камень
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

        pwd_admin = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        pwd_prod = bcrypt.hashpw("prod123".encode(), bcrypt.gensalt()).decode()
        conn.executemany("INSERT INTO users (username, password_hash, role_id, shift_status) VALUES (?,?,?,?)",
                         [("admin", pwd_admin, 1, "active"), ("worker", pwd_prod, 2, "inactive")])
        conn.commit()
    conn.close()


# ---------- Модели (без изменений) ----------
def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute(
        "SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.username=?",
        (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_login(username, password):
    user = get_user_by_username(username)
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None


def toggle_shift(user_id):
    conn = get_conn()
    curr = conn.execute("SELECT shift_status FROM users WHERE id=?", (user_id,)).fetchone()
    new_status = "inactive" if curr["shift_status"] == "active" else "active"
    conn.execute("UPDATE users SET shift_status=? WHERE id=?", (new_status, user_id))
    conn.commit()
    conn.close()
    return new_status


def get_all_buildings():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM buildings").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_policies_by_role_building(role_id, building_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM policies WHERE role_id=? AND building_id=?", (role_id, building_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_access(user, building_id):
    building = next((b for b in get_all_buildings() if b["id"] == building_id), None)
    if not building:
        return False
    if building["is_accessible_to_all"]:
        return True
    if not user.get("is_active", True):
        return False

    policies = get_policies_by_role_building(user["role_id"], building_id)
    now = datetime.datetime.now()
    ctx_time = now.time()
    ctx_day = now.strftime("%a")
    for p in policies:
        if p["requires_shift_active"] and user["shift_status"] != "active":
            continue
        days = [d.strip() for d in p["days_allowed"].split(",")]
        if "All" not in days and ctx_day not in days:
            continue
        try:
            t_start = datetime.datetime.strptime(p["time_start"], "%H:%M").time()
            t_end = datetime.datetime.strptime(p["time_end"], "%H:%M").time()
            if t_start <= ctx_time <= t_end:
                return True
        except ValueError:
            continue
    return False


# ---------- Flask приложение с красивой 3D сценой ----------
app = Flask(__name__)
app.secret_key = 'beautiful3dscud'

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>СКУД – Премиум 3D визуализация</title>
    <style>
        body { margin: 0; overflow: hidden; font-family: 'Segoe UI', 'Roboto', sans-serif; }
        #info {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0,0,0,0.65);
            backdrop-filter: blur(8px);
            color: white;
            padding: 14px 24px;
            border-radius: 16px;
            pointer-events: none;
            z-index: 10;
            border-left: 4px solid #ffaa44;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            font-weight: 500;
        }
        #info span { color: #ffaa44; font-weight: bold; }
        .status-panel {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.65);
            backdrop-filter: blur(8px);
            border-radius: 16px;
            padding: 14px 24px;
            color: white;
            text-align: right;
            font-size: 16px;
            pointer-events: none;
            z-index: 10;
            border-right: 3px solid #88ccff;
            font-weight: 500;
        }
        .status-panel span { color: #88ccff; }
        #controls {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(0,0,0,0.5);
            backdrop-filter: blur(5px);
            border-radius: 12px;
            padding: 8px 16px;
            font-size: 12px;
            color: #ccc;
            font-family: monospace;
            pointer-events: none;
        }
        #toggle-shift-btn {
            position: absolute;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #ff9800, #f57c00);
            color: white;
            border: none;
            padding: 12px 28px;
            border-radius: 40px;
            font-weight: bold;
            cursor: pointer;
            font-size: 16px;
            z-index: 20;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            transition: transform 0.1s, box-shadow 0.2s;
            pointer-events: auto;
            font-family: inherit;
        }
        #toggle-shift-btn:hover { background: linear-gradient(135deg, #ffb74d, #ff9800); box-shadow: 0 6px 18px rgba(0,0,0,0.4); }
        #toggle-shift-btn:active { transform: scale(0.96); }
        .login-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        .login-card {
            background: rgba(30,30,45,0.95);
            padding: 40px;
            border-radius: 32px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            width: 340px;
            text-align: center;
            color: white;
            border-top: 4px solid #ffaa44;
        }
        .login-card h2 { margin-bottom: 20px; font-weight: 600; }
        .login-card input {
            width: 100%;
            padding: 14px;
            margin: 12px 0;
            background: #2a2a3a;
            border: 1px solid #4a4a5a;
            border-radius: 12px;
            color: white;
            font-size: 16px;
            outline: none;
            transition: 0.2s;
        }
        .login-card input:focus { border-color: #ffaa44; box-shadow: 0 0 8px rgba(255,170,68,0.5); }
        .login-card button {
            background: #ffaa44;
            color: #1e1e2f;
            border: none;
            padding: 14px;
            width: 100%;
            border-radius: 40px;
            font-size: 18px;
            cursor: pointer;
            margin-top: 10px;
            font-weight: bold;
            transition: 0.2s;
        }
        .login-card button:hover { background: #ffbb55; transform: scale(1.02); }
        .error-msg { color: #ff7777; margin-top: 12px; font-size: 14px; }
        .demo-note { margin-top: 20px; font-size: 12px; color: #aaa; }
    </style>
</head>
<body>
    <div id="info">
        🏢 <strong>СКУД – ABAC контроль доступа</strong> &nbsp;|&nbsp; 👤 <span id="username_display"></span> &nbsp;|&nbsp; 🎭 <span id="role_display"></span> &nbsp;|&nbsp; 🔄 Смена: <span id="shift_status_display"></span>
    </div>
    <div class="status-panel">
        📅 <span id="current_date"></span><br>
        ⏰ <span id="current_time"></span>
    </div>
    <div id="controls">
        🖱️ Мышь: вращение | ПКМ: панорама | Колёсико: масштаб | ✨ 3D сцена с тенями и текстурами
    </div>
    <button id="toggle-shift-btn">🔄 Переключить смену</button>

    <div id="login-overlay" class="login-overlay">
        <div class="login-card">
            <h2>🔐 Вход в СКУД</h2>
            <input type="text" id="login-username" placeholder="Логин" autocomplete="off">
            <input type="password" id="login-password" placeholder="Пароль">
            <button id="login-btn">Войти</button>
            <div id="login-error" class="error-msg"></div>
            <div class="demo-note">demo: admin / admin123 &nbsp;|&nbsp; worker / prod123</div>
        </div>
    </div>

    <script type="importmap">
        {
            "imports": {
                "three": "https://unpkg.com/three@0.128.0/build/three.module.js",
                "three/addons/": "https://unpkg.com/three@0.128.0/examples/jsm/"
            }
        }
    </script>

    <script type="module">
        import * as THREE from 'three';
        import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
        import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

        // --- Глобальные переменные ---
        let scene, camera, renderer, labelRenderer, controls;
        let buildingsMeshes = [];
        let currentUser = null;
        let intervalId = null;
        let treesGroup = null;

        // --- Процедурные текстуры ---
        function createBrickTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#b5651e';
            ctx.fillRect(0, 0, 512, 512);
            ctx.fillStyle = '#8b4513';
            const brickW = 64, brickH = 32;
            for (let x = 0; x < 512; x += brickW) {
                for (let y = 0; y < 512; y += brickH) {
                    const offset = (y / brickH) % 2 === 0 ? 0 : brickW/2;
                    ctx.fillRect(x + offset, y, brickW-2, brickH-2);
                }
            }
            ctx.strokeStyle = '#c27e3a';
            ctx.lineWidth = 2;
            for (let x = 0; x <= 512; x += brickW) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, 512);
                ctx.stroke();
            }
            for (let y = 0; y <= 512; y += brickH) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(512, y);
                ctx.stroke();
            }
            const texture = new THREE.CanvasTexture(canvas);
            texture.wrapS = THREE.RepeatWrapping;
            texture.wrapT = THREE.RepeatWrapping;
            texture.repeat.set(2, 2);
            return texture;
        }

        function createConcreteTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#a0a0a0';
            ctx.fillRect(0, 0, 512, 512);
            for (let i = 0; i < 8000; i++) {
                ctx.fillStyle = `rgba(80,80,80,${Math.random() * 0.5})`;
                ctx.fillRect(Math.random()*512, Math.random()*512, 2, 2);
            }
            return new THREE.CanvasTexture(canvas);
        }

        function createMetalTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#7a8c8c';
            ctx.fillRect(0, 0, 512, 512);
            for (let i = 0; i < 2000; i++) {
                ctx.fillStyle = `rgba(200,200,200,${Math.random() * 0.3})`;
                ctx.fillRect(Math.random()*512, Math.random()*512, 3, 1);
            }
            const tex = new THREE.CanvasTexture(canvas);
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            tex.repeat.set(3, 3);
            return tex;
        }

        function createWoodTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#c2a15b';
            ctx.fillRect(0, 0, 512, 512);
            for (let i = 0; i < 300; i++) {
                ctx.beginPath();
                ctx.moveTo(0, i*2);
                ctx.lineTo(512, i*2);
                ctx.strokeStyle = `rgba(80,50,20,${Math.random() * 0.6})`;
                ctx.lineWidth = 2+Math.random()*3;
                ctx.stroke();
            }
            return new THREE.CanvasTexture(canvas);
        }

        function createGrassTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 1024;
            canvas.height = 1024;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#5c9e3e';
            ctx.fillRect(0, 0, 1024, 1024);
            for (let i = 0; i < 15000; i++) {
                ctx.fillStyle = `rgba(80,130,40,${Math.random() * 0.7})`;
                ctx.fillRect(Math.random()*1024, Math.random()*1024, 2, Math.random()*6);
            }
            const tex = new THREE.CanvasTexture(canvas);
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            tex.repeat.set(8, 8);
            return tex;
        }

        function createLeafTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#3c9e3c';
            ctx.fillRect(0, 0, 256, 256);
            ctx.fillStyle = '#2a7a2a';
            for (let i = 0; i < 500; i++) {
                ctx.beginPath();
                ctx.arc(Math.random()*256, Math.random()*256, Math.random()*8+2, 0, Math.PI*2);
                ctx.fill();
            }
            return new THREE.CanvasTexture(canvas);
        }

        // --- Создание дерева (ствол + крона) ---
        function createTree(x, z) {
            const group = new THREE.Group();
            const trunkMat = new THREE.MeshStandardMaterial({ color: 0x8B5A2B, roughness: 0.7, metalness: 0.1 });
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(4, 5, 8, 8), trunkMat);
            trunk.position.y = 4;
            trunk.castShadow = true;
            trunk.receiveShadow = true;
            group.add(trunk);

            const leafMat = new THREE.MeshStandardMaterial({ color: 0x5a9e4e, roughness: 0.4, metalness: 0.05 });
            const leaf1 = new THREE.Mesh(new THREE.SphereGeometry(5, 16, 16), leafMat);
            leaf1.position.y = 10;
            leaf1.castShadow = true;
            const leaf2 = new THREE.Mesh(new THREE.SphereGeometry(4, 16, 16), leafMat);
            leaf2.position.y = 14;
            leaf2.castShadow = true;
            const leaf3 = new THREE.Mesh(new THREE.SphereGeometry(3, 16, 16), leafMat);
            leaf3.position.y = 17;
            leaf3.castShadow = true;
            group.add(leaf1, leaf2, leaf3);
            group.position.set(x, 0, z);
            return group;
        }

        // --- Инициализация сцены ---
        function initScene() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87CEEB);
            scene.fog = new THREE.FogExp2(0x87CEEB, 0.0004);

            camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 2000);
            camera.position.set(600, 500, 800);
            camera.lookAt(400, 0, 300);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            renderer.setPixelRatio(window.devicePixelRatio);
            document.body.appendChild(renderer.domElement);

            labelRenderer = new CSS2DRenderer();
            labelRenderer.setSize(window.innerWidth, window.innerHeight);
            labelRenderer.domElement.style.position = 'absolute';
            labelRenderer.domElement.style.top = '0px';
            labelRenderer.domElement.style.left = '0px';
            labelRenderer.domElement.style.pointerEvents = 'none';
            document.body.appendChild(labelRenderer.domElement);

            controls = new OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.rotateSpeed = 0.8;
            controls.zoomSpeed = 1.2;
            controls.panSpeed = 0.8;
            controls.target.set(400, 100, 300);

            // --- Освещение ---
            const ambientLight = new THREE.AmbientLight(0x5c6e7e, 0.55);
            scene.add(ambientLight);
            const sunLight = new THREE.DirectionalLight(0xfff5e0, 1.2);
            sunLight.position.set(300, 400, 200);
            sunLight.castShadow = true;
            sunLight.receiveShadow = true;
            sunLight.shadow.mapSize.width = 2048;
            sunLight.shadow.mapSize.height = 2048;
            sunLight.shadow.camera.near = 0.5;
            sunLight.shadow.camera.far = 1000;
            sunLight.shadow.camera.left = -300;
            sunLight.shadow.camera.right = 300;
            sunLight.shadow.camera.top = 300;
            sunLight.shadow.camera.bottom = -300;
            scene.add(sunLight);

            const fillLight = new THREE.PointLight(0x88aaff, 0.4);
            fillLight.position.set(-100, 200, 400);
            scene.add(fillLight);
            const rimLight = new THREE.PointLight(0xffaa66, 0.3);
            rimLight.position.set(100, 150, -250);
            scene.add(rimLight);

            // --- Земля с текстурой травы ---
            const groundMat = new THREE.MeshStandardMaterial({ map: createGrassTexture(), roughness: 0.8, metalness: 0.05 });
            const ground = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200), groundMat);
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = -2;
            ground.receiveShadow = true;
            scene.add(ground);

            // --- Дорожки (опционально) ---
            const pathMat = new THREE.MeshStandardMaterial({ color: 0xaa9a7a, roughness: 0.9 });
            const path = new THREE.Mesh(new THREE.PlaneGeometry(80, 400), pathMat);
            path.rotation.x = -Math.PI / 2;
            path.position.set(400, -1.8, 200);
            path.receiveShadow = true;
            scene.add(path);

            // --- Деревья вокруг зданий ---
            const treePositions = [
                [150, 150], [160, 200], [140, 260], [500, 80], [520, 130], [480, 210],
                [700, 300], [720, 350], [680, 420], [250, 480], [300, 510], [350, 490],
                [800, 80], [850, 120], [900, 180], [80, 400], [100, 450], [50, 500]
            ];
            treePositions.forEach(pos => {
                const tree = createTree(pos[0], pos[1]);
                scene.add(tree);
            });

            // --- Небольшие кусты (простые сферы) ---
            const bushMat = new THREE.MeshStandardMaterial({ color: 0x5c9e3c });
            for (let i = 0; i < 200; i++) {
                const bush = new THREE.Mesh(new THREE.SphereGeometry(1.5 + Math.random()*1.5, 6), bushMat);
                const x = Math.random() * 1000 + 50;
                const z = Math.random() * 700 + 50;
                bush.position.set(x, -1, z);
                bush.castShadow = true;
                bush.receiveShadow = true;
                scene.add(bush);
            }

            // --- Облака (простые плоскости с текстурой) ---
            const cloudMat = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 });
            for (let i = 0; i < 15; i++) {
                const cloudGroup = new THREE.Group();
                const parts = [2, 3, 2.5, 1.8];
                parts.forEach((rad, idx) => {
                    const part = new THREE.Mesh(new THREE.SphereGeometry(rad, 7, 7), cloudMat);
                    part.position.set(idx*2.5 - 3, 0, (idx-2)*1.5);
                    part.castShadow = false;
                    cloudGroup.add(part);
                });
                cloudGroup.position.set(Math.random() * 1000 - 200, 180 + Math.random() * 50, Math.random() * 800 - 200);
                scene.add(cloudGroup);
            }
        }

        // --- Создание 3D модели здания с текстурами ---
        function getTextureForBuilding(building) {
            const name = building.name;
            if (name === "Администрация") return createBrickTexture();
            if (name === "Производство") return createMetalTexture();
            if (name === "Столовая") return createWoodTexture();
            return createConcreteTexture();
        }

        function createBuildingMesh(building) {
            const width = building.w;
            const height = building.h;
            const depth = building.depth;
            const geometry = new THREE.BoxGeometry(width, height, depth);
            const texture = getTextureForBuilding(building);
            const material = new THREE.MeshStandardMaterial({
                map: texture,
                roughness: 0.4,
                metalness: 0.2,
                emissive: 0x000000
            });
            const mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.position.set(building.x, height / 2, building.y);
            mesh.userData = { buildingId: building.id, name: building.name };

            // CSS2D текст
            const div = document.createElement('div');
            div.textContent = building.name;
            div.style.color = '#fff';
            div.style.fontSize = '18px';
            div.style.fontWeight = 'bold';
            div.style.textShadow = '1px 1px 2px black';
            div.style.backgroundColor = 'rgba(0,0,0,0.6)';
            div.style.padding = '6px 14px';
            div.style.borderRadius = '24px';
            div.style.borderLeft = `3px solid ${building.color_hex}`;
            div.style.backdropFilter = 'blur(4px)';
            div.style.whiteSpace = 'nowrap';
            const label = new CSS2DObject(div);
            label.position.set(building.x, height + 12, building.y);
            scene.add(label);
            return { mesh, label };
        }

        async function loadBuildings() {
            const response = await fetch('/api/buildings');
            const buildings = await response.json();
            buildings.forEach(b => {
                const { mesh, label } = createBuildingMesh(b);
                scene.add(mesh);
                buildingsMeshes.push({
                    mesh: mesh,
                    buildingId: b.id,
                    defaultColor: b.color_hex,
                    label: label
                });
            });
        }

        async function updateAccessColors() {
            if (!currentUser) return;
            const response = await fetch('/api/access_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id })
            });
            const data = await response.json();
            for (let item of buildingsMeshes) {
                const accessible = data[item.buildingId];
                const mat = item.mesh.material;
                if (accessible) {
                    mat.emissiveIntensity = 0.15;
                    mat.emissive.setHex(0x44aa44);
                    // slight highlight
                } else {
                    mat.emissiveIntensity = 0;
                    // дополнительное затемнение материала
                    mat.color.multiplyScalar(0.65);
                }
            }
        }

        async function refreshUserInfo() {
            if (!currentUser) return;
            const response = await fetch('/api/user_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id })
            });
            const userData = await response.json();
            currentUser.shift_status = userData.shift_status;
            document.getElementById('username_display').innerText = currentUser.username;
            document.getElementById('role_display').innerText = currentUser.role_name;
            document.getElementById('shift_status_display').innerText = currentUser.shift_status === 'active' ? 'АКТИВНА' : 'НЕАКТИВНА';
            await updateAccessColors();
        }

        async function toggleShift() {
            if (!currentUser) return;
            await fetch('/api/toggle_shift', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id })
            });
            await refreshUserInfo();
        }

        async function login(username, password) {
            const resp = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await resp.json();
            if (data.success) {
                currentUser = data.user;
                document.getElementById('login-overlay').style.display = 'none';
                await loadBuildings();
                await refreshUserInfo();
                if (intervalId) clearInterval(intervalId);
                intervalId = setInterval(async () => {
                    await updateAccessColors();
                }, 3000);
            } else {
                document.getElementById('login-error').innerText = data.error || 'Ошибка входа';
            }
        }

        function updateDateTime() {
            const now = new Date();
            document.getElementById('current_date').innerText = now.toLocaleDateString('ru-RU');
            document.getElementById('current_time').innerText = now.toLocaleTimeString('ru-RU');
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
            labelRenderer.render(scene, camera);
        }

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
            labelRenderer.setSize(window.innerWidth, window.innerHeight);
        });

        initScene();
        animate();

        document.getElementById('toggle-shift-btn').addEventListener('click', toggleShift);
        document.getElementById('login-btn').addEventListener('click', () => {
            const user = document.getElementById('login-username').value;
            const pwd = document.getElementById('login-password').value;
            login(user, pwd);
        });
        document.getElementById('login-password').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') document.getElementById('login-btn').click();
        });
    </script>
</body>
</html>
'''


# --- API endpoints (те же, что и ранее) ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = verify_login(username, password)
    if user:
        session['user_id'] = user['id']
        return jsonify({'success': True,
                        'user': {'id': user['id'], 'username': user['username'], 'role_name': user['role_name'],
                                 'shift_status': user['shift_status']}})
    else:
        return jsonify({'success': False, 'error': 'Неверный логин или пароль'})


@app.route('/api/buildings', methods=['GET'])
def api_buildings():
    buildings = get_all_buildings()
    return jsonify([{**b, 'color_hex': b['color_hex']} for b in buildings])


@app.route('/api/access_status', methods=['POST'])
def api_access_status():
    data = request.json
    user_id = data.get('user_id')
    conn = get_conn()
    user_row = conn.execute(
        "SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id=?",
        (user_id,)).fetchone()
    conn.close()
    if not user_row:
        return jsonify({'error': 'User not found'}), 404
    user = dict(user_row)
    buildings = get_all_buildings()
    result = {}
    for b in buildings:
        result[b['id']] = check_access(user, b['id'])
    return jsonify(result)


@app.route('/api/user_status', methods=['POST'])
def api_user_status():
    data = request.json
    user_id = data.get('user_id')
    conn = get_conn()
    row = conn.execute("SELECT shift_status FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return jsonify({'shift_status': row['shift_status']})
    return jsonify({'error': 'no user'}), 404


@app.route('/api/toggle_shift', methods=['POST'])
def api_toggle_shift():
    data = request.json
    user_id = data.get('user_id')
    new_status = toggle_shift(user_id)
    return jsonify({'shift_status': new_status})


if __name__ == '__main__':
    init_db()
    seed_data()
    print("🌳 Запуск премиум 3D СКУД с текстурами и природой: http://127.0.0.1:5000/")
    print("📌 Логин: admin / admin123   или   worker / prod123")
    app.run(host="127.0.0.1", port=5000, debug=False)