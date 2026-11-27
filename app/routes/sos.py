import time
from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from ..extensions import db
from ..forms.sos import SOSForm
from ..models import RequestCategory, District, EmergencyRequest, RequestUpdate, RescueTeam
from ..services import hooks
from ..services.settings import get_float

bp = Blueprint('sos', __name__)
_hits = defaultdict(list)


def _limited(ip):
    limit = int(get_float('sos_rate_limit_per_hour', 5))
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < 3600]
    return len(_hits[ip]) >= limit


@bp.route('/sos', methods=['GET', 'POST'])
def submit():
    form = SOSForm()
    form.category_id.choices = [(0, '-- select --')] + [(c.id, c.name) for c in RequestCategory.query.order_by(RequestCategory.name)]
    form.district_id.choices = [(0, '-- select --')] + [(d.id, d.name) for d in District.query.order_by(District.name)]
    if request.method == 'GET' and current_user.is_authenticated:
        form.requester_name.data = current_user.full_name
        form.phone.data = current_user.phone
    if form.validate_on_submit():
        if form.website.data:                      # honeypot hit: pretend success, store nothing
            flash('Request received.', 'success')
            return redirect(url_for('main.index'))
        has_geo = form.latitude.data is not None and form.longitude.data is not None
        if (form.latitude.data is None) != (form.longitude.data is None):
            form.latitude.errors.append('Provide both latitude and longitude.')
        elif not has_geo and not (form.address.data or '').strip():
            form.address.errors.append('Provide a location on the map or describe it here.')
        elif _limited(request.remote_addr):
            flash('Too many requests from this connection. If this is life-threatening call 1122 / 115 now.', 'danger')
        else:
            _hits[request.remote_addr].append(time.time())
            obj = EmergencyRequest(
                requester_name=form.requester_name.data.strip(), phone=form.phone.data.strip(),
                people_count=form.people_count.data, has_injured=form.has_injured.data,
                needs_medical=form.needs_medical.data, category_id=form.category_id.data or None,
                district_id=form.district_id.data or None, address=(form.address.data or '').strip() or None,
                latitude=form.latitude.data, longitude=form.longitude.data, description=form.description.data,
                data_source='reported', status='pending', tracking_code=hooks.new_tracking_code(),
                created_by_id=current_user.id if current_user.is_authenticated else None)
            obj.priority = hooks.auto_priority(obj)
            db.session.add(obj)
            db.session.flush()
            db.session.add(RequestUpdate(request_id=obj.id, status='pending', note='Request received'))
            hooks.notify_new_sos(obj)
            db.session.commit()
            flash('Your SOS was received. Keep your tracking code.', 'success')
            return redirect(url_for('sos.track', code=obj.tracking_code))
    return render_template('pages/sos_form.html', form=form)


@bp.route('/sos/track', methods=['GET', 'POST'])
def lookup():
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        return redirect(url_for('sos.track', code=code))
    return render_template('pages/sos_track.html', req=None, code='')


@bp.route('/sos/track/<code>')
def track(code):
    req = EmergencyRequest.query.filter_by(tracking_code=code.strip().upper()[:20]).first()
    team = db.session.get(RescueTeam, req.assigned_team_id) if req and req.assigned_team_id else None
    return render_template('pages/sos_track.html', req=req, code=code, team=team)


@bp.route('/api/sos/pending')
@login_required
def pending():
    if not current_user.can('emergency_requests', 'all'):
        return jsonify(pending=0, latest_id=0)
    q = EmergencyRequest.query.filter_by(status='pending')
    last = q.order_by(EmergencyRequest.id.desc()).first()
    return jsonify(pending=q.count(), latest_id=last.id if last else 0,
                   latest=dict(code=last.tracking_code, people=last.people_count, priority=last.priority,
                               url=url_for('crud.detail', slug='emergency_requests', id=last.id)) if last else None)
