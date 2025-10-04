# backend/routes/spread.py
from flask import Blueprint, request, jsonify
import math

bp_spread = Blueprint('spread', __name__, url_prefix='/api/spread')

def sector_polygon(lat, lon, radius_km, bearing_deg, width_deg=60, steps=24):
    # Great-circle sector approximated in lat/lon; small-radius assumption
    R = 6371.0
    lat0 = math.radians(lat)
    lon0 = math.radians(lon)
    start = math.radians(bearing_deg - width_deg/2)
    end = math.radians(bearing_deg + width_deg/2)
    pts = [{"type":"Point","coordinates":[lon, lat]}]
    coords = []
    for i in range(steps+1):
        b = start + (end-start)*i/steps
        # destination point formula
        d = radius_km / R
        lat1 = math.asin(math.sin(lat0)*math.cos(d) + math.cos(lat0)*math.sin(d)*math.cos(b))
        lon1 = lon0 + math.atan2(math.sin(b)*math.sin(d)*math.cos(lat0),
                                 math.cos(d)-math.sin(lat0)*math.sin(lat1))
        coords.append([math.degrees(lon1), math.degrees(lat1)])
    # close polygon back to center
    ring = [[lon, lat]] + coords + [[lon, lat]]
    return {
        "type":"Feature",
        "geometry":{"type":"Polygon","coordinates":[ring]},
        "properties":{}
    }

def clamp(x, lo, hi): return max(lo, min(hi, x))

@bp_spread.route("/wildfire", methods=["GET"])
def wildfire():
    from math import cos, radians
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))

    # What‑if params from UI
    h = (request.args.get("h") or "3h").lower()       # '1h','3h','6h','12h'
    w = float(request.args.get("w", 20.0))            # wind km/h
    m = (request.args.get("m") or "normal").lower()   # 'dry'|'normal'|'wet'

    # Optional direction (deg) for sector orientation
    wind_dir_deg = float(request.args.get("wind_dir", 45.0))

    # Simple scale factors
    scale = {"1h": 1.0, "3h": 1.6, "6h": 2.2, "12h": 3.0}.get(h, 1.6)
    moisture = {"dry": 1.3, "normal": 1.0, "wet": 0.7}.get(m, 1.0)

    # Radius model (km) — placeholder demo logic
    radius_km = max(0.5, 2.0 * scale * moisture * (0.5 + w/60.0))

    # Helper: quick rectangular polygon around center for demo
    def rect(r_km):
        dlat = r_km / 110.574
        dlon = r_km / (111.320 * cos(radians(lat)))
        coords = [
            [lon - dlon, lat - dlat],
            [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat],
            [lon - dlon, lat - dlat],
        ]
        return {
            "type": "Feature",
            "properties": {"horizon": h, "radius_km": r_km, "wind_dir": wind_dir_deg},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        }

    # Two rings to suggest growth
    features = [rect(radius_km*0.6), rect(radius_km)]

    # Meta KPIs for UI strip
    meta = {
        "area_km2": round((2*radius_km)*(2*radius_km), 2),
        "pop_exposed": int(1200*scale*moisture + w*10),
        "assets_exposed": int(50*scale + w),
        "delta": f"+{int(200*scale)} vs 1h",
    }

    return jsonify({"type": "FeatureCollection", "features": features, "meta": meta})
