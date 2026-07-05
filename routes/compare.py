"""
Comparison blueprint — side-by-side scenario comparison.

Routes:
  GET  /compare                → comparison page (query: ?ids=id1&ids=id2&...)
  GET  /api/compare            → JSON payload for all selected scenarios
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify
from engine.fire_calculator import run_fire_scenario
import storage.scenario_store as store

logger = logging.getLogger(__name__)

compare_bp = Blueprint("compare", __name__, url_prefix="/compare")


def _load_results(scenario_ids: list[str]) -> list[dict]:
    """Load and run up to 5 scenarios, returning list of result dicts."""
    results = []
    for sid in scenario_ids[:5]:   # cap at 5
        try:
            profile, scenario = store.load(sid)
        except FileNotFoundError:
            continue
        try:
            result = run_fire_scenario(
                profile=profile,
                scenario_name=scenario.name,
                scenario_id=scenario.id,
                assumptions=scenario.assumptions,
                region_key=scenario.region,
            )
        except Exception:
            logger.exception(
                "Engine error in compare for scenario %s (%s)", sid, scenario.name
            )
            continue
        results.append({
            "scenario": scenario,
            "profile": profile,
            "result": result,
        })
    return results


@compare_bp.route("/")
def index():
    store.init_store(current_app.config["SCENARIOS_DIR"])
    ids = request.args.getlist("ids")

    if not ids:
        return redirect(url_for("scenarios.index"))

    items = _load_results(ids)

    if not items:
        from flask import flash
        flash("None of the selected scenarios could be loaded.", "error")
        return redirect(url_for("scenarios.index"))

    # All available scenarios for the "add to comparison" selector
    all_scenarios = store.load_all()

    return render_template(
        "compare.html",
        items=items,
        selected_ids=ids,
        all_scenarios=all_scenarios,
        title="Scenario Comparison",
    )


@compare_bp.route("/api")
def api():
    store.init_store(current_app.config["SCENARIOS_DIR"])
    ids = request.args.getlist("ids")
    items = _load_results(ids)
    payload = []
    for item in items:
        r = item["result"]
        payload.append({
            "id": item["scenario"].id,
            "name": item["scenario"].name,
            "fire_variant": item["scenario"].assumptions.fire_variant,
            "fire_number_jpy": r.fire_number_jpy,
            "years_to_fire": r.years_to_fire,
            "fire_age": r.fire_age,
            "progress_pct": r.progress_pct,
            "success_rate_pct": r.monte_carlo.success_rate_pct if r.monte_carlo else None,
            # Model B1': WR Budget (portfolio x WR) is what Monte Carlo and the
            # trajectory actually withdraw, independent of FIRE variant.
            # annual_expenses_jpy remains the STATED (variant-aware) figure,
            # used only to size the FIRE number and the deemed-WR check.
            "wr_budget_annual_jpy": r.wr_budget_annual_jpy,
            "deemed_wr_gap_pct": r.deemed_wr_gap_pct,
            "deemed_wr_steady_pct": r.deemed_wr_steady_pct,
            "annual_expenses_jpy": r.active_annual_expenses_jpy,
            "annual_pension_net_jpy": r.annual_pension_net_jpy,
            "annual_nhi_jpy": r.active_annual_nhi_jpy,
            "annual_withdrawal_needed_jpy": r.active_annual_withdrawal_jpy,
            "nisa_at_retirement_jpy": r.nisa_at_retirement_jpy,
            "ideco_at_retirement_jpy": r.ideco_at_retirement_jpy,
            "coast_fire_number_jpy": r.coast_fire_number_jpy,
            "coast_fire_reached": r.coast_fire_reached,
            "investment_return_pct": item["scenario"].assumptions.investment_return_pct,
            "retirement_return_pct": item["scenario"].assumptions.retirement_return_pct,
            "withdrawal_rate_pct": item["scenario"].assumptions.withdrawal_rate_pct,
            "retirement_expense_growth_pct": item["scenario"].assumptions.retirement_expense_growth_pct,
            "trajectory_p50": [
                {"age": yr.age, "phase": yr.phase, "value": yr.portfolio_value_jpy}
                for yr in r.trajectory
            ],
            "mc_p50": r.monte_carlo.p50 if r.monte_carlo else [],
        })
    return jsonify(payload)
