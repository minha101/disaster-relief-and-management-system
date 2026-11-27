from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session, abort, send_from_directory, \
    current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from ..extensions import db
from ..models import (User, Incident, EmergencyRequest, AuditLog, Notification, Attachment, IncidentImage, ReliefCamp,
                      Organization, Volunteer, District, DonationCampaign, DonationTransaction, DistributionRecord,
                      Resource, ResourceAllocation, Donation, Disaster)
from ..services import stats

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if User.query.count() == 0:
        return redirect(url_for('auth.setup'))
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    f, w = stats.active_alerts(4)
    return render_template('pages/landing.html', flood_alerts=f, weather_alerts=w)


@bp.route('/dashboard')
@login_required
def dashboard():
    c = stats.counts()
    can = current_user.can
    latest = recent = my_sos = []
    if can('emergency_requests', 'all'):
        latest = (EmergencyRequest.query.filter(stats.scope(EmergencyRequest))
                  .order_by(EmergencyRequest.id.desc()).limit(8).all())
    if can('audit_logs', 'view'):
        recent = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all()
    elif can('incidents', 'view'):
        recent = Incident.query.filter(stats.scope(Incident)).order_by(Incident.reported_at.desc()).limit(8).all()
    if can('emergency_requests', 'create') and not can('emergency_requests', 'all'):
        my_sos = EmergencyRequest.query.filter_by(created_by_id=current_user.id).order_by(EmergencyRequest.id.desc()).limit(5).all()
    f, w = stats.active_alerts(5)
    return render_template('pages/dashboard.html', c=c, latest=latest, recent=recent, my_sos=my_sos, flood_alerts=f,
                           weather_alerts=w, districts=stats.district_stats()[:8], comp=stats.composition(),
                           lookups=dict(users={u.id: u.full_name for u in User.query.all()}))


@bp.route('/api/dashboard')
@login_required
def api_dashboard():
    months, inc = stats.monthly(Incident, Incident.reported_at)
    _, dons = stats.monthly(DonationTransaction, DonationTransaction.transaction_date, DonationTransaction.amount, 12,
                            DonationTransaction.status == 'completed')
    ds = stats.district_stats()[:10]
    camps = (ReliefCamp.query.filter(stats.scope(ReliefCamp), ReliefCamp.status.in_(['open', 'full']))
             .order_by(ReliefCamp.current_occupancy.desc()).limit(8).all())
    return jsonify(
        months=months, incidents=inc, donations=dons,
        severity=stats.count_by(Incident, Incident.severity, Incident.status.in_(['reported', 'active'])),
        sos=stats.count_by(EmergencyRequest, EmergencyRequest.status),
        districts=dict(names=[d['district'] for d in ds], affected=[d['affected'] for d in ds],
                       rescued=[d['rescued'] for d in ds]),
        camps=dict(names=[c.name[:22] for c in camps], pct=[c.occupancy_pct for c in camps]))


@bp.post('/scope/<value>')
@login_required
def set_scope(value):
    session['scope'] = 'real' if value == 'real' else 'all'
    nxt = request.form.get('next') or ''
    return redirect(nxt if nxt.startswith('/') and not nxt.startswith('//') else url_for('main.dashboard'))


# ---------------------------------------------------------------- notifications
@bp.route('/api/notifications')
@login_required
def api_notifications():
    q = Notification.query.filter_by(user_id=current_user.id)
    items = q.order_by(Notification.id.desc()).limit(8).all()
    return jsonify(unread=q.filter_by(is_read=False).count(),
                   items=[dict(id=n.id, title=n.title, message=n.message, level=n.level, link=n.link, read=n.is_read,
                               at=n.created_at.strftime('%d %b %H:%M')) for n in items])


@bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    p = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('pages/notifications.html', p=p)


@bp.post('/notifications/read')
@login_required
def notifications_read():
    q = Notification.query.filter_by(user_id=current_user.id, is_read=False)
    nid = request.form.get('id', type=int)
    if nid:
        q = q.filter_by(id=nid)
    q.update(dict(is_read=True, read_at=datetime.utcnow()))
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'fetch':
        return jsonify(ok=True)
    return redirect(request.referrer or url_for('main.notifications'))


# ---------------------------------------------------------------- files
@bp.route('/files/<name>')
@login_required
def files(name):
    known = Attachment.query.filter_by(stored_name=name).first() or IncidentImage.query.filter_by(stored_name=name).first()
    if not known:
        abort(404)
    original = getattr(known, 'original_name', None) or getattr(known, 'file_name', name)
    is_img = name.rsplit('.', 1)[-1].lower() in ('png', 'jpg', 'jpeg', 'gif', 'webp')
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], name, as_attachment=not is_img,
                               download_name=original)


# ---------------------------------------------------------------- search
@bp.route('/search')
@login_required
def search():
    term = (request.args.get('q') or '').strip()[:60]
    results = []
    if len(term) >= 2:
        like = f'%{term}%'
        spec = [('incidents', Incident, [Incident.title], 'Incident'),
                ('emergency_requests', EmergencyRequest, [EmergencyRequest.tracking_code, EmergencyRequest.requester_name], 'SOS'),
                ('relief_camps', ReliefCamp, [ReliefCamp.name, ReliefCamp.code], 'Relief camp'),
                ('organizations', Organization, [Organization.name], 'Organization'),
                ('volunteers', Volunteer, [Volunteer.full_name], 'Volunteer'),
                ('districts', District, [District.name], 'District'),
                ('disasters', Disaster, [Disaster.title], 'Disaster')]
        for slug, model, cols, kind in spec:
            if not current_user.can(slug, 'view'):
                continue
            q = model.query.filter(or_(*[c.ilike(like) for c in cols]))
            if hasattr(model, 'created_by_id') and not current_user.can(slug, 'all'):
                q = q.filter(model.created_by_id == current_user.id)
            for o in q.limit(8).all():
                results.append(dict(kind=kind, label=o.label, url=url_for('crud.detail', slug=slug, id=o.id)))
    return render_template('pages/search.html', term=term, results=results)


# ---------------------------------------------------------------- public transparency
@bp.route('/transparency')
def transparency():
    camp_rows = (db.session.query(DonationCampaign.id, DonationCampaign.title, DonationCampaign.goal_amount,
                                  func.coalesce(func.sum(DonationTransaction.amount), 0))
                 .outerjoin(Donation, Donation.campaign_id == DonationCampaign.id)
                 .outerjoin(DonationTransaction, (DonationTransaction.donation_id == Donation.id) &
                            (DonationTransaction.status == 'completed') & stats.scope(DonationTransaction))
                 .filter(stats.scope(DonationCampaign))
                 .group_by(DonationCampaign.id, DonationCampaign.title, DonationCampaign.goal_amount).all())
    campaigns = [dict(title=t, goal=float(g or 0), raised=float(r or 0),
                      pct=round(100 * float(r or 0) / float(g), 1) if g else 0) for _, t, g, r in camp_rows]
    dist = (db.session.query(Resource.name, Resource.unit, func.sum(DistributionRecord.quantity),
                             func.sum(DistributionRecord.beneficiaries))
            .join(DistributionRecord, DistributionRecord.resource_id == Resource.id)
            .filter(stats.scope(DistributionRecord)).group_by(Resource.name, Resource.unit).all())
    delivered = ResourceAllocation.query.filter(ResourceAllocation.status == 'delivered', stats.scope(ResourceAllocation)).count()
    return render_template('pages/transparency.html', campaigns=campaigns, dist=dist, delivered=delivered,
                           comp=stats.composition(), total=sum(c['raised'] for c in campaigns))
