from .base import *


class RescueTeam(Tracked):
    __tablename__ = 'rescue_teams'
    name = Str(120, nullable=False)
    code = Str(30, unique=True, nullable=False)
    team_type = Ch(['boat', 'medical', 'search_rescue', 'logistics', 'general'])
    organization_id = FK('organizations')
    district_id = FK('districts')
    lead_user_id = FK('users')
    phone = Str(30)
    status = Ch(['available', 'deployed', 'standby', 'offline'], index=True)
    base_latitude = Flt()
    base_longitude = Flt()
    last_latitude = Flt()      # manually reported position (NOT live GPS)
    last_longitude = Flt()
    last_location_at = Dt()
    equipment = Txt()


class TeamMember(Base):
    __tablename__ = 'team_members'
    team_id = FK('rescue_teams', False)
    user_id = FK('users')
    volunteer_id = FK('volunteers')
    name = Str(120, nullable=False)
    role = Str(80)
    phone = Str(30)
    is_leader = Bool(False)
    team = db.relationship('RescueTeam', backref=db.backref('members', cascade='all, delete-orphan'))


class RescueOperation(Tracked):
    __tablename__ = 'rescue_operations'
    name = Str(160, nullable=False)
    disaster_id = FK('disasters')
    incident_id = FK('incidents')
    district_id = FK('districts')
    commander_user_id = FK('users')
    status = Ch(['planned', 'active', 'paused', 'completed', 'aborted'], 'planned', index=True)
    priority = Ch(PRIO, 'high')
    started_at = Dt()
    ended_at = Dt()
    people_targeted = Int(default=0, nullable=False)
    people_rescued = Int(default=0, nullable=False)
    description = Txt()


class RescueAssignment(Tracked):
    __tablename__ = 'rescue_assignments'
    __label__ = 'assignment {id}'
    operation_id = FK('rescue_operations', False)
    team_id = FK('rescue_teams', False)
    request_id = FK('emergency_requests')
    vehicle_id = FK('vehicles')
    status = Ch(['assigned', 'en_route', 'on_site', 'completed', 'cancelled'], index=True)
    assigned_at = Dt(default=now, nullable=False)
    completed_at = Dt()
    people_rescued = Int(default=0, nullable=False)
    notes = Txt()
    operation = db.relationship('RescueOperation', backref=db.backref('assignments', cascade='all, delete-orphan'))


class ReliefCamp(Tracked):
    __tablename__ = 'relief_camps'
    __hidden__ = ('current_occupancy',)
    name = Str(160, nullable=False)
    code = Str(30, unique=True, nullable=False)
    district_id = FK('districts', False)
    village_id = FK('villages')
    organization_id = FK('organizations')
    latitude = Flt()
    longitude = Flt()
    address = Str(255)
    capacity = Int(nullable=False)
    current_occupancy = Int(default=0, nullable=False)
    status = Ch(['planned', 'open', 'full', 'closed'], 'open', index=True)
    manager_name = Str(120)
    phone = Str(30)
    opened_on = Dat()

    @property
    def occupancy_pct(self):
        return round(100.0 * (self.current_occupancy or 0) / self.capacity, 1) if self.capacity else 0.0


class CampFacility(Base):
    __tablename__ = 'camp_facilities'
    __label__ = '{facility_type}'
    camp_id = FK('relief_camps', False)
    facility_type = Ch(['toilets', 'clean_water', 'kitchen', 'medical_post', 'electricity', 'school_tent',
                        'women_space', 'security'])
    quantity = Int(default=1, nullable=False)
    facility_condition = Ch(['good', 'fair', 'poor', 'none'])
    notes = Str(255)
    camp = db.relationship('ReliefCamp', backref=db.backref('facilities', cascade='all, delete-orphan'))


class CampResident(Tracked):
    __tablename__ = 'camp_residents'
    __label__ = '{full_name}'
    camp_id = FK('relief_camps', False)
    household_id = FK('affected_households')
    full_name = Str(120, nullable=False)
    persons = Int(default=1, nullable=False)     # household members covered by this registration
    age = Int()
    gender = Ch(['male', 'female', 'other'])
    phone = Str(30)
    special_needs = Str(255)
    check_in = Dat(default=today, nullable=False)
    check_out = Dat()
    status = Ch(['resident', 'left', 'transferred'], index=True)


class CampCapacityHistory(Base):
    __tablename__ = 'camp_capacity_histories'
    __label__ = 'snapshot {id}'
    camp_id = FK('relief_camps', False)
    recorded_at = Dt(default=now, nullable=False)
    capacity = Int(nullable=False)
    occupancy = Int(nullable=False)
    note = Str(255)
    camp = db.relationship('ReliefCamp', backref=db.backref('history', cascade='all, delete-orphan'))


class EvacuationPlan(Tracked):
    __tablename__ = 'evacuation_plans'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    disaster_id = FK('disasters')
    district_id = FK('districts', False)
    village_id = FK('villages')
    destination_camp_id = FK('relief_camps')
    status = Ch(['draft', 'approved', 'active', 'completed', 'cancelled'], index=True)
    trigger_condition = Str(255)
    people_to_evacuate = Int(default=0, nullable=False)
    people_evacuated = Int(default=0, nullable=False)
    start_time = Dt()
    end_time = Dt()
    description = Txt()


class EvacuationRoute(Tracked):
    __tablename__ = 'evacuation_routes'
    plan_id = FK('evacuation_plans', False)
    name = Str(160, nullable=False)
    start_latitude = Flt(nullable=False)
    start_longitude = Flt(nullable=False)
    end_latitude = Flt(nullable=False)
    end_longitude = Flt(nullable=False)
    distance_km = Flt()
    estimated_minutes = Int()
    status = Ch(['open', 'blocked', 'flooded', 'unknown'])
    notes = Str(255)
    plan = db.relationship('EvacuationPlan', backref=db.backref('routes', cascade='all, delete-orphan'))
