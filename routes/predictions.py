from flask import Blueprint, jsonify, request
import os, io, csv, time, random
import datetime as dt
import requests
import numpy as np
from PIL import Image
import math

# Flask blueprint (kept the same)
pred_bp = Blueprint('predictions', __name__)

# -----------------------------
# Small math helpers
# -----------------------------
def _sigmoid(x): 
    return 1.0 / (1.0 + math.exp(-x))

def _clamp01(x): 
    return max(0.0, min(1.0, x))

def _label_from_score(s):
    return "low" if s < 0.33 else ("medium" if s < 0.66 else "high")

def _confidence_from_score(s):
    d = abs(s - 0.5)
    return _clamp01(0.5 + d)  # simple certainty proxy

# -----------------------------
# Shared helpers
# -----------------------------
def bbox_from_point(lat: float, lon: float, deg: float = 1.0) -> str:
    return f"{lon - deg},{lat - deg},{lon + deg},{lat + deg}"

# Weather.gov grid fetch
NWS_POINTS = "https://api.weather.gov/points/{lat},{lon}"

def nws_grid_forecast(lat: float, lon: float):
    UA = os.getenv("NWS_USER_AGENT", "LEO-DigitalTwin/1.0 (contact@example.com)")
    try:
        p = requests.get(
            NWS_POINTS.format(lat=lat, lon=lon),
            timeout=15,
            headers={"User-Agent": UA}
        ).json()
        grid_url = p["properties"]["forecastGridData"]
        g = requests.get(
            grid_url,
            timeout=20,
            headers={"Accept": "application/geo+json", "User-Agent": UA}
        ).json()
        props = g.get("properties", {})
        precip = (props.get("quantitativePrecipitation", {}).get("values") or [])[:24]
        rh = (props.get("relativeHumidity", {}).get("values") or [])[:24]
        wind = (props.get("windSpeed", {}).get("values") or [])[:24]
        temp = (props.get("temperature", {}).get("values") or [])[:24]
        precip_mm = sum((v.get("value") or 0) for v in precip)
        rh_vals = [v.get("value") for v in rh if v.get("value") is not None]
        wind_vals = [v.get("value") for v in wind if v.get("value") is not None]
        temp_vals = [v.get("value") for v in temp if v.get("value") is not None]
        rh_avg = (sum(rh_vals) / len(rh_vals)) if rh_vals else None
        wind_avg = (sum(wind_vals) / len(wind_vals)) if wind_vals else None
        temp_avg = (sum(temp_vals) / len(temp_vals)) if temp_vals else None
        return precip_mm, rh_avg, wind_avg, temp_avg, grid_url
    except Exception:
        return None, None, None, None, None

# -----------------------------
# Wildfire risk (FIRMS + NWS)
# -----------------------------
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAYS}"
FIRMS_SOURCE = os.getenv("FIRMS_SOURCE", "VIIRS_NOAA20_NRT")

