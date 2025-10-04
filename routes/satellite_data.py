from flask import Blueprint, jsonify, request
import random, datetime

satellite_bp = Blueprint('satellite', __name__)

@satellite_bp.route('/satellite-status')
def satellite_status():
    now = datetime.datetime.utcnow().isoformat()
    sats = [{'id': f'LEO-SAT-{i:03d}', 'status': 'operational', 'last_update': now} for i in range(1, 13)]
    return jsonify({'status': 'success', 'constellation_health': 'optimal', 'operational': len(sats), 'satellites': sats})


@satellite_bp.route('/cost-savings')
def cost_savings():
    scenarios = {
        'wildfire_prevention': {'without': 50_000_000, 'with': 5_000_000, 'success': 0.85, 'annual': 100},
        'flood_prevention': {'without': 25_000_000, 'with': 2_500_000, 'success': 0.75, 'annual': 150},
    }
    total = 0; details = {}
    for k,v in scenarios.items():
        per = (v['without'] - v['with']) * v['success']
        ann = per * v['annual']; total += ann
        details[k] = {'savings_per_incident': per, 'annual_savings': ann, 'success_rate': v['success']}
    return jsonify({'status':'success','total_annual_savings': total,
                    'details': details,
                    'roi_projection': {'system_cost': 100_000_000,
                                       'payback_period_months': round((100_000_000/total)*12,1),
                                       '5_year_net_benefit': total*5 - 100_000_000}})
