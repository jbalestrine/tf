import json
import os
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request


gallery_bp = Blueprint('gallery_routes', __name__)


_GALLERY_SESSIONS = {}


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _gallery_dir() -> Path:
    return _root() / 'data' / 'gallery'


def _gallery_meta_file() -> Path:
    return _root() / 'data' / 'gallery_meta.json'


def _gallery_orders_file() -> Path:
    return _root() / 'data' / 'gallery_orders.json'


def _gallery_admin_file() -> Path:
    return _root() / 'data' / 'gallery_admin.json'


def _ensure_gallery():
    _gallery_dir().mkdir(parents=True, exist_ok=True)


def _load_gallery_meta():
    _ensure_gallery()
    path = _gallery_meta_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []


def _save_gallery_meta(meta):
    _ensure_gallery()
    _gallery_meta_file().write_text(json.dumps(meta, indent=2), encoding='utf-8')


def _load_orders():
    path = _gallery_orders_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []


def _save_orders(orders):
    _gallery_orders_file().write_text(json.dumps(orders, indent=2), encoding='utf-8')


def _load_admin_config():
    path = _gallery_admin_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass

    default = {
        'username': 'admin',
        'password': 'masterchief',
        'gallery_name': 'MasterChief Art Gallery',
        'contact_email': '',
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(default, indent=2), encoding='utf-8')
    return default


@gallery_bp.route('/gallery')
def art_gallery():
    """Serve the Art Gallery web UI."""
    try:
        page = _root() / 'gallery.html'
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}
    except Exception:
        current_app.logger.exception('Failed to serve gallery.html')
    return ('Art Gallery not available', 404)


@gallery_bp.route('/api/gallery/list')
def gallery_list():
    """Return all gallery metadata."""
    return jsonify(_load_gallery_meta())


@gallery_bp.route('/api/gallery/upload', methods=['POST'])
def gallery_upload():
    """Upload one or more images to the gallery."""
    _ensure_gallery()
    meta = _load_gallery_meta()
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    title = request.form.get('title', 'Untitled')
    artist = request.form.get('artist', 'Unknown')
    genre = request.form.get('genre', 'portraits')
    desc = request.form.get('desc', '')
    tags_raw = request.form.get('tags', '')
    tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]

    try:
        price = float(request.form.get('price', '0'))
    except (ValueError, TypeError):
        price = 0.0

    for_sale = request.form.get('forSale', 'false') == 'true'
    medium = request.form.get('medium', '')
    dimensions = request.form.get('dimensions', '')

    added = []
    for index, file_obj in enumerate(files):
        if not file_obj or not file_obj.filename:
            continue
        ext = Path(file_obj.filename).suffix.lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'):
            continue

        uid = f"{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        fname = f"{uid}{ext}"
        dest = _gallery_dir() / fname
        file_obj.save(str(dest))

        entry = {
            'id': uid,
            'filename': fname,
            'title': f"{title} ({index + 1})" if len(files) > 1 else title,
            'artist': artist,
            'genre': genre,
            'desc': desc,
            'tags': tags,
            'date': int(time.time() * 1000),
            'fav': False,
            'size': dest.stat().st_size,
            'price': price,
            'forSale': for_sale,
            'sold': False,
            'medium': medium,
            'dimensions': dimensions,
        }
        meta.append(entry)
        added.append(entry)

    _save_gallery_meta(meta)
    return jsonify({'added': len(added), 'items': added})


@gallery_bp.route('/api/gallery/image/<filename>')
def gallery_image(filename):
    """Serve a gallery image file."""
    _ensure_gallery()
    file_path = _gallery_dir() / filename
    if not file_path.exists() or not file_path.is_file():
        return ('Not found', 404)

    import mimetypes

    mime_type = mimetypes.guess_type(str(file_path))[0] or 'image/png'
    return file_path.read_bytes(), 200, {'Content-Type': mime_type, 'Cache-Control': 'public, max-age=86400'}


