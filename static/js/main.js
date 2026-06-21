import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

const SITE_CENTER = new THREE.Vector3(450, 0, 290);
const SPEEDS = [0.25, 1, 5, 30, 120, 600];
const STATUS = {
    available: { color: 0x52e6a5, css: '#52e6a5', title: 'Доступно' },
    closed: { color: 0xf5b95f, css: '#f5b95f', title: 'Не работает' },
    denied: { color: 0xff6f78, css: '#ff6f78', title: 'Нет доступа' },
    unknown: { color: 0x8fa0b4, css: '#8fa0b4', title: 'Ожидание' }
};

let scene;
let camera;
let renderer;
let labelRenderer;
let controls;
let transformControls;
let ambientLight;
let hemisphereLight;
let sunLight;
let moonLight;
let sunMesh;
let moonMesh;
let stars;
let buildingsMeshes = [];
let currentUser = null;
let selectedItem = null;
let editMode = false;
let accessRequestPending = false;
let lastAccessUpdate = 0;
let lastAccessMinute = '';
let toastTimer;

const timeState = {
    anchorReal: performance.now(),
    anchorSim: Date.now(),
    speed: 1,
    previousSpeed: 1,
    live: true
};

const region = resolveRegion();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const textureCache = new Map();

function resolveRegion() {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    const known = {
        'Asia/Yekaterinburg': [56.84, 60.61, 'Екатеринбург'],
        'Europe/Moscow': [55.76, 37.62, 'Москва'],
        'Asia/Novosibirsk': [55.03, 82.92, 'Новосибирск'],
        'Asia/Omsk': [54.99, 73.37, 'Омск'],
        'Asia/Krasnoyarsk': [56.02, 92.87, 'Красноярск'],
        'Asia/Irkutsk': [52.29, 104.28, 'Иркутск'],
        'Asia/Vladivostok': [43.12, 131.89, 'Владивосток'],
        'Asia/Kamchatka': [53.02, 158.65, 'Камчатка'],
        'Europe/Kaliningrad': [54.71, 20.51, 'Калининград']
    };
    const offsetHours = -new Date().getTimezoneOffset() / 60;
    const fallbackLatitude = timezone.startsWith('Asia/') || timezone.startsWith('Europe/') ? 55 : 40;
    const [latitude, longitude, localizedLabel] = known[timezone] || [fallbackLatitude, offsetHours * 15, null];
    return {
        timezone,
        latitude,
        longitude,
        label: localizedLabel || (timezone === 'UTC' ? 'UTC' : timezone.split('/').pop().replaceAll('_', ' '))
    };
}

function createPatternTexture(kind) {
    if (textureCache.has(kind)) return textureCache.get(kind);
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#d6d9dc';
    ctx.fillRect(0, 0, 256, 256);
    ctx.globalAlpha = 0.2;
    if (kind.includes('Администрац')) {
        ctx.fillStyle = '#5c392a';
        for (let y = 0; y < 256; y += 18) {
            for (let x = -20; x < 256; x += 40) {
                const offset = (y / 18) % 2 ? 20 : 0;
                ctx.fillRect(x + offset + 1, y + 1, 37, 15);
            }
        }
    } else if (kind.includes('Производ')) {
        ctx.fillStyle = '#ffffff';
        for (let x = 0; x < 256; x += 12) ctx.fillRect(x, 0, 2, 256);
    } else {
        for (let i = 0; i < 1300; i += 1) {
            const shade = 100 + Math.random() * 100;
            ctx.fillStyle = `rgb(${shade},${shade},${shade})`;
            ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1);
        }
    }
    ctx.globalAlpha = 1;
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(2, 1);
    texture.encoding = THREE.sRGBEncoding;
    textureCache.set(kind, texture);
    return texture;
}

function createRadialTexture(inner, outer) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createRadialGradient(64, 64, 5, 64, 64, 62);
    gradient.addColorStop(0, inner);
    gradient.addColorStop(0.25, inner);
    gradient.addColorStop(1, outer);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(canvas);
}

