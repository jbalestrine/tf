import io
import json


def test_roku_json_playlist_is_supported(client):
    payload = [
        {"title": "Local News", "url": "https://example.com/local-news.m3u8", "group": "News", "category": "news"},
        {"title": "Local Sports", "url": "https://example.com/local-sports.m3u8", "group": "Sports", "category": "sports"},
        {"title": "Local Movies", "url": "https://example.com/local-movies.m3u8", "group": "Movies", "category": "movies"},
    ]
    resp = client.post('/api/roku/validate', json={'playlist_json': json.dumps(payload)})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['ok'] is True
    assert body['count'] == 3
    assert 'news' in body['grouped']


def test_roku_build_generates_manifest_and_zip(client):
    payload = {
        'channel_name': 'MasterChief IPTV',
        'bundle_id': 'com.masterchief.iptv',
        'playlist_url': '',
        'developer_ip': '192.168.1.50',
        'theme': 'dark',
    }
    m3u_text = (
        '#EXTM3U\n'
        '#EXTINF:-1 tvg-group="News" tvg-logo="logo.png",BBC News\n'
        'https://example.com/bbc-news.m3u8\n'
        '#EXTINF:-1 tvg-group="Sports" tvg-logo="logo.png",Sky Sports\n'
        'https://example.com/sky-sports.m3u8\n'
        '#EXTINF:-1 tvg-group="Movies" tvg-logo="logo.png",Cinema Plus\n'
        'https://example.com/cinema-plus.m3u8\n'
    )
    data = {
        'file': (io.BytesIO(m3u_text.encode('utf-8')), 'sample.m3u8')
    }

    resp = client.post('/api/roku/build', data=data, content_type='multipart/form-data', buffered=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['ok'] is True
    assert 'manifest_path' in body
    assert 'zip_path' in body


def test_roku_validate_preserves_group_names_as_categories(client):
    playlist = (
        '#EXTM3U\n'
        '#EXTINF:-1 group-title="US",US CNN\n'
        'https://example.com/us-cnn.m3u8\n'
        '#EXTINF:-1 group-title="US",US FOX\n'
        'https://example.com/us-fox.m3u8\n'
        '#EXTINF:-1 group-title="Movies",Movie Premiere\n'
        'https://example.com/movie-premiere.m3u8\n'
    )
    resp = client.post('/api/roku/validate', json={'playlist_text': playlist})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['ok'] is True
    assert 'us' in body['grouped']
    assert 'movies' in body['grouped']
    assert len(body['grouped']['us']) == 2
    assert len(body['grouped']['movies']) == 1


def test_roku_validate_groups_content_by_category(client):
    resp = client.post(
        '/api/roku/validate',
        json={
            'playlist_url': 'http://1tv41.icu:8080/get.php?username=davidcooke&password=8433032009&type=m3u'
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['ok'] is True
    assert 'grouped' in body
    assert 'live' in body['grouped'] or 'news' in body['grouped'] or 'movies' in body['grouped'] or 'sports' in body['grouped'] or 'series' in body['grouped']
