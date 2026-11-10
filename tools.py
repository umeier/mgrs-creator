import numpy as np
from shapely import distance, LineString
from shapely.geometry import Polygon
import pyproj


def _densify_axis_aligned_edge(p1, p2, max_distance_meters):
    """
    Unterteilt eine Kante hochpräzise entlang des WGS84-Ellipsoids.
    Garantiert, dass Achsen-parallele Linien (starr auf Lon oder Lat) perfekt flach bleiben.
    """
    lon1, lat1 = p1
    lon2, lat2 = p2

    # WGS84 Ellipsoid für exakte Distanzberechnungen initialisieren
    geod = pyproj.Geod(ellps="WGS84")
    new_coords = [p1]

    # 1. Fall: Ost-West-Kante (Breitengrad ist identisch)
    if abs(lat1 - lat2) < 1e-9:
        # Berechne die exakte Distanz entlang dieses spezifischen Breitengrads
        # Da lat1 == lat2, bewegen wir uns auf einem Kleinkreis des Ellipsoids
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)

        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            # Nur die Längengrade (lon) aufteilen, lat bleibt absolut starr
            lons = np.linspace(lon1, lon2, num_segments + 1)[1:-1]
            for lon in lons:
                new_coords.append((lon, lat1))

    # 2. Fall: Nord-Süd-Kante (Längengrad ist identisch)
    elif abs(lon1 - lon2) < 1e-9:
        # Berechne die exakte Distanz entlang des Meridians (Ellipsoid-Berücksichtigung)
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)

        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            # Nur die Breitengrade (lat) aufteilen, lon bleibt absolut starr
            lats = np.linspace(lat1, lat2, num_segments + 1)[1:-1]
            for lat in lats:
                new_coords.append((lon1, lat))

    # 3. Fall: Sicherheitsnetz (Sollte laut Definition hier nicht vorkommen)
    else:
        _, _, distance_meters = geod.inv(lon1, lat1, lon2, lat2)
        if distance_meters > max_distance_meters:
            num_segments = int(np.ceil(distance_meters / max_distance_meters))
            # Nutzen Sie pyproj für echte Großkreis-Zwischenpunkte (Orthodromen)
            lon_lats = geod.npts(lon1, lat1, lon2, lat2, num_segments - 1)
            new_coords.extend(lon_lats)

    return new_coords


def densify_polygon_ellipsoidal(polygon_4326, scale):
    """
    Verdichtet ein EPSG:4326 Polygon unter Erhalt der Eckpunkte und
    achsenparallelen Linien auf Basis des WGS84-Ellipsoids.
    """
    # Kartografischer Richtwert: 0.25 mm auf der Karte/Bildschirm
    max_distance_meters = scale * 0.00025

    def process_ring(ring):
        coords = list(ring.coords)
        dense_coords = []
        for i in range(len(coords) - 1):
            dense_coords.extend(_densify_axis_aligned_edge(coords[i], coords[i + 1], max_distance_meters))
        dense_coords.append(coords[-1])  # Letzten Originalpunkt exakt anhängen
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