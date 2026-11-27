import math
from collections import defaultdict
from datetime import date, datetime
from flask import session
from sqlalchemy import func, and_, true, extract
from ..extensions import db
from ..models import (Disaster, DisasterType, Incident, EmergencyRequest, RescueTeam, ReliefCamp, Inventory,
                      DonationTransaction, Volunteer, District, Province, FloodAlert, WeatherAlert)


def scope(model):
    """Honours the 'real data only' toggle (hides records flagged as sample)."""
    if session.get('scope') == 'real' and hasattr(model, 'data_source'):
        return model.data_source != 'sample'
    return true()


def _n(v):
    return float(v) if v is not None else 0.0


def counts():
    q = db.session.query
    flood_ids = [t.id for t in DisasterType.query.filter_by(is_flood=True).all()] or [0]
    return dict(
        disasters=q(func.count(Disaster.id)).filter(scope(Disaster)).scalar(),
        active_floods=q(func.count(Incident.id)).filter(scope(Incident), Incident.status.in_(['reported', 'active']),
                                                        Incident.incident_type_id.in_(flood_ids)).scalar(),
        affected=int(_n(q(func.coalesce(func.sum(Incident.affected_people), 0)).filter(scope(Incident)).scalar())),
        rescued=int(_n(q(func.coalesce(func.sum(Incident.people_rescued), 0)).filter(scope(Incident)).scalar())),
        pending_sos=q(func.count(EmergencyRequest.id)).filter(scope(EmergencyRequest), EmergencyRequest.status == 'pending').scalar(),
        active_teams=q(func.count(RescueTeam.id)).filter(scope(RescueTeam), RescueTeam.status.in_(['available', 'deployed', 'standby'])).scalar(),
        camps=q(func.count(ReliefCamp.id)).filter(scope(ReliefCamp), ReliefCamp.status.in_(['open', 'full'])).scalar(),
        resources=q(func.count(func.distinct(Inventory.resource_id))).filter(scope(Inventory), Inventory.quantity > 0).scalar(),
        low_stock=q(func.count(Inventory.id)).filter(scope(Inventory), Inventory.reorder_level > 0,
                                                     Inventory.quantity <= Inventory.reorder_level).scalar(),
        donations=_n(q(func.coalesce(func.sum(DonationTransaction.amount), 0)).filter(
            scope(DonationTransaction), DonationTransaction.status == 'completed').scalar()),
        volunteers=q(func.count(Volunteer.id)).filter(scope(Volunteer), Volunteer.status == 'approved').scalar(),
    )


def month_keys(months=12):
    y, m = date.today().year, date.today().month
    keys = []
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return keys[::-1]


def monthly(model, datecol, value=None, months=12, *filters):
    keys = month_keys(months)
    start = datetime(keys[0][0], keys[0][1], 1)
    agg = func.count(model.id) if value is None else func.coalesce(func.sum(value), 0)
    rows = (db.session.query(extract('year', datecol), extract('month', datecol), agg)
            .filter(datecol >= start, scope(model), *filters)
            .group_by(extract('year', datecol), extract('month', datecol)).all())
    got = {(int(y), int(m)): _n(c) for y, m, c in rows}
    return [f'{y}-{m:02d}' for y, m in keys], [got.get(k, 0) for k in keys]


def district_stats(province_id=None, type_id=None, since=None):
    cond = [Incident.district_id == District.id, scope(Incident)]
    if type_id:
        cond.append(Incident.incident_type_id == type_id)
    if since:
        cond.append(Incident.reported_at >= since)
    q = (db.session.query(District.id, District.name, Province.name, District.latitude, District.longitude,
                          func.count(Incident.id), func.coalesce(func.sum(Incident.affected_people), 0),
                          func.coalesce(func.sum(Incident.people_rescued), 0))
         .join(Province, Province.id == District.province_id)
         .outerjoin(Incident, and_(*cond)))
    if province_id:
        q = q.filter(District.province_id == province_id)
    rows = q.group_by(District.id, District.name, Province.name, District.latitude, District.longitude).all()
    sos = dict(db.session.query(EmergencyRequest.district_id, func.count(EmergencyRequest.id))
               .filter(scope(EmergencyRequest), EmergencyRequest.status.in_(['pending', 'acknowledged', 'assigned', 'in_progress']))
               .group_by(EmergencyRequest.district_id).all())
    camps = {d: (c, _n(o)) for d, c, o in db.session.query(
        ReliefCamp.district_id, func.count(ReliefCamp.id), func.coalesce(func.sum(ReliefCamp.current_occupancy), 0))
        .filter(scope(ReliefCamp), ReliefCamp.status.in_(['open', 'full'])).group_by(ReliefCamp.district_id).all()}
    out = []
    for did, name, prov, lat, lng, n, aff, resc in rows:
        aff, resc = int(_n(aff)), int(_n(resc))
        out.append(dict(id=did, district=name, province=prov, lat=lat, lng=lng, incidents=n, affected=aff, rescued=resc,
                        rescue_pct=round(100.0 * resc / aff, 1) if aff else 0.0, open_sos=sos.get(did, 0),
                        camps=camps.get(did, (0, 0))[0], camp_occupancy=int(camps.get(did, (0, 0))[1])))
    return sorted(out, key=lambda r: (-r['affected'], r['district']))


def count_by(model, col, *filters):
    rows = db.session.query(col, func.count(model.id)).filter(scope(model), *filters).group_by(col).all()
    return {k: v for k, v in rows}


def composition():
    """How many records are sample / reported / verified in the headline tables."""
    out = {}
    for name, model in (('Incidents', Incident), ('SOS requests', EmergencyRequest), ('Relief camps', ReliefCamp)):
        rows = dict(db.session.query(model.data_source, func.count(model.id)).group_by(model.data_source).all())
        out[name] = {k: rows.get(k, 0) for k in ('sample', 'reported', 'verified')}
    return out


def has_sample():
    return (db.session.query(func.count(Incident.id)).filter(Incident.data_source == 'sample').scalar() or 0) > 0


def active_alerts(limit=6):
    f = FloodAlert.query.filter(FloodAlert.is_active.is_(True), scope(FloodAlert)).order_by(FloodAlert.issued_at.desc()).limit(limit).all()
    w = WeatherAlert.query.filter(WeatherAlert.is_active.is_(True), scope(WeatherAlert)).order_by(WeatherAlert.issued_at.desc()).limit(limit).all()
    return f, w
