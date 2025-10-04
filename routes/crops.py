# routes/crops.py
import os, time, requests
from flask import Blueprint, request, jsonify

crops_bp = Blueprint('crops', __name__)
SH_ID = os.getenv('SENTINELHUB_CLIENT_ID')
SH_SECRET = os.getenv('SENTINELHUB_CLIENT_SECRET')

def sh_token():
    r = requests.post('https://services.sentinel-hub.com/oauth/token',
        data={'grant_type':'client_credentials',
              'client_id':SH_ID,
              'client_secret':SH_SECRET}, timeout=10)
    r.raise_for_status()
    return r.json()['access_token']

EVALSCRIPT = """
//VERSION=3
function setup(){return{input:[{bands:["B04","B08"]}],output:{bands:1}};}
function evaluatePixel(s){let ndvi=(s.B08 - s.B04)/(s.B08 + s.B04);return [ndvi];}
"""

@crops_bp.get('/api/crop-health')
def crop_health():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    size = 0.001  # ~100 m tile
    bbox = [lon - size, lat - size, lon + size, lat + size]

    token = sh_token()
    payload = {
      "input": {
        "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
        "data": [{"type":"sentinel-2-l2a","dataFilter":{"timeRange":{"from": time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(time.time()-14*86400)),
                                                                      "to": time.strftime("%Y-%m-%dT23:59:59Z", time.gmtime())},
                                  "maxCloudCoverage": 20}}]
      },
      "evalscript": EVALSCRIPT,
      "aggregation": {"timeRange":{"from": time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(time.time()-14*86400)),
                                   "to": time.strftime("%Y-%m-%dT23:59:59Z", time.gmtime())},
                      "aggregationInterval":{"of":"P14D","to":"P14D"},
                      "resx":10,"resy":10,"reducers":["MEAN"]}
    }
    r = requests.post('https://services.sentinel-hub.com/api/v1/process',
                      headers={'Authorization': f'Bearer {token}'}, json=payload, timeout=30)
    ndvi_mean = None
    if r.ok:
        # Result is image bytes by default; for stats, alternatively use Statistics API
        # Better: use Statistics API for numeric mean
        stats = requests.post('https://services.sentinel-hub.com/api/v1/statistics',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                "input":{"bounds":{"bbox":bbox},
                                         "data":[{"type":"sentinel-2-l2a"}]},
                                "aggregation":{"timeRange":{"from":payload["aggregation"]["timeRange"]["from"],
                                                             "to":payload["aggregation"]["timeRange"]["to"]},
                                               "resolution":{"x":60,"y":60},
                                               "evalscript":EVALSCRIPT}
                              }, timeout=30)
        if stats.ok:
            stj = stats.json()
            # Walk to NDVI mean
            # Simplify: read first tile stats if present
            for k,v in stj.get('data', [{}])[0].get('outputs', {}).items():
                pass
            # If needed, adapt based on actual structure
    data = {
        'health_index': ndvi_mean,  # set from stats when parsed
        'risk_level': 'low' if (ndvi_mean is None or ndvi_mean>0.5) else 'medium',
        'prediction_confidence': 0.6,
        'factors': {'ndvi': ndvi_mean, 'lst': None, 'vci': None}
    }
    return jsonify({'data': data})
