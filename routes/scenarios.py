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
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from models.scenario import Scenario, AssumptionSet
from engine.fire_calculator import run_fire_scenario
from engine.report_generator import generate_markdown_report
import storage.scenario_store as store

logger = logging.getLogger(__name__)

scenarios_bp = Blueprint("scenarios", __name__, url_prefix="/scenarios")


def _validate_assumptions_form(form) -> list[str]:
    errors = []
    def fv(key):
        try: return float(form.get(key, 0) or 0)
        except (ValueError, TypeError): return None

    ret = fv("investment_return_pct")
    if ret is None or not (0 <= ret <= 20):
        errors.append("Investment return must be between 0% and 20%.")
    wr = fv("withdrawal_rate_pct")
    if wr is None or not (0.5 <= wr <= 10):
        errors.append("Withdrawal rate must be between 0.5% and 10%.")
    inf = fv("japan_inflation_pct")
    if inf is None or not (0 <= inf <= 15):
        errors.append("Inflation rate must be between 0% and 15%.")
    sims = form.get("monte_carlo_simulations", "1000")
    try:
        sims_int = int(sims)
        if not (100 <= sims_int <= 50_000):
            errors.append("Number of simulations must be between 100 and 50,000.")
    except (ValueError, TypeError):
        errors.append("Number of simulations must be a whole number.")

    # Coast FIRE target age must be > current age (loaded from profile)
    coast_age_raw = form.get("coast_target_retirement_age")
    if coast_age_raw:
        try:
            coast_age = int(coast_age_raw)
            if coast_age <= 0:
                errors.append("Coast FIRE target retirement age must be a positive number.")
        except (ValueError, TypeError):
            pass  # will fall back to default in _assumptions_from_form

    return errors


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
        nhi_municipality_key=form.get("nhi_municipality_key", "tokyo_shinjuku"),
        nhi_household_members=i("nhi_household_members", 1),
        fire_variant=form.get("fire_variant", "regular"),
        lean_monthly_expenses_jpy=i("lean_monthly_expenses_jpy", 0),
        fat_monthly_expenses_jpy=i("fat_monthly_expenses_jpy", 0),
        barista_income_monthly_jpy=i("barista_income_monthly_jpy", 0),
        coast_target_retirement_age=i("coast_target_retirement_age", 65),
        retirement_expense_growth_pct=f("retirement_expense_growth_pct", 1.5),
        foreign_inflation_pct=f("foreign_inflation_pct", 2.5),
    )


def _run_and_render_detail(profile, scenario, region_key):
    """Run calculation engine and return ScenarioResult, or raise EngineError."""
    try:
        return run_fire_scenario(
            profile=profile,
            scenario_name=scenario.name,
            scenario_id=scenario.id,
            assumptions=scenario.assumptions,
            region_key=region_key,
        )
    except Exception:
        logger.exception(
            "Engine error for scenario %s (%s)", scenario.id, scenario.name
        )
        raise


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
    except (FileNotFoundError, ValueError):
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    try:
        result = _run_and_render_detail(profile, scenario, scenario.region)
    except Exception as exc:
        logger.exception(
            "Engine error for scenario %s (%s): %s",
            scenario.id, scenario.name, exc
        )
        flash(
            f"Calculation error: {exc}",
            "error",
        )
        return redirect(url_for("scenarios.index"))

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
    except (FileNotFoundError, ValueError):
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
    except (FileNotFoundError, ValueError):
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    errors = _validate_assumptions_form(request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("scenario_form.html", scenario=scenario, profile=profile,
                               action=url_for("scenarios.update", scenario_id=scenario_id),
                               title=f"Edit Assumptions — {scenario.name}")
    scenario.name = request.form.get("scenario_name", scenario.name)
    scenario.description = request.form.get("description", scenario.description)
    scenario.region = request.form.get("region", scenario.region)
    assumptions = _assumptions_from_form(request.form)
    # Hard cap: prevent runaway computation
    assumptions.monte_carlo_simulations = min(assumptions.monte_carlo_simulations, 10_000)
    scenario.assumptions = assumptions
    store.save(profile, scenario)
    flash("Scenario updated.", "success")
    return redirect(url_for("scenarios.detail", scenario_id=scenario_id))


@scenarios_bp.route("/<scenario_id>/delete", methods=["POST"])
def delete(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    store.delete(scenario_id)
    flash("Scenario deleted.", "success")
    return redirect(url_for("scenarios.index"))


@scenarios_bp.route("/<scenario_id>/clone", methods=["POST"])
def clone(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except (FileNotFoundError, ValueError):
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    import uuid
    new_scenario = Scenario.from_dict(scenario.to_dict())
    new_scenario.id = str(uuid.uuid4())
    new_scenario.name = f"{scenario.name} (copy)"
    store.save(profile, new_scenario)
    flash(f"Cloned scenario as '{new_scenario.name}'.", "success")
    return redirect(url_for("scenarios.detail", scenario_id=new_scenario.id))


@scenarios_bp.route("/<scenario_id>/report.md")
def report_md(scenario_id):
    """Download a full Markdown report for this scenario."""
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except (FileNotFoundError, ValueError):
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    try:
        result = _run_and_render_detail(profile, scenario, scenario.region)
    except Exception:
        flash("Could not generate report — calculation error.", "error")
        return redirect(url_for("scenarios.detail", scenario_id=scenario_id))

    md = generate_markdown_report(profile, scenario, result)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in scenario.name).strip()
    filename = f"jpfirecalc_{safe_name}.md".replace(" ", "_")

    return Response(
        md.encode("utf-8"),
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@scenarios_bp.route("/<scenario_id>/run")
def run(scenario_id):
    """HTMX endpoint — returns the results partial only."""
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        return "<p class='error'>Scenario not found.</p>", 404

    try:
        result = _run_and_render_detail(profile, scenario, scenario.region)
    except Exception:
        return (
            "<p class='form-inline-error'>Calculation error — check your inputs and try again.</p>",
            500,
        )

    return render_template(
        "partials/results.html",
        scenario=scenario,
        profile=profile,
        result=result,
    )
