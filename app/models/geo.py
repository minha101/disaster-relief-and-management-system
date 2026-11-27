from .base import *


class Province(Base):
    __tablename__ = 'provinces'
    name = Str(80, unique=True, nullable=False)
    code = Str(10, unique=True)


class District(Base):
    __tablename__ = 'districts'
    __table_args__ = (db.UniqueConstraint('province_id', 'name'),)
    province_id = FK('provinces', False)
    name = Str(100, nullable=False)
    latitude = Flt()      # approximate centroid
    longitude = Flt()
    population = Int()


class City(Base):
    __tablename__ = 'cities'
    district_id = FK('districts', False)
    name = Str(100, nullable=False)
    latitude = Flt()
    longitude = Flt()
    population = Int()


class Village(Tracked):
    __tablename__ = 'villages'
    district_id = FK('districts', False)
    city_id = FK('cities')
    name = Str(120, nullable=False)
    latitude = Flt()
    longitude = Flt()
    population = Int()


class Location(Tracked):
    __tablename__ = 'locations'
    name = Str(160, nullable=False)
    location_type = Ch(['point', 'village', 'camp', 'hospital', 'landmark', 'other'])
    district_id = FK('districts')
    latitude = Flt(nullable=False)
    longitude = Flt(nullable=False)
    address = Str(255)
