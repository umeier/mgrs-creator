import math

import numpy as np
from shapely import LineString
from shapely.geometry import Point, Polygon
import pyproj


def move_point_off_tile_edges(point):
    max_latitude = math.degrees(math.atan(math.sinh(math.pi)))
    if (point.is_empty or not math.isfinite(point.x) or not math.isfinite(point.y)
            or not -180 <= point.x <= 180 or not -max_latitude <= point.y <= max_latitude):
        raise ValueError("Point must be within the Web Mercator world extent")

    to_mercator = pyproj.Transformer.from_crs(4326, 3857, always_xy=True)
    to_wgs84 = pyproj.Transformer.from_crs(3857, 4326, always_xy=True)
    x, y = to_mercator.transform(point.x, point.y)
    half_world = math.pi * 6378137
    tile_size = 2 * half_world / (1 << 19)

    def on_edge(value):
        index = round((value + half_world) / tile_size)
        return abs(value - (-half_world + index * tile_size)) <= 1e-7

    east, north = on_edge(x), on_edge(y)
    if not east and not north:
        return point
    lon, lat = to_wgs84.transform(x + 10 * east, y + 10 * north)
    return Point(lon, lat)


def _densify_axis_aligned_edge(p1, p2, max_distance_meters):
    lon1, lat1 = p1
    lon2, lat2 = p2

    geod = pyproj.Geod(ellps="WGS84")
    new_coords = [p1]

    if abs(lat1 - lat2) < 1e-9:
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)

        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            lons = np.linspace(lon1, lon2, num_segments + 1)[1:-1]
            for lon in lons:
                new_coords.append((lon, lat1))

    elif abs(lon1 - lon2) < 1e-9:
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)

        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            lats = np.linspace(lat1, lat2, num_segments + 1)[1:-1]
            for lat in lats:
                new_coords.append((lon1, lat))

    else:
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)
        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            lon_lats = geod.npts(lon1, lat1, lon2, lat2, num_segments - 1)
            new_coords.extend(lon_lats)

    return new_coords


def densify_polygon_ellipsoidal(polygon_4326, max_distance_meters):

    def process_ring(ring):
        coords = list(ring.coords)
        dense_coords = []
        for i in range(len(coords) - 1):
            dense_coords.extend(_densify_axis_aligned_edge(coords[i], coords[i + 1], max_distance_meters))
        dense_coords.append(coords[-1])
        return dense_coords

    dense_ext = process_ring(polygon_4326.exterior)
    dense_ints = [process_ring(interior) for interior in polygon_4326.interiors]

    return Polygon(dense_ext, dense_ints)


def _densify_cartesian_line(p1, p2, max_distance_meters):
    line = LineString([p1, p2])
    distances = np.arange(0, line.length, max_distance_meters)
    if len(distances) > 1:
        new_coords = [line.interpolate(distance) for distance in distances]
        if distances[-1] < line.length:
            new_coords.append(p2)
        return LineString(new_coords)
    else:
        return None


def densify_line_utm(line, max_distance_meters):
    p1, p2 = line.coords[0], line.coords[-1]
    return _densify_cartesian_line(p1, p2, max_distance_meters)

def densify_polygon_utm(polygon_utm, max_distance_meters):

    def process_ring(ring):
        coords = list(ring.coords)
        dense_coords = []
        for i in range(len(coords) -1):
            dense_line = _densify_cartesian_line(coords[i], coords[i + 1], max_distance_meters)
            dense_coords.extend(dense_line.coords)
        dense_coords.append(coords[-1])
        return dense_coords

    dense_ext = process_ring(polygon_utm.exterior)
    dense_ints = [process_ring(interior) for interior in polygon_utm.interiors]

    return Polygon(dense_ext, dense_ints)


