"""Module registry: one entry per database table. Drives CRUD pages, RBAC permissions and the sidebar."""
from .models import *
from .models import all_models

GROUPS = ['Operations', 'Relief Camps', 'Resources', 'Medical & Transport', 'Funding', 'People & Tasks',
          'Organizations', 'Alerts & Communication', 'Geography & Reference', 'Administration']

REGISTRY = {}
TABLE2MODEL = {m.__tablename__: m for m in all_models()}


def R(slug, model, title, group, icon, cols, search=(), filters=(), **kw):
    REGISTRY[slug] = dict(slug=slug, model=model, title=title, group=group, icon=icon, cols=list(cols),
                          search=list(search), filters=list(filters), children=kw.pop('children', []),
                          readonly=kw.pop('readonly', False), immutable=kw.pop('immutable', False),
                          virtual=kw.pop('virtual', []), hide=kw.pop('hide', []), **kw)


# ---- Operations
R('disasters', Disaster, 'Disasters', 'Operations', 'cloud-lightning-rain',
  ['title', 'disaster_type_id', 'severity', 'status', 'start_date', 'estimated_affected'],
  ['title', 'official_reference'], ['disaster_type_id', 'severity', 'status'],
  children=[('incidents', 'disaster_id'), ('affected_areas', 'disaster_id')])
R('incidents', Incident, 'Flood Incidents', 'Operations', 'exclamation-triangle',
  ['title', 'incident_type_id', 'district_id', 'severity', 'status', 'affected_people', 'people_rescued', 'reported_at'],
  ['title', 'description'], ['district_id', 'incident_type_id', 'severity', 'status'],
  children=[('rescue_operations', 'incident_id'), ('emergency_requests', 'incident_id'), ('tasks', 'incident_id')])
R('incident_images', IncidentImage, 'Incident Images', 'Operations', 'images',
  ['file_name', 'incident_id', 'caption', 'created_at'], ['file_name', 'caption'], ['incident_id'], readonly=True)
R('emergency_requests', EmergencyRequest, 'Emergency SOS Requests', 'Operations', 'broadcast',
  ['tracking_code', 'requester_name', 'category_id', 'district_id', 'people_count', 'priority', 'status', 'created_at'],
  ['tracking_code', 'requester_name', 'phone', 'address', 'description'],
  ['district_id', 'category_id', 'priority', 'status'], children=[('request_updates', 'request_id')])
R('request_updates', RequestUpdate, 'Request Updates', 'Operations', 'clock-history',
  ['request_id', 'status', 'note', 'updated_by_id', 'created_at'], ['note'], ['status'], readonly=True)
R('request_categories', RequestCategory, 'Request Categories', 'Geography & Reference', 'tags',
  ['name', 'code', 'priority_weight'], ['name'])
R('affected_areas', AffectedArea, 'Affected Areas', 'Operations', 'geo',
  ['district_id', 'village_id', 'disaster_id', 'population_affected', 'households_affected', 'houses_damaged', 'status'],
  [], ['district_id', 'disaster_id', 'status'])
R('affected_households', AffectedHousehold, 'Affected Population', 'Operations', 'people',
  ['head_name', 'family_size', 'district_id', 'village_id', 'status', 'camp_id'],
  ['head_name', 'phone', 'needs'], ['district_id', 'status'])
R('rescue_teams', RescueTeam, 'Rescue Teams', 'Operations', 'life-preserver',
  ['name', 'code', 'team_type', 'district_id', 'status', 'last_location_at'],
  ['name', 'code'], ['team_type', 'status', 'district_id'], children=[('team_members', 'team_id')])
R('team_members', TeamMember, 'Team Members', 'Operations', 'person-badge',
  ['name', 'team_id', 'role', 'phone', 'is_leader'], ['name', 'phone'], ['team_id'])
R('rescue_operations', RescueOperation, 'Rescue Operations', 'Operations', 'shield-check',
  ['name', 'district_id', 'status', 'priority', 'people_targeted', 'people_rescued', 'started_at'],
  ['name', 'description'], ['district_id', 'status', 'priority'], children=[('rescue_assignments', 'operation_id')])
R('rescue_assignments', RescueAssignment, 'Rescue Assignments', 'Operations', 'diagram-3',
  ['operation_id', 'team_id', 'request_id', 'status', 'people_rescued', 'assigned_at'], ['notes'],
  ['team_id', 'operation_id', 'status'])
R('evacuation_plans', EvacuationPlan, 'Evacuation Plans', 'Operations', 'signpost-split',
  ['title', 'district_id', 'status', 'people_to_evacuate', 'people_evacuated', 'destination_camp_id'],
  ['title', 'description'], ['district_id', 'status'], children=[('evacuation_routes', 'plan_id')])