function initScene() {
    const root = document.getElementById('scene-root');
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x80b8df);
    scene.fog = new THREE.FogExp2(0x80b8df, 0.00055);

    camera = new THREE.PerspectiveCamera(46, window.innerWidth / window.innerHeight, 1, 2600);
    camera.position.set(730, 510, 870);

    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    root.appendChild(renderer.domElement);

    labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(window.innerWidth, window.innerHeight);
    Object.assign(labelRenderer.domElement.style, {
        position: 'absolute', inset: '0', pointerEvents: 'none'
    });
    root.appendChild(labelRenderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;
    controls.target.copy(SITE_CENTER).setY(55);
    controls.minDistance = 260;
    controls.maxDistance = 1500;
    controls.minPolarAngle = 0.12;
    controls.maxPolarAngle = Math.PI / 2.04;

    transformControls = new TransformControls(camera, renderer.domElement);
    transformControls.setMode('translate');
    transformControls.showY = false;
    transformControls.addEventListener('dragging-changed', event => {
        controls.enabled = !event.value;
    });
    transformControls.addEventListener('mouseUp', saveSelectedPosition);
    scene.add(transformControls);

    ambientLight = new THREE.AmbientLight(0x8da1bb, 0.48);
    hemisphereLight = new THREE.HemisphereLight(0x9dcfff, 0x26351e, 0.55);
    sunLight = new THREE.DirectionalLight(0xffedcf, 1.5);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.set(2048, 2048);
    sunLight.shadow.camera.left = -650;
    sunLight.shadow.camera.right = 650;
    sunLight.shadow.camera.top = 650;
    sunLight.shadow.camera.bottom = -650;
    sunLight.shadow.camera.near = 1;
    sunLight.shadow.camera.far = 1800;
    sunLight.shadow.bias = -0.00012;
    sunLight.target.position.copy(SITE_CENTER);
    moonLight = new THREE.DirectionalLight(0x8ba9dc, 0.08);
    moonLight.target.position.copy(SITE_CENTER);
    scene.add(ambientLight, hemisphereLight, sunLight, sunLight.target, moonLight, moonLight.target);

    createEnvironment();
    createCelestialBodies();

    renderer.domElement.addEventListener('click', onSceneClick);
    renderer.domElement.addEventListener('dblclick', onSceneDoubleClick);
    window.addEventListener('resize', onResize);
}

function createEnvironment() {
    const groundTexture = createGroundTexture();
    const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(1500, 1300),
        new THREE.MeshStandardMaterial({ map: groundTexture, color: 0x88a96b, roughness: 1 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(450, -2, 300);
    ground.receiveShadow = true;
    scene.add(ground);

    const roadMaterial = new THREE.MeshStandardMaterial({ color: 0x56606a, roughness: 0.96 });
    const roads = [
        [900, 52, 450, 305],
        [52, 680, 435, 305],
        [580, 36, 520, 95],
        [520, 36, 500, 500]
    ];
    roads.forEach(([w, d, x, z]) => {
        const road = new THREE.Mesh(new THREE.BoxGeometry(w, 1.5, d), roadMaterial);
        road.position.set(x, -0.9, z);
        road.receiveShadow = true;
        scene.add(road);
    });

    const lineMaterial = new THREE.MeshBasicMaterial({ color: 0xc9c2a6, transparent: true, opacity: .42 });
    for (let x = 65; x < 840; x += 55) {
        const line = new THREE.Mesh(new THREE.BoxGeometry(24, .3, 1.8), lineMaterial);
        line.position.set(x, .1, 305);
        scene.add(line);
    }

    const treePositions = [
        [92, 110], [135, 155], [105, 235], [70, 390], [125, 475],
        [270, 570], [340, 560], [420, 585], [560, 570], [710, 555],
        [875, 490], [920, 420], [930, 250], [900, 145], [810, 80],
        [610, 72], [430, 70], [260, 82]
    ];
    treePositions.forEach(([x, z], index) => scene.add(createTree(x, z, 0.85 + (index % 4) * 0.08)));

    const grid = new THREE.GridHelper(1200, 24, 0x55705f, 0x55705f);
    grid.position.set(450, -0.6, 300);
    grid.material.transparent = true;
    grid.material.opacity = 0.08;
    scene.add(grid);
}

function createGroundTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 512;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#769a5e';
    ctx.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 9000; i += 1) {
        const alpha = Math.random() * .16;
        ctx.fillStyle = `rgba(25,60,24,${alpha})`;
        ctx.fillRect(Math.random() * 512, Math.random() * 512, 1, 2 + Math.random() * 3);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(9, 8);
    texture.encoding = THREE.sRGBEncoding;
    return texture;
}

function createTree(x, z, scale = 1) {
    const group = new THREE.Group();
    const trunk = new THREE.Mesh(
        new THREE.CylinderGeometry(2.6, 3.7, 20, 7),
        new THREE.MeshStandardMaterial({ color: 0x684830, roughness: 1 })
    );
    trunk.position.y = 10;
    trunk.castShadow = true;
    group.add(trunk);
    const leafMaterial = new THREE.MeshStandardMaterial({ color: 0x416f43, roughness: .9 });
    [[0, 24, 10], [-5, 28, 8], [5, 29, 8], [0, 35, 7]].forEach(([lx, ly, radius]) => {
        const crown = new THREE.Mesh(new THREE.IcosahedronGeometry(radius, 1), leafMaterial);
        crown.position.set(lx, ly, 0);
        crown.castShadow = true;
        group.add(crown);
    });
    group.position.set(x, 0, z);
    group.scale.setScalar(scale);
    return group;
}

function createCelestialBodies() {
    const sunMaterial = new THREE.MeshBasicMaterial({ color: 0xffd274, fog: false });
    sunMesh = new THREE.Mesh(new THREE.SphereGeometry(18, 24, 24), sunMaterial);
    const sunHalo = new THREE.Sprite(new THREE.SpriteMaterial({
        map: createRadialTexture('rgba(255,226,137,0.8)', 'rgba(255,180,60,0)'),
        transparent: true,
        depthWrite: false,
        fog: false
    }));
    sunHalo.scale.set(105, 105, 1);
    sunMesh.add(sunHalo);

    moonMesh = new THREE.Mesh(
        new THREE.SphereGeometry(13, 24, 24),
        new THREE.MeshStandardMaterial({ color: 0xcbd8e9, roughness: .92, emissive: 0x344763, emissiveIntensity: .25, fog: false })
    );

    const starGeometry = new THREE.BufferGeometry();
    const points = [];
    for (let i = 0; i < 800; i += 1) {
        const radius = 1000 + Math.random() * 300;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI * .48;
        points.push(
            SITE_CENTER.x + radius * Math.sin(phi) * Math.cos(theta),
            radius * Math.cos(phi),
            SITE_CENTER.z + radius * Math.sin(phi) * Math.sin(theta)
        );
    }
    starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({
        color: 0xdbe8ff, size: 2.4, transparent: true, opacity: 0, depthWrite: false, fog: false
    }));
    scene.add(stars, sunMesh, moonMesh);
}

