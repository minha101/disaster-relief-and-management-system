from functools import wraps
from flask import abort
from flask_login import current_user
from ..extensions import db
from ..models import Role, Permission, RolePermission
from ..registry import REGISTRY

ACTIONS = ['view', 'create', 'edit', 'delete', 'all']
LEVELS = {
    'full': ['view', 'create', 'edit', 'delete', 'all'],
    'manage': ['view', 'create', 'edit', 'all'],
    'view': ['view', 'all'],
    'participate': ['view', 'create', 'all'],   # can read everything and add own entries
    'own': ['view', 'create', 'edit'],          # sees / edits only the records they created
    'none': [],
}
ADMIN_ONLY = {'users', 'roles', 'permissions', 'user_roles', 'role_permissions', 'audit_logs',
              'system_settings', 'notifications', 'attachments', 'reports'}
GEO = ['provinces', 'districts', 'cities', 'villages', 'locations', 'disaster_types', 'request_categories',
       'resource_categories', 'resources']
PUBLIC_INFO = ['relief_camps', 'camp_facilities', 'weather_alerts', 'flood_alerts', 'emergency_contacts',
               'evacuation_plans', 'evacuation_routes', 'hospitals', 'medical_facilities', 'disasters']


def G(level, *slugs):
    return {s: level for s in slugs}


SPECS = {
    'super_admin': ('Super Admin', 'Full control of the whole system', 'full', {}),
    'admin': ('Admin', 'Manages users and all operational data', 'full',
              G('view', 'roles', 'permissions', 'role_permissions', 'user_roles', 'audit_logs')),
    'dma': ('Disaster Management Authority', 'Coordinates the response across districts', 'manage',
            {**G('full', 'disasters', 'incidents', 'emergency_requests', 'affected_areas', 'affected_households',
                 'rescue_teams', 'team_members', 'rescue_operations', 'rescue_assignments', 'relief_camps',
                 'camp_facilities', 'camp_residents', 'evacuation_plans', 'evacuation_routes', 'weather_alerts',
                 'flood_alerts', 'risk_assessments', 'communications', 'tasks', 'emergency_contacts'),
             **G('view', 'users', 'audit_logs', 'reports'), 'reports': 'manage'}),
    'ngo': ('NGO / Relief Organization', 'Runs relief operations, stock and fundraising', 'view',
            {**G('manage', 'organizations', 'departments', 'organization_members', 'volunteers', 'volunteer_skills',
                 'volunteer_assignments', 'tasks', 'task_assignments', 'task_comments', 'inventories',
                 'stock_transactions', 'resource_requests', 'resource_allocations', 'distribution_records',
                 'donors', 'donations', 'donation_transactions', 'camp_residents', 'camp_facilities',
                 'medical_assistances', 'communications', 'complaints', 'affected_households', 'resources',
                 'vehicles', 'reports'),
             **G('full', 'donation_campaigns'), **G('view', 'incidents', 'emergency_requests', 'risk_assessments',
                                                    'rescue_teams', 'ambulances', 'feedbacks')}),
    'rescue_team': ('Rescue Team', 'Field rescue teams', 'none',
                    {**G('view', 'incidents', 'affected_areas', 'rescue_teams', 'ambulances', 'vehicles',
                         'risk_assessments', 'relief_camps', 'camp_residents', 'volunteers'),
                     **G('manage', 'emergency_requests', 'request_updates', 'rescue_operations',
                         'rescue_assignments', 'team_members', 'tasks', 'task_assignments', 'communications',
                         'medical_assistances'),
                     **G('participate', 'task_comments'), **G('own', 'complaints', 'feedbacks')}),
    'volunteer': ('Volunteer', 'Registered volunteers', 'none',
                  {**G('view', 'incidents', 'tasks', 'volunteer_assignments', 'rescue_teams', 'organizations'),
                   **G('participate', 'task_comments'), **G('own', 'volunteers', 'volunteer_skills', 'complaints',
                                                              'feedbacks')}),
    'donor': ('Donor', 'Donors and sponsors', 'none',
              {**G('view', 'donation_campaigns', 'distribution_records', 'resource_allocations', 'organizations'),
               **G('own', 'donors', 'donations', 'donation_transactions', 'feedbacks', 'complaints')}),
    'affected': ('Affected Person', 'Flood-affected individuals and families', 'none',
                 {**G('own', 'emergency_requests', 'affected_households', 'complaints', 'feedbacks')}),
}


def level_for(role_code, slug):
    name, desc, base, ov = SPECS[role_code]
    if slug in ov:
        return ov[slug]
    if role_code in ('super_admin', 'admin'):
        return base
    if slug in GEO or slug in PUBLIC_INFO:
        return 'view'
    if slug in ADMIN_ONLY:
        return 'none'
    return base


def sync_rbac():
    """Idempotent: creates missing permissions, roles and role-permission links."""
    perms = {p.code: p for p in Permission.query.all()}
    for slug, cfg in REGISTRY.items():
        for a in ACTIONS:
            code = f'{slug}.{a}'
            if code not in perms:
                perms[code] = Permission(code=code, module=slug, action=a, description=f'{a} - {cfg["title"]}')
                db.session.add(perms[code])
    roles = {r.code: r for r in Role.query.all()}
    for code, (name, desc, base, ov) in SPECS.items():
        if code not in roles:
            roles[code] = Role(code=code, name=name, description=desc, is_system=True)
            db.session.add(roles[code])
    db.session.flush()
    have = {(rp.role_id, rp.permission_id) for rp in RolePermission.query.all()}
    for code in SPECS:
        for slug in REGISTRY:
            for a in LEVELS[level_for(code, slug)]:
                key = (roles[code].id, perms[f'{slug}.{a}'].id)
                if key not in have:
                    db.session.add(RolePermission(role_id=key[0], permission_id=key[1]))
                    have.add(key)
    db.session.commit()


def perm_required(slug, action='view'):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                return current_user_unauthorized()
            if not current_user.can(slug, action):
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def current_user_unauthorized():
    from ..extensions import login_manager
    return login_manager.unauthorized()
