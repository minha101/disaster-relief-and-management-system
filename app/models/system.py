from .base import *


class WeatherAlert(Tracked):
    __tablename__ = 'weather_alerts'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    district_id = FK('districts')
    alert_type = Ch(['heavy_rain', 'storm', 'heatwave', 'cloudburst', 'landslide', 'glof', 'other'])
    severity = Ch(SEV, 'moderate', index=True)
    source_name = Str(150, nullable=False)      # e.g. issuing agency; entered manually, never auto-generated
    source_reference = Str(200)
    issued_at = Dt(default=now, nullable=False)
    valid_from = Dt()
    valid_until = Dt()
    is_active = Bool(True)
    message = Txt()


class FloodAlert(Tracked):
    __tablename__ = 'flood_alerts'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    district_id = FK('districts')
    river = Str(100)
    station = Str(100)
    flood_level = Ch(['normal', 'low', 'medium', 'high', 'very_high', 'exceptional'], 'medium', index=True)
    discharge_cusecs = Flt()       # only from an official bulletin; never estimated
    source_name = Str(150, nullable=False)
    source_reference = Str(200)
    issued_at = Dt(default=now, nullable=False)
    valid_until = Dt()
    is_active = Bool(True)
    message = Txt()


class Notification(Base):
    __tablename__ = 'notifications'
    __label__ = '{title}'
    user_id = FK('users', False)
    title = Str(200, nullable=False)
    message = Str(500)
    level = Ch(['info', 'success', 'warning', 'danger'])
    link = Str(255)
    is_read = Bool(False)
    read_at = Dt()


class Communication(Tracked):
    """Log of communications. The system records them; it does not send SMS/calls itself."""
    __tablename__ = 'communications'
    __label__ = '{subject}'
    channel = Ch(['sms', 'call', 'email', 'radio', 'in_app', 'meeting'])
    direction = Ch(['outbound', 'inbound'])
    subject = Str(200, nullable=False)
    message = Txt()
    recipient_name = Str(120)
    recipient_contact = Str(120)
    incident_id = FK('incidents')
    request_id = FK('emergency_requests')
    status = Ch(['logged', 'sent', 'delivered', 'failed'])
    sent_at = Dt(default=now)


class Complaint(Tracked):
    __tablename__ = 'complaints'
    __label__ = '{subject}'
    __hidden__ = ('resolved_at',)
    __staff_only__ = ('status', 'response', 'priority')
    subject = Str(200, nullable=False)
    category = Ch(['aid_delay', 'camp_conditions', 'misconduct', 'missing_supplies', 'other'])
    camp_id = FK('relief_camps')
    contact_phone = Str(30)
    description = Txt(nullable=False)
    priority = Ch(PRIO, 'medium')
    status = Ch(['open', 'under_review', 'resolved', 'rejected'], index=True)
    response = Txt()
    resolved_at = Dt()


class Feedback(Tracked):
    __tablename__ = 'feedbacks'
    __label__ = 'feedback {id}'
    category = Ch(['service', 'camp', 'platform', 'distribution'])
    camp_id = FK('relief_camps')
    rating = Int(nullable=False)
    comment = Txt()


class EmergencyContact(Tracked):
    __tablename__ = 'emergency_contacts'
    name = Str(150, nullable=False)
    category = Ch(['rescue', 'police', 'disaster_authority', 'hospital', 'utility', 'ngo', 'other'])
    organization_id = FK('organizations')
    designation = Str(100)
    phone = Str(30, nullable=False)
    alt_phone = Str(30)
    email = Str(150)
    district_id = FK('districts')
    is_national = Bool(False)
    notes = Str(255)


class Report(Tracked):
    __tablename__ = 'reports'
    __label__ = '{title}'
    title = Str(200, nullable=False)
    report_type = Ch(['summary', 'camps', 'inventory', 'donations', 'analytics', 'risk', 'module_export'])
    data_scope = Str(20)
    parameters = Txt()
    file_name = Str(200)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    __label__ = '{action} {entity}'
    __table_args__ = (db.Index('ix_audit_entity', 'entity', 'entity_id'),)
    user_id = FK('users')
    action = Str(40, nullable=False, index=True)
    entity = Str(60)
    entity_id = Int()
    details = Txt()
    ip_address = Str(45)
    user_agent = Str(255)


class SystemSetting(Base):
    __tablename__ = 'system_settings'
    __label__ = '{setting_key}'
    setting_key = Str(80, unique=True, nullable=False)
    setting_value = Str(500)
    description = Str(255)


class Attachment(Base):
    __tablename__ = 'attachments'
    __label__ = '{original_name}'
    __table_args__ = (db.Index('ix_attach_entity', 'entity_slug', 'entity_id'),)
    entity_slug = Str(60, nullable=False)
    entity_id = Int(nullable=False)
    original_name = Str(200, nullable=False)
    stored_name = Str(80, unique=True, nullable=False)
    mime_type = Str(100)
    size_bytes = Int()
    description = Str(255)
    uploaded_by_id = FK('users')


class RiskAssessment(Tracked):
    __tablename__ = 'risk_assessments'
    __label__ = 'risk {id}'
    district_id = FK('districts', False)
    disaster_type_id = FK('disaster_types')
    method = Ch(['heuristic_v1', 'manual'])
    risk_score = Flt(nullable=False)
    risk_level = Ch(['low', 'moderate', 'high', 'very_high'], index=True)
    incident_count = Int(default=0, nullable=False)
    confidence = Ch(['low', 'medium', 'high'])
    data_basis = Str(255)
    assessed_on = Dat(default=today, nullable=False)
    is_validated_model = Bool(False)     # True only if a statistically validated model produced it
    notes = Txt()