function createBuildingMesh(building) {
    const group = new THREE.Group();
    group.position.set(Number(building.x), 0, Number(building.y));
    group.userData.buildingId = building.id;
    group.userData.buildingRoot = group;

    const baseColor = new THREE.Color(building.color_hex || '#7b8791');
    const wallMaterial = new THREE.MeshStandardMaterial({
        color: baseColor,
        map: createPatternTexture(building.name || ''),
        roughness: .72,
        metalness: building.name?.includes('Производ') ? .32 : .06
    });
    const body = new THREE.Mesh(new THREE.BoxGeometry(building.w, building.h, building.depth), wallMaterial);
    body.position.y = building.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    body.userData.buildingRoot = group;
    group.add(body);

    const roof = new THREE.Mesh(
        new THREE.BoxGeometry(building.w + 5, 4, building.depth + 5),
        new THREE.MeshStandardMaterial({ color: 0x303a43, roughness: .82, metalness: .16 })
    );
    roof.position.y = building.h + 2;
    roof.castShadow = true;
    roof.userData.buildingRoot = group;
    group.add(roof);

    const doorWidth = Math.max(10, Math.min(20, building.w * .12));
    const doorHeight = Math.max(15, Math.min(30, building.h * .38));
    const door = new THREE.Mesh(
        new THREE.BoxGeometry(doorWidth, doorHeight, 1.6),
        new THREE.MeshStandardMaterial({ color: 0x28323b, roughness: .55, metalness: .38 })
    );
    door.position.set(0, doorHeight / 2, building.depth / 2 + .85);
    door.userData.buildingRoot = group;
    group.add(door);

    const windowMaterial = new THREE.MeshStandardMaterial({
        color: 0x7ba6bd, emissive: 0x273f54, emissiveIntensity: .35, roughness: .25, metalness: .25
    });
    const windowCount = Math.max(2, Math.min(5, Math.round(building.w / 45)));
    for (let i = 0; i < windowCount; i += 1) {
        const wx = (i - (windowCount - 1) / 2) * Math.min(32, building.w / (windowCount + .8));
        if (Math.abs(wx) < doorWidth * .8) continue;
        const windowMesh = new THREE.Mesh(new THREE.BoxGeometry(13, 10, 1), windowMaterial);
        windowMesh.position.set(wx, building.h * .58, building.depth / 2 + .7);
        windowMesh.userData.buildingRoot = group;
        group.add(windowMesh);
    }

    const edgeGeometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(building.w + 1, building.h + 1, building.depth + 1));
    const outline = new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({
        color: STATUS.unknown.color, transparent: true, opacity: .62
    }));
    outline.position.y = building.h / 2;
    outline.userData.buildingRoot = group;
    group.add(outline);

    const radius = Math.max(building.w, building.depth) * .58;
    const ring = new THREE.Mesh(
        new THREE.RingGeometry(Math.max(10, radius - 2), radius, 64),
        new THREE.MeshBasicMaterial({ color: STATUS.unknown.color, transparent: true, opacity: .38, side: THREE.DoubleSide, depthWrite: false })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = .35;
    group.add(ring);

    const labelElement = document.createElement('div');
    labelElement.className = 'building-label unknown';
    labelElement.innerHTML = `<div class="building-label-name"></div><div class="building-label-state">Ожидание</div>`;
    labelElement.querySelector('.building-label-name').textContent = building.name;
    const label = new CSS2DObject(labelElement);
    label.position.set(0, building.h + 19, 0);
    group.add(label);

    scene.add(group);
    const item = { mesh: group, body, roof, door, outline, ring, label, labelElement, data: { ...building }, accessible: null, baseColor };
    setBuildingStatus(item, null);
    return item;
}

