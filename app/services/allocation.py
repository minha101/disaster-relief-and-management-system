"""Smart resource allocation: finds camps short of food / water / medicine and proposes transfers."""
from collections import defaultdict
from ..extensions import db
from ..models import ReliefCamp, Inventory, Resource, ResourceCategory, ResourceAllocation
from .settings import get_float
from .stats import scope

KINDS = {'food': ('pack', 'need_food_per_person_day'),
         'water': ('litre', 'need_water_per_person_day'),
         'medical': ('kit', 'need_medical_per_person_day')}
PENDING = ('proposed', 'approved', 'dispatched')


def analyse():
    plan_days = get_float('planning_days', 3)
    crit_days = get_float('critical_days', 1)
    rates = {k: get_float(v[1], 1) for k, v in KINDS.items()}
    camps = ReliefCamp.query.filter(ReliefCamp.status.in_(['open', 'full']), scope(ReliefCamp)).order_by(ReliefCamp.name).all()
    rows = (db.session.query(Inventory, Resource, ResourceCategory)
            .join(Resource, Resource.id == Inventory.resource_id)
            .join(ResourceCategory, ResourceCategory.id == Resource.category_id)
            .filter(ResourceCategory.kind.in_(list(KINDS))).all())
    stock = defaultdict(float)
    lines = defaultdict(list)           # kind -> inventory lines in standard unit
    skipped = set()
    for inv, res, cat in rows:
        if (res.unit or '').strip().lower() != KINDS[cat.kind][0]:
            skipped.add(f'{res.name} ({res.unit})')
            continue
        if inv.camp_id:
            stock[(inv.camp_id, cat.kind)] += inv.quantity or 0
        lines[cat.kind].append(inv)
    incoming = defaultdict(float)
    outgoing = defaultdict(float)
    for a, cat in (db.session.query(ResourceAllocation, ResourceCategory)
                   .join(Resource, Resource.id == ResourceAllocation.resource_id)
                   .join(ResourceCategory, ResourceCategory.id == Resource.category_id)
                   .filter(ResourceAllocation.status.in_(PENDING)).all()):
        incoming[(a.camp_id, cat.kind)] += a.quantity
        if a.source_inventory_id:
            outgoing[a.source_inventory_id] += a.quantity
    result, shortages = [], []
    for c in camps:
        occ = c.current_occupancy or 0
        entry = dict(camp=c, occupancy=occ, kinds={})
        for kind, (unit, _) in KINDS.items():
            have = stock[(c.id, kind)]
            inc = incoming[(c.id, kind)]
            per_day = occ * rates[kind]
            days = (have / per_day) if per_day else None
            required = per_day * plan_days
            short = max(0.0, required - have - inc)
            status = 'ok' if days is None else 'critical' if days < crit_days else 'low' if days < plan_days else 'ok'
            entry['kinds'][kind] = dict(stock=have, incoming=inc, days=days, required=required, shortage=short,
                                        status=status, unit=unit)
            if short > 0 and occ > 0:
                shortages.append((days if days is not None else 99, c, kind, short, unit))
        result.append(entry)
    avail = {i.id: (i.quantity or 0) - outgoing[i.id] for k in lines for i in lines[k]}
    suggestions = []
    for days, camp, kind, short, unit in sorted(shortages, key=lambda s: s[0]):
        left = short
        for inv in sorted(lines[kind], key=lambda i: (i.camp_id is not None, -avail[i.id])):
            if left <= 0:
                break
            if inv.camp_id == camp.id:
                continue
            if inv.camp_id:       # a camp may only give what exceeds 1.5x its own planning need
                src_camp = next((e for e in result if e['camp'].id == inv.camp_id), None)
                keep = (src_camp['kinds'][kind]['required'] * 1.5) if src_camp else 0
                can = min(avail[inv.id], max(0.0, src_camp['kinds'][kind]['stock'] - keep)) if src_camp else 0
            else:
                can = avail[inv.id]
            qty = min(left, can)
            if qty >= 1:
                qty = float(int(qty))
                avail[inv.id] -= qty
                left -= qty
                suggestions.append(dict(camp=camp, kind=kind, inventory=inv, resource=inv.resource, quantity=qty,
                                        unit=unit, from_camp=inv.camp_id is not None, days=days if days != 99 else None))
        if left > 0:
            suggestions.append(dict(camp=camp, kind=kind, inventory=None, resource=None, quantity=left, unit=unit,
                                    from_camp=False, days=days if days != 99 else None, unmet=True))
    return dict(camps=result, suggestions=suggestions, plan_days=plan_days, crit_days=crit_days, rates=rates,
                skipped=sorted(skipped))