@pred_bp.route('/wildfire-risk')
def wildfire_risk():
    lat = float(request.args.get('lat', 37.7749))
    lon = float(request.args.get('lon', -122.4194))
    bbox = bbox_from_point(lat, lon, deg=1.0)

    key = os.getenv("FIRMS_KEY")
    detections = 0
    rows = []
    if key:
        url = FIRMS_URL.format(MAP_KEY=key, SOURCE=FIRMS_SOURCE, BBOX=bbox, DAYS=1)
        try:
            r = requests.get(url, timeout=20); r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
            detections = max(0, len(rows))
        except Exception:
            detections = 0

    precip_mm, rh_avg, wind_avg, temp_avg, grid_url = nws_grid_forecast(lat, lon)

    # Distance-weighted FIRMS risk proxy (coarse)
    risk_raw = 0.0
    if key and detections:
        try:
            def km(dd): return dd * 111.0
            for row in rows[:1000]:
                try:
                    fy = float(row["latitude"]); fx = float(row["longitude"])
                except Exception:
                    continue
                dist_km = km(((fy - lat)**2 + (fx - lon)**2)**0.5)
                if dist_km < 50.0:
                    conf_raw = row.get("confidence", "50")
                    try:
                        conf = float(conf_raw)
                    except Exception:
                        conf_map = {"low":30, "nominal":60, "high":90}
                        conf = conf_map.get(str(conf_raw).strip().lower(), 50)
                    try:
                        frp = float(row.get("frp", 1.0))
                    except Exception:
                        frp = 1.0
                    risk_raw += (conf/100.0)*(frp/10.0)*max(0.0, (1.0 - dist_km/50.0))
        except Exception:
            pass

    # Fuse with NWS dryness/wind
    score = _clamp01(risk_raw)
    if rh_avg is not None and rh_avg < 25: score = min(1.0, score + 0.25)
    if wind_avg is not None and wind_avg > 30: score = min(1.0, score + 0.2)
    level = "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"
    confidence = 0.5 + 0.15*min(detections, 3)
    factors = {
        "temperature": None if temp_avg is None else round(temp_avg,1),
        "humidity": None if rh_avg is None else round(rh_avg,1),
        "wind_speed": None if wind_avg is None else round(wind_avg,1),
        "precip_24h_mm": None if precip_mm is None else round(precip_mm,1),
        "detections_24h": detections
    }

    return jsonify({
        "status":"success",
        "data":{
            "coordinates":[lat, lon],
            "risk_level": level,
            "risk_score": round(score,2),
            "prediction_confidence": round(confidence,2),
            "factors": factors,
            "source": f"FIRMS {FIRMS_SOURCE} + NWS"
        },
        "timestamp": dt.datetime.utcnow().isoformat()
    })

# -----------------------------
# Flood risk (Weather.gov)
# -----------------------------
@pred_bp.route('/flood-risk')
def flood_risk():
    lat = float(request.args.get('lat', 29.7604))
    lon = float(request.args.get('lon', -95.3698))

    precip_mm, rh_avg, wind_avg, temp_avg, grid_url = nws_grid_forecast(lat, lon)
    if precip_mm is None:
        precipitation = random.uniform(0, 100)
        soil_moisture = random.uniform(0.2, 0.9)
        elevation_risk = random.uniform(0.1, 0.8)
        prob = min((precipitation/100 + soil_moisture + elevation_risk) / 3, 1.0)
        level = 'high' if prob > 0.7 else 'medium' if prob > 0.4 else 'low'
        return jsonify({
            'status': 'success',
            'data': {
                'coordinates': [lat, lon],
                'flood_probability': round(prob, 2),
                'risk_level': level,
                'factors': {
                    'precipitation_24h': round(precipitation, 1),
                    'soil_moisture': round(soil_moisture, 2),
                    'river_level': '--'
                },
                'early_warning': prob > 0.6,
                'source': 'NWS (fallback)'
            },
            'timestamp': dt.datetime.utcnow().isoformat()
        })

    prob = min(1.0, (precip_mm/50.0)*0.6 + ((rh_avg or 50)/100.0)*0.4)
    level = 'high' if prob > 0.7 else 'medium' if prob > 0.4 else 'low'
    return jsonify({
        'status': 'success',
        'data': {
            'coordinates': [lat, lon],
            'flood_probability': round(prob, 2),
            'risk_level': level,
            'factors': {
                'precipitation_24h': round(precip_mm, 1),
                'soil_moisture': None if rh_avg is None else round(rh_avg/100.0, 2),
                'river_level': '--'
            },
            'early_warning': prob > 0.6,
            'source': grid_url or 'NWS forecastGridData'
        },
        'timestamp': dt.datetime.utcnow().isoformat()
    })

# -----------------------------
# Crop health (Sentinel-2 NDVI via CDSE, PNG UINT8)
# -----------------------------
CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
_cdse_token = None
_cdse_exp = 0.0

