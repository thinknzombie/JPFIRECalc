"""
Scenarios blueprint — manage and view FIRE scenarios.

Routes:
  GET  /scenarios                  → dashboard list of all scenarios
  GET  /scenarios/<id>             → scenario detail + results
  GET  /scenarios/<id>/edit        → edit assumptions form
  POST /scenarios/<id>/edit        → update assumptions, re-run, redirect to detail
  POST /scenarios/<id>/delete      → delete scenario, redirect to dashboard
  GET  /scenarios/<id>/run         → HTMX partial: run calculation and return results fragment
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models.scenario import Scenario, AssumptionSet
from engine.fire_calculator import run_fire_scenario
import storage.scenario_store as store

scenarios_bp = Blueprint("scenarios", __name__, url_prefix="/scenarios")


def _assumptions_from_form(form) -> AssumptionSet:
    """Parse POST form into AssumptionSet."""
    def f(key, default):
        try:
            return float(form.get(key, default) or default)
        except (ValueError, TypeError):
            return default

    def i(key, default):
        try:
            return int(form.get(key, default) or default)
        except (ValueError, TypeError):
            return default

    def b(key, default=True):
        raw = form.get(key)
        if raw is None:
            return default
        return raw in ("on", "true", "1", "yes")

    return AssumptionSet(
        investment_return_pct=f("investment_return_pct", 5.0),
        retirement_return_pct=f("retirement_return_pct", 4.5),
        japan_inflation_pct=f("japan_inflation_pct", 2.0),
        withdrawal_rate_pct=f("withdrawal_rate_pct", 3.5),
        usd_jpy_rate=f("usd_jpy_rate", 150.0),
        monte_carlo_simulations=i("monte_carlo_simulations", 1000),
        simulation_years=i("simulation_years", 40),
        return_volatility_pct=f("return_volatility_pct", 15.0),
        sequence_of_returns_risk=b("sequence_of_returns_risk"),
        nhi_municipality_key=form.get("nhi_municipality_key", "national_average"),
        nhi_household_members=i("nhi_household_members", 1),
        fire_variant=form.get("fire_variant", "regular"),
        barista_income_monthly_jpy=i("barista_income_monthly_jpy", 0),
        coast_target_retirement_age=i("coast_target_retirement_age", 65),
        retirement_expense_growth_pct=f("retirement_expense_growth_pct", 1.5),
    )


def _run_and_render_detail(profile, scenario, region_key):
    """Run calculation engine and return template context."""
    result = run_fire_scenario(
        profile=profile,
        scenario_name=scenario.name,
        scenario_id=scenario.id,
        assumptions=scenario.assumptions,
        region_key=region_key,
    )
    return result


@scenarios_bp.route("/")
def index():
    store.init_store(current_app.config["SCENARIOS_DIR"])
    all_scenarios = store.load_all()
    return render_template("dashboard.html", scenarios=all_scenarios)


@scenarios_bp.route("/<scenario_id>")
def detail(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    result = _run_and_render_detail(profile, scenario, scenario.region)

    return render_template(
        "scenario_detail.html",
        scenario=scenario,
        profile=profile,
        result=result,
        title=scenario.name,
    )


@scenarios_bp.route("/<scenario_id>/edit", methods=["GET"])
def edit(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))
    return render_template(
        "scenario_form.html",
        scenario=scenario,
        profile=profile,
        action=url_for("scenarios.update", scenario_id=scenario_id),
        title=f"Edit Assumptions — {scenario.name}",
    )


@scenarios_bp.route("/<scenario_id>/edit", methods=["POST"])
def update(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    scenario.name = request.form.get("scenario_name", scenario.name)
    scenario.description = request.form.get("description", scenario.description)
    scenario.region = request.form.get("region", scenario.region)
    scenario.assumptions = _assumptions_from_form(request.form)
    store.save(profile, scenario)
    flash("Scenario updated.", "success")
    return redirect(url_for("scenarios.detail", scenario_id=scenario_id))


@scenarios_bp.route("/<scenario_id>/delete", methods=["POST"])
def delete(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    store.delete(scenario_id)
    flash("Scenario deleted.", "success")
    return redirect(url_for("scenarios.index"))


@scenarios_bp.route("/<scenario_id>/run")
def run(scenario_id):
    """HTMX endpoint — returns the results partial only."""
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        return "<p class='error'>Scenario not found.</p>", 404

    result = _run_and_render_detail(profile, scenario, scenario.region)
    return render_template(
        "partials/results.html",
        scenario=scenario,
        result=result,
    )
