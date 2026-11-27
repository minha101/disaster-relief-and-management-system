import os
import secrets
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)


def _secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY must be set in production (.env).')
    path = os.path.join(instance_dir, 'secret.key')
    if not os.path.exists(path):
        with open(path, 'w') as fh:
            fh.write(secrets.token_hex(32))
    with open(path) as fh:
        return fh.read().strip()



def _db_url():
    url = os.environ.get('DATABASE_URL', '').strip()

    if url:
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    return 'sqlite:///' + os.path.join(
        instance_dir, 'drms.db'
    ).replace('\\', '/')



class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    AUTO_CREATE_TABLES = os.environ.get('AUTO_CREATE_TABLES', 'true').lower() == 'true'
    UPLOAD_FOLDER = os.path.join(instance_dir, 'uploads')
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = None
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
    PER_PAGE = 15
