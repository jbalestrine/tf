/* Source Map 3D view: components (large) and the files they use (small) in a rotatable canvas.
   Usage: SourceMap3D.mount(canvas, infoBox, components, onPick) */
(function (global) {
    'use strict';
    var COLORS = ['#7aa2f7', '#9ece6a', '#f7768e', '#e0af68', '#bb9af7', '#7dcfff', '#ff9e64', '#73daca'];

    function build(components) {
        var nodes = [], links = [], byPath = {}, cats = {};
        components.forEach(function (c) {
            if (!(c.category in cats)) { cats[c.category] = Object.keys(cats).length; }
            var n = { kind: 'component', label: c.title, data: c, color: COLORS[cats[c.category] % COLORS.length], r: 7 };
            nodes.push(n);
            (c.files || []).forEach(function (f) {
                var key = f.path;
                if (!byPath[key]) {
                    byPath[key] = { kind: 'file', label: f.path, data: f, color: f.exists === false ? '#f0c674' : '#6b7280', r: 3, uses: 0 };
                    nodes.push(byPath[key]);
                }
                byPath[key].uses += 1;
                links.push([n, byPath[key]]);
            });
        });
        nodes.forEach(function (n, i) {
            var a = i * 2.399963, y = 1 - 2 * ((i + 0.5) / nodes.length), rr = Math.sqrt(1 - y * y);
            n.x = Math.cos(a) * rr * 120; n.y = y * 120; n.z = Math.sin(a) * rr * 120;
            n.vx = n.vy = n.vz = 0;
        });
        return { nodes: nodes, links: links };
    }

    function settle(g) {
        var nodes = g.nodes, i, j, k, a, b, dx, dy, dz, d2, d, f;
        for (k = 0; k < 160; k++) {
            for (i = 0; i < nodes.length; i++) {
                a = nodes[i];
                for (j = i + 1; j < nodes.length; j++) {
                    b = nodes[j];
                    dx = a.x - b.x; dy = a.y - b.y; dz = a.z - b.z;
                    d2 = dx * dx + dy * dy + dz * dz + 0.01;
                    if (d2 > 40000) { continue; }
                    f = 900 / d2; d = Math.sqrt(d2);
                    a.vx += dx / d * f; a.vy += dy / d * f; a.vz += dz / d * f;
                    b.vx -= dx / d * f; b.vy -= dy / d * f; b.vz -= dz / d * f;
                }
            }
            g.links.forEach(function (l) {
                var p = l[0], q = l[1];
                dx = q.x - p.x; dy = q.y - p.y; dz = q.z - p.z;
                d = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
                f = (d - 45) * 0.02;
                p.vx += dx / d * f; p.vy += dy / d * f; p.vz += dz / d * f;
                q.vx -= dx / d * f; q.vy -= dy / d * f; q.vz -= dz / d * f;
            });
            nodes.forEach(function (n) {
                n.vx -= n.x * 0.004; n.vy -= n.y * 0.004; n.vz -= n.z * 0.004;
                n.x += n.vx; n.y += n.vy; n.z += n.vz;
                n.vx *= 0.8; n.vy *= 0.8; n.vz *= 0.8;
            });
        }
    }

    function mount(canvas, components, onPick) {
        var g = build(components), ctx = canvas.getContext('2d');
        settle(g);
        var rotY = 0.5, rotX = 0.3, zoom = 1.05, auto = true, drag = null, hover = null, picked = null, projected = [];
        var dpr = global.devicePixelRatio || 1;

        function resize() {
            var w = canvas.clientWidth || 600, h = canvas.clientHeight || 380;
            canvas.width = w * dpr; canvas.height = h * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        function project(n, w, h) {
            var cy = Math.cos(rotY), sy = Math.sin(rotY), cx = Math.cos(rotX), sx = Math.sin(rotX);
            var x = n.x * cy + n.z * sy, z = -n.x * sy + n.z * cy, y = n.y * cx - z * sx;
            z = n.y * sx + z * cx;
            var s = (260 / (260 + z)) * zoom;
            return { n: n, x: w / 2 + x * s, y: h / 2 + y * s, s: s, z: z };
        }
        function draw() {
            var w = canvas.clientWidth, h = canvas.clientHeight;
            ctx.clearRect(0, 0, w, h);
            var map = new Map();
            projected = g.nodes.map(function (n) { var p = project(n, w, h); map.set(n, p); return p; });
            var focus = picked || hover;
            var linked = new Set();
            if (focus) {
                linked.add(focus);
                g.links.forEach(function (l) { if (l[0] === focus) { linked.add(l[1]); } if (l[1] === focus) { linked.add(l[0]); } });
            }
            ctx.lineWidth = 1;
            g.links.forEach(function (l) {
                var a = map.get(l[0]), b = map.get(l[1]), on = focus && (l[0] === focus || l[1] === focus);
                ctx.strokeStyle = on ? 'rgba(122,162,247,.9)' : 'rgba(148,163,184,.14)';
                ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
            });
            projected.slice().sort(function (a, b) { return b.z - a.z; }).forEach(function (p) {
                var dim = focus && !linked.has(p.n);
                ctx.globalAlpha = dim ? 0.25 : Math.max(0.45, Math.min(1, p.s / 1.05));
                ctx.fillStyle = p.n.color;
                ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(1.5, p.n.r * p.s), 0, 6.2832); ctx.fill();
                if (p.n.kind === 'component' && !dim) {
                    ctx.globalAlpha = 0.9; ctx.fillStyle = '#e5e7eb'; ctx.font = '11px sans-serif';
                    ctx.fillText(p.n.label, p.x + p.n.r * p.s + 3, p.y + 3);
                }
            });
            ctx.globalAlpha = 1;
            if (hover && hover !== picked) {
                var hp = map.get(hover);
                ctx.fillStyle = '#111827'; ctx.strokeStyle = '#374151';
                var tw = ctx.measureText(hover.label).width + 10;
                ctx.fillRect(hp.x + 8, hp.y - 18, tw, 18); ctx.strokeRect(hp.x + 8, hp.y - 18, tw, 18);
                ctx.fillStyle = '#e5e7eb'; ctx.fillText(hover.label, hp.x + 13, hp.y - 5);
            }
        }
        function tick() {
            if (auto && !drag && !picked) { rotY += 0.0035; }
            draw();
            global.requestAnimationFrame(tick);
        }
        function nearest(ev) {
            var r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, best = null, bd = 169;
            projected.forEach(function (p) {
                var d = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y);
                if (d < bd) { bd = d; best = p.n; }
            });
            return best;
        }
        canvas.addEventListener('mousedown', function (e) { drag = { x: e.clientX, y: e.clientY, moved: false }; });
        global.addEventListener('mouseup', function (e) {
            if (drag && !drag.moved && e.target === canvas) {
                picked = nearest(e);
                onPick(picked ? { kind: picked.kind, label: picked.label, data: picked.data, links: linksOf(picked) } : null);
            }
            drag = null;
        });
        global.addEventListener('mousemove', function (e) {
            if (drag) {
                var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
                if (Math.abs(dx) + Math.abs(dy) > 2) { drag.moved = true; }
                rotY += dx * 0.008; rotX = Math.max(-1.4, Math.min(1.4, rotX + dy * 0.008));
                drag.x = e.clientX; drag.y = e.clientY;
            } else if (e.target === canvas) { hover = nearest(e); }
        });
        canvas.addEventListener('mouseleave', function () { hover = null; });
        canvas.addEventListener('wheel', function (e) {
            e.preventDefault(); zoom = Math.max(0.6, Math.min(4, zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
        }, { passive: false });
        function linksOf(n) {
            return g.links.filter(function (l) { return l[0] === n || l[1] === n; })
                .map(function (l) { return l[0] === n ? l[1] : l[0]; })
                .map(function (o) { return { kind: o.kind, label: o.label, data: o.data }; });
        }
        resize(); global.addEventListener('resize', resize); tick();
        return {
            reset: function () { picked = null; auto = true; rotX = 0.3; zoom = 1.05; onPick(null); },
            toggleSpin: function () { auto = !auto; return auto; },
            stats: { components: g.nodes.filter(function (n) { return n.kind === 'component'; }).length,
                     files: g.nodes.filter(function (n) { return n.kind === 'file'; }).length,
                     shared: g.nodes.filter(function (n) { return n.kind === 'file' && n.uses > 1; }).length }
        };
    }

    global.SourceMap3D = { mount: mount };
})(window);
