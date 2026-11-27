import json
from flask import request, has_request_context
from flask_login import current_user
from ..extensions import db
from ..models import AuditLog


def log(action, entity=None, entity_id=None, details=None, user_id=None, commit=True):
    uid = user_id
    ip = ua = None
    if has_request_context():
        if uid is None and current_user and current_user.is_authenticated:
            uid = current_user.id
        ip = request.remote_addr
        ua = (request.headers.get('User-Agent') or '')[:255]
    if isinstance(details, (dict, list)):
        details = json.dumps(details, default=str)
    db.session.add(AuditLog(user_id=uid, action=action, entity=entity, entity_id=entity_id,
                            details=(details or '')[:2000] or None, ip_address=ip, user_agent=ua))
    if commit:
        db.session.commit()