async function loadBuildings() {
    const response = await fetch('/api/buildings');
    if (!response.ok) throw new Error('Не удалось загрузить здания');
    const buildings = await response.json();
    buildingsMeshes.forEach(item => scene.remove(item.mesh));
    buildingsMeshes = buildings.map(createBuildingMesh);
    renderStatusList();
}

function setBuildingStatus(item, statusInfo) {
    const normalized = statusInfo && typeof statusInfo === 'object'
        ? statusInfo
        : statusInfo === null ? null : { access: Boolean(statusInfo), status: statusInfo ? 'available' : 'denied' };
    item.statusInfo = normalized;
    item.accessible = normalized?.access ?? null;
    const key = normalized?.status || 'unknown';
    const status = STATUS[key];
    item.body.material.color.copy(item.baseColor);
    if (key === 'denied') item.body.material.color.multiplyScalar(.62);
    if (key === 'closed') item.body.material.color.multiplyScalar(.76);
    item.body.material.emissive.setHex(status.color);
    item.body.material.emissiveIntensity = normalized === null ? .02 : key === 'available' ? .12 : .08;
    item.outline.material.color.setHex(status.color);
    item.outline.material.opacity = selectedItem === item ? 1 : .76;
    item.ring.material.color.setHex(status.color);
    item.ring.material.opacity = selectedItem === item ? .72 : .34;
    item.labelElement.className = `building-label ${key}`;
    item.labelElement.querySelector('.building-label-state').textContent = status.title;
}

