"""
API yetki politikası: girişsiz kimse veri silemez/değiştiremez,
normal kullanıcı yönetici işlemi yapamaz ve başkasının kargosunu göremez.
"""
import pytest

from app import app as flask_app

# Yönetici dışındakilere kapalı olması gereken örnek uçlar (yöntem, yol)
ADMIN_ONLY = [
    ('DELETE', '/api/cargos/delete-all'),
    ('POST', '/api/cargos/bulk-delete'),
    ('POST', '/api/scenarios/load/1'),
    ('POST', '/api/routes/optimize'),
    ('DELETE', '/api/trips/delete-all'),
    ('POST', '/api/vehicles'),
    ('DELETE', '/api/vehicles/1'),
    ('DELETE', '/api/stations/2'),
    ('PUT', '/api/parameters'),
    ('GET', '/api/users'),
    ('GET', '/api/trips'),
    ('GET', '/api/distance-matrix'),
]

PUBLIC = [('GET', '/api/stations'), ('GET', '/api/vehicles'), ('GET', '/api/analytics/summary')]


@pytest.mark.parametrize('method,path', ADMIN_ONLY)
def test_anonymous_gets_401(client, method, path):
    r = client.open(path, method=method, json={})
    assert r.status_code == 401
    assert r.is_json and 'error' in r.get_json()


@pytest.mark.parametrize('method,path', ADMIN_ONLY)
def test_user_gets_403(user, method, path):
    assert user.open(path, method=method, json={}).status_code == 403


@pytest.mark.parametrize('method,path', PUBLIC)
def test_public_endpoints_stay_open(client, method, path):
    assert client.open(path, method=method).status_code == 200


def test_every_api_route_is_covered_by_policy(client):
    """Yeni eklenen bir uç unutulsa bile girişsiz erişime kapalı olmalı (varsayılan-ret)."""
    from app import PUBLIC_API_ENDPOINTS
    for rule in flask_app.url_map.iter_rules():
        if not rule.rule.startswith('/api/') or rule.endpoint in PUBLIC_API_ENDPOINTS:
            continue
        path = rule.rule
        for arg in rule.arguments:
            path = path.replace(f'<int:{arg}>', '1').replace(f'<{arg}>', '1')
        method = sorted(rule.methods - {'HEAD', 'OPTIONS'})[0]
        r = client.open(path, method=method, json={})
        assert r.status_code == 401, f'{method} {path} girişsiz {r.status_code} döndü'


def test_anonymous_cannot_list_cargos(client):
    assert client.get('/api/cargos').status_code == 401


def _send_cargo(c, station_id, sender='Gönderen'):
    r = c.post('/api/cargos', json={'sender_name': sender, 'receiver_name': 'Prof. Test',
                                    'weight': 10, 'source_station_id': station_id})
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()


def test_user_sees_only_own_cargos(new_user, stations):
    station_id = next(s['id'] for s in stations if not s['is_depot'])
    alice, bob = new_user(), new_user()
    _send_cargo(alice, station_id, 'Alice')
    _send_cargo(bob, station_id, 'Bob')

    senders = {c['sender_name'] for c in alice.get('/api/cargos').get_json()}
    assert senders == {'Alice'}
    assert {c['sender_name'] for c in alice.get('/api/cargos/my').get_json()} == {'Alice'}


def test_user_cannot_track_someone_elses_cargo(new_user, stations, client):
    station_id = next(s['id'] for s in stations if not s['is_depot'])
    alice, bob = new_user(), new_user()
    _send_cargo(alice, station_id, 'Alice')
    alice_cargo_id = alice.get('/api/cargos').get_json()[0]['id']

    assert alice.get(f'/api/cargos/track/{alice_cargo_id}').status_code == 200
    assert bob.get(f'/api/cargos/track/{alice_cargo_id}').status_code == 404
    assert bob.get(f'/api/cargos/my-route/{alice_cargo_id}').status_code == 404
    assert client.get(f'/api/cargos/track/{alice_cargo_id}').status_code == 401


def test_admin_can_track_any_cargo(admin, new_user, stations):
    station_id = next(s['id'] for s in stations if not s['is_depot'])
    alice = new_user()
    _send_cargo(alice, station_id, 'Alice')
    cargo_id = alice.get('/api/cargos').get_json()[0]['id']
    assert admin.get(f'/api/cargos/track/{cargo_id}').status_code == 200
