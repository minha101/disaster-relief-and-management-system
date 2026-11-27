"""Business rules that run around generic CRUD saves, keyed by module slug."""
import re
import secrets
from datetime import datetime
from ..extensions import db
from ..models import (Role, UserRole, EmergencyRequest, RequestUpdate, RequestCategory, Inventory, StockTransaction,
                      Donation, ResourceAllocation, ResourceRequest, Task, User, RescueTeam)
from . import notify, stock

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
PASSWORD_RE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$')
CLOSED_SOS = ('rescued', 'resolved', 'cancelled', 'false_alarm')


def new_tracking_code():
    while True:
        code = 'SOS-' + ''.join(secrets.choice(ALPHABET) for _ in range(8))
        if not EmergencyRequest.query.filter_by(tracking_code=code).first():
            return code


def auto_priority(obj):
    score = (2 if obj.has_injured else 0) + (1 if obj.needs_medical else 0) + (1 if (obj.people_count or 1) >= 10 else 0)
    if obj.category_id:
        cat = db.session.get(RequestCategory, obj.category_id)
        score += (cat.priority_weight or 0) if cat else 0
    return 'critical' if score >= 5 else 'high' if score >= 3 else 'medium' if score >= 1 else 'low'


def notify_new_sos(obj):
    notify.notify_roles(['super_admin', 'admin', 'dma', 'rescue_team'],
                        f'New SOS {obj.tracking_code}',
                        f'{obj.people_count} people - {obj.priority} priority' + (' - injured reported' if obj.has_injured else ''),
                        'danger', f'/m/emergency_requests/{obj.id}')


def password_error(pw):
    return None if PASSWORD_RE.match(pw or '') else 'Password needs 8+ characters with upper-case, lower-case and a digit.'


# ------------------------------------------------------------------ before save
def before_save(slug, obj, creating, ctx):
    user, data = ctx['user'], ctx['data']
    fn = globals().get('_before_' + slug)
    return fn(obj, creating, user, data, ctx) if fn else None


def _before_emergency_requests(obj, creating, user, data, ctx):
    if not obj.latitude and not (obj.address or '').strip():
        return 'Provide coordinates or an address so teams can find the location.'
    if (obj.latitude is None) != (obj.longitude is None):
        return 'Latitude and longitude must be provided together.'
    if creating:
        obj.tracking_code = new_tracking_code()
        if not user.can('emergency_requests', 'all'):
            obj.status, obj.priority = 'pending', auto_priority(obj)
    if obj.status in CLOSED_SOS and not obj.resolved_at:
        obj.resolved_at = datetime.utcnow()


def _before_incidents(obj, creating, user, data, ctx):
    if (obj.people_rescued or 0) > (obj.affected_people or 0):
        return 'People rescued cannot exceed affected people.'


def _before_stock_transactions(obj, creating, user, data, ctx):
    inv = db.session.get(Inventory, obj.inventory_id)
    if obj.txn_type == 'out' and obj.quantity > (inv.quantity or 0) + 1e-9:
        return f'Insufficient stock: only {inv.quantity:g} available.'
    if not obj.quantity or obj.quantity <= 0:
        return 'Quantity must be greater than zero.'


def _before_distribution_records(obj, creating, user, data, ctx):
    if obj.camp_id:
        inv = stock.get_inventory(obj.resource_id, obj.camp_id)
        if not inv or obj.quantity > (inv.quantity or 0) + 1e-9:
            return 'Insufficient stock in this camp inventory for that resource.'


def _before_inventories(obj, creating, user, data, ctx):
    if not obj.camp_id and not (obj.warehouse_name or '').strip():
        return 'Choose a camp or enter a warehouse name.'
    q = Inventory.query.filter_by(resource_id=obj.resource_id, camp_id=obj.camp_id)
    if not obj.camp_id:
        q = q.filter(Inventory.warehouse_name == obj.warehouse_name)
    if obj.id:
        q = q.filter(Inventory.id != obj.id)
    if q.first():
        return 'An inventory line for this resource and location already exists.'


