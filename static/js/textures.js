export function createBrickTexture() {
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

export function createConcreteTexture() {
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

export function createMetalTexture() {
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

export function createWoodTexture() {
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

export function createGrassTexture() {
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

export function createTree(x, z, scene) {
    const group = new THREE.Group();
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x8B5A2B, roughness: 0.7 });
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(4, 5, 8, 8), trunkMat);
    trunk.position.y = 4;
    trunk.castShadow = true;
    group.add(trunk);
    const leafMat = new THREE.MeshStandardMaterial({ color: 0x5a9e4e, roughness: 0.4 });
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
    scene.add(group);
}