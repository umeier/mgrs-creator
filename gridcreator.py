import mgrs
from tqdm import tqdm, trange
from geoalchemy2.shape import from_shape, to_shape
from pyproj import Transformer
from shapely import transform, intersection, union
from shapely.geometry import box
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import sessionmaker, Session, joinedload

from database import get_database_url
from models import Band, GridSquare, Zone, Base
from tools import densify_polygon_ellipsoidal, densify_polygon_utm


def make_gridsquares(band):
    gridsquares = []
    m = mgrs.MGRS()
    band_geom = to_shape(band.geom)
    epsg = band.crs
    transformer_to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    transformer_from_utm = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    band_geom_utm = transform(band_geom, transformer_to_utm.transform, interleaved=False)
    min_east, min_north, max_east, max_north = band_geom_utm.bounds
    min_east = int((min_east // 100000) * 100000)
    min_north = int((min_north // 100000) * 100000)
    max_east = int((max_east // 100000) * 100000)
    max_north = int((max_north // 100000) * 100000)
    for east in range(min_east, max_east + 100000, 100000):
        for north in range(min_north, max_north + 100000, 100000):
            poly = box(east, north, east + 100000, north + 100000)
            poly_dense = densify_polygon_utm(poly, 500000)
            poly_clipped = intersection(poly_dense, band_geom_utm)
            if poly_clipped.area > 0:
                mid_point = poly_clipped.centroid
                mid_point_wgs84 = transform(mid_point, transformer_from_utm.transform, interleaved=False)
                poly_wgs84 = transform(poly_clipped, transformer_from_utm.transform, interleaved=False)
                lon, lat = mid_point_wgs84.coords[0]
                cell = m.toMGRS(lat, lon)[3:5]
                current_subgrid = GridSquare(band=band, designator=cell, geom=from_shape(poly_wgs84, srid=4326))
                gridsquares.append(current_subgrid)
    return gridsquares


def truncate_all(engine, schema="public", exclude=("alembic_version", "spatial_ref_sys")):
    quote = engine.dialect.identifier_preparer.format_table
    tables = [quote(t) for t in Base.metadata.sorted_tables if t.name not in exclude]
    if not tables:
        return
    stmt = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
    with engine.begin() as conn:
        conn.execute(text(stmt))


if __name__ == '__main__':
    engine = create_engine(get_database_url(),
                           plugins=["geoalchemy2"])

    with Session(engine) as session:
        zones_total = session.scalar(select(func.count()).select_from(Zone))
        bands_total = session.scalar(select(func.count()).select_from(Band))

        if zones_total != 60 or bands_total != 1197:
            truncate_all(engine)
            for z in trange(1, 61, desc="Creating zones", unit="zone"):
                zone = Zone(number=z)
                session.add(zone)
                session.commit()
            session.commit()
            bands_total = session.scalar(select(func.count()).select_from(Band))

    with Session(engine) as session:
        stmt = select(Band)
        gridsquares_total = session.scalar(select(func.count()).select_from(GridSquare))
        if gridsquares_total != 69459:
            truncate_all(engine, exclude=('alembic_version', 'spatial_ref_sys', 'zones', 'bands'))
            for band in tqdm(session.scalars(stmt.execution_options(yield_per=100)), total=bands_total,
                             desc="Creating gridsquares per band", unit="band"):
                gridsquares = make_gridsquares(band)
                session.add_all(gridsquares)
                session.flush()
            session.commit()
