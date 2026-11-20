/* Perspective projection adapted from Source Map's rotatable 3D canvas. */
(() => {
  const canvas = document.getElementById('ecosystem-canvas');
  const select = document.getElementById('ecosystem-file');
  const detail = document.getElementById('ecosystem-detail');
  const reset = document.getElementById('ecosystem-reset');
  const ctx = canvas.getContext('2d');
  let nodes = [], edges = [], projected = [], rotationX = 0.3, rotationY = 0.5, zoom = 1, drag = null;

  function showDetail() {
    detail.replaceChildren();
    const path = select.value;
    if (!path) {
      detail.textContent = nodes.length ? `${nodes.length} files in the map. Select a file to inspect its direct connections.` : 'No files to display.';
      return;
    }
    const heading = document.createElement('strong');
    heading.textContent = path;
    detail.append(heading);
    detail.append(' ', window.gitFileEditorLink(path));
    const connections = edges.filter(edge => edge.from === path || edge.to === path);
    if (!connections.length) {
      const message = document.createElement('p');
      message.textContent = 'No resolved Python imports involving this file were found in the displayed results.';
      detail.append(message);
      return;
    }
    const list = document.createElement('ul');
    for (const edge of connections) {
      const item = document.createElement('li');
      item.textContent = edge.from === path ? `Imports: ${edge.to}` : `Imported by: ${edge.from}`;
      list.append(item);
    }
    detail.append(list);
  }

  function draw() {
    if (!ctx) return;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const cy = Math.cos(rotationY), sy = Math.sin(rotationY), cx = Math.cos(rotationX), sx = Math.sin(rotationX);
    const scale = Math.min(width, height) * 0.36 * zoom;
    const positions = new Map();
    projected = nodes.map(node => {
      const x = node.x * cy + node.z * sy, z0 = -node.x * sy + node.z * cy;
      const y = node.y * cx - z0 * sx, z = node.y * sx + z0 * cx;
      const perspective = 3 / (3 + z);
      const point = { node, x: width / 2 + x * scale * perspective, y: height / 2 + y * scale * perspective, z, perspective };
      positions.set(node.path, point);
      return point;
    });
    const focus = select.value;
    const neighbors = new Set(focus ? [focus] : []);
    for (const edge of edges) {
      if (edge.from === focus) neighbors.add(edge.to);
      if (edge.to === focus) neighbors.add(edge.from);
      const a = positions.get(edge.from), b = positions.get(edge.to);
      if (!a || !b) continue;
      const active = focus && (edge.from === focus || edge.to === focus);
      ctx.strokeStyle = active ? 'rgba(125,211,252,.95)' : 'rgba(148,163,184,.25)';
      ctx.lineWidth = active ? 2 : 1;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    projected.slice().sort((a, b) => b.z - a.z).forEach(point => {
      ctx.globalAlpha = focus && !neighbors.has(point.node.path) ? 0.18 : 1;
      ctx.fillStyle = point.node.changed ? '#80dcac' : '#7aa2f7';
      ctx.beginPath();
      ctx.arc(point.x, point.y, (point.node.path === focus ? 7 : point.node.changed ? 5 : 3.5) * point.perspective, 0, Math.PI * 2);
      ctx.fill();
      if (point.node.path === focus) {
        ctx.fillStyle = '#fff'; ctx.font = '12px sans-serif';
        ctx.fillText(point.node.path, point.x + 9, point.y - 7);
      }
    });
    ctx.globalAlpha = 1;
  }

  function load(data) {
    if (!ctx) {
      detail.textContent = '3D canvas is unavailable in this browser. Use the file and relationship lists below.';
      return;
    }
    const changed = new Set(data.files.map(file => file.path));
    const paths = new Set(changed);
    edges = data.edges;
    for (const edge of edges) { paths.add(edge.from); paths.add(edge.to); }
    nodes = Array.from(paths).sort().map((path, i, all) => {
      const angle = i * 2.399963, y = 1 - 2 * (i + 0.5) / all.length, radius = Math.sqrt(1 - y * y);
      return { path, changed: changed.has(path), x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius };
    });
    const previous = select.value;
    select.replaceChildren(new Option('All files', ''));
    for (const node of nodes) select.add(new Option(`${node.changed ? 'Changed: ' : 'Related: '}${node.path}`, node.path));
    select.value = paths.has(previous) ? previous : '';
    select.disabled = reset.disabled = !nodes.length;
    showDetail(); draw();
  }

  select.addEventListener('change', () => { showDetail(); draw(); if (select.value) window.GitActivityEditor.open(select.value); });
  reset.addEventListener('click', () => {
    rotationX = 0.3; rotationY = 0.5; zoom = 1; select.value = '';
    showDetail(); draw();
  });
  canvas.addEventListener('pointerdown', event => {
    drag = { x: event.clientX, y: event.clientY, moved: false };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    if (!drag) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
    rotationY += dx * 0.008; rotationX = Math.max(-1.4, Math.min(1.4, rotationX + dy * 0.008));
    drag.x = event.clientX; drag.y = event.clientY; draw();
  });
  canvas.addEventListener('pointerup', event => {
    if (drag && !drag.moved) {
      const rect = canvas.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      let closest = null, distance = 144;
      for (const point of projected) {
        const d = (point.x - x) ** 2 + (point.y - y) ** 2;
        if (d < distance) { distance = d; closest = point.node.path; }
      }
      select.value = closest || ''; showDetail(); draw();
      if (closest) window.GitActivityEditor.open(closest);
    }
    drag = null;
  });
  canvas.addEventListener('pointercancel', () => { drag = null; });
  canvas.addEventListener('wheel', event => {
    event.preventDefault(); zoom = Math.max(0.5, Math.min(3, zoom * (event.deltaY < 0 ? 1.1 : 0.9))); draw();
  }, { passive: false });
  window.addEventListener('resize', draw);
  window.GitActivity3D = { load };
})();
