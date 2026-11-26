"""Sayfalar, giriş, kayıt ve şifre sıfırlama."""
import re

from conftest import ADMIN, USER, login


def test_public_pages_open(client):
    for path in ['/', '/login', '/register', '/forgot-password']:
        assert client.get(path).status_code == 200, path


def test_panels_require_login(client):
    for path in ['/admin', '/user']:
        r = client.get(path)
        assert r.status_code == 302 and '/login' in r.headers['Location'], path


def test_admin_login_goes_to_admin_panel(client):
    r = login(client, *ADMIN)
    assert r.status_code == 302 and r.headers['Location'].endswith('/admin')
    assert client.get('/admin').status_code == 200


def test_user_login_goes_to_user_panel(client):
    r = login(client, *USER)
    assert r.headers['Location'].endswith('/user')
    assert client.get('/user').status_code == 200


def test_user_cannot_open_admin_panel(user):
    r = user.get('/admin')
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_wrong_password_is_rejected(client):
    r = login(client, ADMIN[0], 'yanlis')
    assert r.status_code == 200
    assert 'hatalı' in r.get_data(as_text=True)
    assert client.get('/admin').status_code == 302


def test_register_rejects_mismatched_passwords(client):
    r = client.post('/register', data={'full_name': 'A B', 'email': 'esit@test.com', 'phone': '',
                                       'password': 'abc123', 'password_confirm': 'xyz789'})
    assert 'eşleşmiyor' in r.get_data(as_text=True)


def test_register_rejects_duplicate_email(client):
    r = client.post('/register', data={'full_name': 'A B', 'email': USER[0], 'phone': '',
                                       'password': 'abc123', 'password_confirm': 'abc123'})
    assert 'zaten kayıtlı' in r.get_data(as_text=True)


def test_password_reset_flow(client):
    email = 'sifre@test.com'
    client.post('/register', data={'full_name': 'Şifre Test', 'email': email, 'phone': '',
                                   'password': 'eski123', 'password_confirm': 'eski123'})
    html = client.post('/forgot-password', data={'email': email}).get_data(as_text=True)
    token = re.search(r'/reset-password/([A-Za-z0-9_-]+)', html).group(1)

    client.post(f'/reset-password/{token}', data={'password': 'yeni456', 'password_confirm': 'yeni456'})

    assert login(client, email, 'eski123').status_code == 200  # eski şifre artık geçmez
    assert login(client, email, 'yeni456').headers['Location'].endswith('/user')
    # aynı bağlantı ikinci kez kullanılamaz
    assert 'Geçersiz' in client.get(f'/reset-password/{token}').get_data(as_text=True)
