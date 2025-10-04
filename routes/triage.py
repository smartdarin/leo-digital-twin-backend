# backend/routes/triage.py
from flask import Blueprint, request, jsonify
import math

bp_triage = Blueprint("triage", __name__)

def haversine_km(lat1, lon1, lat2, lon2):
    R=6371.0
    from math import radians,sin,cos,asin,sqrt
    dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))

@bp_triage.route("/triage", methods=["GET"])
def triage():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))

        # Nearby ring like your frontend uses
        ring = [
            {"lat":lat, "lon":lon, "name":"Selected"},
            {"lat":lat+0.5, "lon":lon, "name":"N"},
            {"lat":lat-0.5, "lon":lon, "name":"S"},
            {"lat":lat, "lon":lon+0.5, "name":"E"},
            {"lat":lat, "lon":lon-0.5, "name":"W"},
        ]

        items = []
        for loc in ring:
            # Pull your real values here (risk_score, factors, exposure)
            # Placeholder logic:
            risk = max(0.0, min(1.0, 0.2 + 0.6*abs((loc["lat"]-lat)+(loc["lon"]-lon))))
            exposure = max(0.0, min(1.0, 0.3 + 0.7*(1.0/(1.0+haversine_km(lat,lon,loc["lat"],loc["lon"])+0.1))))
            priority = round(risk*exposure, 3)
            tags = []
            if risk > 0.6: tags.append("high risk")
            if exposure > 0.6: tags.append("high exposure")
            items.append({**loc, "risk":risk, "exposure":exposure, "priority":priority, "tags":tags})

        items.sort(key=lambda x: x["priority"], reverse=True)
        return jsonify({"status":"success","items":items})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 400
