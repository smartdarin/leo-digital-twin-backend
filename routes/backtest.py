# backend/routes/backtest.py
from flask import Blueprint, jsonify, request
import time

bp_backtest = Blueprint("backtest", __name__)

# Static demo metrics; swap to CSV/DB lookup later
AGG_METRICS = {"precision": 0.82, "recall": 0.74, "lead_time_h": 6.3}
CASES = [
    {
        "id": "case_colville",
        "region": "Colville",
        "start": "2024-07-01",
        "end": "2024-07-07",
        "precision": 0.84,
        "recall": 0.72,
        "lead_time_h": 7.1,
    },
    {
        "id": "case_sonoma",
        "region": "Sonoma",
        "start": "2024-09-11",
        "end": "2024-09-16",
        "precision": 0.79,
        "recall": 0.75,
        "lead_time_h": 5.5,
    },
]

@bp_backtest.route("/backtest", methods=["GET"])
def backtest():
    return jsonify({
        "status": "success",
        "generated_at": int(time.time()),
        "metrics": AGG_METRICS,
        "cases": CASES
    })

@bp_backtest.route("/validate/spread", methods=["GET"])
def validate_spread():
    """
    Minimal validation helper for the demo:
    accepts predicted_angle_deg and expected_angle_deg as query params,
    returns absolute error in degrees.
    Example: /api/validate/spread?predicted_angle_deg=40&expected_angle_deg=45
    """
    try:
        pred = float(request.args.get("predicted_angle_deg"))
        exp  = float(request.args.get("expected_angle_deg"))
    except Exception:
        return jsonify({"error": "invalid predicted/expected"}), 400
    err = pred - exp
    return jsonify({
        "predicted_angle_deg": pred,
        "expected_angle_deg": exp,
        "error_deg": err,
        "abs_error_deg": abs(err),
        "validated_at": int(time.time())
    })