@gallery_bp.route('/api/gallery/update/<art_id>', methods=['POST'])
def gallery_update(art_id):
    """Toggle favorite or update metadata for a gallery item."""
    meta = _load_gallery_meta()
    item = next((row for row in meta if row['id'] == art_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(silent=True) or {}
    for key in ('fav', 'title', 'genre', 'tags', 'artist', 'desc', 'price', 'forSale', 'sold', 'medium', 'dimensions'):
        if key in data:
            item[key] = data[key]

    _save_gallery_meta(meta)
    return jsonify(item)


@gallery_bp.route('/api/gallery/delete/<art_id>', methods=['DELETE'])
def gallery_delete(art_id):
    """Delete a gallery item and its file."""
    meta = _load_gallery_meta()
    item = next((row for row in meta if row['id'] == art_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404

    file_path = _gallery_dir() / item.get('filename', '')
    if file_path.exists():
        file_path.unlink()

    meta = [row for row in meta if row['id'] != art_id]
    _save_gallery_meta(meta)
    return jsonify({'deleted': art_id})


@gallery_bp.route('/api/gallery/admin/login', methods=['POST'])
def gallery_admin_login():
    """Authenticate gallery admin."""
    data = request.get_json(silent=True) or {}
    cfg = _load_admin_config()
    if data.get('username') == cfg['username'] and data.get('password') == cfg['password']:
        token = os.urandom(24).hex()
        _GALLERY_SESSIONS[token] = time.time() + 86400
        return jsonify({'ok': True, 'token': token})
    return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401


@gallery_bp.route('/api/gallery/admin/verify', methods=['POST'])
def gallery_admin_verify():
    """Check if admin token is still valid."""
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    expires_at = _GALLERY_SESSIONS.get(token, 0)
    if expires_at > time.time():
        return jsonify({'valid': True})
    _GALLERY_SESSIONS.pop(token, None)
    return jsonify({'valid': False}), 401


@gallery_bp.route('/api/gallery/admin/logout', methods=['POST'])
def gallery_admin_logout():
    """Invalidate admin token."""
    data = request.get_json(silent=True) or {}
    _GALLERY_SESSIONS.pop(data.get('token', ''), None)
    return jsonify({'ok': True})


@gallery_bp.route('/api/gallery/admin/settings', methods=['GET', 'POST'])
def gallery_admin_settings():
    """Get or update gallery admin settings."""
    cfg = _load_admin_config()

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        token = data.get('token', '')
        if _GALLERY_SESSIONS.get(token, 0) <= time.time():
            return jsonify({'error': 'Unauthorized'}), 401

        for key in ('username', 'password', 'gallery_name', 'contact_email'):
            if key in data and data[key]:
                cfg[key] = data[key]

        _gallery_admin_file().write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        return jsonify({'ok': True})

    return jsonify({'gallery_name': cfg.get('gallery_name', ''), 'contact_email': cfg.get('contact_email', '')})


@gallery_bp.route('/api/gallery/purchase', methods=['POST'])
def gallery_purchase():
    """Place an order for artwork."""
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    buyer = data.get('buyer', {})
    if not items:
        return jsonify({'error': 'No items'}), 400
    if not buyer.get('name') or not buyer.get('email'):
        return jsonify({'error': 'Buyer name and email required'}), 400

    meta = _load_gallery_meta()
    orders = _load_orders()
    order_items = []
    total = 0.0

    for art_id in items:
        item = next((row for row in meta if row['id'] == art_id), None)
        if item and item.get('forSale') and not item.get('sold'):
            order_items.append({'id': item['id'], 'title': item['title'], 'price': item.get('price', 0)})
            total += item.get('price', 0)
            item['sold'] = True

    if not order_items:
        return jsonify({'error': 'No available items to purchase'}), 400

    order = {
        'orderId': f"ORD-{int(time.time() * 1000)}",
        'date': int(time.time() * 1000),
        'buyer': buyer,
        'items': order_items,
        'total': total,
        'status': 'confirmed',
    }
    orders.append(order)
    _save_orders(orders)
    _save_gallery_meta(meta)
    return jsonify(order)


@gallery_bp.route('/api/gallery/orders')
def gallery_orders():
    """List all orders."""
    return jsonify(_load_orders())
