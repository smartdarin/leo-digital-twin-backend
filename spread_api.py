# backend/spread_api.py
from flask import Blueprint, request, jsonify
import math
import requests
import time

bp_spread_live = Blueprint("spread_live", __name__)

def cosd(x): 
    return math.cos(math.radians(x))

def clamp(v, vmin, vmax): 
    return max(vmin, min(v, vmax))

# Simple attenuation helpers
def humidity_factor(h_pct, k_h=0.8):
    h = clamp(h_pct, 0, 100) / 100.0
    return 1.0 + k_h * (1.0 - h)  # drier -> larger

def fuel_factor(fuel_index, k_f=0.6):
    f = clamp(fuel_index, 0.0, 1.0)
    return 1.0 + k_f * f  # heavier/drier fuel -> larger

def fetch_weather(lat: float, lon: float):
    """
    Live weather provider using Open-Meteo.
    Returns dict or None on failure.
    """
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "windspeed_10m,winddirection_10m,relativehumidity_2m,soil_moisture_0_to_7cm",
                "past_days": 0,
                "forecast_days": 1,
                "timezone": "UTC",
            },
            timeout=6,
        )
        r.raise_for_status()
        j = r.json()
        idx = 0  # use current/next hour
        soil_series = j["hourly"].get("soil_moisture_0_to_7cm")
        soil_val = soil_series[idx] if soil_series else 0.22
        return {
            "wind_speed_kmph": float(j["hourly"]["windspeed_10m"][idx]),
            "wind_bearing_deg": float(j["hourly"]["winddirection_10m"][idx]),
            "humidity_pct": float(j["hourly"]["relativehumidity_2m"][idx]),
            "soil_moisture": float(soil_val),
            "fuel_index": 0.4,  # keep simple placeholder; map NDVI/landcover if available
            "observed_unix": int(time.time()),
            "source": "open-meteo",
        }
    except Exception:
        return None

@bp_spread_live.route("/spread")
def spread():
    # Parse inputs
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        horizon = float(request.args.get("h", 3.0))
    except Exception:
        return jsonify({"error": "invalid lat/lon/h"}), 400

    # Try live weather; if unavailable, use prior in-app provider, then fallback demo
    weather = fetch_weather(lat, lon)
    if not weather:
        # optionally use an injected cache/provider if your app sets it
        provider = request.environ.get("weather_cache_lookup", None)
        if callable(provider):
            weather = provider(lat, lon)

    if not weather:
        weather = {
            "wind_speed_kmph": 18.0,
            "wind_bearing_deg": 250.0,  # blowing from 250°
            "humidity_pct": 62.0,
            "soil_moisture": 0.22,
            "fuel_index": 0.4,
            "observed_unix": None,
            "source": "demo-fallback",
        }

    # Extract fields
    ws = float(weather["wind_speed_kmph"])
    wb = float(weather["wind_bearing_deg"])
    h_pct = float(weather["humidity_pct"])
    fuel_idx = float(weather.get("fuel_index", 0.3))

    # Tunables
    k0 = 0.12      # base km per hour per km/h wind
    k_h = 0.8
    k_f = 0.6
    alpha = 0.5    # directional bias 0..1
    r_min = 0.5    # km/h lower clamp
    r_max = 8.0    # km/h upper clamp

    r0_kmph = k0 * ws * humidity_factor(h_pct, k_h) * fuel_factor(fuel_idx, k_f)
    r0_kmph = clamp(r0_kmph, r_min, r_max)

    # Sector bearings for N,E,S,W (destination direction of spread)
    sectors = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}
    r_dir_km = {}
    for key, bearing in sectors.items():
        # downwind boost via cosine of angle between wind-bearing and sector
        bias = 1.0 + alpha * cosd(bearing - wb)
        r_dir_km[key] = max(0.0, r0_kmph * bias * horizon)

    # Triage weights from relative sector areas ~ r^2
    denom = sum(v * v for v in r_dir_km.values()) or 1.0
    w_dir = {k: int(round(100.0 * (v * v) / denom)) for k, v in r_dir_km.items()}
    # Ensure sum == 100
    rem = 100 - sum(w_dir.values())
    if rem != 0:
        mx = max(w_dir, key=w_dir.get)
        w_dir[mx] += rem

    return jsonify({
        "lat": lat,
        "lon": lon,
        "horizon_hours": horizon,
        "weather": weather,                 # includes source and observed_unix
        "r0_kmph": r0_kmph,
        "r_dir_km": r_dir_km,
        "w_dir_pct": w_dir
    })