def _before_resource_allocations(obj, creating, user, data, ctx):
    if obj.applied and obj.status != 'delivered':
        return 'This allocation has already been delivered and applied to stock; it cannot be changed.'
    if obj.status == 'delivered' and not obj.applied:
        src = db.session.get(Inventory, obj.source_inventory_id) if obj.source_inventory_id else None
        if not src:
            return 'Select a source inventory before marking as delivered.'
        if src.resource_id != obj.resource_id:
            return 'Source inventory holds a different resource.'
        if src.camp_id == obj.camp_id:
            return 'Source and destination cannot be the same camp.'
        if obj.quantity > (src.quantity or 0) + 1e-9:
            return f'Insufficient stock at source: {src.quantity:g} available.'


def _before_donations(obj, creating, user, data, ctx):
    if obj.donation_type == 'cash' and not (obj.amount and obj.amount > 0):
        return 'Cash donations need an amount greater than zero.'
    if obj.donation_type == 'in_kind' and not (obj.resource_id and obj.quantity):
        return 'In-kind donations need a resource and quantity.'


def _before_donation_transactions(obj, creating, user, data, ctx):
    if not obj.amount or obj.amount <= 0:
        return 'Amount must be greater than zero.'


def _before_weather_alerts(obj, creating, user, data, ctx):
    if obj.valid_from and obj.valid_until and obj.valid_until < obj.valid_from:
        return 'Valid-until must be after valid-from.'


_before_flood_alerts = lambda obj, c, u, d, x: (
    'Valid-until must be after issue time.' if obj.valid_until and obj.issued_at and obj.valid_until < obj.issued_at else None)


def _before_relief_camps(obj, creating, user, data, ctx):
    if not obj.capacity or obj.capacity <= 0:
        return 'Capacity must be greater than zero.'


def _before_tasks(obj, creating, user, data, ctx):
    if creating:
        obj.sort_order = (db.session.query(db.func.coalesce(db.func.max(Task.sort_order), 0)).scalar() or 0) + 1
    obj.completed_at = datetime.utcnow() if obj.status == 'done' else None


def _before_complaints(obj, creating, user, data, ctx):
    if obj.status in ('resolved', 'rejected') and not obj.resolved_at:
        obj.resolved_at = datetime.utcnow()


def _before_users(obj, creating, user, data, ctx):
    obj.email = (obj.email or '').strip().lower()
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', obj.email):
        return 'Enter a valid e-mail address.'
    role = Role.query.filter_by(code=data.get('role_code')).first()
    if not role:
        return 'Select a role.'
    if role.code == 'super_admin' and not user.has_role('super_admin'):
        return 'Only a Super Admin can grant the Super Admin role.'
    if not creating and obj.has_role('super_admin') and not user.has_role('super_admin'):
        return 'Only a Super Admin can modify a Super Admin account.'
    pw = data.get('password') or ''
    if creating and not pw:
        return 'Password is required for new users.'
    if pw:
        err = password_error(pw)
        if err:
            return err
        obj.set_password(pw)
    if not creating and obj.id == user.id and not obj.active:
        return 'You cannot deactivate your own account.'
    ctx['role'] = role


# ------------------------------------------------------------------ after save
def after_save(slug, obj, creating, ctx):
    fn = globals().get('_after_' + slug)
    if fn:
        fn(obj, creating, ctx)


def _after_emergency_requests(obj, creating, ctx):
    old = ctx.get('old') or {}
    if creating:
        db.session.add(RequestUpdate(request_id=obj.id, status=obj.status, note='Request received',
                                     updated_by_id=ctx['user'].id))
        notify_new_sos(obj)
    elif old.get('status') != obj.status:
        db.session.add(RequestUpdate(request_id=obj.id, status=obj.status, note=f'Status changed to {obj.status}',
                                     updated_by_id=ctx['user'].id))
    if obj.assigned_team_id and old.get('assigned_team_id') != obj.assigned_team_id:
        team = db.session.get(RescueTeam, obj.assigned_team_id)
        if team and team.lead_user_id:
            notify.notify_user(team.lead_user_id, f'SOS {obj.tracking_code} assigned to your team',
                               obj.address or 'See map for location', 'warning', f'/m/emergency_requests/{obj.id}')


