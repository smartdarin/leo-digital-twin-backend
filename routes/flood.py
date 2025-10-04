# routes/flood.py
import math
import requests
from flask import Blueprint, request, jsonify

# Mount under the same prefix the frontend calls
flood_bp = Blueprint("flood", __name__, url_prefix="/api/spread")

USER_AGENT = "LEO-DTE/1.0 (contact: email@example.com)"

def parse_float_arg(name):
    """Return float value for query arg or None if missing/invalid."""
    v = request.args.get(name, type=str)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def http_get(url, headers=None, timeout=10):
    """Small helper to wrap requests.get with consistent headers and error handling."""
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        return r
    except requests.RequestException:
        return None

@flood_bp.get("/flood")
def flood_risk():
    # 1) Validate inputs
    lat = parse_float_arg("lat")
    lon = parse_float_arg("lon")
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon are required numeric query params"}), 400

    # Optional scenario params used by UI; keep but don’t fail on them
    rp = request.args.get("rp")      # return period or region param (optional)
    tide = request.args.get("tide")  # tide flag (optional)

    # 2) Default scores/factors
    precip24 = 0.0
    soil_m = None
    river_level = None

    # 3) NOAA NWS forecast grid lookup (US-only; safe-fail outside coverage)
    pts = http_get(f"https://api.weather.gov/points/{lat},{lon}")
    if pts and pts.ok:
        grid = (pts.json().get("properties") or {}).get("forecastGridData")
        if grid:
            gridj = http_get(grid, headers={"Accept": "application/geo+json"})
            if gridj and gridj.ok:
                props = gridj.json().get("properties") or {}
                qpf = (props.get("quantitativePrecipitation", {}).get("values") or [])[:24]
                precip24 = sum(v.get("value") or 0 for v in qpf if v.get("value") is not None)

    # 4) Simple scoring model (placeholder)
    score = 0.0
    if precip24 >= 25:
        score += 0.6
    elif precip24 >= 10:
        score += 0.3

    # 5) Compose response
    data = {
        "risk_level": "high" if score > 0.7 else "medium" if score > 0.35 else "low",
        "risk_score": round(score, 2),
        "prediction_confidence": 0.6,
        "factors": {
            "river_level": river_level,
            "soil_moisture": soil_m,
            "precip_24h": round(precip24, 2),
        },
        "meta": {
            "rp": rp,
            "tide": tide,
            "source": "api.weather.gov (QPF 24h)",
        },
    }
    return jsonify({"data": data}), 200
