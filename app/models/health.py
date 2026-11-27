from .base import *


class Hospital(Tracked):
    __tablename__ = 'hospitals'
    name = Str(160, nullable=False)
    district_id = FK('districts', False)
    address = Str(255)
    phone = Str(30)
    emergency_phone = Str(30)
    latitude = Flt()
    longitude = Flt()
    total_beds = Int(default=0, nullable=False)
    available_beds = Int(default=0, nullable=False)    # manually updated, see updated_at
    has_icu = Bool(False)
    has_trauma_unit = Bool(False)
    status = Ch(['operational', 'limited', 'closed'])


class MedicalFacility(Tracked):
    __tablename__ = 'medical_facilities'
    name = Str(160, nullable=False)
    facility_type = Ch(['bhu', 'rhc', 'dispensary', 'mobile_clinic', 'field_hospital', 'pharmacy'])
    hospital_id = FK('hospitals')
    camp_id = FK('relief_camps')
    district_id = FK('districts', False)
    latitude = Flt()
    longitude = Flt()
    phone = Str(30)
    staff_count = Int(default=0, nullable=False)
    status = Ch(['operational', 'limited', 'closed'])


class Ambulance(Tracked):
    __tablename__ = 'ambulances'
    __label__ = '{plate_no}'
    plate_no = Str(20, unique=True, nullable=False)
    hospital_id = FK('hospitals')
    district_id = FK('districts')
    driver_name = Str(120)
    phone = Str(30)
    equipment_level = Ch(['basic', 'advanced'])
    status = Ch(['available', 'dispatched', 'maintenance', 'offline'], index=True)
    last_latitude = Flt()      # manually reported (NOT live GPS)
    last_longitude = Flt()
    last_location_at = Dt()


class Vehicle(Tracked):
    __tablename__ = 'vehicles'
    __label__ = '{plate_no}'
    plate_no = Str(20, unique=True, nullable=False)
    vehicle_type = Ch(['truck', 'boat', 'pickup', 'van', 'helicopter', 'tractor', 'bus'])
    capacity = Int(default=0, nullable=False)
    organization_id = FK('organizations')
    team_id = FK('rescue_teams')
    district_id = FK('districts')
    driver_name = Str(120)
    phone = Str(30)
    status = Ch(['available', 'in_use', 'maintenance', 'offline'], index=True)


class MedicalAssistance(Tracked):
    __tablename__ = 'medical_assistances'
    __label__ = '{patient_name}'
    camp_id = FK('relief_camps')
    resident_id = FK('camp_residents')
    facility_id = FK('medical_facilities')
    hospital_id = FK('hospitals')
    patient_name = Str(120, nullable=False)
    age = Int()
    medical_condition = Str(200, nullable=False)
    treatment = Str(255)
    severity = Ch(SEV, 'moderate')
    status = Ch(['registered', 'under_treatment', 'referred', 'recovered', 'closed'], index=True)
    assistance_date = Dat(default=today, nullable=False)
