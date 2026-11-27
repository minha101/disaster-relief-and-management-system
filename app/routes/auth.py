from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..forms.auth import LoginForm, SetupForm, RegisterForm, ChangePasswordForm
from ..models import User, Role, UserRole, Volunteer, Donor
from ..services import audit
from ..services.settings import get_setting

bp = Blueprint('auth', __name__)


def safe_next():
    nxt = request.args.get('next') or ''
    return nxt if nxt.startswith('/') and not nxt.startswith('//') and '\\' not in nxt else None


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if User.query.count() == 0:
        return redirect(url_for('auth.setup'))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        now = datetime.utcnow()
        if user and user.locked_until and user.locked_until > now:
            flash('Too many failed attempts. Account is locked for a few minutes.', 'danger')
        elif user and user.active and user.check_password(form.password.data):
            user.failed_logins, user.locked_until, user.last_login = 0, None, now
            login_user(user, remember=form.remember.data)
            session.permanent = True
            audit.log('login', 'users', user.id)
            return redirect(safe_next() or url_for('main.dashboard'))
        else:
            if user:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= 5:
                    user.locked_until, user.failed_logins = now + timedelta(minutes=15), 0
            audit.log('login_failed', 'users', user.id if user else None, {'email': email[:150]})
            flash('Invalid e-mail or password.', 'danger')
    return render_template('auth/login.html', form=form)


@bp.post('/logout')
@login_required
def logout():
    audit.log('logout', 'users', current_user.id)
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """First-run only: creates the Super Admin. Disabled as soon as any user exists."""
    if User.query.count() > 0:
        flash('Setup has already been completed.', 'info')
        return redirect(url_for('auth.login'))
    form = SetupForm()
    if form.validate_on_submit():
        role = Role.query.filter_by(code='super_admin').first()
        u = User(email=form.email.data.strip().lower(), full_name=form.full_name.data.strip(), active=True)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        audit.log('setup_super_admin', 'users', u.id, user_id=u.id)
        flash('Super Admin created. Please sign in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/setup.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if get_setting('allow_self_registration', 'true') != 'true':
        flash('Self-registration is disabled. Contact an administrator.', 'warning')
        return redirect(url_for('auth.login'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append('This e-mail is already registered.')
        else:
            u = User(email=email, full_name=form.full_name.data.strip(), phone=form.phone.data.strip(), active=True)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.flush()
            role = Role.query.filter_by(code=form.role_code.data).first()
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            if role.code == 'volunteer':
                db.session.add(Volunteer(user_id=u.id, full_name=u.full_name, phone=u.phone, email=u.email,
                                         status='pending', created_by_id=u.id))
            elif role.code == 'donor':
                db.session.add(Donor(user_id=u.id, name=u.full_name, email=u.email, phone=u.phone,
                                     donor_type='individual', created_by_id=u.id))
            db.session.commit()
            audit.log('register', 'users', u.id, {'role': role.code}, user_id=u.id)
            flash('Account created. You can sign in now.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current.data):
            form.current.errors.append('Current password is incorrect.')
        else:
            current_user.set_password(form.password.data)
            audit.log('password_changed', 'users', current_user.id, commit=False)
            db.session.commit()
            flash('Password updated.', 'success')
            return redirect(url_for('auth.profile'))
    return render_template('auth/profile.html', form=form)