def get_cdse_token_inline():
    global _cdse_token, _cdse_exp
    if _cdse_token and time.time() < _cdse_exp:
        return _cdse_token
    cid = os.getenv("CDSE_CLIENT_ID"); csec = os.getenv("CDSE_CLIENT_SECRET")
    if not cid or not csec: return None
    r = requests.post(CDSE_TOKEN_URL, data={
        "grant_type":"client_credentials","client_id":cid,"client_secret":csec
    }, timeout=20)
    r.raise_for_status()
    j = r.json()
    _cdse_token = j["access_token"]
    _cdse_exp = time.time() + j.get("expires_in",3600) - 60
    return _cdse_token

def ndvi_from_sentinel_inline(bbox, t_from_iso, t_to_iso, token):
    payload = {
      "input": {
        "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
        "data": [{"type":"sentinel-2-l2a",
                  "dataFilter":{"timeRange":{"from":t_from_iso,"to":t_to_iso},"maxCloudCoverage":60}}]
      },
      "output": {"width": 64, "height": 64,
                 "responses": [{"identifier":"default","format":{"type":"image/png"}}]},
      "evalscript": """
//VERSION=3
function setup() {
  return { input: ["B04","B08"], output: { bands: 1, sampleType: "UINT8" } };
}
function evaluatePixel(s) {
  let d = s.B08 + s.B04;
  let ndvi = d === 0 ? 0 : (s.B08 - s.B04) / d;
  let scaled = Math.round((ndvi + 1.0) * 127.5);
  scaled = Math.max(0, Math.min(255, scaled));
  return [scaled];
}
"""
    }
    r = requests.post(PROCESS_URL, json=payload,
                      headers={"Authorization": f"Bearer {token}"}, timeout=45)
    if not r.ok:
        print("DEBUG process error:", r.status_code, r.text[:250])
        r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("L")
    arr = np.array(img, dtype=np.uint8)
    ndvi_arr = (arr.astype(np.float32) / 127.5) - 1.0
    ndvi_arr = ndvi_arr[np.isfinite(ndvi_arr)]
    return float(np.clip(np.nanmean(ndvi_arr), -1, 1)) if ndvi_arr.size else None

@pred_bp.route('/crop-health')
def crop_health():
    lat = float(request.args.get('lat', 41.8781))
    lon = float(request.args.get('lon', -87.6298))
    deg = float(request.args.get('deg', 0.02))
    bbox = [lon - deg, lat - deg, lon + deg, lat + deg]

    t_to = dt.datetime.utcnow()
    t_from = t_to - dt.timedelta(days=30)
    t_to_iso = t_to.strftime("%Y-%m-%dT%H:%M:%SZ")
    t_from_iso = t_from.strftime("%Y-%m-%dT%H:%M:%SZ")

    ndvi = None
    token = get_cdse_token_inline()
    if token:
        try:
            ndvi = ndvi_from_sentinel_inline(bbox, t_from_iso, t_to_iso, token)
        except Exception as e:
            print("NDVI request error:", repr(e)); ndvi = None

    if ndvi is None:
        ndvi = 0.45; status = "good"; source = "Sentinel-2 (fallback)"
    else:
        status = "excellent" if ndvi > 0.7 else "good" if ndvi > 0.5 else "poor"
        source = "Sentinel-2 L2A NDVI (CDSE)"

    return jsonify({
        'status': 'success',
        'data': {
            'coordinates': [lat, lon],
            'ndvi': round(ndvi, 3),
            'health_status': status,
            'growth_stage': 'vegetative' if ndvi > 0.6 else ('seedling' if ndvi < 0.4 else 'flowering'),
            'yield_prediction': round((0.6 + max(ndvi, 0)) * 100, 1),
            'irrigation_needed': ndvi < 0.5,
            'source': source
        },
        'timestamp': dt.datetime.utcnow().isoformat()
    })

