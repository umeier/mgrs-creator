from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Zone(Base):
    __tablename__ = 'zones'

    id = Column(Integer, primary_key=True)
    zone = Column(Integer)
    hemisphere = Column(String(1))
    crs = Column(Integer)
    geom = Column(Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True))

class Band(Base):
    __tablename__ = 'bands'

    id = Column(Integer, primary_key=True)
    zone = Column(Integer)
    band = Column(String(1))
    hemisphere = Column(String(1))
    crs = Column(Integer)
    geom = Column(Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True))

class Grid100km(Base):
    __tablename__ = 'grid100km'

    id = Column(Integer, primary_key=True)
    zone = Column(Integer)
    band = Column(String(1))
    hemisphere = Column(String(1))
    square = Column(String(2))
    crs = Column(Integer)
    geom = Column(Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True))

class Line(Base):
    __tablename__ = 'lines'

    id = Column(Integer, primary_key=True)
    zone = Column(Integer)
    band = Column(String(1))
    hemisphere = Column(String(1))
    square = Column(String(1))
    crs = Column(Integer)
    orientation = Column(String(1))
    val = Column(Integer)
    geom = Column(Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=True))
