from .base import *


class DisasterType(Base):
    __tablename__ = 'disaster_types'
    name = Str(80, unique=True, nullable=False)
    code = Str(20, unique=True, nullable=False)
    is_flood = Bool(False)
    color = Str(20)
    description = Str(255)


class Disaster(Tracked):
    __tablename__ = 'disasters'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    disaster_type_id = FK('disaster_types', False)
    province_id = FK('provinces')
    severity = Ch(SEV, 'high')
    status = Ch(['monitoring', 'active', 'recovering', 'closed'], 'active', index=True)
    start_date = Dat(nullable=False)
    end_date = Dat()
    estimated_affected = Int(default=0, nullable=False)
    official_reference = Str(150)
    description = Txt()


class Incident(Tracked):
    __tablename__ = 'incidents'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    disaster_id = FK('disasters')
    incident_type_id = FK('disaster_types', False)
    district_id = FK('districts', False)
    village_id = FK('villages')
    location_id = FK('locations')
    latitude = Flt()
    longitude = Flt()
    severity = Ch(SEV, 'moderate', index=True)
    status = Ch(['reported', 'active', 'contained', 'resolved'], index=True)
    reported_at = Dt(default=now, nullable=False, index=True)
    affected_people = Int(default=0, nullable=False)
    people_rescued = Int(default=0, nullable=False)
    injured = Int(default=0, nullable=False)
    fatalities = Int(default=0, nullable=False)
    water_level_m = Flt()   # only if reported by an official source; never estimated
    description = Txt()


class IncidentImage(Base):
    __tablename__ = 'incident_images'
    __label__ = '{file_name}'
    incident_id = FK('incidents', False)
    file_name = Str(200, nullable=False)
    stored_name = Str(80, nullable=False)
    caption = Str(255)
    uploaded_by_id = FK('users')
    incident = db.relationship('Incident', backref=db.backref('images', cascade='all, delete-orphan'))


class AffectedArea(Tracked):
    __tablename__ = 'affected_areas'
    __label__ = 'area {id}'
    disaster_id = FK('disasters')
    district_id = FK('districts', False)
    village_id = FK('villages')
    population_affected = Int(default=0, nullable=False)
    households_affected = Int(default=0, nullable=False)
    houses_damaged = Int(default=0, nullable=False)
    crop_area_ha = Flt()
    status = Ch(['assessing', 'affected', 'recovering', 'recovered'], 'affected')
    assessment_date = Dat()


class AffectedHousehold(Tracked):
    __tablename__ = 'affected_households'
    __label__ = '{head_name}'
    __staff_only__ = ('status', 'camp_id')
    head_name = Str(120, nullable=False)
    phone = Str(30)
    family_size = Int(default=1, nullable=False)
    disaster_id = FK('disasters')
    district_id = FK('districts', False)
    village_id = FK('villages')
    camp_id = FK('relief_camps')
    status = Ch(['affected', 'displaced', 'in_camp', 'rescued', 'returned'], index=True)
    latitude = Flt()
    longitude = Flt()
    needs = Txt()


class RequestCategory(Base):
    __tablename__ = 'request_categories'
    name = Str(80, unique=True, nullable=False)
    code = Str(20, unique=True)
    priority_weight = Int(default=1, nullable=False)
    description = Str(255)


class EmergencyRequest(Tracked):
    __tablename__ = 'emergency_requests'
    __label__ = '{tracking_code}'
    __hidden__ = ('tracking_code', 'resolved_at')
    __staff_only__ = ('priority', 'status', 'assigned_team_id', 'incident_id')
    tracking_code = Str(20, unique=True, nullable=False)
    category_id = FK('request_categories')
    requester_name = Str(120, nullable=False)
    phone = Str(30, nullable=False)
    people_count = Int(default=1, nullable=False)
    has_injured = Bool(False)
    needs_medical = Bool(False)
    district_id = FK('districts')
    address = Str(255)
    latitude = Flt()
    longitude = Flt()
    description = Txt()
    priority = Ch(PRIO, 'medium', index=True)
    status = Ch(['pending', 'acknowledged', 'assigned', 'in_progress', 'rescued', 'resolved',
                 'cancelled', 'false_alarm'], index=True)
    assigned_team_id = FK('rescue_teams')
    incident_id = FK('incidents')
    resolved_at = Dt()


class RequestUpdate(Base):
    __tablename__ = 'request_updates'
    __label__ = 'update {id}'
    request_id = FK('emergency_requests', False)
    status = Str(30, nullable=False)
    note = Str(500)
    updated_by_id = FK('users')
    request = db.relationship('EmergencyRequest', backref=db.backref('updates', cascade='all, delete-orphan',
                                                                      order_by='RequestUpdate.id'))
