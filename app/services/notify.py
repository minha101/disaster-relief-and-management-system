from ..extensions import db
from ..models import Notification, User, UserRole, Role


def notify_user(user_id, title, message='', level='info', link=None):
    db.session.add(Notification(user_id=user_id, title=title[:200], message=message[:500], level=level, link=link))


def notify_roles(role_codes, title, message='', level='info', link=None, exclude_user_id=None):
    users = (db.session.query(User.id).join(UserRole, UserRole.user_id == User.id)
             .join(Role, Role.id == UserRole.role_id)
             .filter(Role.code.in_(role_codes), User.active.is_(True)).distinct().limit(500).all())
    for (uid,) in users:
        if uid != exclude_user_id:
            notify_user(uid, title, message, level, link)
