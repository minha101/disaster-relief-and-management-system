from datetime import datetime
from flask import Blueprint, render_template, jsonify, url_for
from flask_login import login_required, current_user
from ..extensions import db
from ..models import (Incident, EmergencyRequest, RescueTeam, ReliefCamp, AffectedArea, Village, Hospital, FloodAlert,
                      District, EvacuationRoute, EvacuationPlan, DisasterType)
from ..services import stats

bp = Blueprint('gis', __name__)
ACTIVE_SOS = ['pending', 'acknowledged', 'assigned', 'in_progress']


def _own(slug, model, q):
    if not current_user.can(slug, 'all') and hasattr(model, 'created_by_id'):
        q = q.filter(model.created_by_id == current_user.id)
    return q


@bp.route('/map')
@login_required
def map_page():
    layers = [(k, label) for k, slug, label in (
        ('incidents', 'incidents', 'Flood incidents'), ('sos', 'emergency_requests', 'SOS requests'),
        ('camps', 'relief_camps', 'Relief camps'), ('teams', 'rescue_teams', 'Rescue teams (last reported)'),
        ('areas', 'affected_areas', 'Affected villages'), ('hospitals', 'hospitals', 'Hospitals'),
        ('alerts', 'flood_alerts', 'Flood alerts (district)'), ('routes', 'evacuation_routes', 'Evacuation routes'))
        if current_user.can(slug, 'view')]
    return render_template('pages/map.html', layers=layers)


@bp.route('/api/map')
@login_required
def api_map():
    can = current_user.can
    out = {}
    if can('incidents', 'view'):
        rows = (Incident.query.filter(stats.scope(Incident), Incident.latitude.isnot(None))
                .order_by(Incident.reported_at.desc()).limit(500).all())
        d = {x.id: x.name for x in District.query.all()}
        out['incidents'] = [dict(id=r.id, lat=r.latitude, lng=r.longitude, title=r.title, severity=r.severity,
                                 status=r.status, district=d.get(r.district_id), affected=r.affected_people,
                                 rescued=r.people_rescued, src=r.data_source,
                                 url=url_for('crud.detail', slug='incidents', id=r.id)) for r in rows]
    if can('emergency_requests', 'view'):
        q = _own('emergency_requests', EmergencyRequest,
                 EmergencyRequest.query.filter(stats.scope(EmergencyRequest), EmergencyRequest.status.in_(ACTIVE_SOS),
                                               EmergencyRequest.latitude.isnot(None)))
        staff = can('emergency_requests', 'all')
        out['sos'] = [dict(id=r.id, lat=r.latitude, lng=r.longitude, code=r.tracking_code, people=r.people_count,
                           priority=r.priority, status=r.status, injured=r.has_injured, src=r.data_source,
                           phone=r.phone if staff else None, when=r.created_at.strftime('%d %b %H:%M'),
                           url=url_for('crud.detail', slug='emergency_requests', id=r.id)) for r in q.limit(500).all()]
    if can('relief_camps', 'view'):
        rows = ReliefCamp.query.filter(stats.scope(ReliefCamp), ReliefCamp.latitude.isnot(None),
                                       ReliefCamp.status.in_(['open', 'full'])).limit(500).all()
        out['camps'] = [dict(id=r.id, lat=r.latitude, lng=r.longitude, name=r.name, cap=r.capacity,
                             occ=r.current_occupancy, pct=r.occupancy_pct, status=r.status, src=r.data_source,
                             url=url_for('crud.detail', slug='relief_camps', id=r.id)) for r in rows]
    if can('rescue_teams', 'view'):
        rows = RescueTeam.query.filter(stats.scope(RescueTeam), RescueTeam.status != 'offline').limit(200).all()
        teams = []
        for r in rows:
            lat, lng = (r.last_latitude, r.last_longitude) if r.last_latitude is not None else (r.base_latitude, r.base_longitude)
            if lat is None:
                continue
            teams.append(dict(id=r.id, lat=lat, lng=lng, name=r.name, status=r.status, type=r.team_type, src=r.data_source,
                              is_base=r.last_latitude is None,
                              at=r.last_location_at.strftime('%d %b %H:%M') if r.last_location_at else None,
                              url=url_for('crud.detail', slug='rescue_teams', id=r.id)))
        out['teams'] = teams
    if can('affected_areas', 'view'):
        rows = (db.session.query(AffectedArea, Village).join(Village, Village.id == AffectedArea.village_id)
                .filter(stats.scope(AffectedArea), Village.latitude.isnot(None)).limit(500).all())
        out['areas'] = [dict(id=a.id, lat=v.latitude, lng=v.longitude, name=v.name, pop=a.population_affected,
                             houses=a.houses_damaged, status=a.status, src=a.data_source) for a, v in rows]
    if can('hospitals', 'view'):
        out['hospitals'] = [dict(id=h.id, lat=h.latitude, lng=h.longitude, name=h.name, beds=h.available_beds,
                                 total=h.total_beds, status=h.status, upd=h.updated_at.strftime('%d %b %H:%M'), src=h.data_source)
                            for h in Hospital.query.filter(stats.scope(Hospital), Hospital.latitude.isnot(None)).limit(300).all()]
    if can('flood_alerts', 'view'):
        rows = (db.session.query(FloodAlert, District).join(District, District.id == FloodAlert.district_id)
                .filter(FloodAlert.is_active.is_(True), stats.scope(FloodAlert), District.latitude.isnot(None)).all())
        out['alerts'] = [dict(lat=d.latitude, lng=d.longitude, district=d.name, title=a.title, level=a.flood_level,
                              source=a.source_name, river=a.river, src=a.data_source) for a, d in rows]
    if can('evacuation_routes', 'view'):
        rows = (db.session.query(EvacuationRoute, EvacuationPlan).join(EvacuationPlan, EvacuationPlan.id == EvacuationRoute.plan_id)
                .filter(EvacuationPlan.status.in_(['approved', 'active']), stats.scope(EvacuationRoute)).limit(200).all())
        out['routes'] = [dict(name=r.name, plan=p.title, status=r.status, a=[r.start_latitude, r.start_longitude],
                              b=[r.end_latitude, r.end_longitude], km=r.distance_km, src=r.data_source) for r, p in rows]
    out['generated'] = datetime.now().strftime('%d %b %Y %H:%M:%S')
    out['has_sample'] = stats.has_sample()
    return jsonify(out)
