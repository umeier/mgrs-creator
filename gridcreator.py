import os

from shapely.geometry import box
import geopandas as gpd
from tools import densify_polygon_ellipsoidal

BANDS = "CDEFGHJKLMNPQRSTUVWX"  # 80°S bis 84°N, ohne I und O

def gzd_polygons():
    """Liefert (Bezeichner, Polygon in WGS84) für alle UTM-Grid-Zones."""
    for i, band in enumerate(BANDS):
        lat0 = -80 + 8 * i
        lat1 = 84 if band == "X" else lat0 + 8   # Band X ist 12° hoch
        for zone in range(1, 61):
            lon0 = -180 + 6 * (zone - 1)
            lon1 = lon0 + 6
            if band == "V":                       # Sonderfall Norwegen
                if zone == 31: lon1 = 3
                elif zone == 32: lon0 = 3
            if band == "X":                       # Sonderfall Svalbard
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



