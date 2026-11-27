import json
from flask import Blueprint, render_template, abort, Response, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import ReliefCamp, Inventory, DonationCampaign, Donation, DonationTransaction, Report, Incident
from sqlalchemy import func
from ..services import stats, risk, audit, pdfgen
from ..services.rbac import perm_required

bp = Blueprint('reports', __name__, url_prefix='/reports')
KINDS = {
    'summary': 'Situation summary', 'camps': 'Relief camps & occupancy', 'inventory': 'Inventory & stock levels',
    'donations': 'Donation transparency', 'analytics': 'District analytics', 'risk': 'District risk index (heuristic)'}


@bp.route('/')
@login_required
@perm_required('reports', 'view')
def index():
    return render_template('pages/reports.html', kinds=KINDS)


def _comp_note():
    comp = stats.composition()
    return 'Record mix - ' + '; '.join(f'{k}: {v["sample"]} sample / {v["reported"]} reported / {v["verified"]} verified'
                                      for k, v in comp.items())


@bp.route('/<kind>.pdf')
@login_required
@perm_required('reports', 'view')
def generate(kind):
    if kind not in KINDS:
        abort(404)
    sections = []
    if kind == 'summary':
        c = stats.counts()
        sections.append(('Key figures', ['Indicator', 'Value'], [
            ['Disasters recorded', c['disasters']], ['Active flood incidents', c['active_floods']],
            ['People affected (incident records)', f'{c["affected"]:,}'], ['People rescued', f'{c["rescued"]:,}'],
            ['Pending SOS requests', c['pending_sos']], ['Active rescue teams', c['active_teams']],
            ['Open relief camps', c['camps']], ['Resource types in stock', c['resources']],
            ['Low-stock inventory lines', c['low_stock']], ['Donations received (PKR, completed)', f'{c["donations"]:,.0f}'],
            ['Approved volunteers', c['volunteers']]]))
        sections.append(('District statistics (top 20)', ['District', 'Province', 'Incidents', 'Affected', 'Rescued', 'Rescue %', 'Open SOS'],
                         [[d['district'], d['province'], d['incidents'], f'{d["affected"]:,}', f'{d["rescued"]:,}',
                           d['rescue_pct'], d['open_sos']] for d in stats.district_stats()[:20]]))
    elif kind == 'camps':
        rows = ReliefCamp.query.filter(stats.scope(ReliefCamp)).order_by(ReliefCamp.name).all()
        sections.append(('Relief camps', ['Camp', 'Code', 'Capacity', 'Occupancy', 'Occupancy %', 'Status', 'Manager', 'Data'],
                         [[r.name, r.code, r.capacity, r.current_occupancy, r.occupancy_pct, r.status, r.manager_name,
                           r.data_source] for r in rows]))
    elif kind == 'inventory':
        rows = Inventory.query.filter(stats.scope(Inventory)).all()
        sections.append(('Inventory', ['Resource', 'Location', 'Quantity', 'Unit', 'Reorder level', 'Flag', 'Data'],
                         [[r.resource.name, r.camp.name if r.camp else r.warehouse_name, f'{r.quantity:g}', r.resource.unit,
                           f'{r.reorder_level:g}', 'LOW' if r.reorder_level and r.quantity <= r.reorder_level else '',
                           r.data_source] for r in sorted(rows, key=lambda x: x.resource.name)]))
    elif kind == 'donations':
        rows = (db.session.query(DonationCampaign.title, DonationCampaign.goal_amount, func.coalesce(func.sum(DonationTransaction.amount), 0),
                                 func.count(func.distinct(Donation.id)))
                .outerjoin(Donation, Donation.campaign_id == DonationCampaign.id)
                .outerjoin(DonationTransaction, (DonationTransaction.donation_id == Donation.id) & (DonationTransaction.status == 'completed'))
                .filter(stats.scope(DonationCampaign)).group_by(DonationCampaign.id, DonationCampaign.title, DonationCampaign.goal_amount).all())
        sections.append(('Campaign funding (donor identities omitted)', ['Campaign', 'Goal (PKR)', 'Received (PKR)', 'Progress %', 'Donations'],
                         [[t, f'{float(g):,.0f}', f'{float(r):,.0f}', round(100 * float(r) / float(g), 1) if g else 0, n]
                          for t, g, r, n in rows]))
    elif kind == 'analytics':
        sections.append(('District analytics', ['District', 'Province', 'Incidents', 'Affected', 'Rescued', 'Rescue %', 'Open SOS', 'Camps', 'Camp occupancy'],
                         [[d['district'], d['province'], d['incidents'], f'{d["affected"]:,}', f'{d["rescued"]:,}', d['rescue_pct'],
                           d['open_sos'], d['camps'], d['camp_occupancy']] for d in stats.district_stats()]))
    elif kind == 'risk':
        basis = request.args.get('basis', 'all')
        basis = basis if basis in risk.BASIS else 'all'
        res = [r for r in risk.compute(basis) if r['has_data']]
        sections.append((f'Heuristic risk index - {risk.BASIS_LABEL[basis]} (NOT a validated predictive model)',
                         ['District', 'Province', 'Incidents', 'Score', 'Level', 'Confidence', 'Sample share %'],
                         [[r['district'], r['province'], r['incidents'], r['score'], r['level'], r['confidence'],
                           r['sample_share']] for r in res]))
    scope_label = 'real data only (sample excluded)' if stats.session.get('scope') == 'real' else 'all data incl. SAMPLE demo records'
    pdf = pdfgen.build_pdf(KINDS[kind], sections, pdfgen.meta(current_user, scope_label, _comp_note()))
    db.session.add(Report(title=KINDS[kind], report_type=kind, data_scope='real' if stats.session.get('scope') == 'real' else 'all',
                          created_by_id=current_user.id, file_name=f'{kind}.pdf', parameters=json.dumps(dict(request.args))))
    audit.log('report_generated', 'reports', details=kind, commit=False)
    db.session.commit()
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename={kind}_report.pdf'})
