import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from ..extensions import db
from ..models import (Province, DisasterType, Incident, RescueOperation, ReliefCamp, Inventory, Resource, ResourceAllocation)
from ..services import stats, risk, allocation, audit
from ..services.rbac import perm_required
from .crud import need

bp = Blueprint('intel', __name__)


# ---------------------------------------------------------------- analytics
def _filters():
    prov = request.args.get('province', type=int)
    typ = request.args.get('type', type=int)
    days = request.args.get('days', type=int)
    since = datetime.utcnow() - timedelta(days=days) if days else None
    return prov, typ, since


@bp.route('/analytics')
@login_required
@perm_required('incidents', 'view')
def analytics():
    return render_template('pages/analytics.html', provinces=Province.query.order_by(Province.name).all(),
                           types=DisasterType.query.order_by(DisasterType.name).all(), args=request.args,
                           comp=stats.composition())


@bp.route('/api/analytics')
@login_required
@perm_required('incidents', 'view')
def api_analytics():
    prov, typ, since = _filters()
    ds = stats.district_stats(prov, typ, since)
    types = dict(DisasterType.query.with_entities(DisasterType.id, DisasterType.name).all())
    by_type = stats.count_by(Incident, Incident.incident_type_id)
    months, inc = stats.monthly(Incident, Incident.reported_at)
    ops = stats.count_by(RescueOperation, RescueOperation.status)
    top = [d for d in ds if d['incidents'] or d['affected']][:15]
    return jsonify(
        districts=top,
        by_type={types.get(k, '?'): v for k, v in by_type.items()},
        months=months, monthly=inc, ops=ops,
        totals=dict(incidents=sum(d['incidents'] for d in ds), affected=sum(d['affected'] for d in ds),
                    rescued=sum(d['rescued'] for d in ds)))


@bp.route('/analytics.csv')
@login_required
@perm_required('incidents', 'view')
def analytics_csv():
    prov, typ, since = _filters()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['district', 'province', 'incidents', 'affected', 'rescued', 'rescue_pct', 'open_sos', 'open_camps', 'camp_occupancy'])
    for d in stats.district_stats(prov, typ, since):
        w.writerow([d['district'], d['province'], d['incidents'], d['affected'], d['rescued'], d['rescue_pct'],
                    d['open_sos'], d['camps'], d['camp_occupancy']])
    return Response('\ufeff' + buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=district_analytics.csv'})


# ---------------------------------------------------------------- risk index
@bp.route('/risk')
@login_required
@perm_required('risk_assessments', 'view')
def risk_page():
    basis = request.args.get('basis', 'all')
    if basis not in risk.BASIS:
        basis = 'all'
    results = risk.compute(basis)
    n_inc = sum(r['incidents'] for r in results)
    return render_template('pages/risk.html', results=results, basis=basis, labels=risk.BASIS_LABEL, weights=risk.WEIGHTS,
                           years=risk.YEARS, n_inc=n_inc, comp=stats.composition(),
                           can_save=current_user.can('risk_assessments', 'create'))


@bp.post('/risk/snapshot')
@login_required
@perm_required('risk_assessments', 'create')
def risk_snapshot():
    basis = request.form.get('basis', 'all')
    basis = basis if basis in risk.BASIS else 'all'
    n = risk.save_snapshot(risk.compute(basis), basis, current_user.id)
    audit.log('risk_snapshot', 'risk_assessments', details={'basis': basis, 'rows': n})
    flash(f'Saved {n} district assessments (method: heuristic index, not a validated model).', 'success')
    return redirect(url_for('crud.index', slug='risk_assessments'))


# ---------------------------------------------------------------- smart allocation
@bp.route('/allocation')
@login_required
@perm_required('resource_allocations', 'view')
def allocation_page():
    res = allocation.analyse()
    return render_template('pages/allocation.html', r=res, kinds=allocation.KINDS,
                           can_propose=current_user.can('resource_allocations', 'create'))


@bp.post('/allocation/propose')
@login_required
@perm_required('resource_allocations', 'create')
def propose():
    try:
        camp_id = int(request.form['camp_id'])
        inv_id = int(request.form['inventory_id'])
        qty = float(request.form['quantity'])
    except (KeyError, ValueError):
        flash('Invalid proposal.', 'danger')
        return redirect(url_for('intel.allocation_page'))
    inv = db.session.get(Inventory, inv_id)
    camp = db.session.get(ReliefCamp, camp_id)
    if not inv or not camp or qty <= 0 or inv.camp_id == camp_id or qty > (inv.quantity or 0) + 1e-9:
        flash('Proposal rejected: check quantity and source stock.', 'danger')
        return redirect(url_for('intel.allocation_page'))
    a = ResourceAllocation(resource_id=inv.resource_id, source_inventory_id=inv.id, camp_id=camp_id, quantity=qty,
                           status='proposed', created_by_id=current_user.id, data_source='reported',
                           notes='Created from Smart Allocation suggestion - requires approval')
    db.session.add(a)
    db.session.flush()
    audit.log('propose_allocation', 'resource_allocations', a.id, commit=False)
    db.session.commit()
    flash('Allocation proposed. Approve and mark delivered from the Resource Allocation module to move stock.', 'success')
    return redirect(url_for('crud.detail', slug='resource_allocations', id=a.id))
