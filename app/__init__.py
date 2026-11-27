import click
from flask import Flask, render_template, session
from flask_login import current_user
from sqlalchemy import func
from .extensions import db, migrate, login_manager, csrf


def create_app(config_object='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config['ENV_NAME'] = 'production' if app.config.get('SESSION_COOKIE_SECURE') else 'development'
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registers every table)
    from .registry import REGISTRY, GROUPS
    from .routes import register_blueprints
    from .services import rbac, settings

    @login_manager.user_loader
    def load_user(uid):
        try:
            return db.session.get(models.User, int(uid))
        except (TypeError, ValueError):
            return None

    register_blueprints(app)

    @app.context_processor
    def inject():
        nav = []
        if current_user.is_authenticated:
            for g in GROUPS:
                items = [(c['slug'], c['title'], c['icon']) for c in REGISTRY.values()
                         if c['group'] == g and current_user.can(c['slug'], 'view')]
                if items:
                    nav.append((g, sorted(items, key=lambda x: x[1])))
        from .services.stats import has_sample
        try:
            sample = has_sample() if current_user.is_authenticated else False
        except Exception:
            sample = False
        return dict(nav=nav, scope=session.get('scope', 'all'), has_sample=sample, site_name='Flood & Disaster Relief')

    @app.after_request
    def headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'same-origin')
        if current_user.is_authenticated:
            resp.headers.setdefault('Cache-Control', 'no-store')
        return resp

    for code, msg in ((403, 'You do not have permission to open this page.'), (404, 'Page or record not found.'),
                      (413, 'Uploaded file is too large (max 8 MB).'), (400, 'Bad request or expired form. Reload and retry.'),
                      (500, 'Unexpected server error. It has been logged.')):
        app.register_error_handler(code, lambda e, code=code, msg=msg: (render_template('errors/error.html', code=code, msg=msg), code))

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt='Full name')
    @click.password_option()
    def create_admin(email, name, password):
        """Create a Super Admin (password is prompted, never stored in files)."""
        from .services.hooks import password_error
        err = password_error(password)
        if err:
            raise click.ClickException(err)
        role = models.Role.query.filter_by(code='super_admin').first()
        u = models.User(email=email.strip().lower(), full_name=name, active=True)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
        db.session.add(models.UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        click.echo('Super Admin created.')

    @app.cli.command('sync-rbac')
    def sync_rbac_cmd():
        """Create missing permissions/roles after adding modules."""
        rbac.sync_rbac()
        click.echo('RBAC synchronised.')

    with app.app_context():
        try:
            if app.config['AUTO_CREATE_TABLES']:
                db.create_all()
            if __import__('sqlalchemy').inspect(db.engine).has_table('roles'):
                if models.Permission.query.count() != len(REGISTRY) * 5 or models.Role.query.count() == 0:
                    rbac.sync_rbac()
                settings.ensure_defaults()
        except Exception as exc:       # e.g. database not reachable / tables not migrated yet
            app.logger.warning('Database initialisation skipped: %s', exc)
    return app
