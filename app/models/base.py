import re
from datetime import datetime, date
from sqlalchemy.orm import declared_attr
from ..extensions import db

SEV = ['low', 'moderate', 'high', 'critical']
PRIO = ['low', 'medium', 'high', 'critical']
DATA_SOURCES = ['sample', 'reported', 'verified']


def Str(n=120, **kw):
    return db.Column(db.String(n), **kw)


def Txt(**kw):
    return db.Column(db.Text, **kw)


def Int(**kw):
    return db.Column(db.Integer, **kw)


def Flt(**kw):
    return db.Column(db.Float, **kw)


def Bool(default=False, **kw):
    return db.Column(db.Boolean, default=default, nullable=False, **kw)


def Dt(**kw):
    return db.Column(db.DateTime, **kw)


def Dat(**kw):
    return db.Column(db.Date, **kw)


def Money(**kw):
    return db.Column(db.Numeric(14, 2), **kw)


def Ch(choices, default=None, n=30, **kw):
    kw.setdefault('nullable', False)
    return db.Column(db.String(n), default=default or choices[0], info={'choices': list(choices)}, **kw)


def FK(table, null=True, **kw):
    return db.Column(db.Integer, db.ForeignKey(table + '.id'), nullable=null, index=True, **kw)


def now():
    return datetime.utcnow()


def today():
    return date.today()


class Base(db.Model):
    __abstract__ = True
    __label__ = '{name}'
    __hidden__ = ()          # columns never shown in forms
    __staff_only__ = ()      # columns hidden from users without "<module>.all"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def label(self):
        text = re.sub(r'\{(\w+)\}', lambda m: str(getattr(self, m.group(1), '') or ''), self.__label__).strip()
        return text or f'#{self.id}'

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id}>'


class Tracked(Base):
    """Transactional record: tracks who created it and whether it is sample / reported / verified."""
    __abstract__ = True
    data_source = db.Column(db.String(10), default='reported', nullable=False, index=True,
                            info={'choices': DATA_SOURCES})
    verified_at = db.Column(db.DateTime)

    @declared_attr
    def created_by_id(cls):
        return db.Column(db.Integer, db.ForeignKey('users.id'), index=True)

    @declared_attr
    def verified_by_id(cls):
        return db.Column(db.Integer, db.ForeignKey('users.id'))
