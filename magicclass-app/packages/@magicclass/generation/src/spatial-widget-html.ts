import type { SpatialWidget } from './spatial-widget.js';

/** Render the same geometry in the browser and on clients that consume widgetConfig. */
export function spatialWidgetHtml(config: SpatialWidget): string {
  const data = JSON.stringify(config).replace(/</g, '\\u003c');
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  *{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#142733;color:#f2e9d3;font:16px system-ui,sans-serif}
  main{display:grid;grid-template-rows:minmax(230px,1fr) auto;min-height:100vh}
  #stage{position:relative;min-height:230px;background:#101f2b}
  #stage canvas{display:block;width:100%;height:100%;touch-action:none;position:absolute;inset:0}
  #status{position:absolute;z-index:1;left:12px;top:12px;margin:0;padding:6px 8px;background:#142733;border-radius:6px;pointer-events:none}
  #status:empty{display:none}
  footer{padding:9px 14px;background:#192f39}nav{display:flex;gap:8px;flex-wrap:wrap}
  button{min-width:44px;min-height:44px;border:1px solid #587079;border-radius:8px;background:#203943;color:inherit;font:inherit;cursor:pointer}
  button:focus-visible{outline:2px solid #dab27a;outline-offset:2px}button:disabled{opacity:.5;cursor:default}
  #description{margin:8px 0;line-height:1.4;overflow-wrap:anywhere}
</style>
<script type="importmap">
{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}
</script>
</head>
<body>
<main>
<section id="stage"><p id="status" role="status"></p></section>
<footer>
  <nav>
    <button type="button" id="zoom-out" disabled>−</button>
    <button type="button" id="zoom-in" disabled>+</button>
    <button type="button" id="reset-view" disabled>↺</button>
    <button type="button" id="toggle-motion" hidden>▶</button>
  </nav>
  <p id="description"></p>
</footer>
</main>
<script type="application/json" id="widget-config">${data}</script>
<script type="module">
  const element = (id) => document.getElementById(id);
  const config = JSON.parse(element('widget-config').textContent);
  const stage = element('stage');
  const status = element('status');
  const zh = /[\\u3400-\\u9fff]/.test(config.description);
  const text = (chinese, english) => zh ? chinese : english;
  document.documentElement.lang = zh ? 'zh' : 'en';
  element('description').textContent = config.description;
  status.textContent = text('正在加载三维模型', 'Loading the 3D model');
  element('zoom-out').setAttribute('aria-label', text('缩小模型', 'Zoom out'));
  element('zoom-in').setAttribute('aria-label', text('放大模型', 'Zoom in'));
  element('reset-view').setAttribute('aria-label', text('重置视角', 'Reset view'));
  const objects = new Map();
  let highlight;
  let queuedHighlight;
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    const message = event.data;
    if ((message?.type ?? message?.action) !== 'HIGHLIGHT_ELEMENT') return;
    const target = message.target ?? message.payload?.elementId;
    if (typeof target === 'string') {
      queuedHighlight = target.replace(/^#/, '');
      highlight?.(queuedHighlight);
    }
  });
  async function mount() {
    const [T, { OrbitControls }] = await Promise.all([
      import('three'), import('three/addons/controls/OrbitControls.js'),
    ]);
    const scene = new T.Scene();
    const model = new T.Group();
    scene.add(model, new T.HemisphereLight(0xeef7ff, 0x7a664e, 2));
    const key = new T.DirectionalLight(0xffefd3, 2);
    key.position.set(-3, 5, 4);
    scene.add(key);
    const camera = new T.PerspectiveCamera(42, 1, 0.01, 1000);
    const renderer = new T.WebGLRenderer({ antialias: true });
    renderer.setClearColor(0x101f2b);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    stage.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    const shapes = {
      box: () => new T.BoxGeometry(1, 1, 1),
      sphere: () => new T.SphereGeometry(.5, 20, 12),
      cylinder: () => new T.CylinderGeometry(.5, .5, 1, 24),
      cone: () => new T.ConeGeometry(.5, 1, 24),
      torus: () => new T.TorusGeometry(.36, .12, 10, 26),
      plane: () => new T.PlaneGeometry(1, 1),
    };
    const motions = [];
    function makeSolid(parent, item) {
      const material = item.material;
      const colors = { color: material.color, wireframe: material.wireframe ?? false,
        transparent: material.transparent ?? false, opacity: material.opacity ?? 1,
        side: item.type === 'plane' ? T.DoubleSide : T.FrontSide };
      const surface = ['basic', 'emissive'].includes(material.type)
        ? new T.MeshBasicMaterial(colors) : new T.MeshStandardMaterial(colors);
      const mesh = new T.Mesh(shapes[item.type](), surface);
      if (item.position) mesh.position.set(item.position.x, item.position.y, item.position.z);
      if (item.rotation) mesh.rotation.set(item.rotation.x, item.rotation.y, item.rotation.z);
      if (typeof item.scale === 'number') mesh.scale.setScalar(item.scale);
      else if (item.scale) mesh.scale.set(item.scale.x, item.scale.y, item.scale.z);
      parent.add(mesh);
      objects.set(item.id, { mesh, item, color: surface.color.clone() });
      if (item.animation) {
        const axis = item.animation.axis ?? 'y';
        const direction = new T.Vector3();
        direction[axis] = 1;
        motions.push({ mesh, motion: item.animation, axis, direction, position: mesh.position.clone(),
          rotation: mesh.rotation[axis], scale: mesh.scale.clone() });
      }
      for (const child of item.children ?? []) makeSolid(mesh, child);
    }
    for (const item of config.objects) makeSolid(model, item);
    function pose(elapsed) {
      for (const {mesh, motion, axis, direction, position, rotation, scale} of motions) {
        const phase = elapsed * (motion.speed ?? 1);
        if (motion.type === 'rotate') mesh.rotation[axis] = rotation + phase;
        if (motion.type === 'orbit') mesh.position.copy(position).applyAxisAngle(direction, phase);
        if (motion.type === 'bounce') mesh.position.copy(position).addScaledVector(direction, .25 * Math.abs(Math.sin(phase)));
        if (motion.type === 'pulse') mesh.scale.copy(scale).multiplyScalar(1 + .12 * Math.sin(phase));
      }
    }
    const bounds = new T.Box3().setFromObject(model);
    for (const time of [.5, 1, 2, 4, 8]) {
      pose(time);
      bounds.expandByObject(model);
    }
    pose(0);
    const sphere = bounds.getBoundingSphere(new T.Sphere());
    const radius = Math.max(.02, sphere.radius);
    const zoomBy = (factor) => {
      const offset = camera.position.clone().sub(controls.target);
      offset.setLength(T.MathUtils.clamp(offset.length() * factor, controls.minDistance, controls.maxDistance));
      camera.position.copy(controls.target).add(offset);
      controls.update();
    };
    controls.minDistance = radius * 1.25;
    controls.maxDistance = radius * 14;
    camera.near = Math.max(.001, radius / 100);
    camera.far = radius * 30;
    function resetView() {
      const distance = Math.min(controls.maxDistance, 3.4 * radius / Math.min(1, camera.aspect));
      controls.target.copy(sphere.center);
      camera.position.copy(controls.target).add(new T.Vector3(.54, .33, .78).normalize().multiplyScalar(distance));
      controls.update();
    }
    function resize() {
      const width = Math.max(1, stage.clientWidth);
      const height = Math.max(1, stage.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }
    resize();
    resetView();
    const observer = new ResizeObserver(resize);
    observer.observe(stage);
    element('zoom-out').onclick = () => zoomBy(1.22);
    element('zoom-in').onclick = () => zoomBy(1 / 1.22);
    element('reset-view').onclick = resetView;
    for (const id of ['zoom-out', 'zoom-in', 'reset-view']) element(id).disabled = false;
    const toggle = element('toggle-motion');
    toggle.hidden = !motions.length;
    let playing = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const updateButton = () => {
      toggle.textContent = playing ? 'Ⅱ' : '▶';
      toggle.setAttribute('aria-label', playing ? text('暂停动画', 'Pause animation') : text('播放动画', 'Play animation'));
    };
    toggle.onclick = () => { playing = !playing; updateButton(); };
    updateButton();
    status.textContent = '';
    highlight = (id) => {
      const selection = objects.get(id);
      for (const {mesh, color} of objects.values()) mesh.material.color.copy(color);
      if (selection) selection.mesh.material.color.lerp(new T.Color(0xf6c779), .66);
      status.textContent = selection?.item.name ?? '';
    };
    if (queuedHighlight) highlight(queuedHighlight);
    let elapsed = 0;
    let previous = 0;
    renderer.setAnimationLoop((now) => {
      if (previous && playing && motions.length) {
        elapsed += Math.min((now - previous) / 1000, .10);
        pose(elapsed);
      }
      previous = now;
      renderer.render(scene, camera);
    });
    window.addEventListener('pagehide', () => {
      observer.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      model.traverse((mesh) => { mesh.geometry?.dispose(); mesh.material?.dispose(); });
      renderer.dispose();
    }, { once: true });
  }
  mount().catch(() => {
    status.textContent = text('当前浏览器无法加载三维模型。', 'This browser could not load the 3D model.');
  });
</script>
</body>
</html>`;
}