function localIsoString(date) {
    const pad = value => String(value).padStart(2, '0');
    const offset = -date.getTimezoneOffset();
    const sign = offset >= 0 ? '+' : '-';
    const abs = Math.abs(offset);
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
        `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

async function updateAccessColors(force = false) {
    if (!currentUser || accessRequestPending) return;
    const now = performance.now();
    if (!force && now - lastAccessUpdate < 900) return;
    accessRequestPending = true;
    lastAccessUpdate = now;
    try {
        const simulationDate = getSimulationDate();
        const response = await fetch('/api/access_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentUser.id,
                timestamp: localIsoString(simulationDate)
            })
        });
        if (!response.ok) throw new Error('Ошибка проверки доступа');
        const statuses = await response.json();
        buildingsMeshes.forEach(item => setBuildingStatus(item, statuses[item.data.id]));
        renderStatusList();
        if (selectedItem) showBuildingDetails(selectedItem);
    } catch (error) {
        showToast(error.message);
    } finally {
        accessRequestPending = false;
    }
}

function renderStatusList() {
    const container = document.getElementById('building-status-list');
    if (!currentUser) {
        container.innerHTML = '<div class="empty-state">Войдите, чтобы увидеть доступы</div>';
        return;
    }
    const priority = { available: 0, closed: 1, denied: 2, unknown: 3 };
    const sorted = [...buildingsMeshes].sort((a, b) =>
        priority[a.statusInfo?.status || 'unknown'] - priority[b.statusInfo?.status || 'unknown'] || a.data.name.localeCompare(b.data.name, 'ru'));
    container.replaceChildren(...sorted.map(item => {
        const stateKey = item.statusInfo?.status || 'unknown';
        const status = STATUS[stateKey];
        const button = document.createElement('button');
        button.className = `building-row ${stateKey}${selectedItem === item ? ' selected' : ''}`;
        button.innerHTML = '<span class="row-dot"></span><span class="row-main"><span class="row-name"></span><span class="row-hours"></span></span><span class="row-state"></span>';
        button.querySelector('.row-name').textContent = item.data.name;
        button.querySelector('.row-hours').textContent = formatBuildingSchedule(item.data);
        button.querySelector('.row-state').textContent = status.title;
        button.addEventListener('click', () => selectBuilding(item, true));
        return button;
    }));
    const available = buildingsMeshes.filter(item => item.accessible).length;
    document.getElementById('access-counter').textContent = `${available} / ${buildingsMeshes.length}`;
}

function selectBuilding(item, focus = false) {
    if (selectedItem && selectedItem !== item) setBuildingStatus(selectedItem, selectedItem.statusInfo);
    selectedItem = item;
    if (!item) {
        transformControls.detach();
        document.getElementById('building-details').classList.remove('visible');
        renderStatusList();
        return;
    }
    setBuildingStatus(item, item.statusInfo);
    item.outline.material.opacity = 1;
    item.ring.material.opacity = .76;
    showBuildingDetails(item);
    renderStatusList();
    if (editMode) transformControls.attach(item.mesh);
    if (focus) {
        controls.target.set(item.mesh.position.x, Math.min(80, item.data.h * .45), item.mesh.position.z);
    }
}

function showBuildingDetails(item) {
    const panel = document.getElementById('building-details');
    const stateKey = item.statusInfo?.status || 'unknown';
    document.getElementById('details-name').textContent = item.data.name;
    const status = document.getElementById('details-status');
    status.className = `details-status ${stateKey}`;
    status.textContent = `● ${item.statusInfo?.reason || STATUS[stateKey].title}`;
    document.getElementById('details-size').textContent = `${item.data.w} × ${item.data.depth} × ${item.data.h} м`;
    document.getElementById('details-schedule').textContent = formatBuildingSchedule(item.data);
    document.getElementById('details-days').textContent = formatBuildingDays(item.data.open_days);
    document.getElementById('details-type').textContent = item.data.is_accessible_to_all ? 'Общий' : 'По политике ABAC';
    panel.classList.add('visible');
}

function formatBuildingSchedule(building) {
    return building.is_24_hours ? 'Круглосуточно' : `${building.open_time || '08:00'}–${building.close_time || '20:00'}`;
}

function formatBuildingDays(value = '') {
    if (value === 'All') return 'Каждый день';
    if (value === 'Mon,Tue,Wed,Thu,Fri') return 'Пн–Пт';
    const names = { Mon: 'Пн', Tue: 'Вт', Wed: 'Ср', Thu: 'Чт', Fri: 'Пт', Sat: 'Сб', Sun: 'Вс' };
    return value.split(',').map(day => names[day.trim()] || day.trim()).filter(Boolean).join(', ');
}

function findBuildingFromIntersection(object) {
    let cursor = object;
    while (cursor && !cursor.userData.buildingRoot) cursor = cursor.parent;
    const root = cursor?.userData.buildingRoot;
    return root ? buildingsMeshes.find(item => item.mesh === root) : null;
}

function pickBuilding(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(buildingsMeshes.map(item => item.mesh), true);
    return hits.length ? findBuildingFromIntersection(hits[0].object) : null;
}

function onSceneClick(event) {
    if (transformControls.dragging) return;
    const item = pickBuilding(event);
    if (item) selectBuilding(item);
    else if (!editMode) selectBuilding(null);
}

function onSceneDoubleClick(event) {
    if (!editMode) return;
    const item = pickBuilding(event);
    if (item) openEditModal(item.data.id);
}

async function refreshUserInfo() {
    if (!currentUser) return;
    const response = await fetch('/api/user_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.id })
    });
    if (!response.ok) return;
    const data = await response.json();
    currentUser.shift_status = data.shift_status;
    document.getElementById('username').textContent = currentUser.username;
    document.getElementById('role').textContent = currentUser.role_name;
    document.getElementById('session-dot').classList.add('online');
    const shiftBadge = document.getElementById('shift-badge');
    const active = currentUser.shift_status === 'active';
    shiftBadge.classList.toggle('active', active);
    document.getElementById('shift').textContent = active ? 'Смена активна' : 'Смена неактивна';
    document.getElementById('toggle-shift-btn').textContent = active ? 'Завершить смену' : 'Начать смену';
    await updateAccessColors(true);
}

async function toggleShift() {
    if (!currentUser) {
        showToast('Сначала войдите в систему');
        return;
    }
    const response = await fetch('/api/toggle_shift', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.id })
    });
    if (response.ok) {
        await refreshUserInfo();
        showToast('Статус смены обновлён');
    }
}

async function login(username, password) {
    const button = document.getElementById('login-btn');
    button.disabled = true;
    button.textContent = 'Загружаем карту…';
    document.getElementById('login-error').textContent = '';
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Не удалось войти');
        currentUser = data.user;
        await loadBuildings();
        await refreshUserInfo();
        document.getElementById('login-overlay').classList.add('hidden');
        document.getElementById('toggle-shift-btn').disabled = false;
        if (currentUser.role_id === 1) {
            document.getElementById('admin-edit-btn').hidden = false;
            document.getElementById('add-building-btn').hidden = false;
        }
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = 'Открыть карту';
    }
}

function toggleEditMode() {
    editMode = !editMode;
    const button = document.getElementById('admin-edit-btn');
    button.classList.toggle('active', editMode);
    button.textContent = editMode ? 'Готово' : 'Редактировать';
    document.getElementById('edit-mode-banner').classList.toggle('visible', editMode);
    renderer.domElement.style.cursor = editMode ? 'crosshair' : 'default';
    if (!editMode) transformControls.detach();
    else if (selectedItem) transformControls.attach(selectedItem.mesh);
}

async function saveSelectedPosition() {
    if (!selectedItem || !editMode) return;
    const item = selectedItem;
    item.data.x = Math.round(item.mesh.position.x);
    item.data.y = Math.round(item.mesh.position.z);
    const response = await fetch(`/api/admin/buildings/${item.data.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item.data)
    });
    showToast(response.ok ? 'Положение сохранено' : 'Не удалось сохранить положение');
}