R('evacuation_routes', EvacuationRoute, 'Evacuation Routes', 'Operations', 'sign-turn-right',
  ['name', 'plan_id', 'distance_km', 'estimated_minutes', 'status'], ['name'], ['plan_id', 'status'])

# ---- Relief camps
R('relief_camps', ReliefCamp, 'Relief Camps', 'Relief Camps', 'house-heart',
  ['name', 'code', 'district_id', 'capacity', 'current_occupancy', 'status', 'manager_name'],
  ['name', 'code', 'manager_name'], ['district_id', 'status'],
  children=[('camp_facilities', 'camp_id'), ('camp_residents', 'camp_id'), ('inventories', 'camp_id'),
            ('camp_capacity_histories', 'camp_id'), ('resource_requests', 'camp_id')])
R('camp_facilities', CampFacility, 'Camp Facilities', 'Relief Camps', 'building-gear',
  ['camp_id', 'facility_type', 'quantity', 'facility_condition'], ['notes'], ['camp_id', 'facility_type', 'facility_condition'])
R('camp_residents', CampResident, 'Camp Residents', 'Relief Camps', 'person-lines-fill',
  ['full_name', 'camp_id', 'persons', 'gender', 'check_in', 'status'], ['full_name', 'phone'], ['camp_id', 'status'])
R('camp_capacity_histories', CampCapacityHistory, 'Capacity Monitoring', 'Relief Camps', 'graph-up',
  ['camp_id', 'recorded_at', 'capacity', 'occupancy', 'note'], ['note'], ['camp_id'])

# ---- Resources
R('resource_categories', ResourceCategory, 'Resource Categories', 'Resources', 'collection',
  ['name', 'kind', 'description'], ['name'], ['kind'])
R('resources', Resource, 'Relief Resources', 'Resources', 'box-seam',
  ['name', 'category_id', 'unit', 'sku', 'perishable'], ['name', 'sku'], ['category_id'])
R('inventories', Inventory, 'Inventory / Stock', 'Resources', 'boxes',
  ['resource_id', 'camp_id', 'warehouse_name', 'quantity', 'reorder_level', 'updated_at'],
  ['warehouse_name'], ['resource_id', 'camp_id'])
R('stock_transactions', StockTransaction, 'Stock Transactions', 'Resources', 'arrow-left-right',
  ['inventory_id', 'txn_type', 'quantity', 'reason', 'reference', 'txn_date'], ['reference', 'notes'],
  ['txn_type', 'reason', 'inventory_id'], immutable=True)
R('resource_requests', ResourceRequest, 'Resource Requests', 'Resources', 'cart-plus',
  ['camp_id', 'resource_id', 'quantity_needed', 'urgency', 'status', 'needed_by'], ['notes'],
  ['camp_id', 'resource_id', 'urgency', 'status'])
R('resource_allocations', ResourceAllocation, 'Resource Allocation', 'Resources', 'truck',
  ['resource_id', 'source_inventory_id', 'camp_id', 'quantity', 'status', 'applied'], ['notes'],
  ['camp_id', 'resource_id', 'status'])
R('distribution_records', DistributionRecord, 'Food & Water Distribution', 'Resources', 'basket',
  ['resource_id', 'camp_id', 'village_id', 'quantity', 'beneficiaries', 'distribution_date'],
  ['distributed_by', 'notes'], ['camp_id', 'resource_id'], immutable=True)

# ---- Medical & transport
R('hospitals', Hospital, 'Hospitals', 'Medical & Transport', 'hospital',
  ['name', 'district_id', 'total_beds', 'available_beds', 'has_icu', 'status', 'updated_at'],
  ['name', 'address', 'phone'], ['district_id', 'status'], children=[('ambulances', 'hospital_id')])
R('medical_facilities', MedicalFacility, 'Medical Facilities', 'Medical & Transport', 'bandaid',
  ['name', 'facility_type', 'district_id', 'camp_id', 'staff_count', 'status'], ['name'],
  ['facility_type', 'district_id', 'status'])
R('ambulances', Ambulance, 'Ambulances', 'Medical & Transport', 'truck-front',
  ['plate_no', 'hospital_id', 'district_id', 'driver_name', 'equipment_level', 'status'],
  ['plate_no', 'driver_name'], ['status', 'district_id'])
R('vehicles', Vehicle, 'Vehicles & Transport', 'Medical & Transport', 'bus-front',
  ['plate_no', 'vehicle_type', 'capacity', 'team_id', 'district_id', 'status'], ['plate_no', 'driver_name'],
  ['vehicle_type', 'status', 'district_id'])
