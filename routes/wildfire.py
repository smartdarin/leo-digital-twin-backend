# routes/wildfire.py
import os, math, requests
from flask import Blueprint, request, jsonify

wildfire_bp = Blueprint('wildfire', __name__)

def bbox(lat, lon, km=25):
    dlat = km / 110.574
    dlon = km / (111.320 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat

@wildfire_bp.get('/api/wildfire-risk')
def wildfire_risk():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))

    # 1) NASA FIRMS VIIRS last 24h for bbox
    minx, miny, maxx, maxy = bbox(lat, lon, km=25)
    # Public FIRMS CSV endpoint example (no key) – adjust for region/global as needed:
    # Docs: https://firms.modaps.eosdis.nasa.gov/active_fire/
    firms_url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/VIIRS_NOAA20_NRT/world/24h?xmin={minx}&ymin={miny}&xmax={maxx}&ymax={maxy}'
    fires_csv = requests.get(firms_url, timeout=10)
    detections_24h = 0
    if fires_csv.ok and 'latitude' in fires_csv.text:
        # very simple count (can parse CSV properly with csv module)
        detections_24h = max(0, len([ln for ln in fires_csv.text.splitlines()[1:] if ln.strip()]))

    # 2) NOAA NWS weather
    points = requests.get(f'https://api.weather.gov/points/{lat},{lon}',
                          headers={'User-Agent':'LEO-DTE/1.0 (email@example.com)'},
                          timeout=10)
    humidity = None
    wind = None
    temp_c = None
    if points.ok:
        grid = points.json()['properties'].get('forecastGridData')
        if grid:
            gridj = requests.get(grid,
                                 headers={'Accept':'application/geo+json',
                                          'User-Agent':'LEO-DTE/1.0 (email@example.com)'},
                                 timeout=10)
            if gridj.ok:
                g = gridj.json().get('properties', {})
                rh_vals = (g.get('relativeHumidity', {}).get('values') or [])[:1]
                ws_vals = (g.get('windSpeed', {}).get('values') or [])[:1]
                t_vals  = (g.get('temperature', {}).get('values') or [])[:1]
                humidity = (rh_vals[0]['value'] if rh_vals else None)
                wind = (ws_vals[0]['value'] if ws_vals else None)
                temp_c = (t_vals[0]['value'] if t_vals else None)

    # 3) Simple risk score from detections + weather
    score = 0.0
    if humidity is not None and humidity < 30: score += 0.3
    if wind is not None and wind > 30: score += 0.3
    if detections_24h > 0: score += min(0.4, 0.05 * detections_24h)

    data = {
        'risk_level': 'high' if score > 0.7 else 'medium' if score > 0.35 else 'low',
        'risk_score': round(score, 2),
        'prediction_confidence': 0.6,  # can compute if you add more signals
        'factors': {
            'temperature': round(temp_c, 1) if temp_c is not None else None,
            'humidity': round(humidity, 1) if humidity is not None else None,
            'wind_speed': round(wind, 1) if wind is not None else None,
            'detections_24h': detections_24h
        }
    }
    return jsonify({'data': data})