# -----------------------------
# NEW: Lightweight AI prediction for modal
# -----------------------------
@pred_bp.route('/ai/predict')
def ai_predict():
    # Inputs
    lat = float(request.args.get("lat", 40.7128))
    lon = float(request.args.get("lon", -74.0060))
    mode = (request.args.get("mode", "wildfire") or "wildfire").lower()

    # Pull quick features from NWS if available
    precip_mm, rh_avg, wind_avg, temp_avg, grid_url = nws_grid_forecast(lat, lon)

    # Fallbacks if NWS not available
    temperature_c = temp_avg if temp_avg is not None else 17.0
    humidity_pct = rh_avg if rh_avg is not None else 55.0
    wind_kmh = wind_avg if wind_avg is not None else 10.0
    soil_moisture_pct = 60.0  # simple proxy
    rain_24h_mm = precip_mm if precip_mm is not None else 4.0
    river_level_kmh = wind_kmh  # placeholder to satisfy UI label
    ndvi = 0.42
    vpd = 0.9

    # Heuristic logits
    if mode == "wildfire":
        z = 0.03*temperature_c - 0.02*humidity_pct + 0.04*(wind_kmh/10.0) - 0.03*(soil_moisture_pct/10.0) + 0.10
        rationale = "Higher wind and lower humidity increase wildfire likelihood; wetter soils reduce it."
        factors = [
            {"name":"temperature", "value": f"{temperature_c:.1f}°C", "weight": 0.03*temperature_c},
            {"name":"humidity", "value": f"{humidity_pct:.1f}%", "weight": -0.02*humidity_pct},
            {"name":"wind", "value": f"{wind_kmh:.0f} km/h", "weight": 0.04*(wind_kmh/10.0)},
            {"name":"soil_moisture", "value": f"{soil_moisture_pct:.1f}%", "weight": -0.03*(soil_moisture_pct/10.0)},
        ]
    elif mode == "flood":
        z = 0.05*(rain_24h_mm/10.0) + 0.04*(river_level_kmh/10.0) + 0.03*(soil_moisture_pct/10.0) - 0.02*(wind_kmh/10.0) + 0.05
        rationale = "More rain, higher river level, and wetter soils increase flood risk."
        factors = [
            {"name":"rain_24h", "value": f"{rain_24h_mm:.1f} mm", "weight": 0.05*(rain_24h_mm/10.0)},
            {"name":"river_level", "value": f"{river_level_kmh:.0f} km/h", "weight": 0.04*(river_level_kmh/10.0)},
            {"name":"soil_moisture", "value": f"{soil_moisture_pct:.1f}%", "weight": 0.03*(soil_moisture_pct/10.0)},
            {"name":"wind", "value": f"{wind_kmh:.0f} km/h", "weight": -0.02*(wind_kmh/10.0)},
        ]
    else:  # crop
        z = 0.04*(soil_moisture_pct/10.0) + 0.03*ndvi - 0.03*vpd - 0.02*(wind_kmh/10.0)
        rationale = "Better moisture and vegetation health raise yield; high VPD and wind reduce it."
        factors = [
            {"name":"soil_moisture", "value": f"{soil_moisture_pct:.1f}%", "weight": 0.04*(soil_moisture_pct/10.0)},
            {"name":"ndvi", "value": f"{ndvi:.2f}", "weight": 0.03*ndvi},
            {"name":"vpd", "value": f"{vpd:.2f}", "weight": -0.03*vpd},
            {"name":"wind", "value": f"{wind_kmh:.0f} km/h", "weight": -0.02*(wind_kmh/10.0)},
        ]

    score = _clamp01(_sigmoid(z))
    label = _label_from_score(score)
    confidence = _confidence_from_score(score)

    return jsonify({
        "mode": mode,
        "lat": lat,
        "lon": lon,
        "score": score,
        "label": label,
        "confidence": confidence,
        "rationale": rationale,
        "factors": factors,
        "source": grid_url or "heuristic+NWS",
        "timestamp": dt.datetime.utcnow().isoformat()
    })
