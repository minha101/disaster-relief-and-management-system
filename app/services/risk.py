"""Transparent district risk INDEX (heuristic). It is NOT a validated predictive model."""
import math
from collections import defaultdict
from datetime import datetime, timedelta, date
from ..extensions import db
from ..models import Incident, FloodAlert, District, Province, RiskAssessment

BASIS = {'verified': {'verified'}, 'reported': {'verified', 'reported'}, 'all': {'verified', 'reported', 'sample'}}
BASIS_LABEL = {'verified': 'Verified records only', 'reported': 'Verified + reported records',
               'all': 'All records incl. SAMPLE demo data'}
SEV_W = {'low': 1, 'moderate': 2, 'high': 3, 'critical': 4}
ALERT_W = {'normal': 0, 'low': .2, 'medium': .4, 'high': .6, 'very_high': .8, 'exceptional': 1.0}
WEIGHTS = {'frequency': .25, 'severity': .20, 'affected_population': .25, 'recency': .20, 'active_flood_alerts': .10}
YEARS = 5


def level_of(score):
    return 'low' if score < 25 else 'moderate' if score < 50 else 'high' if score < 75 else 'very_high'


def compute(basis='all'):
    sources = BASIS.get(basis, BASIS['all'])
    now = datetime.utcnow()
    inc = (db.session.query(Incident.district_id, Incident.severity, Incident.affected_people, Incident.reported_at,
                            Incident.data_source)
           .filter(Incident.data_source.in_(list(sources)), Incident.reported_at >= now - timedelta(days=365 * YEARS)).all())
    per = defaultdict(lambda: dict(n=0, sev=0.0, aff=0, rec=0.0, sample=0, verified=0))
    for did, sev, aff, at, src in inc:
        p = per[did]
        p['n'] += 1
        p['sev'] += SEV_W.get(sev, 1)
        p['aff'] += aff or 0
        p['rec'] += math.exp(-max((now - at).days, 0) / 365.0)
        p['sample'] += src == 'sample'
        p['verified'] += src == 'verified'
    alert = defaultdict(float)
    for did, lvl in db.session.query(FloodAlert.district_id, FloodAlert.flood_level).filter(
            FloodAlert.is_active.is_(True), FloodAlert.data_source.in_(list(sources))).all():
        alert[did] = max(alert[did], ALERT_W.get(lvl, 0))
    max_n = max([p['n'] for p in per.values()] or [1])
    max_aff = max([math.log1p(p['aff']) for p in per.values()] or [1]) or 1
    max_rec = max([p['rec'] for p in per.values()] or [1]) or 1
    out = []
    for d, prov in db.session.query(District, Province.name).join(Province, Province.id == District.province_id).all():
        p = per.get(d.id)
        n = p['n'] if p else 0
        comp = dict(frequency=(n / max_n) if p else 0,
                    severity=(p['sev'] / n / 4.0) if p else 0,
                    affected_population=(math.log1p(p['aff']) / max_aff) if p else 0,
                    recency=(p['rec'] / max_rec) if p else 0,
                    active_flood_alerts=alert.get(d.id, 0))
        score = round(100 * sum(WEIGHTS[k] * v for k, v in comp.items()), 1)
        sample_share = (p['sample'] / n) if n else 0
        conf = 'low' if (n < 3 or sample_share > .5) else 'medium' if n < 8 else 'high'
        out.append(dict(district_id=d.id, district=d.name, province=prov, lat=d.latitude, lng=d.longitude, incidents=n,
                        score=score, level=level_of(score) if (n or alert.get(d.id)) else 'low',
                        confidence=conf, sample_share=round(100 * sample_share), has_data=bool(n),
                        components={k: round(v, 2) for k, v in comp.items()}))
    return sorted(out, key=lambda r: -r['score'])


def save_snapshot(results, basis, user_id):
    uses_sample = 'sample' in BASIS.get(basis, BASIS['all'])
    n = 0
    for r in results:
        if not r['has_data']:
            continue
        db.session.add(RiskAssessment(
            district_id=r['district_id'], method='heuristic_v1', risk_score=r['score'], risk_level=r['level'],
            incident_count=r['incidents'], confidence=r['confidence'], assessed_on=date.today(),
            data_basis=f'basis={basis}; incidents last {YEARS}y; sample share {r["sample_share"]}%',
            is_validated_model=False, created_by_id=user_id, data_source='sample' if uses_sample else 'reported',
            notes='Heuristic index from recorded incidents and active flood alerts. Not a validated predictive model.'))
        n += 1
    db.session.commit()
    return n
