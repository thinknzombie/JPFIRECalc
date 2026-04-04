"""
Profile blueprint — capture and edit the user's financial profile.

Routes:
  GET  /profile/new          → blank profile form
  POST /profile/new          → save profile, redirect to scenario form
  GET  /profile/<id>/edit    → edit existing profile (pre-filled form)
  POST /profile/<id>/edit    → update existing profile, redirect to scenario
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models.profile import FinancialProfile, UserProfile
from models.scenario import Scenario, AssumptionSet
import storage.scenario_store as store

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


def _validate_profile_form(form) -> list[str]:
    """Return a list of validation error messages, or [] if valid."""
    errors = []
    def iv(key):
        try: return int(form.get(key, 0) or 0)
        except (ValueError, TypeError): return None

    age = iv("current_age")
    retire_age = iv("target_retirement_age")
    income = iv("annual_gross_income_jpy")
    expenses = iv("monthly_expenses_jpy")

    if age is None or not (18 <= age <= 80):
        errors.append("Current age must be between 18 and 80.")
    if retire_age is None or not (30 <= retire_age <= 90):
        errors.append("Target retirement age must be between 30 and 90.")
    if age is not None and retire_age is not None and retire_age <= age:
        errors.append("Target retirement age must be greater than current age.")
    if income is None or income < 0:
        errors.append("Annual gross income must be 0 or more.")
    if expenses is None or expenses < 0:
        errors.append("Monthly expenses must be 0 or more.")
    nisa = iv("monthly_nisa_contribution_jpy")
    if nisa is not None and nisa > 100_000:
        errors.append("Monthly NISA (tsumitate) contribution cannot exceed ¥100,000.")
    claim_age = iv("nenkin_claim_age")
    if claim_age is not None and not (60 <= claim_age <= 75):
        errors.append("Pension claim age must be between 60 and 75.")
    return errors


def _profile_from_form(form) -> FinancialProfile:
    """Parse the flat POST form into a FinancialProfile dataclass."""
    def i(key, default=0):
        try:
            return int(form.get(key, default) or default)
        except (ValueError, TypeError):
            return default

    def f(key, default=0.0):
        try:
            return float(form.get(key, default) or default)
        except (ValueError, TypeError):
            return default

    def b(key):
        return form.get(key) in ("on", "true", "1", "yes")

    def s(key, default=""):
        return form.get(key, default) or default

    return FinancialProfile(
        current_age=i("current_age", 35),
        target_retirement_age=i("target_retirement_age", 50),
        employment_type=s("employment_type", "company_employee"),
        nationality=s("nationality", "JP").upper()[:2],
        residency_status=s("residency_status", "permanent_resident"),
        treaty_country=s("treaty_country", ""),
        years_in_japan=i("years_in_japan", 10),
        annual_gross_income_jpy=i("annual_gross_income_jpy"),
        has_spouse=b("has_spouse"),
        spouse_income_jpy=i("spouse_income_jpy"),
        num_dependents=i("num_dependents"),
        social_insurance_annual_jpy=i("social_insurance_annual_jpy"),
        nisa_balance_jpy=i("nisa_balance_jpy"),
        nisa_lifetime_used_jpy=i("nisa_lifetime_used_jpy"),
        ideco_balance_jpy=i("ideco_balance_jpy"),
        taxable_brokerage_jpy=i("taxable_brokerage_jpy"),
        cash_savings_jpy=i("cash_savings_jpy"),
        foreign_assets_usd=f("foreign_assets_usd"),
        monthly_expenses_jpy=i("monthly_expenses_jpy", 250_000),
        monthly_nisa_contribution_jpy=i("monthly_nisa_contribution_jpy", 100_000),
        nisa_growth_frame_annual_jpy=i("nisa_growth_frame_annual_jpy"),
        ideco_monthly_contribution_jpy=i("ideco_monthly_contribution_jpy", 23_000),
        nenkin_contribution_months=i("nenkin_contribution_months"),
        nenkin_net_kosei_annual_jpy=i("nenkin_net_kosei_annual_jpy") or None,
        avg_standard_monthly_remuneration_jpy=i("avg_standard_monthly_remuneration_jpy"),
        nenkin_claim_age=i("nenkin_claim_age", 65),
        foreign_pension_annual_jpy=i("foreign_pension_annual_jpy"),
        foreign_pension_start_age=i("foreign_pension_start_age", 67),
        usd_jpy_rate=f("usd_jpy_rate", 150.0),
        owns_property=b("owns_property"),
        property_value_jpy=i("property_value_jpy"),
        mortgage_balance_jpy=i("mortgage_balance_jpy"),
        monthly_mortgage_payment_jpy=i("monthly_mortgage_payment_jpy"),
        rental_income_monthly_jpy=i("rental_income_monthly_jpy"),
        property_paid_off_at_retirement=b("property_paid_off_at_retirement"),
    )


@profile_bp.route("/new", methods=["GET"])
def new():
    return render_template(
        "profile.html",
        profile=FinancialProfile(),
        scenario=None,
        action=url_for("profile.create"),
        title="New Profile",
    )


@profile_bp.route("/new", methods=["POST"])
def create():
    errors = _validate_profile_form(request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("profile.html", profile=_profile_from_form(request.form),
                               scenario=None, action=url_for("profile.create"),
                               title="New Profile")
    profile = _profile_from_form(request.form)
    scenario = Scenario(
        name=request.form.get("scenario_name", "My Scenario"),
        region=request.form.get("region", "tokyo"),
    )
    store.init_store(current_app.config["SCENARIOS_DIR"])
    scenario_id = store.save(profile, scenario)
    flash("Profile saved! Now configure your scenario assumptions.", "success")
    return redirect(url_for("scenarios.edit", scenario_id=scenario_id))


@profile_bp.route("/<scenario_id>/edit", methods=["GET"])
def edit(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        profile, scenario = store.load(scenario_id)
    except FileNotFoundError:
        flash("Scenario not found.", "error")
        return redirect(url_for("main.dashboard"))
    return render_template(
        "profile.html",
        profile=profile,
        scenario=scenario,
        action=url_for("profile.update", scenario_id=scenario_id),
        title=f"Edit Profile — {scenario.name}",
    )


@profile_bp.route("/<scenario_id>/edit", methods=["POST"])
def update(scenario_id):
    store.init_store(current_app.config["SCENARIOS_DIR"])
    try:
        _, scenario = store.load(scenario_id)
    except FileNotFoundError:
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))
    errors = _validate_profile_form(request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("profile.html", profile=_profile_from_form(request.form),
                               scenario=scenario,
                               action=url_for("profile.update", scenario_id=scenario_id),
                               title=f"Edit Profile — {scenario.name}")
    profile = _profile_from_form(request.form)
    scenario.name = request.form.get("scenario_name", scenario.name)
    scenario.region = request.form.get("region", scenario.region)
    store.save(profile, scenario)
    flash("Profile updated.", "success")
    return redirect(url_for("scenarios.detail", scenario_id=scenario_id))
