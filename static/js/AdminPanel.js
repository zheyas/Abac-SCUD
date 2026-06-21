import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

export class AdminPanel {
    constructor(user) {
        this.user = user;
        this.panel = document.getElementById('admin-panel');
        this.transformControls = null;
        this.selectedBuildingMesh = null;
        this.selectedBuildingId = null;
        this.initUI();
        this.initTransformControls();
    }

    initUI() {
        document.getElementById('admin-toggle-btn').onclick = () => {
            this.panel.style.display = this.panel.style.display === 'none' ? 'block' : 'none';
        };
        document.getElementById('close-admin').onclick = () => this.panel.style.display = 'none';
        const tabs = document.querySelectorAll('.tab-btn');
        tabs.forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.getElementById(btn.dataset.tab + '-tab').classList.add('active');
                tabs.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                if (btn.dataset.tab === 'buildings') this.refreshBuildingsList();
                if (btn.dataset.tab === 'users') this.refreshUsersList();
                if (btn.dataset.tab === 'policies') this.refreshPoliciesList();
            };
        });
        document.getElementById('add-building').onclick = () => this.createBuilding();
        document.getElementById('apply-building-changes').onclick = () => this.applyBuildingChanges();
        document.getElementById('delete-building').onclick = () => this.deleteBuilding();
        this.refreshBuildingsList();
        this.refreshUsersList();
        this.refreshPoliciesList();
    }

    initTransformControls() {
        this.transformControls = new TransformControls(window.camera, window.renderer.domElement);
        this.transformControls.addEventListener('dragging-changed', (event) => {
            window.controls.enabled = !event.value;
        });
        this.transformControls.addEventListener('objectChange', () => {
            if (this.selectedBuildingMesh) {
                // обновляем форму при перемещении
                const pos = this.selectedBuildingMesh.position;
                // можно отобразить текущие координаты, но в данном UI нет полей X,Y
            }
        });
        window.scene.add(this.transformControls);
    }

    async refreshBuildingsList() {
        const res = await fetch('/api/buildings');
        const buildings = await res.json();
        const container = document.getElementById('buildings-list');
        container.innerHTML = '';
        buildings.forEach(b => {
            const div = document.createElement('div');
            div.className = 'building-item';
            div.innerText = `${b.name} (${b.x},${b.y})`;
            div.onclick = () => {
                this.selectBuilding(b.id);
                document.querySelectorAll('.building-item').forEach(i => i.classList.remove('selected'));
                div.classList.add('selected');
            };
            container.appendChild(div);
        });
    }

    selectBuilding(buildingId) {
        const item = window.buildingsMeshes.find(m => m.buildingId === buildingId);
        if (item) {
            this.selectedBuildingMesh = item.mesh;
            this.selectedBuildingId = buildingId;
            this.transformControls.attach(this.selectedBuildingMesh);
            const data = item.data;
            document.getElementById('edit-name').value = data.name;
            document.getElementById('edit-color').value = data.color_hex;
            document.getElementById('edit-w').value = data.w;
            document.getElementById('edit-h').value = data.h;
            document.getElementById('edit-depth').value = data.depth;
            document.getElementById('edit-all').checked = data.is_accessible_to_all;
            document.getElementById('selected-name').innerText = `Выбрано: ${data.name}`;
        }
    }

    async applyBuildingChanges() {
        if (!this.selectedBuildingMesh) return;
        const newData = {
            name: document.getElementById('edit-name').value,
            color_hex: document.getElementById('edit-color').value,
            x: this.selectedBuildingMesh.position.x,
            y: this.selectedBuildingMesh.position.z,
            w: parseInt(document.getElementById('edit-w').value),
            h: parseInt(document.getElementById('edit-h').value),
            depth: parseInt(document.getElementById('edit-depth').value),
            is_accessible_to_all: document.getElementById('edit-all').checked
        };
        const res = await fetch(`/api/buildings/${this.selectedBuildingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newData)
        });
        if (res.ok) {
            // обновляем геометрию и материал
            this.selectedBuildingMesh.scale.set(newData.w / this.selectedBuildingMesh.userData.buildingData.w,
                                                newData.h / this.selectedBuildingMesh.userData.buildingData.h,
                                                newData.depth / this.selectedBuildingMesh.userData.buildingData.depth);
            this.selectedBuildingMesh.userData.buildingData = newData;
            // обновляем цвет/текстуру (простейший способ – пересоздать материал)
            this.selectedBuildingMesh.material.dispose();
            const newMat = new THREE.MeshStandardMaterial({ color: newData.color_hex, roughness: 0.4 });
            this.selectedBuildingMesh.material = newMat;
            // также обновляем label
            // для простоты перезагрузим страницу или обновим все здания
            window.location.reload();
        }
    }

    async deleteBuilding() {
        if (!this.selectedBuildingId) return;
        if (confirm('Удалить здание?')) {
            await fetch(`/api/buildings/${this.selectedBuildingId}`, { method: 'DELETE' });
            this.transformControls.detach();
            this.selectedBuildingMesh.parent.remove(this.selectedBuildingMesh);
            this.selectedBuildingMesh = null;
            this.refreshBuildingsList();
        }
    }

    async createBuilding() {
        const name = prompt('Название нового здания');
        if (!name) return;
        const newBuilding = {
            name, color_hex: '#cccccc', x: 300, y: 300, w: 80, h: 60, depth: 25, is_accessible_to_all: false
        };
        await fetch('/api/buildings', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newBuilding)
        });
        window.location.reload();
    }

    async refreshUsersList() {
        const res = await fetch('/api/users');
        const users = await res.json();
        const container = document.getElementById('users-list');
        container.innerHTML = '';
        users.forEach(u => {
            const div = document.createElement('div');
            div.className = 'user-item';
            div.innerText = `${u.username} (${u.role_name || ''}) - ${u.is_active ? 'активен' : 'заблокирован'}`;
            div.onclick = () => this.editUser(u.id);
            container.appendChild(div);
        });
    }

    editUser(uid) {
        // упрощённо: удаление/изменение можно добавить по аналогии
        alert('Редактирование пользователя будет реализовано в расширенной версии');
    }

    async refreshPoliciesList() {
        const res = await fetch('/api/policies');
        const policies = await res.json();
        const container = document.getElementById('policies-list');
        container.innerHTML = '';
        policies.forEach(p => {
            const div = document.createElement('div');
            div.className = 'policy-item';
            div.innerText = `Роль ${p.role_id} → Здание ${p.building_id}: ${p.time_start}-${p.time_end}`;
            container.appendChild(div);
        });
    }
}