R('medical_assistances', MedicalAssistance, 'Medical Assistance', 'Medical & Transport', 'heart-pulse',
  ['patient_name', 'camp_id', 'medical_condition', 'severity', 'status', 'assistance_date'],
  ['patient_name', 'medical_condition'], ['camp_id', 'severity', 'status'])

# ---- Funding
R('donors', Donor, 'Donors', 'Funding', 'person-heart',
  ['name', 'donor_type', 'country', 'is_anonymous'], ['name', 'email'], ['donor_type'], children=[('donations', 'donor_id')])
R('donation_campaigns', DonationCampaign, 'Fundraising Campaigns', 'Funding', 'megaphone',
  ['title', 'disaster_id', 'goal_amount', 'status', 'start_date', 'end_date'], ['title'], ['status'],
  children=[('donations', 'campaign_id')])
R('donations', Donation, 'Donations', 'Funding', 'cash-coin',
  ['donor_id', 'campaign_id', 'donation_type', 'amount', 'status', 'donated_on'], ['message'],
  ['campaign_id', 'donation_type', 'status'], children=[('donation_transactions', 'donation_id')])
R('donation_transactions', DonationTransaction, 'Donation Transactions', 'Funding', 'receipt',
  ['donation_id', 'amount', 'method', 'reference_no', 'status', 'transaction_date'], ['reference_no', 'receipt_no'],
  ['method', 'status'])

# ---- People & tasks
R('volunteers', Volunteer, 'Volunteers', 'People & Tasks', 'people-fill',
  ['full_name', 'phone', 'district_id', 'availability', 'status', 'registered_on'], ['full_name', 'phone', 'email'],
  ['district_id', 'availability', 'status'], children=[('volunteer_skills', 'volunteer_id'), ('volunteer_assignments', 'volunteer_id')])
R('volunteer_skills', VolunteerSkill, 'Volunteer Skills', 'People & Tasks', 'tools',
  ['volunteer_id', 'skill', 'level', 'certified'], [], ['skill', 'level'])
R('volunteer_assignments', VolunteerAssignment, 'Volunteer Assignments', 'People & Tasks', 'clipboard-check',
  ['volunteer_id', 'task_id', 'camp_id', 'role', 'status', 'hours_logged'], ['role'], ['status', 'camp_id'])
R('tasks', Task, 'Tasks', 'People & Tasks', 'kanban',
  ['title', 'status', 'priority', 'due_date', 'district_id', 'camp_id'], ['title', 'description'],
  ['status', 'priority', 'district_id'], children=[('task_assignments', 'task_id'), ('task_comments', 'task_id')])
R('task_assignments', TaskAssignment, 'Task Assignments', 'People & Tasks', 'person-check',
  ['task_id', 'user_id', 'volunteer_id', 'team_id', 'assigned_at'], ['note'], ['task_id'])
R('task_comments', TaskComment, 'Task Comments', 'People & Tasks', 'chat-left-text',
  ['task_id', 'body', 'created_by_id', 'created_at'], ['body'], ['task_id'])

# ---- Organizations
R('organizations', Organization, 'NGOs & Organizations', 'Organizations', 'building',
  ['name', 'org_type', 'district_id', 'phone', 'is_verified'], ['name', 'email', 'registration_no'],
  ['org_type', 'district_id', 'is_verified'], children=[('departments', 'organization_id'), ('organization_members', 'organization_id')])
R('departments', Department, 'Departments', 'Organizations', 'diagram-2',
  ['name', 'organization_id', 'head_name'], ['name', 'head_name'], ['organization_id'])
R('organization_members', OrganizationMember, 'Organization Members', 'Organizations', 'person-workspace',
  ['organization_id', 'user_id', 'department_id', 'position', 'joined_on'], ['position'], ['organization_id'])
R('emergency_contacts', EmergencyContact, 'Emergency Contacts', 'Organizations', 'telephone',
  ['name', 'category', 'phone', 'district_id', 'is_national', 'data_source'], ['name', 'phone', 'designation'],
  ['category', 'district_id'])

# ---- Alerts & communication
R('weather_alerts', WeatherAlert, 'Weather Alerts', 'Alerts & Communication', 'cloud-rain-heavy',
  ['title', 'district_id', 'alert_type', 'severity', 'source_name', 'valid_until', 'is_active'], ['title', 'source_name', 'message'],
  ['district_id', 'alert_type', 'severity', 'is_active'])
R('flood_alerts', FloodAlert, 'Flood Alerts', 'Alerts & Communication', 'water',
  ['title', 'district_id', 'river', 'flood_level', 'source_name', 'valid_until', 'is_active'], ['title', 'river', 'station', 'message'],
  ['district_id', 'flood_level', 'is_active'])
