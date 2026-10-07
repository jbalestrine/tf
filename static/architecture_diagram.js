(() => {
  'use strict';

  const namespace = 'http://www.w3.org/2000/svg';

  function svgElement(name, attributes, text) {
    const element = document.createElementNS(namespace, name);
    Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (text != null) element.textContent = text;
    return element;
  }

  function renderArchitectureDiagram(container, graph) {
    const allNodes = graph.nodes || [];
    if (allNodes.length > 40) throw new Error('Architecture diagrams support up to 40 components.');
    const hub = graph.hub || graph.title || 'System';
    const sourceNodes = allNodes.map((node, index) =>
      typeof node === 'string'
        ? { id: `component-${index}`, label: node }
        : { id: node.id || `component-${index}`, label: node.label || node.id, subtitle: node.subtitle || '', kind: node.kind || '' }
    );
    const byLabel = new Map(sourceNodes.flatMap(node => [[node.id, node.id], [node.label, node.id]]));
    const hubId = '__architecture_hub__';
    byLabel.set(hub, hubId);
    byLabel.set('hub', hubId);

    let edges = (graph.edges || []).map(edge => ({
      from: byLabel.get(edge.from) || edge.from,
      to: byLabel.get(edge.to) || edge.to,
      label: edge.label || ''
    })).filter(edge => edge.from && edge.to);
    if (!edges.length) {
      edges = sourceNodes.map((node, index) => index < sourceNodes.length - 1
        ? { from: node.id, to: sourceNodes[index + 1].id, label: '' }
        : { from: node.id, to: hubId, label: '' });
    }

    const networkNodes = sourceNodes.filter(node =>
      /(?:^|[.\s])(?:azurerm_virtual_network|aws_vpc|google_compute_network)(?:$|[.\s])|(?:^|[.\s])virtual[ _]network(?:$|[.\s])/i
        .test(`${node.id} ${node.label} ${node.subtitle}`)
    );
    const peeringEdges = edges.filter(edge =>
      /peering/i.test(`${edge.label} ${edge.from} ${edge.to}`)
    );
    const hubNetwork = networkNodes.find(node => /\bhub\b/i.test(`${node.id} ${node.label}`))
      || networkNodes.reduce((best, node) => {
        const degree = peeringEdges.filter(edge => edge.from === node.id || edge.to === node.id).length;
        const bestDegree = best
          ? peeringEdges.filter(edge => edge.from === best.id || edge.to === best.id).length
          : -1;
        return degree > bestDegree ? node : best;
      }, null);
    const hubSpoke = Boolean(hubNetwork && networkNodes.length > 1 && (
      peeringEdges.length || networkNodes.some(node => /\bspoke\b/i.test(`${node.id} ${node.label}`))
    ));
    const columns = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(sourceNodes.length))));
    const width = hubSpoke ? 1760 : 320 + columns * 300;
    const rowCount = Math.ceil(sourceNodes.length / columns);
    const cardWidth = 250;
    const cardHeight = 96;
    const boxes = new Map();
    const serviceNodes = hubSpoke
      ? sourceNodes.filter(node => !networkNodes.includes(node)
        && !/peering/i.test(`${node.id} ${node.label} ${node.subtitle}`))
      : sourceNodes;
    const subnetNodes = serviceNodes.filter(node => /subnet/i.test(`${node.id} ${node.label}`));
    const subnetParents = new Map();
    subnetNodes.forEach(subnet => {
      const parent = networkNodes.find(network =>
        edges.some(edge => edge.from === network.id && edge.to === subnet.id
          || edge.to === network.id && edge.from === subnet.id)
      );
      if (parent) subnetParents.set(subnet.id, parent.id);
    });
    const nestedSubnetIds = new Set(subnetParents.keys());
    let height;
    let serviceStartY = 0;
    let networkBottom = 0;

    if (hubSpoke) {
      const spokeNetworks = networkNodes.filter(node => node !== hubNetwork);
      const subnetCount = network =>
        Array.from(subnetParents.values()).filter(parentId => parentId === network.id).length;
      const networkHeight = network => 150 + subnetCount(network) * 38;
      boxes.set(hubNetwork.id, {
        ...hubNetwork, x: 90, y: 145, w: 470, h: networkHeight(hubNetwork), network: true, hub: true
      });
      let spokeY = 145;
      spokeNetworks.forEach(node => {
        const boxHeight = networkHeight(node);
        boxes.set(node.id, {
          ...node, x: 1030, y: spokeY, w: 570, h: boxHeight, network: true
        });
        spokeY += boxHeight + 55;
      });
      networkBottom = Math.max(...Array.from(boxes.values(), box => box.y + box.h));
      serviceStartY = networkBottom + 120;
      serviceNodes.filter(node => !nestedSubnetIds.has(node.id)).forEach((node, index) => {
        const row = Math.floor(index / 4);
        const column = index % 4;
        boxes.set(node.id, {
          ...node, x: 75 + column * 405, y: serviceStartY + row * 125,
          w: 340, h: 84
        });
      });
      const subnetPositions = new Map();
      subnetNodes.forEach(node => {
        const parentId = subnetParents.get(node.id);
        if (!parentId) return;
        const parentBox = boxes.get(parentId);
        const position = subnetPositions.get(parentId) || 0;
        subnetPositions.set(parentId, position + 1);
        boxes.set(node.id, {
          ...node, x: parentBox.x + 20, y: parentBox.y + 70 + position * 38,
          w: parentBox.w - 40, h: 28, nestedSubnet: true
        });
      });
      const platformNodes = serviceNodes.filter(node => !nestedSubnetIds.has(node.id));
      const serviceRowCount = Math.ceil(platformNodes.length / 4);
      height = Math.max(450, platformNodes.length
        ? serviceStartY + serviceRowCount * 125 + 25
        : networkBottom + 60);
    } else {
      height = 330 + rowCount * 150;
      const hubBox = {
        id: hubId, label: hub, x: width / 2 - 180, y: 105, w: 360, h: 90, hub: true
      };
      boxes.set(hubId, hubBox);
      sourceNodes.forEach((node, index) => {
        const row = Math.floor(index / columns);
        const column = index % columns;
        const rowStart = width / 2 - (Math.min(columns, sourceNodes.length - row * columns) * 300) / 2;
        boxes.set(node.id, {
          ...node, x: rowStart + column * 300 + 25, y: 285 + row * 150,
          w: cardWidth, h: cardHeight
        });
      });
    }

    const right = Math.max(width, ...Array.from(boxes.values(), box => box.x + box.w + 60));
    const bottom = Math.max(height, ...Array.from(boxes.values(), box => box.y + box.h + 60));
    const svg = svgElement('svg', {
      xmlns: namespace, viewBox: `0 0 ${right} ${bottom}`, role: 'img',
      'aria-labelledby': 'architecture-title architecture-description',
      preserveAspectRatio: 'xMidYMid meet'
    });
    svg.append(
      svgElement('title', { id: 'architecture-title' }, `${graph.title || hub} architecture`),
      svgElement('desc', { id: 'architecture-description' },
        hubSpoke ? 'Blueprint-style hub-and-spoke network diagram with separated virtual network regions and labeled peering links.'
          : 'Blueprint-style architecture diagram with aligned components and routed connections.')
    );
    const defs = svgElement('defs');
    const marker = svgElement('marker', {
      id: 'architecture-arrow', markerWidth: 10, markerHeight: 8,
      refX: 9, refY: 4, orient: 'auto', markerUnits: 'strokeWidth'
    });
    marker.append(svgElement('path', { d: 'M0,0 L10,4 L0,8 z', fill: '#61d9ed' }));
    defs.append(marker);
    svg.append(defs);
    svg.append(svgElement('rect', { x: 0, y: 0, width: right, height: bottom, fill: '#0a1927' }));
    for (let x = 0; x < right; x += 32) {
      svg.append(svgElement('path', { d: `M${x} 0V${bottom}`, stroke: '#173047', 'stroke-width': 1 }));
    }
    for (let y = 0; y < bottom; y += 32) {
      svg.append(svgElement('path', { d: `M0 ${y}H${right}`, stroke: '#173047', 'stroke-width': 1 }));
    }
    svg.append(svgElement('rect', {
      x: 18, y: 18, width: right - 36, height: bottom - 36, rx: 8,
      fill: 'none', stroke: '#34718a', 'stroke-width': 2
    }));
    svg.append(svgElement('text', {
      x: 42, y: 55, fill: '#d9f5fa', 'font-size': 23, 'font-family': 'Segoe UI, Arial, sans-serif', 'font-weight': 700,
      'letter-spacing': 1.2
    }, graph.title || hub));
    if (graph.subtitle) svg.append(svgElement('text', {
      x: 42, y: 81, fill: '#87adbc', 'font-size': 14, 'font-family': 'Segoe UI, Arial, sans-serif'
    }, graph.subtitle));
    if (hubSpoke) {
      svg.append(svgElement('text', {
        x: 90, y: 121, fill: '#7fe2ef', 'font-size': 14, 'font-weight': 700,
        'font-family': 'Segoe UI, Arial, sans-serif', 'letter-spacing': 1
      }, 'HUB NETWORK'));
      svg.append(svgElement('text', {
        x: 1030, y: 121, fill: '#7fe2ef', 'font-size': 14, 'font-weight': 700,
        'font-family': 'Segoe UI, Arial, sans-serif', 'letter-spacing': 1
      }, 'SPOKE NETWORKS'));
    }

    const drawn = new Set();
    const visibleEdges = hubSpoke
      ? edges.filter(edge => boxes.has(edge.from) && boxes.has(edge.to)
        && !/peering/i.test(`${edge.label} ${edge.from} ${edge.to}`)
        && !nestedSubnetIds.has(edge.from) && !nestedSubnetIds.has(edge.to)
        && !networkNodes.some(node => node.id === edge.from || node.id === edge.to))
      : edges;
    visibleEdges.forEach(edge => {
      const from = boxes.get(edge.from);
      const to = boxes.get(edge.to);
      if (!from || !to || from.id === to.id) return;
      const key = `${from.id}|${to.id}|${edge.label}`;
      if (drawn.has(key)) return;
      drawn.add(key);
      const sourceRight = to.x >= from.x;
      const startX = sourceRight ? from.x + from.w : from.x;
      const startY = from.y + from.h / 2;
      const endX = sourceRight ? to.x : to.x + to.w;
      const endY = to.y + to.h / 2;
      const midX = (startX + endX) / 2;
      const path = svgElement('path', {
        d: `M ${startX} ${startY} H ${midX} V ${endY} H ${endX}`,
        fill: 'none', stroke: /peering/i.test(edge.label) ? '#61d9ed' : '#85aab6',
        'stroke-width': /peering/i.test(edge.label) ? 3 : 1.7,
        'stroke-dasharray': /peering/i.test(edge.label) ? '9 6' : 'none',
        'marker-end': 'url(#architecture-arrow)'
      });
      svg.append(path);
      if (edge.label) svg.append(svgElement('text', {
        x: midX, y: Math.min(startY, endY) - 8, fill: '#8be8f2',
        'font-size': 12, 'font-family': 'Segoe UI, Arial, sans-serif', 'text-anchor': 'middle',
        'paint-order': 'stroke', stroke: '#0a1927', 'stroke-width': 5, 'stroke-linejoin': 'round'
      }, edge.label));
    });

    if (hubSpoke) {
      if (serviceNodes.some(node => !nestedSubnetIds.has(node.id))) {
        svg.append(svgElement('text', {
          x: 75, y: serviceStartY - 25,
          fill: '#7fe2ef', 'font-size': 14, 'font-weight': 700,
          'font-family': 'Segoe UI, Arial, sans-serif', 'letter-spacing': 1
        }, 'PLATFORM & WORKLOAD COMPONENTS'));
      }
      const spokeNodes = networkNodes.filter(node => node !== hubNetwork);
      const hubCenterY = boxes.get(hubNetwork.id).y + boxes.get(hubNetwork.id).h / 2;
      const spokeCenters = spokeNodes.map(node => boxes.get(node.id).y + boxes.get(node.id).h / 2);
      const busX = 790;
      svg.append(svgElement('path', {
        d: `M560 ${hubCenterY} H${busX}`,
        fill: 'none', stroke: '#61d9ed', 'stroke-width': 3, 'stroke-dasharray': '9 6'
      }));
      if (spokeCenters.length > 1) svg.append(svgElement('path', {
        d: `M${busX} ${Math.min(...spokeCenters)} V${Math.max(...spokeCenters)}`,
        fill: 'none', stroke: '#61d9ed', 'stroke-width': 3, 'stroke-dasharray': '9 6'
      }));
      spokeNodes.forEach((node, index) => {
        const box = boxes.get(node.id);
        const link = peeringEdges.find(edge =>
          edge.from === hubNetwork.id && edge.to === node.id
          || edge.to === hubNetwork.id && edge.from === node.id
        );
        if (!link) return;
        const endY = box.y + box.h / 2;
        svg.append(svgElement('path', {
          d: `M${busX} ${endY} H1030`,
          fill: 'none', stroke: '#61d9ed', 'stroke-width': 3, 'stroke-dasharray': '9 6',
          'marker-end': 'url(#architecture-arrow)'
        }));
        svg.append(svgElement('text', {
          x: 910, y: endY - 8, fill: '#8be8f2', 'font-size': 12,
          'font-family': 'Segoe UI, Arial, sans-serif', 'text-anchor': 'middle',
          'paint-order': 'stroke', stroke: '#0a1927', 'stroke-width': 5, 'stroke-linejoin': 'round'
        }, link.label || 'VNet peering'));
      });
    }

    function drawCard(box, index) {
      const group = svgElement('g', { 'data-component-id': box.id });
      const x = box.network ? box.x : box.x;
      const y = box.network ? box.y : box.y;
      if (box.nestedSubnet) {
        group.append(svgElement('rect', {
          x, y, width: box.w, height: box.h, rx: 4,
          fill: '#173e50', stroke: '#57a9bb', 'stroke-width': 1
        }));
        group.append(svgElement('text', {
          x: x + 10, y: y + 19, fill: '#c3e5e9', 'font-size': 11,
          'font-family': 'Segoe UI, Arial, sans-serif'
        }, `${box.label}  ${wrapLabel(box.subtitle, 40)[0]}`));
        svg.append(group);
        return;
      }
      group.append(svgElement('rect', {
        x, y, width: box.w, height: box.h, rx: box.network ? 10 : 7,
        fill: box.network ? '#102b3d' : (box.hub ? '#16495b' : '#112536'),
        stroke: box.network ? '#38bdd2' : (box.hub ? '#8be8f2' : '#54879a'),
        'stroke-width': box.hub || box.network ? 2.2 : 1.5
      }));
      if (box.network) {
        group.append(svgElement('text', {
          x: x + 18, y: y + 31, fill: '#d9f5fa', 'font-size': 16, 'font-weight': 700,
          'font-family': 'Segoe UI, Arial, sans-serif'
        }, wrapLabel(box.label, 38)[0]));
        group.append(svgElement('text', {
          x: x + 18, y: y + 53, fill: '#80aab8', 'font-size': 11,
          'font-family': 'Segoe UI, Arial, sans-serif'
        }, wrapLabel(box.subtitle || box.kind || 'Virtual network', 62)[0]));
      } else {
        group.append(svgElement('circle', {
          cx: x + 20, cy: y + 20, r: 11, fill: box.hub ? '#26aabd' : '#24829a'
        }));
        group.append(svgElement('text', {
          x: x + box.w / 2, y: y + (box.hub ? 52 : 47), fill: '#d9f5fa',
          'font-size': box.hub ? 17 : 14, 'font-weight': 650, 'text-anchor': 'middle',
          'font-family': 'Segoe UI, Arial, sans-serif'
        }, wrapLabel(box.label, box.hub ? 36 : 28)[0]));
        if (box.subtitle) group.append(svgElement('text', {
          x: x + box.w / 2, y: y + box.h - 17, fill: '#80aab8', 'font-size': 11,
          'text-anchor': 'middle', 'font-family': 'Segoe UI, Arial, sans-serif'
        }, wrapLabel(box.subtitle, 36)[0]));
      }
      svg.append(group);
    }
    if (!hubSpoke) drawCard(boxes.get(hubId), -1);
    const orderedNodes = hubSpoke
      ? [...networkNodes, ...sourceNodes.filter(node => !networkNodes.includes(node))]
      : sourceNodes;
    orderedNodes.forEach((node, index) => {
      const box = boxes.get(node.id);
      if (box) drawCard(box, index);
    });
    svg.append(svgElement('text', {
      x: 42, y: bottom - 28, fill: '#69909e', 'font-size': 12,
      'font-family': 'Segoe UI, Arial, sans-serif'
    }, 'BLUEPRINT VIEW  ·  REVIEW CONNECTIONS BEFORE GENERATING OR DEPLOYING'));
    container.replaceChildren(svg);
    return svg;
  }

  function wrapLabel(value, maxLength) {
    const words = String(value || '').split(/\s+/);
    const lines = [];
    let line = '';
    words.forEach(word => {
      if (line && `${line} ${word}`.length > maxLength) {
        lines.push(line);
        line = word;
      } else {
        line = line ? `${line} ${word}` : word;
      }
    });
    if (line) lines.push(line);
    return lines.length ? lines : [''];
  }

  function downloadArchitectureSvg(container, filename) {
    const svg = container.querySelector('svg');
    if (!svg) throw new Error('Render an architecture diagram before exporting it.');
    const serialized = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${String(filename || 'architecture').replace(/[^a-z0-9_-]+/gi, '_')}.svg`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  window.renderArchitectureDiagram = renderArchitectureDiagram;
  window.downloadArchitectureSvg = downloadArchitectureSvg;
})();
