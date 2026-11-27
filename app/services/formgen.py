"""Generic form handling driven by SQLAlchemy column metadata."""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from ..extensions import db
from ..registry import TABLE2MODEL

EXCLUDE = {'id', 'created_at', 'updated_at', 'created_by_id', 'verified_by_id', 'verified_at', 'data_source',
           'password_hash'}
LAT = (23.0, 38.0)
LNG = (60.0, 78.0)


def fk_target(col):
    fks = list(col.foreign_keys)
    return TABLE2MODEL.get(fks[0].column.table.name) if fks else None


def choices_of(col):
    return (col.info or {}).get('choices')


def is_required(col):
    return (not col.nullable) and col.default is None and col.server_default is None and not col.primary_key


def label_of(col):
    n = col.name[:-3] if col.name.endswith('_id') else col.name
    return n.replace('_', ' ').title()


def form_columns(cfg, user):
    m = cfg['model']
    hidden = set(getattr(m, '__hidden__', ())) | set(cfg.get('hide', ()))
    staff_only = set(getattr(m, '__staff_only__', ()))
    is_staff = user.can(cfg['slug'], 'all')
    return [c for c in m.__table__.columns
            if c.name not in EXCLUDE and c.name not in hidden and (is_staff or c.name not in staff_only)]


def default_of(col):
    d = col.default
    if d is not None and getattr(d, 'is_scalar', False):
        return d.arg
    return None


def label_query(target):
    """Query for a target model with relationships pre-loaded when its label needs them."""
    from sqlalchemy.orm import joinedload
    q = target.query
    if target.__name__ == 'Inventory':
        q = q.options(joinedload(target.resource), joinedload(target.camp))
    return q


def fk_options(col, limit=1000):
    target = fk_target(col)
    if not target:
        return []
    return [(o.id, o.label) for o in label_query(target).order_by(target.id.desc()).limit(limit).all()]


def to_input(col, val):
    if val is None:
        return ''
    if isinstance(col.type, db.DateTime):
        return val.strftime('%Y-%m-%dT%H:%M')
    if isinstance(col.type, db.Date):
        return val.isoformat()
    return val


def field_meta(col, value):
    t = col.type
    f = dict(name=col.name, label=label_of(col), required=is_required(col), value=value, kind='text', help=None)
    ch = choices_of(col)
    if fk_target(col):
        f.update(kind='select', choices=fk_options(col))
    elif ch:
        f.update(kind='select', choices=[(c, c.replace('_', ' ').title()) for c in ch])
    elif isinstance(t, db.Boolean):
        f.update(kind='checkbox', value=bool(value))
    elif isinstance(t, db.Text):
        f.update(kind='textarea')
    elif isinstance(t, db.DateTime):
        f.update(kind='datetime-local')
    elif isinstance(t, db.Date):
        f.update(kind='date')
    elif isinstance(t, db.Integer):
        f.update(kind='number', step='1', min='0' if col.name != 'rating' else '1')
    elif isinstance(t, db.Float):
        f.update(kind='number', step='any')
        if col.name in ('latitude', 'longitude') or col.name.endswith(('_latitude', '_longitude')):
            lo, hi = LAT if 'lat' in col.name else LNG
            f.update(min=str(lo), max=str(hi), help='Decimal degrees inside Pakistan region')
        else:
            f['min'] = '0'
    elif isinstance(t, db.Numeric):
        f.update(kind='number', step='0.01', min='0')
    elif isinstance(t, db.String):
        f['maxlength'] = t.length
        if 'email' in col.name:
            f['kind'] = 'email'
    return f


def coerce(col, raw):
    """Return (value, error)."""
    if raw is None or str(raw).strip() == '':
        return None, None
    raw = str(raw).strip()
    t = col.type
    try:
        if isinstance(t, db.Boolean):
            return raw.lower() in ('1', 'true', 'on', 'yes', 'y', 't'), None
        if isinstance(t, db.Integer):
            v = int(float(raw)) if '.' in raw else int(raw)
            if v < 0:
                return None, 'must not be negative'
            if col.name == 'rating' and not 1 <= v <= 5:
                return None, 'rating must be 1-5'
            return v, None
        if isinstance(t, db.Float):
            v = float(raw)
            if 'latitude' in col.name:
                if not LAT[0] <= v <= LAT[1]:
                    return None, 'latitude outside Pakistan region'
            elif 'longitude' in col.name:
                if not LNG[0] <= v <= LNG[1]:
                    return None, 'longitude outside Pakistan region'
            elif v < 0:
                return None, 'must not be negative'
            return v, None
        if isinstance(t, db.Numeric):
            v = Decimal(raw)
            if v < 0:
                return None, 'must not be negative'
            return v, None
        if isinstance(t, db.DateTime):
            return datetime.fromisoformat(raw.replace('Z', '').replace(' ', 'T')), None
        if isinstance(t, db.Date):
            return date.fromisoformat(raw[:10]), None
    except (ValueError, InvalidOperation):
        return None, 'invalid value'
    if fk_target(col):
        try:
            return int(raw), None
        except ValueError:
            return None, 'invalid selection'
    ch = choices_of(col)
    if ch and raw not in ch:
        return None, 'invalid choice'
    if isinstance(t, db.String) and t.length and len(raw) > t.length:
        return None, f'max {t.length} characters'
    return raw, None


def apply_form(cfg, obj, data, user, creating):
    """Copy submitted values onto obj. Returns dict of field errors."""
    errors = {}
    for col in form_columns(cfg, user):
        if isinstance(col.type, db.Boolean):
            setattr(obj, col.name, data.get(col.name) not in (None, '', 'false', '0'))
            continue
        val, err = coerce(col, data.get(col.name))
        if err:
            errors[col.name] = err
            continue
        if val is None:
            if is_required(col):
                errors[col.name] = 'required'
            elif not col.nullable:
                pass                      # keep existing value / column default
            elif not (creating and col.default is not None):
                setattr(obj, col.name, None)
            continue
        setattr(obj, col.name, val)
    return errors