R('notifications', Notification, 'Notifications (all)', 'Alerts & Communication', 'bell',
  ['user_id', 'title', 'level', 'is_read', 'created_at'], ['title'], ['level', 'is_read'], readonly=True)
R('communications', Communication, 'Communication History', 'Alerts & Communication', 'chat-dots',
  ['subject', 'channel', 'direction', 'recipient_name', 'status', 'sent_at'], ['subject', 'message', 'recipient_name'],
  ['channel', 'direction', 'status'])
R('complaints', Complaint, 'Complaints', 'Alerts & Communication', 'flag',
  ['subject', 'category', 'camp_id', 'priority', 'status', 'created_at'], ['subject', 'description'],
  ['category', 'priority', 'status'])
R('feedbacks', Feedback, 'Feedback', 'Alerts & Communication', 'star',
  ['category', 'camp_id', 'rating', 'comment', 'created_at'], ['comment'], ['category', 'rating'])
R('risk_assessments', RiskAssessment, 'Risk Assessments', 'Alerts & Communication', 'shield-exclamation',
  ['district_id', 'method', 'risk_score', 'risk_level', 'incident_count', 'confidence', 'assessed_on'], ['notes', 'data_basis'],
  ['district_id', 'risk_level', 'method', 'confidence'])

# ---- Geography & reference
R('provinces', Province, 'Provinces', 'Geography & Reference', 'map', ['name', 'code'], ['name'])
R('districts', District, 'Districts', 'Geography & Reference', 'pin-map',
  ['name', 'province_id', 'latitude', 'longitude', 'population'], ['name'], ['province_id'])
R('cities', City, 'Cities', 'Geography & Reference', 'buildings', ['name', 'district_id', 'population'], ['name'], ['district_id'])
R('villages', Village, 'Villages', 'Geography & Reference', 'signpost',
  ['name', 'district_id', 'population', 'latitude', 'longitude'], ['name'], ['district_id'])
R('locations', Location, 'Locations', 'Geography & Reference', 'geo-alt',
  ['name', 'location_type', 'district_id', 'latitude', 'longitude'], ['name', 'address'], ['location_type', 'district_id'])
R('disaster_types', DisasterType, 'Disaster Types', 'Geography & Reference', 'tag',
  ['name', 'code', 'is_flood', 'color'], ['name'])

# ---- Administration
R('users', User, 'Users', 'Administration', 'person-gear',
  ['full_name', 'email', 'organization_id', 'active', 'last_login'], ['full_name', 'email', 'phone'], ['active', 'organization_id'],
  virtual=[dict(name='role_code', label='Role', type='select', required=True),
           dict(name='password', label='Password', type='password', required_on_create=True,
                help='Min 8 chars, upper + lower case + digit. Leave blank on edit to keep current.')])
R('roles', Role, 'Roles', 'Administration', 'person-vcard', ['name', 'code', 'is_system'], ['name', 'code'],
  children=[('role_permissions', 'role_id')])
R('permissions', Permission, 'Permissions', 'Administration', 'key', ['code', 'module', 'action'], ['code'], ['module', 'action'])
R('user_roles', UserRole, 'User Roles', 'Administration', 'person-lock', ['user_id', 'role_id', 'created_at'], [], ['role_id'])
R('role_permissions', RolePermission, 'Role Permissions', 'Administration', 'shield-lock',
  ['role_id', 'permission_id'], [], ['role_id'])
R('reports', Report, 'Generated Reports', 'Administration', 'file-earmark-pdf',
  ['title', 'report_type', 'data_scope', 'created_by_id', 'created_at'], ['title'], ['report_type'], readonly=True)
R('audit_logs', AuditLog, 'Audit Logs', 'Administration', 'journal-text',
  ['created_at', 'user_id', 'action', 'entity', 'entity_id', 'ip_address'], ['action', 'entity', 'details', 'ip_address'],
  ['action', 'entity', 'user_id'], readonly=True)
R('system_settings', SystemSetting, 'System Settings', 'Administration', 'gear',
  ['setting_key', 'setting_value', 'description'], ['setting_key'])
R('attachments', Attachment, 'Uploaded Files', 'Administration', 'paperclip',
  ['original_name', 'entity_slug', 'entity_id', 'mime_type', 'size_bytes', 'uploaded_by_id'], ['original_name'], ['entity_slug'],
  readonly=True)

for _c in REGISTRY.values():     # every model must be registered
    _c['model'].__slug__ = _c['slug']
_missing = set(TABLE2MODEL) - {c['model'].__tablename__ for c in REGISTRY.values()}
assert not _missing, f'Not registered: {_missing}'
