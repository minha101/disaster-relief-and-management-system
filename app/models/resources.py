from .base import *


class ResourceCategory(Base):
    __tablename__ = 'resource_categories'
    name = Str(80, unique=True, nullable=False)
    kind = Ch(['food', 'water', 'medical', 'shelter', 'clothing', 'hygiene', 'other'])
    description = Str(255)


class Resource(Base):
    __tablename__ = 'resources'
    name = Str(120, nullable=False)
    category_id = FK('resource_categories', False)
    unit = Str(20, nullable=False)       # standard units used by Smart Allocation: pack, litre, kit
    sku = Str(40, unique=True)
    perishable = Bool(False)
    description = Str(255)
    category = db.relationship('ResourceCategory', backref='resources')


class Inventory(Tracked):
    __tablename__ = 'inventories'
    __label__ = 'stock {id}'
    __hidden__ = ('quantity',)
    resource_id = FK('resources', False)
    camp_id = FK('relief_camps')
    warehouse_name = Str(120)           # used when camp_id is empty (central / district warehouse)
    quantity = Flt(default=0, nullable=False)
    reorder_level = Flt(default=0, nullable=False)
    last_counted_at = Dt()
    resource = db.relationship('Resource', backref='inventories')
    camp = db.relationship('ReliefCamp', backref='inventories')

    @property
    def label(self):
        place = self.camp.name if self.camp else (self.warehouse_name or 'Warehouse')
        return f'{self.resource.name} @ {place}' if self.resource else f'stock #{self.id}'


class StockTransaction(Tracked):
    __tablename__ = 'stock_transactions'
    __label__ = 'txn {id}'
    inventory_id = FK('inventories', False)
    txn_type = Ch(['in', 'out'])
    quantity = Flt(nullable=False)
    reason = Ch(['donation', 'purchase', 'transfer', 'distribution', 'adjustment', 'other'])
    reference = Str(80)
    txn_date = Dt(default=now, nullable=False, index=True)
    donation_id = FK('donations')
    notes = Str(255)
    inventory = db.relationship('Inventory', backref='transactions')


class ResourceRequest(Tracked):
    __tablename__ = 'resource_requests'
    __label__ = 'request {id}'
    camp_id = FK('relief_camps', False)
    resource_id = FK('resources', False)
    quantity_needed = Flt(nullable=False)
    urgency = Ch(SEV, 'moderate')
    status = Ch(['open', 'approved', 'partially_fulfilled', 'fulfilled', 'rejected'], index=True)
    needed_by = Dat()
    notes = Str(255)


class ResourceAllocation(Tracked):
    __tablename__ = 'resource_allocations'
    __label__ = 'allocation {id}'
    __hidden__ = ('applied',)
    request_id = FK('resource_requests')
    resource_id = FK('resources', False)
    source_inventory_id = FK('inventories')
    camp_id = FK('relief_camps', False)
    quantity = Flt(nullable=False)
    status = Ch(['proposed', 'approved', 'dispatched', 'delivered', 'cancelled'], index=True)
    vehicle_id = FK('vehicles')
    applied = Bool(False)
    notes = Str(255)


class DistributionRecord(Tracked):
    __tablename__ = 'distribution_records'
    __label__ = 'distribution {id}'
    camp_id = FK('relief_camps')
    village_id = FK('villages')
    resource_id = FK('resources', False)
    quantity = Flt(nullable=False)
    beneficiaries = Int(default=0, nullable=False)
    distribution_date = Dat(default=today, nullable=False)
    organization_id = FK('organizations')
    distributed_by = Str(120)
    notes = Str(255)
