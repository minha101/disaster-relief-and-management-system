from ..extensions import db
from ..models import SystemSetting

DEFAULTS = {
    'site_name': ('Flood & Disaster Relief Coordination System', 'Display name'),
    'allow_self_registration': ('true', 'Allow volunteers, donors and affected persons to self-register'),
    'sos_rate_limit_per_hour': ('5', 'Max public SOS submissions per IP per hour'),
    'need_food_per_person_day': ('1', 'Planning assumption: ration packs per person per day'),
    'need_water_per_person_day': ('3', 'Planning assumption: litres of drinking water per person per day'),
    'need_medical_per_person_day': ('0.05', 'Planning assumption: medical kits per person per day'),
    'planning_days': ('3', 'Days of supply a camp should hold'),
    'critical_days': ('1', 'Days of supply below which a camp is flagged CRITICAL'),
}


def ensure_defaults():
    have = {s.setting_key for s in SystemSetting.query.all()}
    for k, (v, d) in DEFAULTS.items():
        if k not in have:
            db.session.add(SystemSetting(setting_key=k, setting_value=v, description=d))
    db.session.commit()


def get_setting(key, default=None):
    s = SystemSetting.query.filter_by(setting_key=key).first()
    if s and s.setting_value not in (None, ''):
        return s.setting_value
    return DEFAULTS.get(key, (default,))[0] if default is None else default


def get_float(key, default=0.0):
    try:
        return float(get_setting(key, default))
    except (TypeError, ValueError):
        return float(default)
