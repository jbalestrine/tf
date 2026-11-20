import RFB from '@novnc/novnc';

const screen = document.getElementById('mc-ubuntu-screen');
const status = document.getElementById('mc-ubuntu-status');
const connect = document.getElementById('mc-ubuntu-connect');
const disconnect = document.getElementById('mc-ubuntu-disconnect');
const start = document.getElementById('mc-ubuntu-start');
const viewer = document.getElementById('mc-ubuntu-viewer');
const fullscreen = document.getElementById('mc-ubuntu-fullscreen');
const source = document.getElementById('mc-ubuntu-source');
const switchSource = document.getElementById('mc-ubuntu-switch');
const sourceStatus = document.getElementById('mc-ubuntu-source-status');
let desktop = null;
let requestedDisconnect = false;

function updateFullscreenButton() {
    const active = document.fullscreenElement === viewer;
    fullscreen.textContent = active ? 'Exit full screen' : 'Full screen';
    fullscreen.setAttribute('aria-pressed', String(active));
}

if (!document.fullscreenEnabled || !viewer.requestFullscreen) {
    fullscreen.disabled = true;
    fullscreen.title = 'Full screen is unavailable in this browser or page.';
}
document.addEventListener('fullscreenchange', updateFullscreenButton);
fullscreen.addEventListener('click', async () => {
    try {
        if (document.fullscreenElement === viewer) {
            await document.exitFullscreen();
        } else {
            await viewer.requestFullscreen();
        }
    } catch (error) {
        status.textContent = `Unable to change full screen: ${error.message}`;
    }
});

async function requestJson(url, options) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `Request failed (${response.status}).`);
    return result;
}

async function refreshStatus() {
    try {
        const result = await requestJson('/api/ubuntu-desktop/status');
        if (result.state === 'running' && !desktop) {
            connect.click();
        } else if (!desktop) {
            status.textContent = `Ubuntu VM: ${result.state}. Select Start Ubuntu.`;
        }
    } catch (error) {
        status.textContent = error.message;
    }
}

async function refreshSource() {
    try {
        const result = await requestJson('/api/ubuntu-desktop/source');
        if (result.source === 'pypi' || result.source === 'github') source.value = result.source;
        const commit = result.github_commit ? ` GitHub commit: ${result.github_commit.slice(0, 12)}.` : '';
        sourceStatus.textContent = `Current Ubuntu app source: ${result.source}.${commit}`;
    } catch (error) {
        sourceStatus.textContent = error.message;
    }
}

switchSource.addEventListener('click', async () => {
    const selected = source.value;
    const name = selected === 'github' ? 'GitHub Masterchief4' : 'PyPI';
    if (!window.confirm(`Switch the Ubuntu app to ${name}? The app will restart. Its app data directory is separate, but the Ubuntu user and external resources are shared.`)) return;
    switchSource.disabled = true;
    sourceStatus.textContent = `Switching to ${name}...`;
    try {
        const result = await requestJson('/api/ubuntu-desktop/source', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source: selected, confirm: true}),
        });
        sourceStatus.textContent = result.message;
        await refreshSource();
    } catch (error) {
        sourceStatus.textContent = error.message;
    } finally {
        switchSource.disabled = false;
    }
});

start.addEventListener('click', async () => {
    start.disabled = true;
    try {
        const result = await requestJson('/api/ubuntu-desktop/start', {method: 'POST'});
        status.textContent = result.message;
    } catch (error) {
        status.textContent = error.message;
    } finally {
        start.disabled = false;
    }
});

connect.addEventListener('click', () => {
    if (desktop) return;
    requestedDisconnect = false;
    status.textContent = 'Connecting to the Ubuntu desktop...';
    connect.disabled = true;
    disconnect.disabled = false;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    desktop = new RFB(screen, `${protocol}//${location.host}/api/ubuntu-desktop/socket`);
    desktop.scaleViewport = true;
    desktop.resizeSession = true;
    desktop.addEventListener('connect', () => {
        status.textContent = 'Connected. Click inside the desktop to use it.';
    });
    desktop.addEventListener('disconnect', () => {
        desktop = null;
        connect.disabled = false;
        disconnect.disabled = true;
        status.textContent = requestedDisconnect
            ? 'Desktop disconnected. The VM is still running.'
            : 'Desktop connection failed or ended. Check that the VM and desktop service are running, then try again.';
    });
    desktop.addEventListener('securityfailure', event => {
        status.textContent = `Desktop security error: ${event.detail.reason || 'connection rejected'}`;
    });
});

disconnect.addEventListener('click', () => {
    if (desktop) {
        requestedDisconnect = true;
        desktop.disconnect();
    }
});

refreshStatus();
refreshSource();
