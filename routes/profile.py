"""
Profile blueprint — capture and edit the user's financial profile.

Routes:
  GET  /profile/new          → blank profile form
  POST /profile/new          → save profile, redirect to scenario form
  GET  /profile/<id>/edit    → edit existing profile (pre-filled form)
  POST /profile/<id>/edit    → update existing profile, redirect to scenario
  GET  /profile/template.json → download annotated JSON template
  GET  /profile/template.csv  → download CSV template
  POST /profile/upload        → parse uploaded file, pre-populate form
"""
import csv
import io
import json
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from models.profile import FinancialProfile, UserProfile
from models.scenario import Scenario, AssumptionSet
import storage.scenario_store as store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field metadata — used to annotate both JSON and CSV download templates
# ---------------------------------------------------------------------------

_FIELD_META: dict[str, dict] = {
    "current_age":                           {"label": "Current Age",                          "type": "int",   "description": "Your current age in years",                                                        "example": 35},
    "target_retirement_age":                 {"label": "Target Retirement Age",                "type": "int",   "description": "Age at which you plan to retire (FIRE target)",                                    "example": 50},
    "employment_type":                       {"label": "Employment Type",                       "type": "str",   "description": "company_employee | public_servant | self_employed | corporate_officer | no_job",   "example": "company_employee"},
    "annual_gross_income_jpy":               {"label": "Annual Gross Income (JPY)",             "type": "int",   "description": "Before-tax annual salary in yen",                                                  "example": 8_000_000},
    "has_spouse":                            {"label": "Has Spouse / Partner",                  "type": "bool",  "description": "true or false",                                                                    "example": False},
    "spouse_income_jpy":                     {"label": "Spouse Annual Income (JPY)",            "type": "int",   "description": "Spouse gross annual income in yen (0 if no spouse)",                               "example": 0},
    "num_dependents":                        {"label": "Number of Dependents",                  "type": "int",   "description": "Dependent family members (children, parents)",                                     "example": 0},
    "social_insurance_annual_jpy":           {"label": "Social Insurance Paid (Annual JPY)",    "type": "int",   "description": "Total shakaihoken premiums paid annually (~14% of gross for company employees)",   "example": 0},
    "nisa_balance_jpy":                      {"label": "NISA Balance (JPY)",                    "type": "int",   "description": "Current 新NISA account market value",                                             "example": 0},
    "nisa_lifetime_used_jpy":                {"label": "NISA Lifetime Cap Used (JPY)",          "type": "int",   "description": "Acquisition cost already used of the 18,000,000 yen lifetime cap",                 "example": 0},
    "ideco_balance_jpy":                     {"label": "iDeCo Balance (JPY)",                   "type": "int",   "description": "Current iDeCo account market value (locked until age 60)",                        "example": 0},
    "taxable_brokerage_jpy":                 {"label": "Taxable Brokerage (JPY)",               "type": "int",   "description": "Current market value of taxable accounts (特定口座)",                             "example": 0},
    "cash_savings_jpy":                      {"label": "Cash Savings (JPY)",                    "type": "int",   "description": "Bank accounts and liquid cash reserves",                                           "example": 0},
    "foreign_assets_usd":                    {"label": "Foreign Assets (USD)",                  "type": "float", "description": "USD-denominated assets (US ETFs, foreign bank accounts, etc.)",                   "example": 0.0},
    "monthly_expenses_jpy":                  {"label": "Monthly Expenses (JPY)",                "type": "int",   "description": "Total monthly living expenses",                                                    "example": 250_000},
    "monthly_nisa_contribution_jpy":         {"label": "Monthly NISA Contribution (JPY)",       "type": "int",   "description": "Tsumitate frame monthly contribution (max 100,000/month)",                        "example": 100_000},
    "nisa_growth_frame_annual_jpy":          {"label": "NISA Growth Frame Annual (JPY)",        "type": "int",   "description": "Growth frame annual lump sum (max 2,400,000/year)",                               "example": 0},
    "ideco_monthly_contribution_jpy":        {"label": "iDeCo Monthly Contribution (JPY)",      "type": "int",   "description": "Monthly iDeCo contribution (company employee max: 23,000)",                       "example": 23_000},
    "nenkin_contribution_months":            {"label": "Nenkin Contribution Months",            "type": "int",   "description": "Total months paid into kokumin nenkin or kosei nenkin",                            "example": 120},
    "nenkin_net_kosei_annual_jpy":           {"label": "Kosei Nenkin Estimate (JPY, optional)", "type": "int",   "description": "Annual kosei nenkin estimate from NenkinNet (0 = calculate from salary)",           "example": 0},
    "avg_standard_monthly_remuneration_jpy": {"label": "Avg Standard Monthly Remuneration (JPY)", "type": "int", "description": "平均標準報酬月額 used for kosei nenkin calculation",                              "example": 0},
    "nenkin_claim_age":                      {"label": "Pension Claim Age",                     "type": "int",   "description": "Age to start drawing nenkin (60–75; deferring to 70+ increases benefit)",         "example": 65},
    "foreign_pension_annual_jpy":            {"label": "Foreign Pension Income (Annual JPY)",   "type": "int",   "description": "Annual foreign pension converted to yen (US Social Security, UK state pension…)",  "example": 0},
    "foreign_pension_start_age":             {"label": "Foreign Pension Start Age",             "type": "int",   "description": "Age at which foreign pension income begins",                                       "example": 67},
    "nationality":                           {"label": "Nationality (ISO 3166-1 alpha-2)",      "type": "str",   "description": "Two-letter country code: JP, US, GB, AU, CA, DE, FR, etc.",                       "example": "JP"},
    "residency_status":                      {"label": "Japan Residency Status",                "type": "str",   "description": "citizen | permanent_resident | long_term_resident | spouse_visa | work_visa | other", "example": "permanent_resident"},
    "treaty_country":                        {"label": "Home Country (for DTA notes)",          "type": "str",   "description": "Full country name for double-tax agreement lookup (e.g. United States)",           "example": ""},
    "years_in_japan":                        {"label": "Years Resident in Japan",               "type": "int",   "description": "Approximate years living in Japan (affects non-permanent resident tax rules)",     "example": 10},
    "usd_jpy_rate":                          {"label": "USD/JPY Rate",                          "type": "float", "description": "Exchange rate used to convert foreign USD assets to JPY",                         "example": 150.0},
    "owns_property":                         {"label": "Owns Property in Japan",                "type": "bool",  "description": "true or false",                                                                    "example": False},
    "property_value_jpy":                    {"label": "Property Value (JPY)",                  "type": "int",   "description": "Current market value of owned property",                                          "example": 0},
    "mortgage_balance_jpy":                  {"label": "Mortgage Balance (JPY)",                "type": "int",   "description": "Outstanding mortgage principal",                                                   "example": 0},
    "monthly_mortgage_payment_jpy":          {"label": "Monthly Mortgage Payment (JPY)",        "type": "int",   "description": "Monthly principal + interest payment",                                             "example": 0},
    "rental_income_monthly_jpy":             {"label": "Monthly Rental Income (JPY)",           "type": "int",   "description": "Monthly rental income from investment property",                                   "example": 0},
    "property_paid_off_at_retirement":       {"label": "Property Paid Off at Retirement",       "type": "bool",  "description": "true or false — whether mortgage clears before FIRE age",                        "example": False},
    "property_planned_sale_age":             {"label": "Japan Property Planned Sale Age",        "type": "int",   "description": "Age at which you plan to sell the Japan property (0 or blank = keep forever)",   "example": 0},
    "property_appreciation_pct":             {"label": "Japan Property Appreciation (% p.a.)",  "type": "float", "description": "Expected annual property appreciation, e.g. 1.0 for 1% per year",                  "example": 0.0},
    "owns_foreign_property":              {"label": "Owns Foreign Real Estate",                "type": "bool",  "description": "true or false",                                                                                    "example": False},
    "foreign_property_value_jpy":         {"label": "Foreign Property Value (JPY)",            "type": "int",   "description": "Combined market value of all overseas property, converted to JPY",                             "example": 0},
    "foreign_property_mortgage_jpy":      {"label": "Foreign Property Mortgage (JPY)",         "type": "int",   "description": "Outstanding mortgage balance on overseas property, in JPY",                                    "example": 0},
    "foreign_property_rental_monthly_jpy":{"label": "Foreign Rental Income Monthly (JPY)",     "type": "int",   "description": "Combined monthly net rental income from overseas property, in JPY",                            "example": 0},
    "foreign_property_planned_sale_age": {"label": "Foreign Property Planned Sale Age",        "type": "int",   "description": "Age at which you plan to sell the overseas property (0 or blank = keep)",                    "example": 0},
    "foreign_property_appreciation_pct": {"label": "Foreign Property Appreciation (% p.a.)",  "type": "float", "description": "Expected annual appreciation of overseas property, e.g. 2.0 for 2% per year",               "example": 0.0},
    "gold_silver_value_jpy":              {"label": "Gold / Precious Metals (JPY)",             "type": "int",   "description": "Current market value of gold, silver, or other precious metals",                               "example": 0},
    "crypto_value_jpy":                   {"label": "Cryptocurrency (JPY)",                    "type": "int",   "description": "Current value of cryptocurrency holdings at market price (BTC, ETH, etc.)",                   "example": 0},
    "rsu_unvested_value_jpy":             {"label": "Unvested RSUs (JPY)",                     "type": "int",   "description": "Fair-market value of unvested RSUs at current stock price — only count if you plan to stay until vest", "example": 0},
    "rsu_vesting_annual_jpy":             {"label": "Annual RSU Vest (JPY)",                   "type": "int",   "description": "Expected annual RSU vest value while still employed (stops at retirement)",                    "example": 0},
    "other_assets_jpy":                   {"label": "Other Assets (JPY)",                      "type": "int",   "description": "Other assets: business equity, art, collectibles, private equity, etc.",                      "example": 0},
}

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
        property_planned_sale_age=i("property_planned_sale_age") or None,
        property_appreciation_pct=f("property_appreciation_pct"),
        owns_foreign_property=b("owns_foreign_property"),
        foreign_property_value_jpy=i("foreign_property_value_jpy"),
        foreign_property_mortgage_jpy=i("foreign_property_mortgage_jpy"),
        foreign_property_rental_monthly_jpy=i("foreign_property_rental_monthly_jpy"),
        foreign_property_planned_sale_age=i("foreign_property_planned_sale_age") or None,
        foreign_property_appreciation_pct=f("foreign_property_appreciation_pct"),
        gold_silver_value_jpy=i("gold_silver_value_jpy"),
        crypto_value_jpy=i("crypto_value_jpy"),
        rsu_unvested_value_jpy=i("rsu_unvested_value_jpy"),
        rsu_vesting_annual_jpy=i("rsu_vesting_annual_jpy"),
        other_assets_jpy=i("other_assets_jpy"),
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


