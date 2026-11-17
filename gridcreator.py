import mgrs
from geoalchemy2.shape import to_shape, from_shape
from pyproj import Transformer
from shapely import transform, intersection, LineString
from shapely.geometry import box
from shapely.ops import linemerge
from tqdm import tqdm, trange
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from database import engine, truncate_all
from models import Band, GridSquare, Zone, Line
from tools import densify_polygon_utm, densify_line_utm


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

def make_lines(gridsquare):
    spacing = 1000
    densify_distance = 100000
    utm_crs = f"EPSG:{gridsquare.band.crs}"
    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    from_utm = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    geometry = transform(to_shape(gridsquare.geom), to_utm.transform, interleaved=False)
    min_east, min_north, max_east, max_north = (
        int((bound // spacing) * spacing) for bound in geometry.bounds
    )
    lines = []

    def add_line(coordinate, endpoints):
        dense = densify_line_utm(LineString(endpoints), densify_distance)
        clipped = intersection(dense, geometry)
        if clipped.geom_type != 'LineString':
            if clipped.geom_type == 'Point':
                return
            extracted_lines = [geom for geom in clipped.geoms if isinstance(geom, LineString)]
            coords = [pt for line in extracted_lines for pt in line.coords]
            clipped = LineString(coords)
        if clipped.length == 0:
            return
        value = coordinate % 100
        wgs84 = transform(clipped, from_utm.transform, interleaved=False)
        lines.append(Line(
            gridsquare=gridsquare,
            val=value,
            is_0=value == 0,
            is_10=value % 10 == 0,
            geom=from_shape(wgs84, srid=4326),
        ))

    for east in range(min_east, max_east + spacing, spacing):
        add_line(east, [(east, min_north), (east, max_north)])
    for north in range(min_north, max_north + spacing, spacing):
        add_line(north, [(min_east, north), (max_east, north)])

    return lines


if __name__ == '__main__':

    with Session(engine) as session:
        zones_total = session.scalar(select(func.count()).select_from(Zone))
        bands_total = session.scalar(select(func.count()).select_from(Band))

        if zones_total != 60 or bands_total != 1197:
            truncate_all(engine)
            for z in trange(1, 61, desc="Creating zones with bands", unit="zone"):
                zone = Zone(number=z)
                session.add(zone)
                session.commit()
            session.commit()
            bands_total = session.scalar(select(func.count()).select_from(Band))
            zones_total = session.scalar(select(func.count()).select_from(Zone))

    with Session(engine) as session:
        gridsquares_total = session.scalar(select(func.count()).select_from(GridSquare))
        stmt = select(Band)
        if gridsquares_total != 69459:
            truncate_all(engine, exclude=('alembic_version', 'spatial_ref_sys', 'zones', 'bands'))
            for band in tqdm(session.scalars(stmt.execution_options(yield_per=100)), total=bands_total,
                             desc="Creating gridsquares per band", unit="band"):
                gridsquares = make_gridsquares(band)
                session.add_all(gridsquares)
                session.flush()
            session.commit()
            gridsquares_total = session.scalar(select(func.count()).select_from(GridSquare))

    with Session(engine) as session:
        lines_total = session.scalar(select(func.count()).select_from(Line))
        if lines_total == 0:
            stmt = select(GridSquare).options(joinedload(GridSquare.band))
            for gridsquare in tqdm(session.scalars(stmt.execution_options(yield_per=100)), total=gridsquares_total,
                                   desc="Creating lines per gridsquare", unit="gridsquare"):
                lines = make_lines(gridsquare)
                session.add_all(lines)
                session.flush()
            session.commit()
        lines_total = session.scalar(select(func.count()).select_from(Line))

    print(f"All done! {zones_total} zones, {bands_total} bands, {gridsquares_total} gridsquares, {lines_total} lines")
