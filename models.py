from typing import List

from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely import box, Point
from shapely.set_operations import union_all
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship,
)

from tools import densify_polygon_ellipsoidal, move_point_off_tile_edges

BANDS = "CDEFGHJKLMNPQRSTUVWX"


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True, eq=False):
    pass


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    number: Mapped[int]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), repr=False, init=False
    )
    zone_labels: Mapped[List["ZoneLabel"]] = relationship(
        back_populates="zone", default_factory=list, repr=False
    )
    bands: Mapped[List["Band"]] = relationship(
        back_populates="zone", default_factory=list, repr=False
    )

    def __post_init__(self):
        geoms = []
        for i, designator in enumerate(BANDS):
            lat0 = -80 + 8 * i
            lat1 = 84 if designator == "X" else lat0 + 8
            lon0 = -180 + 6 * (self.number - 1)
            lon1 = lon0 + 6
            if designator == "V":
                if self.number == 31:
                    lon1 = 3
                elif self.number == 32:
                    lon0 = 3
            if designator == "X":
                if self.number in (32, 34, 36):
                    continue
                if self.number == 31:
                    lon1 = 9
                elif self.number == 33:
                    lon0, lon1 = 9, 21
                elif self.number == 35:
                    lon0, lon1 = 21, 33
                elif self.number == 37:
                    lon0 = 33
            epsg = (32600 if designator >= "N" else 32700) + self.number
            poly = box(lon0, lat0, lon1, lat1)
            poly_dense = densify_polygon_ellipsoidal(poly, 100_000)
            geoms.append(poly_dense)
            self.bands.append(Band(designator=designator, crs=epsg, geom=from_shape(poly_dense, srid=4326), zone=self))
        self.geom = from_shape(union_all(geoms), srid=4326)
        for lat in (-45, 0, 45):
            lon = -180 + 6 * (self.number - 1) + 3
            label_point = move_point_off_tile_edges(
                Point(lon, lat))
            self.zone_labels.append(ZoneLabel(geom=from_shape(label_point, srid=4326), zone=self))


class ZoneLabel(Base):
    __tablename__ = "zone_labels"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), repr=False
    )
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), init=False)
    zone: Mapped["Zone"] = relationship(back_populates="zone_labels", repr=False)


class Band(Base):
    __tablename__ = "bands"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    designator: Mapped[str] = mapped_column(String(1))
    crs: Mapped[int]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), repr=False
    )
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), init=False)
    zone: Mapped["Zone"] = relationship(back_populates="bands", repr=False)
    band_label: Mapped["BandLabel"] = relationship(
        back_populates="band", init=False, repr=False
    )
    gridsquares: Mapped[List["GridSquare"]] = relationship(
        back_populates="band", default_factory=list, repr=False
    )

    def __post_init__(self):
        label_point = move_point_off_tile_edges(to_shape(self.geom).centroid)
        self.band_label = BandLabel(geom=from_shape(label_point, srid=4326), band=self)


class BandLabel(Base):
    __tablename__ = "band_labels"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), repr=False
    )
    band_id: Mapped[int] = mapped_column(ForeignKey("bands.id"), init=False)
    band: Mapped["Band"] = relationship(back_populates="band_label", repr=False)


class GridSquare(Base):
    __tablename__ = "gridsquares"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    designator: Mapped[str] = mapped_column(String(2))
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), repr=False
    )
    band_id: Mapped[int] = mapped_column(ForeignKey("bands.id"), init=False)
    band: Mapped["Band"] = relationship(back_populates="gridsquares", repr=False)
    lines: Mapped[List["Line"]] = relationship(
        back_populates="gridsquare", default_factory=list, repr=False
    )
    grid_square_labels: Mapped[List["GridSquareLabel"]] = relationship(
        back_populates="gridsquare", default_factory=list, repr=False
    )

    def __post_init__(self):
        label_point = move_point_off_tile_edges(to_shape(self.geom).centroid)
        self.grid_square_labels.append(
            GridSquareLabel(geom=from_shape(label_point, srid=4326), gridsquare=self, is_centroid=True))


class GridSquareLabel(Base):
    __tablename__ = "gridsquare_labels"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    gridsquare_id: Mapped[int] = mapped_column(ForeignKey("gridsquares.id"), init=False)
    gridsquare: Mapped["GridSquare"] = relationship(back_populates="grid_square_labels", repr=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), repr=False
    )
    is_centroid: Mapped[bool] = mapped_column(default=False)


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    val: Mapped[int]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True), repr=False
    )
    gridsquare_id: Mapped[int] = mapped_column(ForeignKey("gridsquares.id"), init=False)
    gridsquare: Mapped["GridSquare"] = relationship(back_populates="lines", repr=False)
    is_0: Mapped[bool] = mapped_column(default=False)
    is_10: Mapped[bool] = mapped_column(default=False)