def _after_camp_residents(obj, creating, ctx):
    stock.recompute_camp(obj.camp_id)
    old = (ctx.get('old') or {}).get('camp_id')
    if old and old != obj.camp_id:
        stock.recompute_camp(old)


def _after_stock_transactions(obj, creating, ctx):
    inv = db.session.get(Inventory, obj.inventory_id)
    inv.quantity = (inv.quantity or 0) + (obj.quantity if obj.txn_type == 'in' else -obj.quantity)


def _after_distribution_records(obj, creating, ctx):
    if obj.camp_id and creating:
        inv = stock.get_inventory(obj.resource_id, obj.camp_id)
        stock.apply_stock(inv, 'out', obj.quantity, 'distribution', f'DIST-{obj.id}', ctx['user'].id)


def _after_resource_allocations(obj, creating, ctx):
    if obj.status == 'delivered' and not obj.applied:
        src = db.session.get(Inventory, obj.source_inventory_id)
        dest = stock.get_inventory(obj.resource_id, obj.camp_id, create=True, user_id=ctx['user'].id)
        ref = f'ALLOC-{obj.id}'
        stock.apply_stock(src, 'out', obj.quantity, 'transfer', ref, ctx['user'].id)
        stock.apply_stock(dest, 'in', obj.quantity, 'transfer', ref, ctx['user'].id)
        obj.applied = True
        if obj.request_id:
            req = db.session.get(ResourceRequest, obj.request_id)
            got = (db.session.query(db.func.coalesce(db.func.sum(ResourceAllocation.quantity), 0))
                   .filter(ResourceAllocation.request_id == req.id, ResourceAllocation.status == 'delivered').scalar())
            req.status = 'fulfilled' if got >= req.quantity_needed else 'partially_fulfilled'


def _after_donation_transactions(obj, creating, ctx):
    d = db.session.get(Donation, obj.donation_id)
    if obj.status == 'completed' and d.status == 'pledged':
        d.status = 'received'


def _after_incidents(obj, creating, ctx):
    if creating and obj.severity == 'critical':
        notify.notify_roles(['dma', 'admin', 'super_admin'], f'Critical incident: {obj.title}',
                            f'{obj.affected_people} people affected', 'danger', f'/m/incidents/{obj.id}')


def _after_flood_alerts(obj, creating, ctx):
    if creating and obj.flood_level in ('high', 'very_high', 'exceptional') and obj.is_active:
        notify.notify_roles(['dma', 'admin', 'super_admin', 'rescue_team', 'ngo'], f'Flood alert: {obj.title}',
                            f'Level: {obj.flood_level} (source: {obj.source_name})', 'danger', '/map')


def _after_weather_alerts(obj, creating, ctx):
    if creating and obj.severity in ('high', 'critical') and obj.is_active:
        notify.notify_roles(['dma', 'admin', 'super_admin', 'rescue_team'], f'Weather alert: {obj.title}',
                            f'Severity: {obj.severity} (source: {obj.source_name})', 'warning', '/map')


def _after_users(obj, creating, ctx):
    role = ctx.get('role')
    if not role:
        return
    for ur in list(obj.user_roles):
        if ur.role_id != role.id:
            db.session.delete(ur)
    if not any(ur.role_id == role.id for ur in obj.user_roles):
        db.session.add(UserRole(user_id=obj.id, role_id=role.id, assigned_by_id=ctx['user'].id))


def after_delete(slug, obj):
    if slug == 'camp_residents':
        stock.recompute_camp(obj.camp_id)
