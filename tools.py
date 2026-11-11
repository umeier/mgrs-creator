import numpy as np
from shapely import distance, LineString
from shapely.geometry import Polygon
import pyproj


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


def densify_polygon_ellipsoidal(polygon_4326, scale):
    max_distance_meters = scale * 0.00025

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
    new_coords = [line.interpolate(distance) for distance in distances]
    if distances[-1] < line.length:
        new_coords.append(line.interpolate(line.length))
    return new_coords

def densify_line_utm(line, scale):
    p1, p2 = line.coords[0], line.coords[-1]
    max_distance_meters = scale * 0.00025
    return _densify_cartesian_line(p1, p2, max_distance_meters)

def densify_polygon_utm(polygon_utm, scale):
    max_distance_meters = scale * 0.00025

    def process_ring(ring):
        coords = list(ring.coords)
        dense_coords = []
        for i in range(len(coords) -1):
            dense_coords.extend(_densify_cartesian_line(coords[i], coords[i + 1], max_distance_meters))
        dense_coords.append(coords[-1])
        return dense_coords

    dense_ext = process_ring(polygon_utm.exterior)
    dense_ints = [process_ring(interior) for interior in polygon_utm.interiors]

    return Polygon(dense_ext, dense_ints)