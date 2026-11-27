from ..extensions import db
from ..models import Inventory, StockTransaction, ReliefCamp, CampResident, CampCapacityHistory
from sqlalchemy import func


def get_inventory(resource_id, camp_id=None, warehouse=None, create=False, user_id=None, source='reported'):
    q = Inventory.query.filter_by(resource_id=resource_id, camp_id=camp_id)
    if camp_id is None:
        q = q.filter(Inventory.warehouse_name == warehouse)
    inv = q.first()
    if not inv and create:
        inv = Inventory(resource_id=resource_id, camp_id=camp_id, warehouse_name=warehouse, quantity=0,
                        reorder_level=0, created_by_id=user_id, data_source=source)
        db.session.add(inv)
        db.session.flush()
    return inv


def apply_stock(inv, txn_type, qty, reason, reference=None, user_id=None, source='reported', notes=None, when=None):
    qty = float(qty)
    if qty <= 0:
        raise ValueError('Quantity must be greater than zero')
    if txn_type == 'out' and qty > (inv.quantity or 0) + 1e-9:
        raise ValueError('Insufficient stock')
    inv.quantity = (inv.quantity or 0) + (qty if txn_type == 'in' else -qty)
    t = StockTransaction(inventory_id=inv.id, txn_type=txn_type, quantity=qty, reason=reason, reference=reference,
                         created_by_id=user_id, data_source=source, notes=notes)
    if when:
        t.txn_date = when
    db.session.add(t)
    return t


def recompute_camp(camp_id, snapshot=True, note='auto snapshot'):
    camp = db.session.get(ReliefCamp, camp_id)
    if not camp:
        return
    total = (db.session.query(func.coalesce(func.sum(CampResident.persons), 0))
             .filter(CampResident.camp_id == camp_id, CampResident.status == 'resident').scalar())
    camp.current_occupancy = int(total or 0)
    if camp.status in ('open', 'full'):
        camp.status = 'full' if camp.capacity and camp.current_occupancy >= camp.capacity else 'open'
    if snapshot:
        db.session.add(CampCapacityHistory(camp_id=camp.id, capacity=camp.capacity,
                                           occupancy=camp.current_occupancy, note=note))
