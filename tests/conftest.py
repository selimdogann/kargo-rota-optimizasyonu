"""
Ortak test hazırlığı.

- Her test oturumu kendi geçici SQLite veritabanını kullanır: gerçek cargo_system.db'ye dokunulmaz.
- OSRM (internetteki yol servisi) testlerde kapalıdır: kod kendi yedek mesafe hesabına düşer,
  testler internetsiz ve hızlı çalışır.
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# app import edilmeden ÖNCE veritabanı adresini geçici dosyaya yönlendir
_tmpdir = tempfile.mkdtemp(prefix='kargo-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_tmpdir, 'test.db')
os.environ.setdefault('SECRET_KEY', 'test-secret')

import app as app_module  # noqa: E402
import init_db  # noqa: E402

ADMIN = ('admin@kargo.com', 'admin123')
USER = ('kullanici@test.com', '123456')


@pytest.fixture(scope='session')
def flask_app():
    app_module.app.config['TESTING'] = True
    init_db.init_database(force_reset=True)
    return app_module.app


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """OSRM isteklerini kes: her istek bağlantı hatası verir, kod yedek yola düşer."""
    import requests

    def offline(*args, **kwargs):
        raise requests.exceptions.ConnectionError('testlerde ağ kapalı')

    monkeypatch.setattr('algorithms.clarke_wright.requests.get', offline)


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


def login(client, email, password):
    return client.post('/login', data={'email': email, 'password': password})


@pytest.fixture
def admin(flask_app):
    c = flask_app.test_client()
    login(c, *ADMIN)
    return c


@pytest.fixture
def user(flask_app):
    c = flask_app.test_client()
    login(c, *USER)
    return c


@pytest.fixture
def new_user(flask_app):
    """Her çağrıda yeni bir kullanıcı kaydedip giriş yapmış istemci döndürür."""
    counter = {'n': 0}

    def make():
        counter['n'] += 1
        email = f"kisi{counter['n']}-{os.getpid()}@test.com"
        c = flask_app.test_client()
        c.post('/register', data={'full_name': 'Test Kişi', 'email': email, 'phone': '',
                                  'password': 'abc123', 'password_confirm': 'abc123'})
        login(c, email, 'abc123')
        return c

    return make


@pytest.fixture
def stations(client):
    return client.get('/api/stations').get_json()
