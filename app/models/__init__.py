from .base import Base, Tracked
from .core import *
from .geo import *
from .incidents import *
from .operations import *
from .resources import *
from .people import *
from .health import *
from .system import *
from ..extensions import db


def all_models():
    return sorted((m.class_ for m in db.Model.registry.mappers), key=lambda c: c.__tablename__)