# ---------------------------------------------------------------------------
# Template download routes
# ---------------------------------------------------------------------------

@profile_bp.route("/template.json")
def template_json():
    """Download a fully-annotated JSON template pre-filled with default values."""
    defaults = FinancialProfile().to_dict()
    field_info = {
        name: {
            "label":       meta["label"],
            "type":        meta["type"],
            "description": meta["description"],
        }
        for name, meta in _FIELD_META.items()
    }
    payload = {
        "_meta": {
            "format": "JPFIRECalc profile template v1",
            "instructions": (
                "Fill in the values below then upload this file at the profile page. "
                "The _meta block is ignored on upload. "
                "Boolean fields accept: true / false. "
                "Leave optional fields as 0 or null if not applicable."
            ),
            "fields": field_info,
        }
    }
    # Add actual value fields after _meta so they're easy to find
    payload.update({k: defaults.get(k, meta["example"]) for k, meta in _FIELD_META.items()})

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=jpfirecalc_profile_template.json"},
    )


@profile_bp.route("/template.csv")
def template_csv():
    """Download a CSV template with field_name / value / type / description columns."""
    defaults = FinancialProfile().to_dict()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["# JPFIRECalc Profile Template — fill in the 'value' column then upload"])
    writer.writerow(["# Boolean fields: use true or false  |  Leave optional JPY fields as 0"])
    writer.writerow(["field_name", "value", "type", "description"])
    for name, meta in _FIELD_META.items():
        writer.writerow([
            name,
            defaults.get(name, meta["example"]),
            meta["type"],
            meta["description"],
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=jpfirecalc_profile_template.csv"},
    )


# ---------------------------------------------------------------------------
# File upload route
# ---------------------------------------------------------------------------

_MAX_UPLOAD_BYTES = 256 * 1024  # 256 KB — a profile JSON is ~3 KB


@profile_bp.route("/upload", methods=["POST"])
def upload():
    """Parse an uploaded JSON or CSV profile template and pre-populate the form."""
    if "file" not in request.files:
        flash("No file attached to the request.", "error")
        return redirect(url_for("profile.new"))

    f = request.files["file"]
    if not f.filename:
        flash("No file selected.", "error")
        return redirect(url_for("profile.new"))

    filename = f.filename.lower()
    raw = f.read(_MAX_UPLOAD_BYTES)

    try:
        if filename.endswith(".json"):
            data = json.loads(raw.decode("utf-8"))
            data.pop("_meta", None)  # strip annotation block

        elif filename.endswith(".csv"):
            text = raw.decode("utf-8")
            # Strip comment lines (the template writes # lines before the header)
            lines = [line for line in text.splitlines(True)
                     if not line.lstrip().startswith("#")]
            reader = csv.DictReader(io.StringIO("".join(lines)))
            data = {}
            for row in reader:
                name = (row.get("field_name") or "").strip()
                value = (row.get("value") or "").strip()
                if name and not name.startswith("#"):
                    data[name] = value
            if not data:
                flash("No data found in CSV — check the file has a 'field_name' column.", "error")
                return redirect(url_for("profile.new"))
        else:
            flash("Unsupported file type. Please upload a .json or .csv file.", "error")
            return redirect(url_for("profile.new"))

        profile = FinancialProfile.from_dict(data)

    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        flash(f"Could not read file — make sure it is valid UTF-8 JSON or CSV. ({exc})", "error")
        return redirect(url_for("profile.new"))
    except Exception as exc:
        logger.exception("Profile upload parse error")
        flash(f"Error loading profile from file: {exc}", "error")
        return redirect(url_for("profile.new"))

    flash(
        "Profile loaded from file — review the values below and click "
        "\u201CSave & Configure Assumptions\u201D when ready.",
        "success",
    )
    return render_template(
        "profile.html",
        profile=profile,
        scenario=None,
        action=url_for("profile.create"),
        title="New Profile",
    )
