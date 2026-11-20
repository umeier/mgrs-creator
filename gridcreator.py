import mgrs
from geoalchemy2.shape import to_shape, from_shape
from pyproj import Transformer
from shapely import transform, intersection, LineString
from shapely.geometry import box
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from tqdm import tqdm, trange

from database import engine, truncate_all
from models import Band, GridSquare, Zone, Line
from tools import densify_polygon_utm, densify_line_utm, densify_polygon_ellipsoidal


def make_gridsquares(band):
    grid_size = 100_000
    densify_distance = 10_000
    wgs84_crs = "EPSG:4326"
    utm_crs = f"EPSG:{band.crs}"

    to_utm = Transformer.from_crs(wgs84_crs, utm_crs, always_xy=True)
    from_utm = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)
    band_wgs84 = densify_polygon_ellipsoidal(box(*to_shape(band.geom).bounds), densify_distance)
    band_utm = transform(band_wgs84, to_utm.transform, interleaved=False)
    min_east, min_north, max_east, max_north = (
        int((bound // grid_size) * grid_size) for bound in band_utm.bounds
    )

    mgrs_converter = mgrs.MGRS()
    gridsquares = []
    for east in range(min_east, max_east + grid_size, grid_size):
        for north in range(min_north, max_north + grid_size, grid_size):
            square = box(east, north, east + grid_size, north + grid_size)
            dense_square = densify_polygon_utm(square, densify_distance)
            clipped_square = intersection(dense_square, band_utm)
            if clipped_square.area <= 0:
                continue

            centroid_wgs84 = transform(
                clipped_square.centroid, from_utm.transform, interleaved=False
            )
            square_wgs84 = transform(
                clipped_square, from_utm.transform, interleaved=False
            )
            lon, lat = centroid_wgs84.coords[0]
            designator = mgrs_converter.toMGRS(lat, lon)[3:5]
            gridsquares.append(GridSquare(
                band=band,
                designator=designator,
                geom=from_shape(square_wgs84, srid=4326),
            ))
    return gridsquares

def make_lines(gridsquare):
    spacing = 1_000
    densify_distance = 10_000
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
        if dense is None:
            return
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
    print("Creating mgrs grid")

    with Session(engine) as session:
        zones_total = session.scalar(select(func.count()).select_from(Zone))
        bands_total = session.scalar(select(func.count()).select_from(Band))

        if zones_total != 60 or bands_total != 1197:
            if zones_total != 0 and bands_total != 0:
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
            if gridsquares_total != 0:
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