async function createBuilding() {
    const newBuilding = {
        name: `Новый объект ${buildingsMeshes.length + 1}`, color_hex: '#6f8798', x: 450, y: 300,
        w: 90, h: 60, depth: 45, is_accessible_to_all: false,
        open_days: 'Mon,Tue,Wed,Thu,Fri', open_time: '08:00', close_time: '20:00', is_24_hours: false
    };
    const response = await fetch('/api/admin/buildings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newBuilding)
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
        showToast('Не удалось создать объект');
        return;
    }
    newBuilding.id = result.id;
    const item = createBuildingMesh(newBuilding);
    buildingsMeshes.push(item);
    setBuildingStatus(item, { access: false, building_open: false, status: 'closed', reason: 'Закрыто по графику' });
    selectBuilding(item);
    openEditModal(item.data.id);
    updateAccessColors(true);
}

function openEditModal(buildingId) {
    const item = buildingsMeshes.find(entry => entry.data.id === buildingId);
    if (!item) return;
    item.data.x = Math.round(item.mesh.position.x);
    item.data.y = Math.round(item.mesh.position.z);
    const fields = {
        'edit-name': item.data.name,
        'edit-color': item.data.color_hex,
        'edit-w': item.data.w,
        'edit-h': item.data.h,
        'edit-depth': item.data.depth,
        'edit-open-days': item.data.open_days || 'Mon,Tue,Wed,Thu,Fri',
        'edit-open-time': item.data.open_time || '08:00',
        'edit-close-time': item.data.close_time || '20:00'
    };
    Object.entries(fields).forEach(([id, value]) => { document.getElementById(id).value = value; });
    document.getElementById('edit-all').checked = Boolean(item.data.is_accessible_to_all);
    document.getElementById('edit-24-hours').checked = Boolean(item.data.is_24_hours);
    syncScheduleFields();
    updateRangeOutputs();
    const modal = document.getElementById('building-modal');
    modal.dataset.buildingId = buildingId;
    modal.classList.add('visible');
    document.getElementById('modal-backdrop').classList.add('visible');
}

function closeModal() {
    document.getElementById('building-modal').classList.remove('visible');
    document.getElementById('modal-backdrop').classList.remove('visible');
}

function updateRangeOutputs() {
    document.getElementById('w-val').textContent = `${document.getElementById('edit-w').value} м`;
    document.getElementById('h-val').textContent = `${document.getElementById('edit-h').value} м`;
    document.getElementById('d-val').textContent = `${document.getElementById('edit-depth').value} м`;
}

function syncScheduleFields() {
    const aroundClock = document.getElementById('edit-24-hours').checked;
    document.getElementById('edit-open-time').disabled = aroundClock;
    document.getElementById('edit-close-time').disabled = aroundClock;
}

