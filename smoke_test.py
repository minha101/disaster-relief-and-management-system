"""End-to-end smoke test: builds a throw-away SQLite database, loads sample data and opens every page.

Run:  python smoke_test.py
It never touches your real database (uses instance/smoke_test.db and deletes it afterwards).
"""
import os
import sys
import tempfile

TMP = os.path.join(tempfile.gettempdir(), 'drms_smoke.db')
if os.path.exists(TMP):
    os.remove(TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + TMP.replace('\\', '/')
os.environ['AUTO_CREATE_TABLES'] = 'true'
os.environ['DEMO_USER_PASSWORD'] = 'Smoke-Test-1234'

import seed                                  # noqa: E402
from app import create_app                   # noqa: E402
from config import Config                    # noqa: E402
from app.registry import REGISTRY            # noqa: E402


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def main():
    sys.argv = ['seed.py']
    seed.main()
    app = create_app(TestConfig)
    c = app.test_client()
    fails = []

    def check(method, url, expect=(200,), **kw):
        r = getattr(c, method)(url, follow_redirects=False, **kw)
        if r.status_code not in expect:
            fails.append(f'{method.upper()} {url} -> {r.status_code}')
        return r

    check('get', '/')
    check('get', '/sos')
    check('get', '/transparency')
    check('get', '/login')
    r = check('post', '/login', (302,), data={'email': 'admin1@demo.example', 'password': 'Smoke-Test-1234'})
    for url in ('/dashboard', '/api/dashboard', '/map', '/api/map', '/tasks/', '/analytics', '/api/analytics', '/analytics.csv',
                '/risk', '/allocation', '/reports/', '/reports/summary.pdf', '/reports/camps.pdf', '/reports/inventory.pdf',
                '/reports/donations.pdf', '/reports/analytics.pdf', '/reports/risk.pdf', '/notifications', '/api/notifications',
                '/api/sos/pending', '/search?q=camp', '/profile'):
        check('get', url)
    for slug, cfg in REGISTRY.items():
        check('get', f'/m/{slug}/')
        check('get', f'/m/{slug}/?q=a&sort=id&dir=asc&page=1')
        check('get', f'/m/{slug}/export.csv')
        if not cfg['readonly']:
            check('get', f'/m/{slug}/new')
    with app.app_context():
        for slug, cfg in REGISTRY.items():
            obj = cfg['model'].query.first()
            if obj:
                check('get', f'/m/{slug}/{obj.id}')
                if not cfg['readonly'] and not cfg['immutable']:
                    check('get', f'/m/{slug}/{obj.id}/edit')
    check('get', '/m/emergency_requests/export.pdf')
    r = check('post', '/sos', (302,), data=dict(requester_name='Test Person', phone='0300-0000123', people_count=3, category_id=0,
                                                district_id=0, address='Near test village', latitude='27.7', longitude='68.8',
                                                has_injured='y', description='smoke test'))
    if r.status_code == 302:
        check('get', r.headers['Location'])
    check('post', '/tasks/quick', (200,), data=dict(title='Smoke task', priority='high'))
    print('\nSMOKE TEST:', 'PASSED' if not fails else f'{len(fails)} FAILURE(S)')
    for f in fails:
        print('  -', f)
    os.remove(TMP) if os.path.exists(TMP) else None
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
