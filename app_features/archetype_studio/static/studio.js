(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const svgNS = 'http://www.w3.org/2000/svg';
  const categories = {
    'Diagramming': [['Boundary', 'boundary', '▢'], ['Service', 'service', '▣'], ['Note', 'note', '▤'], ['Decision', 'decision', '◇'], ['External system', 'external', '↗'], ['User', 'user', '♙']],
    'Compute and hosting': [['Virtual machine', 'vm', '▥'], ['Virtual machine scale set', 'vm-scale-set', '▥'], ['App Service', 'app-service', '▣'], ['Azure Function', 'function', 'ƒ'], ['Container Apps', 'container-apps', '▦'], ['Kubernetes Service', 'aks', '▦'], ['Container Registry', 'registry', '▦'], ['Batch', 'batch', '▥']],
    'Networking': [['Virtual network', 'network', '◇'], ['Subnet', 'subnet', '▱'], ['VNet peering', 'peering', '⇄'], ['ExpressRoute', 'expressroute', '⇄'], ['VPN Gateway', 'vpn', '⇄'], ['Virtual WAN', 'vwan', '◇'], ['Load Balancer', 'load-balancer', '⇄'], ['Application Gateway', 'application-gateway', '⇄'], ['Front Door', 'front-door', '⇄'], ['Private Endpoint', 'private-endpoint', '◇'], ['Private DNS zone', 'private-dns-zone', '◇'], ['Private DNS VNet link', 'private-dns-link', '⇄'], ['NAT Gateway', 'nat', '⇄'], ['Network Security Group', 'nsg', '◇'], ['NSG rule', 'nsg-rule', '◇'], ['Azure Firewall', 'firewall', '▣'], ['Web Application Firewall', 'waf', '▣']],
    'Data and storage': [['SQL Database', 'sql-database', '◉'], ['SQL Managed Instance', 'sql-managed', '◉'], ['Cosmos DB', 'cosmos-db', '◉'], ['PostgreSQL', 'postgresql', '◉'], ['MySQL', 'mysql', '◉'], ['Redis cache', 'redis', '◉'], ['Storage account', 'storage', '▦'], ['Blob storage', 'blob', '▦'], ['File storage', 'file-storage', '▦'], ['Data Lake', 'data-lake', '▦'], ['Backup vault', 'backup', '▦']],
    'Integration and messaging': [['API Management', 'api-management', '⇄'], ['Service Bus', 'service-bus', '⇄'], ['Event Grid', 'event-grid', '⇄'], ['Event Hubs', 'event-hubs', '⇄'], ['Logic Apps', 'logic-apps', 'ƒ'], ['Data Factory', 'data-factory', '▣']],
    'Identity and security': [['Microsoft Entra ID', 'entra-id', '♙'], ['Managed identity', 'managed-identity', '♙'], ['Key Vault', 'key-vault', '◆'], ['Defender for Cloud', 'defender', '◆'], ['Microsoft Sentinel', 'sentinel', '◆'], ['DDoS Protection', 'ddos', '◆'], ['Private Link', 'private-link', '◇']],
    'Monitoring and operations': [['Azure Monitor', 'monitor', '◫'], ['Log Analytics', 'log-analytics', '▤'], ['Application Insights', 'application-insights', '◫'], ['Alerts', 'alerts', '◇'], ['Automation', 'automation', '⚙'], ['Recovery Services', 'recovery', '▦']],
    'Analytics and AI': [['Synapse Analytics', 'synapse', '▣'], ['Microsoft Fabric', 'fabric', '▣'], ['Azure Databricks', 'databricks', '▣'], ['Machine Learning', 'machine-learning', '✦'], ['Azure AI services', 'ai-services', '✦'], ['Azure AI Search', 'ai-search', '⌕']],
    'DevOps and governance': [['Source repository', 'repository', '▤'], ['CI/CD pipeline', 'pipeline', '⇢'], ['Terraform', 'terraform', '▣'], ['ARM / Bicep template', 'arm-bicep', '▤'], ['Subscription', 'subscription', '▢'], ['Management group', 'management-group', '▢'], ['Resource group', 'resource-group', '▢'], ['Azure Policy', 'policy', '◆'], ['Cost Management', 'cost-management', '◫']]
  };
  let doc = {version: 1, title: 'Untitled architecture', nodes: [], edges: []};
  let savedSnapshot = JSON.stringify(doc);
  window.addEventListener('beforeunload', event => {
    if (JSON.stringify(doc) !== savedSnapshot) { event.preventDefault(); event.returnValue = ''; }
  });
  let selected = null, mode = 'select', connectFrom = null, drag = null;
  let view = {x: 40, y: 40, scale: 1};
  const uid = () => `n${Date.now().toString(36)}${Math.random().toString(36).slice(2, 9)}`;
  const status = text => { $('status').textContent = text; };
  function ask(message, value) {
    return new Promise(resolve => {
      const dialog = document.createElement('dialog'); dialog.className = 'studio-dialog';
      const form = document.createElement('form'); form.method = 'dialog';
      const heading = document.createElement('h2'); heading.textContent = message;
      form.append(heading);
      let input;
      if (value !== undefined) {
        input = document.createElement('input'); input.value = value; input.setAttribute('aria-label', message);
        form.append(input);
      }
      const buttons = document.createElement('div'); buttons.className = 'dialog-actions';
      const cancel = document.createElement('button'); cancel.value = 'cancel'; cancel.textContent = 'Cancel';
      const accept = document.createElement('button'); accept.value = 'accept'; accept.textContent = 'Continue'; accept.className = 'primary';
      buttons.append(cancel, accept); form.append(buttons); dialog.append(form); document.querySelector('.studio').append(dialog);
      dialog.addEventListener('close', () => {
        const answer = dialog.returnValue === 'accept' ? (input ? input.value : true) : (input ? null : false);
        dialog.remove(); resolve(answer);
      }, {once:true});
      dialog.showModal(); if (input) { input.focus(); input.select(); }
    });
  }
  function element(tag, attrs = {}, text) {
    const el = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function validate(value) {
    if (!value || value.version !== 1 || typeof value.title !== 'string' || value.title.length > 200 ||
        !Array.isArray(value.nodes) || value.nodes.length > 300 || !Array.isArray(value.edges) || value.edges.length > 600)
      throw new Error('Invalid or unsupported diagram document.');
    const ids = new Set();
    for (const n of value.nodes) {
      if (!n || typeof n.id !== 'string' || ids.has(n.id) || !/^[a-zA-Z0-9_-]{1,80}$/.test(n.id) ||
          typeof n.label !== 'string' || n.label.length > 160 || typeof n.kind !== 'string' ||
          ![n.x,n.y,n.w,n.h].every(Number.isFinite) || Math.abs(n.x) > 9000 || Math.abs(n.y) > 9000 ||
          n.w < 60 || n.w > 2000 || n.h < 40 || n.h > 2000 ||
          (n.image != null && (typeof n.image !== 'string' || !/^data:image\/(svg\+xml|png);base64,[A-Za-z0-9+/=]+$/.test(n.image))))
        throw new Error('Invalid shape in diagram.');
      ids.add(n.id);
    }
    const edgeIds = new Set();
    for (const e of value.edges) {
      if (!e || typeof e.id !== 'string' || edgeIds.has(e.id) || !ids.has(e.from) || !ids.has(e.to) || e.from === e.to ||
          typeof e.label !== 'string' || e.label.length > 160 || typeof e.dashed !== 'boolean')
        throw new Error('Invalid connection in diagram.');
      edgeIds.add(e.id);
    }
    return value;
  }
  function renderPalette() {
    const palette = $('palette'); palette.replaceChildren();
    const query = $('search').value.toLowerCase();
    Object.entries(categories).forEach(([category, items]) => {
      const matching = items.filter(item => `${category} ${item[0]}`.toLowerCase().includes(query));
      if (!matching.length) return;
      const heading = document.createElement('h3'); heading.textContent = category; palette.append(heading);
      matching.forEach(([label, kind, icon]) => {
        const button = document.createElement('button'); button.className = 'stencil'; button.type = 'button';
        const symbol = document.createElement('span'); symbol.className = 'stencil-icon'; symbol.textContent = icon;
        const name = document.createElement('span'); name.textContent = label;
        button.append(symbol, name); button.addEventListener('click', () => addNode(label, kind)); palette.append(button);
      });
    });
  }
  function addNode(label, kind, image = null) {
    if (doc.nodes.length >= 300) return status('The diagram has reached its 300-shape limit.');
    const rect = $('viewport').getBoundingClientRect();
    const node = {id: uid(), label, kind, x: (rect.width / 2 - view.x) / view.scale - 80,
      y: (rect.height / 2 - view.y) / view.scale - 40, w: 170, h: 90};
    if (kind === 'boundary') { node.w = 320; node.h = 220; }
    if (image) node.image = image;
    doc.nodes.push(node); selected = {type:'node', id:node.id}; render(); status('Shape added. Drag it to move; edit dimensions in Inspector.');
  }
  function render() {
    $('scene').setAttribute('transform', `translate(${view.x} ${view.y}) scale(${view.scale})`);
    $('zoom-label').textContent = `${Math.round(view.scale * 100)}%`;
    const edgeLayer = $('edges'), nodeLayer = $('nodes'); edgeLayer.replaceChildren(); nodeLayer.replaceChildren();
    const nodes = new Map(doc.nodes.map(n => [n.id, n]));
    for (const e of doc.edges) {
      const a = nodes.get(e.from), b = nodes.get(e.to); if (!a || !b) continue;
      const x1 = a.x+a.w/2, y1 = a.y+a.h/2, x2 = b.x+b.w/2, y2 = b.y+b.h/2;
      const group = element('g', {class: `edge${selected?.type === 'edge' && selected.id === e.id ? ' selected' : ''}`});
      const attrs = {x1,y1,x2,y2};
      group.append(element('line', {...attrs, class:'edge-hit'}));
      group.append(element('line', {...attrs, class:'edge-line', stroke:'#527596', 'stroke-width':2, 'stroke-dasharray':e.dashed?'7 5':'none', 'marker-end':'url(#arrow)'}));
      if (e.label) group.append(element('text', {x:(x1+x2)/2, y:(y1+y2)/2-7, 'text-anchor':'middle', fill:'#344c68', 'font-size':12}, e.label));
      group.addEventListener('pointerdown', event => { event.stopPropagation(); selected={type:'edge',id:e.id}; render(); });
      edgeLayer.append(group);
    }
    // Boundaries are drawn behind other nodes so their interiors do not hide services.
    for (const n of [...doc.nodes].sort((a,b) => (a.kind === 'boundary' ? -1 : 0) - (b.kind === 'boundary' ? -1 : 0))) {
      const group = element('g', {class:`node${selected?.type === 'node' && selected.id === n.id ? ' selected' : ''}`, transform:`translate(${n.x} ${n.y})`});
      group.append(element('rect', {class:'node-box', width:n.w, height:n.h, rx:n.kind === 'boundary'?12:10,
        fill:n.kind === 'boundary'?'#eef5ff':'white', 'fill-opacity':n.kind === 'boundary'?'0.35':'1',
        stroke:n.kind === 'boundary'?'#7ea2c8':'#cad9e9', 'stroke-width':1.5, 'stroke-dasharray':n.kind === 'boundary'?'7 5':'none'}));
      if (n.image) group.append(element('image', {href:n.image, x:12, y:10, width:48, height:48, preserveAspectRatio:'xMidYMid meet'}));
      const labelX = n.image ? 69 : 14;
      group.append(element('text', {x:labelX, y:n.image?30:28, fill:'#243c59', 'font-size':14, 'font-weight':600}, n.label));
      group.append(element('text', {x:labelX, y:n.image?48:48, fill:'#7890aa', 'font-size':10}, n.kind.toUpperCase()));
      group.addEventListener('pointerdown', event => startNode(event,n));
      nodeLayer.append(group);
    }
    updateInspector();
  }
  function updateInspector() {
    const n = selected?.type === 'node' && doc.nodes.find(item => item.id === selected.id);
    const e = selected?.type === 'edge' && doc.edges.find(item => item.id === selected.id);
    $('empty').hidden = Boolean(n || e); $('node-editor').hidden = !n; $('edge-editor').hidden = !e;
    if (n) { $('label').value=n.label; $('width').value=n.w; $('height').value=n.h; renderIacFields(n); }
    if (e) { $('edge-label').value=e.label; $('edge-dashed').checked=e.dashed; }
  }
  const iacFields = {
    'resource-group': [['name','Azure name'],['location','Region code']],
    network: [['name','Azure name'],['location','Region code'],['resource_group','Resource group','resource-group'],['address','Address CIDR']],
    subnet: [['name','Azure name'],['vnet','Parent VNet','network'],['address','Subnet CIDR'],['nsg','Network security group (optional)','nsg']],
    peering: [['name','Peering name'],['source','Source VNet','network'],['target','Target VNet','network']],
    nsg: [['name','Azure name'],['location','Region code'],['resource_group','Resource group','resource-group']],
    'nsg-rule': [['name','Rule name'],['nsg','Network security group','nsg'],['priority','Priority (100–4096)'],['direction','Direction','direction'],['access','Access','access'],['protocol','Protocol','protocol'],['source_port','Source port or range'],['destination_port','Destination port or range'],['source_address','Source IP, CIDR or service tag'],['destination_address','Destination IP, CIDR or service tag']],
    'private-dns-zone': [['name','Storage private DNS zone','dns-zone'],['resource_group','Resource group','resource-group']],
    'private-dns-link': [['name','Link name'],['zone','Private DNS zone','private-dns-zone'],['vnet','Client VNet','network']],
    'private-endpoint': [['name','Endpoint name'],['location','Region code'],['resource_group','Resource group','resource-group'],['subnet','Endpoint subnet','subnet'],['storage','Storage account','storage'],['subresource','Storage subresource','subresource'],['zone','Matching private DNS zone','private-dns-zone']],
    storage: [['name','Azure name'],['location','Region code'],['resource_group','Resource group','resource-group'],['sku','Redundancy SKU','sku']]
  };
  function renderIacFields(n) {
    const root=$('iac-fields'); root.replaceChildren();
    const fields=iacFields[n.kind]; if(!fields) return;
    const title=document.createElement('h3'); title.textContent='IaC configuration'; root.append(title);
    for (const [key,label,ref] of fields) {
      const wrapper=document.createElement('label'); wrapper.textContent=label;
      const control=document.createElement(ref?'select':'input');
      control.setAttribute('aria-label',label);
      if (ref) {
        const blank=document.createElement('option'); blank.value=''; blank.textContent='Select…'; control.append(blank);
        const lists = {
          sku:['Standard_LRS','Standard_ZRS','Standard_GRS','Standard_RAGRS','Standard_GZRS','Standard_RAGZRS'],
          direction:['Inbound','Outbound'], access:['Allow','Deny'], protocol:['Tcp','Udp','Icmp','Esp','Ah','*'],
          subresource:['blob','file','queue','table','dfs'],
          'dns-zone':['blob','file','queue','table','dfs'].map(type=>`privatelink.${type}.core.windows.net`)
        };
        const options=lists[ref] ? lists[ref].map(value=>({id:value,label:value})) : doc.nodes.filter(item=>item.kind===ref);
        for(const item of options) { const opt=document.createElement('option'); opt.value=item.id; opt.textContent=item.label; control.append(opt); }
      } else {
        control.placeholder=key==='location'?'eastus':key==='address'?'10.0.0.0/16':'Required';
      }
      control.value=n.iac?.[key] || '';
      control.addEventListener('change',()=> { n.iac=n.iac || {}; n.iac[key]=control.value.trim(); });
      wrapper.append(control); root.append(wrapper);
    }
  }
  function startNode(event, n) {
    if (mode === 'pan') return;
    event.stopPropagation();
    if (mode === 'connect') {
      if (!connectFrom) { connectFrom=n.id; status(`Selected ${n.label}. Click another shape to connect.`); }
      else if (connectFrom !== n.id) {
        if (doc.edges.length >= 600) return status('The diagram has reached its 600-connection limit.');
        doc.edges.push({id:uid(), from:connectFrom, to:n.id, label:'', dashed:false});
        connectFrom=null; status('Connection added. Select the line to edit its label or style.'); render();
      } else status('Choose a different destination shape.');
      return;
    }
    selected={type:'node',id:n.id}; drag={type:'node',id:n.id, x:event.clientX, y:event.clientY, ox:n.x, oy:n.y};
    $('board').setPointerCapture(event.pointerId); render();
  }
  $('board').addEventListener('pointerdown', e => {
    if (mode === 'pan') { drag={type:'pan',x:e.clientX,y:e.clientY,ox:view.x,oy:view.y}; $('board').setPointerCapture(e.pointerId); }
    else { selected=null; connectFrom=null; render(); }
  });
  $('board').addEventListener('pointermove', e => {
    if (!drag) return;
    if (drag.type === 'pan') { view.x=drag.ox+e.clientX-drag.x; view.y=drag.oy+e.clientY-drag.y; }
    else {
      const n=doc.nodes.find(item => item.id === drag.id);
      if (n) { n.x=Math.max(-9000,Math.min(9000,drag.ox+(e.clientX-drag.x)/view.scale)); n.y=Math.max(-9000,Math.min(9000,drag.oy+(e.clientY-drag.y)/view.scale)); }
    }
    render();
  });
  $('board').addEventListener('pointerup', () => { drag=null; });
  $('board').addEventListener('pointercancel', () => { drag=null; });
  function zoom(factor, x, y) {
    const scale=Math.max(.2,Math.min(3,view.scale*factor));
    view.x=x-(x-view.x)*scale/view.scale; view.y=y-(y-view.y)*scale/view.scale; view.scale=scale; render();
  }
  $('viewport').addEventListener('wheel', e => { e.preventDefault(); const r=$('viewport').getBoundingClientRect(); zoom(e.deltaY<0?1.1:1/1.1,e.clientX-r.left,e.clientY-r.top); }, {passive:false});
  for (const name of ['select','connect','pan']) $(name).addEventListener('click', () => {
    mode=name; connectFrom=null;
    for (const item of ['select','connect','pan']) $(item).classList.toggle('active',item===name);
    status(name==='connect'?'Click a source shape, then a destination.':name==='pan'?'Drag the canvas to pan.':'Select and drag shapes.');
  });
  $('zoom-in').onclick=() => zoom(1.2,$('viewport').clientWidth/2,$('viewport').clientHeight/2);
  $('zoom-out').onclick=() => zoom(1/1.2,$('viewport').clientWidth/2,$('viewport').clientHeight/2);
  $('fit').onclick=() => { view={x:40,y:40,scale:1}; render(); };
  function currentNode() { return doc.nodes.find(n => n.id===selected?.id); }
  function currentEdge() { return doc.edges.find(e => e.id===selected?.id); }
  $('label').oninput=e => { const n=currentNode(); if(n) { n.label=e.target.value; render(); $('label').focus(); } };
  for (const [input,key,min] of [['width','w',60],['height','h',40]]) $(input).onchange=e => {
    const n=currentNode(), value=Number(e.target.value);
    if (n && Number.isFinite(value) && value>=min && value<=2000) n[key]=value;
    else status(`Enter a value between ${min} and 2000.`);
    render();
  };
  $('edge-label').onchange=e => { const edge=currentEdge(); if(edge) edge.label=e.target.value; render(); };
  $('edge-dashed').onchange=e => { const edge=currentEdge(); if(edge) edge.dashed=e.target.checked; render(); };
  $('delete').onclick=async () => { const n=currentNode(); if(!n || !await ask('Delete this shape and its connections?')) return; doc.nodes=doc.nodes.filter(x=>x.id!==n.id); doc.edges=doc.edges.filter(e=>e.from!==n.id&&e.to!==n.id); selected=null; render(); };
  $('delete-edge').onclick=async () => { const e=currentEdge(); if(!e || !await ask('Delete this connection?')) return; doc.edges=doc.edges.filter(x=>x.id!==e.id); selected=null; render(); };
  $('search').oninput=renderPalette;
  $('template').onclick=async () => {
    if ((doc.nodes.length || doc.edges.length) && !await ask('Replace the current diagram with the hub-and-spoke template?')) return;
    const hub={id:uid(),label:'Hub virtual network',kind:'network',x:80,y:200,w:240,h:120};
    const one={id:uid(),label:'Application spoke',kind:'network',x:500,y:80,w:240,h:120};
    const two={id:uid(),label:'Data spoke',kind:'network',x:500,y:320,w:240,h:120};
    doc={version:1,title:'Hub and spoke',nodes:[hub,one,two],edges:[one,two].map(n=>({id:uid(),from:hub.id,to:n.id,label:'VNet peering',dashed:true}))};
    selected=null; view={x:40,y:40,scale:1}; render(); status('Hub-and-spoke starter loaded. Customize the shapes and connections.');
  };
  $('download').onclick=() => {
    const blob=new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}), url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='architecture.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  $('open').onchange=async e => {
    const file=e.target.files[0]; if(!file) return;
    try { if(file.size>4*1024*1024) throw Error('File exceeds the 4 MB limit.'); const parsed=validate(JSON.parse(await file.text()));
      if ((doc.nodes.length || doc.edges.length) && !await ask('Replace the current diagram?')) return;
      doc=parsed; savedSnapshot=JSON.stringify(doc); selected=null; render(); status('Diagram opened from your computer.');
    } catch(err) { status(`Open failed: ${err.message}`); } finally { e.target.value=''; }
  };
  $('icon-file').onchange=e => {
    const file=e.target.files[0]; if(!file) return;
    if(file.size>500000 || !/\.(svg|png)$/i.test(file.name)) { status('Choose an SVG or PNG smaller than 500 KB.'); e.target.value=''; return; }
    const reader=new FileReader(); reader.onerror=()=>status('Could not read the selected icon.');
    reader.onload=()=> { const data=String(reader.result).replace(/^data:[^;]+;/, `data:image/${/\.svg$/i.test(file.name)?'svg+xml':'png'};`);
      addNode(file.name.replace(/\.(svg|png)$/i,''),'imported',data); };
    reader.readAsDataURL(file); e.target.value='';
  };
  async function api(url, options) {
    const response=await fetch(url,options), body=await response.json();
    if(!response.ok || !body.ok) throw Error(body.error || 'Request failed.'); return body;
  }
  async function checkIac() {
    $('iac-download').disabled=true;
    $('iac-report').textContent='Checking diagram...';
    try {
      const result=await api('/ext/archetype_studio/api/iac/preview', {
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({diagram:doc,mode:$('iac-mode').value})
      });
      const report=result.report;
      const details=report.resources.map(item=>`${item.label} (${item.type})\n${JSON.stringify(item.configuration,null,2)}`).join('\n\n') || 'No supported resources ready.';
      const problems=report.issues.map(item=>`${item.label || 'Diagram'}: ${item.messages.join(' ')}`).join('\n') || 'None';
      $('iac-report').textContent=`EXPORT ${report.can_export?'AVAILABLE':'BLOCKED'}\n\nCONFIGURATION\n${details}\n\nOMISSIONS / BLOCKERS\n${problems}\n\nIMPORTANT\n${report.warnings.join('\n')}\n\nARM export is not yet available.`;
      $('iac-download').disabled=!report.can_export;
    } catch(err) { $('iac-report').textContent=`Validation failed: ${err.message}`; }
  }
  $('iac-preview').onclick=() => { $('iac-dialog').showModal(); checkIac(); };
  $('iac-check').onclick=checkIac;
  $('iac-mode').onchange=checkIac;
  $('iac-close').onclick=()=>$('iac-dialog').close();
  $('iac-download').onclick=async () => {
    try {
      $('iac-download').disabled=true;
      const response=await fetch('/ext/archetype_studio/api/iac/export', {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({diagram:doc,mode:$('iac-mode').value})
      });
      if(!response.ok) { const data=await response.json(); throw Error(data.error||'Export failed.'); }
      const url=URL.createObjectURL(await response.blob()), a=document.createElement('a');
      a.href=url; a.download=`archetype-${$('iac-mode').value}-terraform.zip`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
      status('IaC package downloaded. Review its report and plan before deployment.');
      $('iac-download').disabled=false;
    } catch(err) { $('iac-report').textContent=`Export failed: ${err.message}`; }
  };
  $('save').onclick=async () => {
    const name=await ask('Server diagram name (letters, numbers, spaces, hyphens, underscores)',doc.title);
    if(name===null) return;
    if(!/^[A-Za-z0-9][A-Za-z0-9 _-]{0,79}$/.test(name)) return status('Invalid diagram name.');
    try {
      const payload={...doc,title:name}, body=JSON.stringify(payload);
      if(new Blob([body]).size>4*1024*1024) throw Error('Diagram exceeds the 4 MB limit.');
      const endpoint=`/ext/archetype_studio/api/diagrams/${encodeURIComponent(name)}`;
      const options={method:'PUT',headers:{'Content-Type':'application/json'},body};
      let response=await fetch(endpoint,options);
      if(response.status===409 && await ask('A diagram with this name exists. Replace it?')) response=await fetch(endpoint+'?overwrite=1',options);
      const result=await response.json(); if(!response.ok) throw Error(result.error||'Save failed.');
      doc.title=name; savedSnapshot=JSON.stringify(doc); status(`Saved "${name}" on the server.`);
    } catch(err) { status(`Save failed: ${err.message}`); }
  };
  $('load').onclick=async () => {
    try { const result=await api('/ext/archetype_studio/api/diagrams');
      if(!result.diagrams.length) return status('No server diagrams have been saved.');
      const name=await ask(`Available diagrams: ${result.diagrams.join(', ')}. Enter a name to open:`,result.diagrams[0]);
      if(name===null) return;
      const response=await api(`/ext/archetype_studio/api/diagrams/${encodeURIComponent(name)}`);
      const parsed=validate(response.diagram);
      if ((doc.nodes.length || doc.edges.length) && !await ask('Replace the current diagram?')) return;
      doc=parsed; savedSnapshot=JSON.stringify(doc); selected=null; render(); status(`Opened "${name}" from the server.`);
    } catch(err) { status(`Open failed: ${err.message}`); }
  };
  renderPalette(); render();
})();