async function saveBuildingFull() {
    const buildingId = Number(document.getElementById('building-modal').dataset.buildingId);
    const item = buildingsMeshes.find(entry => entry.data.id === buildingId);
    if (!item) return;
    const updated = {
        ...item.data,
        name: document.getElementById('edit-name').value.trim() || 'Без названия',
        color_hex: document.getElementById('edit-color').value,
        x: Math.round(item.mesh.position.x),
        y: Math.round(item.mesh.position.z),
        w: Number(document.getElementById('edit-w').value),
        h: Number(document.getElementById('edit-h').value),
        depth: Number(document.getElementById('edit-depth').value),
        is_accessible_to_all: document.getElementById('edit-all').checked,
        open_days: document.getElementById('edit-open-days').value.trim() || 'All',
        open_time: document.getElementById('edit-open-time').value || '08:00',
        close_time: document.getElementById('edit-close-time').value || '20:00',
        is_24_hours: document.getElementById('edit-24-hours').checked
    };
    const response = await fetch(`/api/admin/buildings/${buildingId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updated)
    });
    if (!response.ok) {
        showToast('Не удалось сохранить объект');
        return;
    }
    const index = buildingsMeshes.indexOf(item);
    const wasSelected = selectedItem === item;
    transformControls.detach();
    scene.remove(item.mesh);
    const replacement = createBuildingMesh(updated);
    buildingsMeshes.splice(index, 1, replacement);
    selectedItem = wasSelected ? replacement : null;
    closeModal();
    await updateAccessColors(true);
    if (wasSelected) selectBuilding(replacement);
    showToast('Изменения сохранены');
}

async function deleteBuilding() {
    const buildingId = Number(document.getElementById('building-modal').dataset.buildingId);
    if (!window.confirm('Удалить здание с карты?')) return;
    const response = await fetch(`/api/admin/buildings/${buildingId}`, { method: 'DELETE' });
    if (!response.ok) {
        showToast('Не удалось удалить объект');
        return;
    }
    const item = buildingsMeshes.find(entry => entry.data.id === buildingId);
    if (item) scene.remove(item.mesh);
    buildingsMeshes = buildingsMeshes.filter(entry => entry.data.id !== buildingId);
    selectedItem = null;
    transformControls.detach();
    closeModal();
    document.getElementById('building-details').classList.remove('visible');
    renderStatusList();
    showToast('Объект удалён');
}

function getSimulationDate(now = performance.now()) {
    return new Date(timeState.anchorSim + (now - timeState.anchorReal) * timeState.speed);
}

function setTimeSpeed(speed, live = false) {
    const currentTime = getSimulationDate().getTime();
    timeState.anchorSim = live ? Date.now() : currentTime;
    timeState.anchorReal = performance.now();
    if (speed > 0) timeState.previousSpeed = speed;
    timeState.speed = speed;
    timeState.live = live;
    updateTimeControls();
    updateAccessColors(true);
}

function setTimeOfDay(minutes) {
    const date = getSimulationDate();
    date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
    timeState.anchorSim = date.getTime();
    timeState.anchorReal = performance.now();
    timeState.live = false;
    updateTimeControls();
    updateAccessColors(true);
}

function changeSpeed(direction) {
    if (timeState.speed === 0) {
        setTimeSpeed(direction > 0 ? timeState.previousSpeed || 1 : SPEEDS[0]);
        return;
    }
    const currentIndex = SPEEDS.reduce((best, value, index) =>
        Math.abs(value - timeState.speed) < Math.abs(SPEEDS[best] - timeState.speed) ? index : best, 0);
    const nextIndex = THREE.MathUtils.clamp(currentIndex + direction, 0, SPEEDS.length - 1);
    setTimeSpeed(SPEEDS[nextIndex]);
}

function toggleTimePause() {
    setTimeSpeed(timeState.speed === 0 ? timeState.previousSpeed || 1 : 0);
}

function updateTimeControls() {
    const speedLabel = timeState.speed === 0 ? 'Пауза' : `×${timeState.speed}`;
    document.getElementById('time-speed').textContent = speedLabel;
    document.getElementById('time-play').textContent = timeState.speed === 0 ? '▶' : 'Ⅱ';
    document.getElementById('time-live').classList.toggle('is-live', timeState.live && timeState.speed === 1);
}

function getSolarDirection(date) {
    const start = new Date(date.getFullYear(), 0, 0);
    const dayOfYear = Math.floor((date - start) / 86400000);
    const hour = date.getHours() + date.getMinutes() / 60 + date.getSeconds() / 3600;
    const gamma = 2 * Math.PI / 365 * (dayOfYear - 1 + (hour - 12) / 24);
    const equationOfTime = 229.18 * (0.000075 + 0.001868 * Math.cos(gamma) - 0.032077 * Math.sin(gamma)
        - 0.014615 * Math.cos(2 * gamma) - 0.040849 * Math.sin(2 * gamma));
    const declination = 0.006918 - 0.399912 * Math.cos(gamma) + 0.070257 * Math.sin(gamma)
        - 0.006758 * Math.cos(2 * gamma) + 0.000907 * Math.sin(2 * gamma)
        - 0.002697 * Math.cos(3 * gamma) + 0.00148 * Math.sin(3 * gamma);
    const timezoneOffset = -date.getTimezoneOffset();
    const solarMinutes = (hour * 60 + equationOfTime + 4 * region.longitude - timezoneOffset + 1440) % 1440;
    const hourAngle = THREE.MathUtils.degToRad(solarMinutes / 4 - 180);
    const latitude = THREE.MathUtils.degToRad(region.latitude);
    const x = Math.cos(declination) * Math.sin(hourAngle);
    const y = Math.sin(latitude) * Math.sin(declination) + Math.cos(latitude) * Math.cos(declination) * Math.cos(hourAngle);
    const z = Math.cos(latitude) * Math.sin(declination) - Math.sin(latitude) * Math.cos(declination) * Math.cos(hourAngle);
    return new THREE.Vector3(x, y, z).normalize();
}

function updateSky(date) {
    const direction = getSolarDirection(date);
    const altitude = Math.asin(THREE.MathUtils.clamp(direction.y, -1, 1));
    const altitudeDeg = THREE.MathUtils.radToDeg(altitude);
    const dayFactor = THREE.MathUtils.smoothstep(altitudeDeg, -6, 14);
    const horizonFactor = 1 - Math.min(1, Math.abs(altitudeDeg) / 28);
    const nightColor = new THREE.Color(0x040a18);
    const dawnColor = new THREE.Color(0xa65e58);
    const dayColor = new THREE.Color(0x79b9df);
    const skyColor = altitudeDeg < 0
        ? nightColor.clone().lerp(dawnColor, THREE.MathUtils.smoothstep(altitudeDeg, -12, 1))
        : dawnColor.clone().lerp(dayColor, THREE.MathUtils.smoothstep(altitudeDeg, 0, 28));
    if (horizonFactor > .55 && altitudeDeg > -6 && altitudeDeg < 16) skyColor.lerp(new THREE.Color(0xd98a68), .14);
    scene.background.copy(skyColor);
    scene.fog.color.copy(skyColor);

    const celestialRadius = 720;
    sunMesh.position.copy(SITE_CENTER).addScaledVector(direction, celestialRadius);
    moonMesh.position.copy(SITE_CENTER).addScaledVector(direction, -celestialRadius);
    sunMesh.visible = altitudeDeg > -10;
    moonMesh.visible = altitudeDeg < 18;

    sunLight.position.copy(SITE_CENTER).addScaledVector(direction, 850);
    sunLight.intensity = Math.max(0, dayFactor * 1.28);
    sunLight.color.set(altitudeDeg < 10 ? 0xffb36f : 0xfff0d5);
    moonLight.position.copy(SITE_CENTER).addScaledVector(direction, -700);
    moonLight.intensity = (1 - dayFactor) * .22;
    ambientLight.intensity = .1 + dayFactor * .3;
    ambientLight.color.set(dayFactor > .4 ? 0xa8bfd5 : 0x53647d);
    hemisphereLight.intensity = .14 + dayFactor * .36;
    stars.material.opacity = Math.pow(1 - dayFactor, 2) * .92;
    renderer.toneMappingExposure = .72 + dayFactor * .25;

    const localHour = hourOf(date);
    const phase = altitudeDeg < -7 || localHour < 4 || localHour >= 23 ? 'Ночь'
        : altitudeDeg < 1 ? (localHour < 12 ? 'Рассвет' : 'Сумерки')
            : altitudeDeg < 12 ? (localHour < 12 ? 'Утро' : 'Вечер') : 'День';
    document.getElementById('day-phase').textContent = phase;
}

function hourOf(date) {
    return date.getHours() + date.getMinutes() / 60;
}

function updateDateTime(date) {
    document.getElementById('datetime').textContent = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('calendar-date').textContent = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    document.getElementById('region-name').textContent = `${region.label} · ${region.timezone}`;
    document.getElementById('time-scrubber').value = date.getHours() * 60 + date.getMinutes();
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2200);
}

function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    labelRenderer.setSize(window.innerWidth, window.innerHeight);
}

let lastUiFrame = 0;
function animate(now = performance.now()) {
    requestAnimationFrame(animate);
    controls.update();
    const date = getSimulationDate(now);
    updateSky(date);
    if (now - lastUiFrame > 90) {
        updateDateTime(date);
        const minuteKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}-${date.getMinutes()}`;
        if (minuteKey !== lastAccessMinute) {
            lastAccessMinute = minuteKey;
            updateAccessColors();
        }
        lastUiFrame = now;
    }
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
}

