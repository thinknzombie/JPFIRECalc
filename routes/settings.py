"""
Settings route — global app configuration.

GET  /settings        → render settings form
POST /settings        → save settings and redirect back
POST /settings/reset  → reset all settings to defaults
"""
from __future__ import annotations

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

import storage.settings_store as store
from storage.settings_store import AppSettings

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET"])
def index():
    store.init_settings(current_app.config["DATA_DIR"])
    settings = store.get()
    return render_template(
        "settings.html",
        settings=settings,
        title="Settings",
    )


@settings_bp.route("/", methods=["POST"])
def save():
    store.init_settings(current_app.config["DATA_DIR"])
    form = request.form

    try:
        settings = AppSettings(
            # Default scenario assumptions
            default_investment_return_pct=float(form.get("default_investment_return_pct", 5.0)),
            default_retirement_return_pct=float(form.get("default_retirement_return_pct", 4.5)),
            default_withdrawal_rate_pct=float(form.get("default_withdrawal_rate_pct", 3.5)),
            default_japan_inflation_pct=float(form.get("default_japan_inflation_pct", 2.0)),
            default_return_volatility_pct=float(form.get("default_return_volatility_pct", 15.0)),
            default_monte_carlo_simulations=int(form.get("default_monte_carlo_simulations", 10000)),
            default_simulation_years=int(form.get("default_simulation_years", 40)),
            default_sequence_of_returns_risk="default_sequence_of_returns_risk" in form,
            default_retirement_expense_growth_pct=float(form.get("default_retirement_expense_growth_pct", 1.5)),
            default_fire_variant=form.get("default_fire_variant", "regular"),
            default_region=form.get("default_region", "tokyo"),
            default_nhi_municipality_key=form.get("default_nhi_municipality_key", "tokyo_shinjuku"),
            default_nhi_household_members=int(form.get("default_nhi_household_members", 1)),
            default_usd_jpy_rate=float(form.get("default_usd_jpy_rate", 150.0)),
            # Tax rates
            capital_gains_tax_rate_pct=float(form.get("capital_gains_tax_rate_pct", 20.315)),
            reconstruction_surtax_pct=float(form.get("reconstruction_surtax_pct", 2.1)),
            residence_tax_rate_pct=float(form.get("residence_tax_rate_pct", 10.0)),
            residence_tax_per_capita_jpy=int(form.get("residence_tax_per_capita_jpy", 5000)),
            mortgage_interest_rate_pct=float(form.get("mortgage_interest_rate_pct", 1.5)),
            # Display
            currency_display=form.get("currency_display", "compact"),
            default_language=form.get("default_language", "en"),
        )
        store.save(settings)
        flash("Settings saved successfully.", "success")
    except (ValueError, TypeError) as exc:
        logger.exception("Settings save error")
        flash(f"Invalid input: {exc}", "error")

    return redirect(url_for("settings.index"))


@settings_bp.route("/reset", methods=["POST"])
def reset():
    store.init_settings(current_app.config["DATA_DIR"])
    store.save(AppSettings())
    flash("Settings reset to defaults.", "success")
    return redirect(url_for("settings.index"))
