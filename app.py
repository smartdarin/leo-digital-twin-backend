from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import random
from datetime import datetime, timedelta

from routes.satellite_data import satellite_bp
from routes.predictions import pred_bp
from routes.spread import bp_spread           # legacy/static spread endpoints
from routes.tasking import bp_tasking
from routes.triage import bp_triage
from spread_api import bp_spread_live
from routes.backtest import bp_backtest         # new live spread endpoint
from routes.flood import flood_bp

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)

# Register each blueprint once, with a single unique name each
app.register_blueprint(bp_tasking)
app.register_blueprint(bp_spread)   
app.register_blueprint(flood_bp)                          # no prefix (legacy UI paths)
app.register_blueprint(bp_triage,     url_prefix="/api")
app.register_blueprint(satellite_bp,  url_prefix="/api")
app.register_blueprint(pred_bp,       url_prefix="/api")
app.register_blueprint(bp_spread_live, url_prefix="/api")  
app.register_blueprint(bp_backtest, url_prefix="/api")   # exposes /api/spread

@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")

# ... keep your mock endpoints here (wildfire-risk, flood-risk, crop-health, etc.) ...

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


# Mock NASA API endpoints (you can replace with real APIs later)
class SatelliteDataService:
    @staticmethod
    def get_wildfire_risk(lat, lon):
        # Simulate wildfire risk calculation
        base_risk = random.uniform(0.1, 0.9)
        temperature_factor = random.uniform(0.8, 1.2)
        humidity_factor = random.uniform(0.7, 1.1)
        
        risk_score = min(base_risk * temperature_factor * (2 - humidity_factor), 1.0)
        
        return {
            "coordinates": [lat, lon],
            "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low",
            "risk_score": round(risk_score, 2),
            "factors": {
                "temperature": round(25 + random.uniform(0, 15), 1),
                "humidity": round(30 + random.uniform(0, 40), 1),
                "wind_speed": round(random.uniform(5, 25), 1)
            },
            "prediction_confidence": round(random.uniform(0.75, 0.95), 2)
        }
    
    @staticmethod
    def get_flood_risk(lat, lon):
        # Simulate flood risk calculation
        precipitation = random.uniform(0, 100)
        soil_moisture = random.uniform(0.2, 0.9)
        elevation_risk = random.uniform(0.1, 0.8)
        
        flood_probability = min((precipitation/100 + soil_moisture + elevation_risk) / 3, 1.0)
        
        return {
            "coordinates": [lat, lon],
            "flood_probability": round(flood_probability, 2),
            "risk_level": "high" if flood_probability > 0.7 else "medium" if flood_probability > 0.4 else "low",
            "factors": {
                "precipitation_24h": round(precipitation, 1),
                "soil_moisture": round(soil_moisture, 2),
                "river_level": round(random.uniform(0.5, 2.5), 1)
            },
            "early_warning": flood_probability > 0.6
        }
    
    @staticmethod
    def get_crop_health(lat, lon):
        # Simulate crop health monitoring
        ndvi = random.uniform(0.2, 0.9)  # Normalized Difference Vegetation Index
        
        return {
            "coordinates": [lat, lon],
            "ndvi": round(ndvi, 3),
            "health_status": "excellent" if ndvi > 0.7 else "good" if ndvi > 0.5 else "poor",
            "growth_stage": random.choice(["seedling", "vegetative", "flowering", "maturity"]),
            "yield_prediction": round(random.uniform(70, 120), 1),  # % of expected yield
            "irrigation_needed": ndvi < 0.5
        }

@app.route('/')
def home():
    return jsonify({
        "message": "LEO Digital Twin Earth API",
        "version": "1.0",
        "endpoints": [
            "/api/wildfire-risk",
            "/api/flood-risk", 
            "/api/crop-health",
            "/api/satellite-status",
            "/api/cost-savings"
        ]
    })

@app.route('/api/wildfire-risk')
def wildfire_risk():
    lat = float(request.args.get('lat', 37.7749))
    lon = float(request.args.get('lon', -122.4194))
    
    risk_data = SatelliteDataService.get_wildfire_risk(lat, lon)
    
    return jsonify({
        "status": "success",
        "data": risk_data,
        "timestamp": datetime.now().isoformat(),
        "source": "LEO Satellite Constellation"
    })

@app.route('/api/flood-risk')
def flood_risk():
    lat = float(request.args.get('lat', 29.7604))
    lon = float(request.args.get('lon', -95.3698))
    
    flood_data = SatelliteDataService.get_flood_risk(lat, lon)
    
    return jsonify({
        "status": "success",
        "data": flood_data,
        "timestamp": datetime.now().isoformat(),
        "source": "LEO Satellite Constellation"
    })

@app.route('/api/crop-health')
def crop_health():
    lat = float(request.args.get('lat', 41.8781))
    lon = float(request.args.get('lon', -87.6298))
    
    crop_data = SatelliteDataService.get_crop_health(lat, lon)
    
    return jsonify({
        "status": "success",
        "data": crop_data,
        "timestamp": datetime.now().isoformat(),
        "source": "LEO Satellite Constellation"
    })

@app.route('/api/satellite-status')
def satellite_status():
    # Simulate LEO constellation status
    satellites = []
    for i in range(12):
        satellites.append({
            "id": f"LEO-SAT-{i+1:03d}",
            "status": random.choice(["operational", "operational", "operational", "maintenance"]),
            "coverage_area": f"Zone-{i+1}",
            "data_quality": round(random.uniform(0.85, 0.99), 2),
            "last_update": (datetime.now() - timedelta(minutes=random.randint(1, 30))).isoformat()
        })
    
    return jsonify({
        "status": "success",
        "constellation_health": "optimal",
        "total_satellites": len(satellites),
        "operational": len([s for s in satellites if s["status"] == "operational"]),
        "satellites": satellites
    })

@app.route('/api/cost-savings')
def cost_savings():
    # Calculate potential cost savings from early warnings
    scenarios = {
        "wildfire_prevention": {
            "average_damage_without_warning": 50000000,  # $50M
            "average_damage_with_warning": 5000000,     # $5M
            "prevention_success_rate": 0.85,
            "annual_incidents": 100
        },
        "flood_prevention": {
            "average_damage_without_warning": 25000000,  # $25M
            "average_damage_with_warning": 2500000,     # $2.5M
            "prevention_success_rate": 0.75,
            "annual_incidents": 150
        }
    }
    
    total_savings = 0
    details = {}
    
    for scenario, data in scenarios.items():
        savings_per_incident = (data["average_damage_without_warning"] - 
                              data["average_damage_with_warning"]) * data["prevention_success_rate"]
        annual_savings = savings_per_incident * data["annual_incidents"]
        total_savings += annual_savings
        
        details[scenario] = {
            "savings_per_incident": savings_per_incident,
            "annual_savings": annual_savings,
            "success_rate": data["prevention_success_rate"]
        }
    
    return jsonify({
        "status": "success",
        "total_annual_savings": total_savings,
        "details": details,
        "roi_projection": {
            "system_cost": 100000000,  # $100M
            "payback_period_months": round((100000000 / total_savings) * 12, 1),
            "5_year_net_benefit": (total_savings * 5) - 100000000
        }
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