function bindInterface() {
    document.getElementById('login-form').addEventListener('submit', event => {
        event.preventDefault();
        login(document.getElementById('login-username').value, document.getElementById('login-password').value);
    });
    document.getElementById('toggle-shift-btn').addEventListener('click', toggleShift);
    document.getElementById('admin-edit-btn').addEventListener('click', toggleEditMode);
    document.getElementById('add-building-btn').addEventListener('click', createBuilding);
    document.getElementById('close-details').addEventListener('click', () => selectBuilding(null));
    document.getElementById('time-slower').addEventListener('click', () => changeSpeed(-1));
    document.getElementById('time-faster').addEventListener('click', () => changeSpeed(1));
    document.getElementById('time-play').addEventListener('click', toggleTimePause);
    document.getElementById('time-live').addEventListener('click', () => setTimeSpeed(1, true));
    document.getElementById('time-scrubber').addEventListener('input', event => setTimeOfDay(Number(event.target.value)));
    document.getElementById('close-modal').addEventListener('click', closeModal);
    document.getElementById('modal-backdrop').addEventListener('click', closeModal);
    document.getElementById('save-building-changes').addEventListener('click', saveBuildingFull);
    document.getElementById('delete-building-btn').addEventListener('click', deleteBuilding);
    ['edit-w', 'edit-h', 'edit-depth'].forEach(id => document.getElementById(id).addEventListener('input', updateRangeOutputs));
    document.getElementById('edit-24-hours').addEventListener('change', syncScheduleFields);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeModal();
            selectBuilding(null);
        }
        if (event.code === 'Space' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
            event.preventDefault();
            toggleTimePause();
        }
    });
    document.getElementById('toggle-shift-btn').disabled = true;
    updateTimeControls();
}

initScene();
bindInterface();
animate();
