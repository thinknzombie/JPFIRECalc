"""
API blueprint — JSON endpoints for HTMX and future JS consumers.

Routes:
  GET  /api/scenarios                    → list all scenario summaries
  GET  /api/scenarios/<id>               → full scenario result as JSON
  POST /api/scenarios/<id>/run           → run calculation, return JSON
  GET  /api/nhi-estimate                 → quick NHI estimate (query params)
  GET  /api/fire-number                  → quick FIRE number (query params)
"""
from flask import Blueprint, jsonify, request, current_app
from models.profile import FinancialProfile
from models.scenario import Scenario, AssumptionSet
from engine.fire_calculator import run_fire_scenario, calculate_fire_number
from engine.nhi_calculator import solve_withdrawal_with_nhi
import storage.scenario_store as store

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/scenarios")
def list_scenarios():
    store.init_store(current_app.config["SCENARIOS_DIR"])
    all_scenarios = store.load_all()
    summaries = []
    for profile, scenario in all_scenarios:
        summaries.append({
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "region": scenario.region,
            "fire_variant": scenario.assumptions.fire_variant,
            "withdrawal_rate_pct": scenario.assumptions.withdrawal_rate_pct,
        })
    return jsonify(summaries)


@api_bp.route("/scenarios/<scenario_id>")
def get_scenario(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404

    result = run_fire_scenario(
        profile=profile,
        scenario_name=scenario.name,
        scenario_id=scenario.id,
        assumptions=scenario.assumptions,
        region_key=scenario.region,
    )
    return jsonify(result.to_dict())


@api_bp.route("/scenarios/<scenario_id>/run", methods=["POST"])
def run_scenario(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404

    result = run_fire_scenario(
        profile=profile,
        scenario_name=scenario.name,
        scenario_id=scenario.id,
        assumptions=scenario.assumptions,
        region_key=scenario.region,
    )
    return jsonify(result.to_dict())


@api_bp.route("/nhi-estimate")
def nhi_estimate():
    """
    Quick NHI estimate for HTMX live-preview.
    Query params: withdrawal_jpy, members, municipality_key, age
    """
    try:
        withdrawal = int(request.args.get("withdrawal_jpy", 3_000_000))
        members = int(request.args.get("members", 1))
        municipality = request.args.get("municipality_key", "national_average")
        age = int(request.args.get("age", 55))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid parameters"}), 400

    result = solve_withdrawal_with_nhi(
        target_net_expenses=withdrawal,
        num_members=members,
        municipality_key=municipality,
        age=age,
    )
    return jsonify({
        "nhi_annual_jpy": result["nhi_premium"],
        "total_withdrawal_jpy": result["gross_withdrawal"],
        "monthly_nhi_jpy": result["nhi_premium"] // 12,
    })


@api_bp.route("/fire-number")
def fire_number():
    """
    Quick FIRE number estimate.
    Query params: annual_expenses_jpy, withdrawal_rate_pct, net_pension_annual_jpy
    """
    try:
        expenses = int(request.args.get("annual_expenses_jpy", 3_000_000))
        wr = float(request.args.get("withdrawal_rate_pct", 3.5)) / 100
        pension = int(request.args.get("net_pension_annual_jpy", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid parameters"}), 400

    result = calculate_fire_number(expenses, wr, pension)
    return jsonify(result)
