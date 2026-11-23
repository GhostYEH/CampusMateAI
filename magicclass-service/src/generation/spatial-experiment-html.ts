/** Self-contained browser player for the portable classroom-spatial/1 data. */
export function spatialExperimentHtml(config: Record<string, unknown>, marker: string): string {
  const data = JSON.stringify(config).replace(/</g, '\\u003c');
  return `<!doctype html><html lang="zh-CN"><head>${marker}
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#142c2b;color:#f2f1e8;font:16px/1.5 system-ui,sans-serif}
main{min-height:100vh;display:grid;grid-template-rows:minmax(180px,1fr) auto}
#stage{position:relative;background:radial-gradient(ellipse at 50% 45%,#30554e,#102522 78%)}
canvas{display:block;position:absolute;inset:0;height:100%;width:100%;touch-action:none;cursor:grab}canvas:active{cursor:grabbing}
#status{position:relative;margin:0;padding:12px;pointer-events:none}#status:empty{display:none}
footer{display:grid;gap:8px;padding:10px 14px;border-top:1px solid #496961}p{margin:0;overflow-wrap:anywhere}
nav{display:flex;flex-wrap:wrap;gap:8px;align-items:center}button,select{font:inherit;color:inherit;background:#234541;
border:1px solid #759589;border-radius:8px;min-height:44px;padding:4px 12px;max-width:100%}button{min-width:44px;cursor:pointer}
button[aria-pressed=true]{background:#dab27a;color:#142c2b}button:focus-visible,select:focus-visible{outline:2px solid #dab27a;outline-offset:2px}
</style></head><body><main>
<section id="stage"><canvas role="img" aria-label="可拖动旋转的三维模型"></canvas><p id="status" role="status"></p></section>
<footer><p id="description"></p><nav aria-label="三维模型控制">
<select id="parts" aria-label="高亮部件"><option value="">查看整体</option></select>
<button id="zoom-out" aria-label="缩小模型" type="button">−</button>
<button id="zoom-in" aria-label="放大模型" type="button">＋</button>
<button id="reset" type="button">重置视角</button>
<button id="motion" type="button" aria-pressed="false" hidden>播放动画</button>
</nav></footer></main>
<script type="application/json" id="widget-config">${data}</script>
<script>
(() => {
  const byId = (id) => document.getElementById(id);
  const config = JSON.parse(byId('widget-config').textContent);
  byId('description').textContent = config.description;
  const canvas = document.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) { byId('status').textContent = '当前设备无法绘制三维模型。'; return; }

  const zero = [0, 0, 0];
  const xyz = (p) => p ? [p.x, p.y, p.z] : zero;
  const sum = (a, b) => a.map((n, k) => n + b[k]);
  const diff = (a, b) => a.map((n, k) => n - b[k]);
  const mul = (a, n) => a.map((v) => v * n);
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = ([x,y,z], [u,v,w]) => [y*w-z*v, z*u-x*w, x*v-y*u];
  const len = (p) => Math.hypot(...p);
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  const box = {
    vertices: [[-.5,-.5,-.5],[.5,-.5,-.5],[.5,.5,-.5],[-.5,.5,-.5],[-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5]],
    faces: [[0,3,2,1],[4,5,6,7],[0,4,7,3],[1,2,6,5],[0,1,5,4],[3,7,6,2]],
  };
  // The six primitives use the same dimensions and axes as the native player.
  function revolve(profile, orientation = (p) => p) {
    const sides = 16, vertices = [], faces = [];
    for (const [height, radius] of profile) {
      for (let i = 0; i < sides; i++) {
        const angle = i * 2 * Math.PI / sides;
        vertices.push(orientation([radius * Math.cos(angle), height, radius * Math.sin(angle)]));
      }
    }
    for (let row = 0; row < profile.length - 1; row++) {
      for (let i = 0; i < sides; i++) {
        const start = row * sides, next = (i + 1) % sides;
        faces.push([start+i, start+sides+i, start+sides+next, start+next]);
      }
    }
    return { vertices, faces };
  }
  const meshes = {
    box,
    plane: { vertices: box.vertices.slice(0,4).map(([x,y]) => [x,y,0]), faces: [[0,1,2,3]] },
    cylinder: revolve([[-.5,0],[-.5,.5],[.5,.5],[.5,0]]),
    cone: revolve([[-.5,0],[-.5,.5],[.5,0]]),
    sphere: revolve(Array.from({length: 11}, (_, i) => [-.5 * Math.cos(i*Math.PI/10), .5 * Math.sin(i*Math.PI/10)])),
    torus: revolve(Array.from({length: 9}, (_, i) => [.12 * Math.sin(i*Math.PI/4), .36 + .12 * Math.cos(i*Math.PI/4)]),
      ([x,y,z]) => [x,-z,y]),
  };

  function makeRotation([rx, ry, rz]) {
    const cx = Math.cos(rx), cy = Math.cos(ry), cz = Math.cos(rz);
    const sx = Math.sin(rx), sy = Math.sin(ry), sz = Math.sin(rz);
    return ([x,y,z]) => {
      const a = x*cz-y*sz, b = x*sz+y*cz;
      const u = a*cy+z*sy, w = -a*sy+z*cy;
      return [u, b*cx-w*sx, b*sx+w*cx];
    };
  }

  const parts = byId('parts');
  let animated = false;
  function makePart(item) {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.name;
    parts.append(option);
    const motion = item.animation;
    animated ||= Boolean(motion);
    const unit = ['x','y','z'].map((axis) => Number(axis === motion?.axis));
    const scale = typeof item.scale === 'number' ? [item.scale,item.scale,item.scale] : xyz(item.scale ?? { x:1,y:1,z:1 });
    return { item, mesh: meshes[item.type], position: xyz(item.position), rotation: xyz(item.rotation),
      scale, motion, unit, children: (item.children ?? []).map(makePart) };
  }
  const solids = config.objects.map(makePart);
  const motionButton = byId('motion');
  motionButton.hidden = !animated;

  function extent(part) {
    const childRadius = Math.max(.87, ...part.children.map((child) => len(child.position) + extent(child)));
    const base = childRadius * Math.max(...part.scale);
    if (part.motion?.type === 'bounce') return base + .25;
    if (part.motion?.type === 'pulse') return base * 1.12;
    if (part.motion?.type === 'orbit') return base + len(part.position);
    return base;
  }
  const bounds = solids.map((part) => ({
    center: part.motion?.type === 'orbit' ? zero : part.position, radius: extent(part),
  }));
  const origin = zero.map((_, axis) => (Math.min(...bounds.map(({center,radius}) => center[axis]-radius)) +
    Math.max(...bounds.map(({center,radius}) => center[axis]+radius))) / 2);
  const radius = Math.max(.01, ...bounds.map((bound) => bound.radius + len(diff(bound.center, origin))));

  let yaw = .65, pitch = .36, zoom = 1, elapsed = 0, lastTime = 0, raf = 0, playing = false;
  const requestPaint = () => { if (!raf && !document.hidden) raf = requestAnimationFrame(draw); };
  function transform(part, parent) {
    let { position, rotation, scale } = part;
    const phase = elapsed * (part.motion?.speed ?? 0);
    if (part.motion?.type === 'rotate') rotation = sum(rotation, mul(part.unit, phase));
    if (part.motion?.type === 'orbit') position = makeRotation(mul(part.unit, phase))(position);
    if (part.motion?.type === 'bounce') position = sum(position, mul(part.unit, .25 * Math.abs(Math.sin(phase))));
    if (part.motion?.type === 'pulse') scale = mul(scale, 1 + .12 * Math.sin(phase));
    const rotate = makeRotation(rotation);
    return (point) => parent(sum(rotate(point.map((n,k) => n * scale[k])), position));
  }

  function draw(now) {
    raf = 0;
    if (playing && lastTime) elapsed += Math.min(.05, (now - lastTime) / 1000);
    lastTime = playing ? now : 0;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(w*dpr)) canvas.width = Math.round(w*dpr);
    if (canvas.height !== Math.round(h*dpr)) canvas.height = Math.round(h*dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,w,h);
    const direction = [Math.sin(yaw)*Math.cos(pitch), Math.sin(pitch), Math.cos(yaw)*Math.cos(pitch)];
    const right = [Math.cos(yaw), 0, -Math.sin(yaw)];
    const up = cross(direction, right);
    const unit = Math.min(w,h) * .46 * zoom / radius;
    const project = (point) => [w/2 + dot(point,right)*unit, h/2 - dot(point,up)*unit];
    const faces = [];
    function visit(part, parent) {
      const world = transform(part, parent);
      const vertices = part.mesh.vertices.map((p) => diff(world(p), origin));
      for (const indices of part.mesh.faces) {
        const points = indices.map((index) => vertices[index]);
        // A ring face at a pole can begin with two coincident vertices.
        const relative = points.slice(1).map((p) => diff(p, points[0]));
        const normal = cross(relative[1], relative[2] ?? relative[0]);
        const magnitude = len(normal);
        const light = magnitude ? Math.abs(dot(normal, [-.36,.78,.5]) / magnitude) : .5;
        faces.push({ points, light, item: part.item, depth: points.reduce((v,p) => v + dot(p,direction), 0)/points.length });
      }
      part.children.forEach((child) => visit(child, world));
    }
    solids.forEach((part) => visit(part, (p) => p));
    faces.sort((a,b) => a.depth - b.depth);
    const selected = parts.value;
    for (const { points, light, item } of faces) {
      const marked = item.id === selected;
      const color = item.material.color;
      ctx.beginPath();
      points.map(project).forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
      ctx.closePath();
      ctx.globalAlpha = (item.material.opacity ?? 1) * (selected && !marked ? .36 : 1);
      if (!item.material.wireframe) {
        ctx.fillStyle = color;
        ctx.fill();
        ctx.globalAlpha *= (1-light)*.34;
        ctx.fillStyle = '#102522';
        ctx.fill();
      }
      if (marked || item.material.wireframe || item.type === 'box' || item.type === 'plane') {
        ctx.globalAlpha = marked ? .9 : .43;
        ctx.strokeStyle = marked ? '#ffd699' : item.material.wireframe ? color : '#102522';
        ctx.lineWidth = marked ? 1.5 : 1;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    if (playing) requestPaint();
  }

  let pointer;
  canvas.addEventListener('pointerdown', (event) => {
    if (pointer || event.button !== 0) return;
    pointer = { id:event.pointerId, x:event.clientX, y:event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (pointer?.id !== event.pointerId) return;
    yaw = (yaw + (pointer.x - event.clientX)*.012) % (2*Math.PI);
    pitch = clamp(pitch + (event.clientY - pointer.y)*.012, -1.5, 1.5);
    pointer.x = event.clientX; pointer.y = event.clientY;
    requestPaint();
  });
  for (const name of ['pointerup','pointercancel','lostpointercapture']) {
    canvas.addEventListener(name, (event) => { if (pointer?.id === event.pointerId) pointer = null; });
  }
  byId('zoom-in').onclick = () => { zoom = clamp(zoom*1.25,.45,4); requestPaint(); };
  byId('zoom-out').onclick = () => { zoom = clamp(zoom/1.25,.45,4); requestPaint(); };
  byId('reset').onclick = () => { yaw = .65; pitch = .36; zoom = 1; requestPaint(); };
  parts.onchange = requestPaint;
  motionButton.onclick = () => {
    playing = !playing;
    lastTime = 0;
    motionButton.textContent = playing ? '暂停动画' : '播放动画';
    motionButton.setAttribute('aria-pressed', String(playing));
    requestPaint();
  };
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent || (event.data?.type ?? event.data?.action) !== 'HIGHLIGHT_ELEMENT') return;
    const target = event.data.target ?? event.data.payload?.elementId;
    if (typeof target !== 'string') return;
    parts.value = target.replace(/^#/, '');
    requestPaint();
  });
  document.addEventListener('visibilitychange', () => { lastTime = 0; requestPaint(); });
  if ('ResizeObserver' in window) new ResizeObserver(requestPaint).observe(canvas);
  else window.addEventListener('resize', requestPaint);
  requestPaint();
})();
</script></body></html>`;
}
