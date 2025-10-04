# backend/routes/tasking.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import time

# Blueprint lives under /api/tasking (matches frontend)
bp_tasking = Blueprint("tasking", __name__, url_prefix="/api/tasking")

# In-memory demo store (clears on server restart)
JOBS = {}

def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _demo_artifact_path():
    # Serve a static image placed at frontend/assets/demo_task.png
    # If Flask is configured to serve ../frontend with static_url_path="/",
    # this relative URL will resolve in the browser.
    return "/assets/demo_task.png"

@bp_tasking.route("", methods=["GET"])
def tasking_point_lookup():
    """
    Lightweight point lookup for UI overlays.
    Example: GET /api/tasking?lat=..&lon=..&mode=wildfire
    Returns a quick ETA and suggested action (no job is created).
    """
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        mode = (request.args.get("mode") or "wildfire").lower()

        # Simple demo signals
        eta_hours = 8 if mode == "wildfire" else 10
        eta = datetime.utcnow() + timedelta(hours=eta_hours)
        cloud_risk = 0.25 if mode == "wildfire" else 0.35

        return jsonify({
            "status": "success",
            "platform": "Sentinel-2",
            "eta": eta.strftime("%Y-%m-%dT%H:%MZ"),
            "cloud_risk": cloud_risk,
            "recommendation": "Optical confirm" if cloud_risk < 0.5 else "Radar tasking",
            "center": {"lat": lat, "lon": lon},
            "mode": mode
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@bp_tasking.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.get_json(force=True) or {}
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        mode = (data.get("mode") or "wildfire").lower()
        confidence = float(data.get("confidence", 0))

        task_id = f"T{int(time.time())}"

        JOBS[task_id] = {
            "id": task_id,
            "created": _now_iso(),
            "status": "queued",
            "progress": 0,
            "center": {"lat": lat, "lon": lon},
            "mode": mode,
            "confidence": confidence,
            "artifact": None,
        }
        return jsonify({"id": task_id, "status": "queued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@bp_tasking.route("/status", methods=["GET"])
def status():
    try:
        task_id = request.args.get("id")
        if not task_id or task_id not in JOBS:
            return jsonify({"status": "error", "message": "unknown id"}), 404

        job = JOBS[task_id]

        # Advance state machine on each poll
        if job["status"] == "queued":
            job["status"] = "running"
            job["progress"] = 10
        elif job["status"] == "running":
            job["progress"] = min(100, job["progress"] + 25)
            if job["progress"] >= 100:
                job["status"] = "done"
                job["artifact"] = _demo_artifact_path()

        return jsonify({
            "id": job["id"],
            "status": job["status"],
            "progress": job.get("progress"),
            "artifact": job.get("artifact"),
            "center": job.get("center"),
            "mode": job.get("mode"),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@bp_tasking.route("/info", methods=["GET"])
def info():
    """
    Convenience endpoint for one-off estimates.
    """
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        now = datetime.utcnow()
        eta = now + timedelta(hours=10)
        cloud_risk = 0.35
        return jsonify({
            "status": "success",
            "platform": "Sentinel-2",
            "eta": eta.strftime("%Y-%m-%dT%H:%MZ"),
            "cloud_risk": cloud_risk,
            "note": "High value target; optical confirm recommended",
            "center": {"lat": lat, "lon": lon}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
