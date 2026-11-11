import os

from pyproj import Transformer
from shapely import transform, intersection
from shapely.geometry import box
import geopandas as gpd
from tools import densify_polygon_ellipsoidal, densify_polygon_utm
import mgrs

BANDS = "CDEFGHJKLMNPQRSTUVWX"

def gzd_polygons():
    for i, band in enumerate(BANDS):
        lat0 = -80 + 8 * i
        lat1 = 84 if band == "X" else lat0 + 8
        for zone in range(1, 61):
            lon0 = -180 + 6 * (zone - 1)
            lon1 = lon0 + 6
            if band == "V":
                if zone == 31: lon1 = 3
                elif zone == 32: lon0 = 3
            if band == "X":
                if zone in (32, 34, 36):
                    continue
                if zone == 31: lon1 = 9
                elif zone == 33: lon0, lon1 = 9, 21
                elif zone == 35: lon0, lon1 = 21, 33
                elif zone == 37: lon0 = 33
            epsg = (32600 if band >= "N" else 32700) + zone
            hemisphere = "N" if band >= "N" else "S"
            poly = box(lon0, lat0, lon1, lat1)
            poly_dense = densify_polygon_ellipsoidal(poly, 50000)
            yield {"zone": zone, "band": band, "epsg": epsg, "hemisphere": hemisphere, "poly": poly_dense}

def subgrids(bands):
    m = mgrs.MGRS()
    g100k = []
    for i, band in bands.iterrows():
        print(band["zone"], band["band"])
        band_geom = band["geometry"]
        transformer_to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{band['epsg']}", always_xy=True)
        transformer_from_utm = Transformer.from_crs(f"EPSG:{band['epsg']}", "EPSG:4326", always_xy=True)
        band_geom_utm = transform(band_geom, transformer_to_utm.transform, interleaved=False)
        min_east, min_north, max_east, max_north = band_geom_utm.bounds
        min_east = int((min_east // 100000) * 100000)
        min_north = int((min_north // 100000) * 100000)
        max_east = int((max_east // 100000) * 100000)
        max_north = int((max_north // 100000) * 100000)
        for east in range(min_east, max_east + 100000, 100000):
            for north in range(min_north, max_north + 100000, 100000):
                poly = box(east, north, east + 100000, north + 100000)
                poly_dense = densify_polygon_utm(poly, 100000)
                poly_clipped = intersection(poly_dense, band_geom_utm)
                if poly_clipped.area > 0:
                    mid_point = poly_clipped.centroid
                    mid_point_wgs84 = transform(mid_point, transformer_from_utm.transform, interleaved=False)
                    poly_wgs84 = transform(poly_clipped, transformer_from_utm.transform, interleaved=False)
                    lon, lat = mid_point_wgs84.coords[0]
                    cell = m.toMGRS(lat, lon)[3:5]
                    print(band["zone"], band["band"], cell)
                    g100k.append({"zone": band["zone"], "band": band["band"], "cell": cell, "geometry": poly_wgs84})
    g100k_df = gpd.GeoDataFrame(g100k, crs="EPSG:4326")
    g100k_df.to_file("output/mgrs.gpkg", layer="g100k", driver="GPKG")


if __name__ == '__main__':
    have_bands = False
    have_zones = False
    if not os.path.exists("output"):
        os.makedirs("output")
    else:
        layers = gpd.list_layers("output/mgrs.gpkg")
        if 'bands' in layers.values:
            have_bands = True
        if 'zones' in layers.values:
            have_zones = True
    if have_bands == True:
        bands = gpd.read_file("output/mgrs.gpkg", layer="bands")
    else:
        bands = {"zone": [], "band": [], "epsg": [], "hemisphere": [], "geometry": []}
        for p in gzd_polygons():
            print(f"Zone: {p['zone']}, Band: {p['band']}")
            bands["zone"].append(p["zone"])
            bands["band"].append(p["band"])
            bands["epsg"].append(p["epsg"])
            bands["hemisphere"].append(p["hemisphere"])
            bands["geometry"].append(p["poly"])
        bands = gpd.GeoDataFrame(bands, crs="EPSG:4326")
        bands.to_file("output/mgrs.gpkg", driver="GPKG", layer="bands")
    if have_zones == False:
        zones = bands[["zone", "epsg", "hemisphere", "geometry"]].dissolve(by=["zone", "epsg"]).reset_index()
        zones.to_file("output/mgrs.gpkg", driver="GPKG", layer="zones")

    subgrids(bands)



