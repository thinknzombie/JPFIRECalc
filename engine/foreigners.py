"""
Foreigners Mode engine — Japan-specific considerations for non-Japanese residents.

Generates a ForeignersAnalysis dataclass with:
  - warnings:  blockers / high-priority items (exit tax, no NHI, pension duplication)
  - notes:     informational items (DTA provisions, pension treaty, remittance rule)
  - dta_info:  structured treaty data for the user's treaty country
  - totalization_eligible: bool + detail

No Flask imports. Accepts FinancialProfile fields. Zero side effects.

Key areas covered:
  1. Residency status → NHI eligibility, tax scope (worldwide vs remittance)
  2. Non-permanent resident rule (非永住者) — 5-of-10-years test
  3. Exit tax (国外転出時課税) — ¥100M asset threshold
  4. DTA provisions for treaty country (dividend WHT, pension note, capital gains)
  5. Totalization — avoids double pension contributions
  6. Foreign pension income in FIRE number
  7. NISA exit-tax interaction
  8. Overseas brokerage accounts — global income reporting obligation
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_dta() -> dict:
    path = _DATA_DIR / "dta_countries.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class ForeignersAnalysis:
    """
    All foreigner-specific FIRE considerations for one profile.

    warnings: items that materially affect the FIRE plan (require action)
    notes:    informational items (good to know, no action required)
    dta_info: raw treaty data for the user's country (or None)
    totalization_eligible: True if the user's country has a totalization agreement with Japan
    non_permanent_resident: True if the 非永住者 (non-PR) rule likely applies
    exit_tax_risk: True if financial assets are likely ≥¥100M at retirement
    """
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dta_info: dict | None = None
    totalization_eligible: bool = False
    non_permanent_resident: bool = False
    exit_tax_risk: bool = False


# Statuses that make someone ineligible or limited for NHI
_NHI_INELIGIBLE = {"tourist", "short_stay", "other_ineligible"}

# Statuses that grant full worldwide income taxation in Japan
_WORLDWIDE_TAX_STATUSES = {
    "permanent_resident", "citizen", "long_term_resident", "spouse_visa",
    "company_employee", "self_employed", "work_visa", "student_visa",
}

# Residency statuses that might qualify for non-permanent resident treatment
# (user must self-assess — we flag it as a note)
_POSSIBLY_NON_PR = {
    "long_term_resident", "spouse_visa", "work_visa", "student_visa", "other",
}


def analyse_foreigners(
    nationality: str,
    residency_status: str,
    treaty_country: str | None,
    is_tax_resident: bool,
    years_in_japan: int,
    current_age: int,
    target_retirement_age: int,
    total_financial_assets_jpy: int,
    projected_fire_number_jpy: int,
    foreign_pension_annual_jpy: int,
    foreign_assets_usd: float,
    usd_jpy_rate: float,
    nisa_balance_jpy: int,
) -> ForeignersAnalysis:
    """
    Run all foreigner-relevant checks and return a ForeignersAnalysis.

    Args:
        nationality:              ISO 3166-1 alpha-2 (e.g. "US", "GB"). "JP" skips most checks.
        residency_status:         One of: citizen, permanent_resident, long_term_resident,
                                  spouse_visa, work_visa, student_visa, other.
        treaty_country:           Country name matching dta_countries.json keys (e.g. "United States").
        is_tax_resident:          Whether the user is currently a Japan tax resident.
        years_in_japan:           Approximate years resident in Japan (for non-PR test).
        current_age:              Current age (used to estimate years to retirement).
        target_retirement_age:    Target FIRE age.
        total_financial_assets_jpy: Current total financial assets (for exit tax check).
        projected_fire_number_jpy: FIRE number (for exit tax check at retirement).
        foreign_pension_annual_jpy: Annual foreign pension income in JPY.
        foreign_assets_usd:       Foreign-held USD assets.
        usd_jpy_rate:             USD/JPY rate.
        nisa_balance_jpy:         Current NISA balance (exit tax NISA interaction).

    Returns:
        ForeignersAnalysis
    """
    result = ForeignersAnalysis()
    dta_data = _load_dta()
    all_countries = dta_data.get("countries", {})
    general = dta_data.get("general_notes", {})

    # ── 0. Japanese citizens — minimal checks ────────────────────────────────
    if nationality == "JP" and residency_status == "citizen":
        # Still check exit tax if assets are large
        _check_exit_tax(result, total_financial_assets_jpy, projected_fire_number_jpy, nisa_balance_jpy)
        return result

    # ── 1. DTA / treaty country ──────────────────────────────────────────────
    if treaty_country and treaty_country in all_countries:
        result.dta_info = all_countries[treaty_country]
        result.totalization_eligible = result.dta_info.get("totalization", False)

        # Pension note
        pension_note = result.dta_info.get("pension_note")
        if pension_note:
            result.notes.append(f"Pension treaty ({treaty_country}): {pension_note}")

        # Country-specific key notes
        for note in result.dta_info.get("key_notes", []):
            result.notes.append(note)

        # Dividend WHT
        wht = result.dta_info.get("dividend_wht_pct")
        if wht is not None:
            result.notes.append(
                f"Dividend withholding tax under Japan–{treaty_country} DTA: {wht}% "
                f"(vs 20.315% Japan standard rate on foreign dividends)."
            )
    elif treaty_country:
        # Country not in our database but user specified one
        result.notes.append(
            f"Japan has a DTA with {treaty_country}. Check the NTA website for "
            "specific provisions on pension income, dividends, and capital gains."
        )
    else:
        # No treaty country
        result.notes.append(
            "No DTA country specified. If your home country has a tax treaty with Japan, "
            "set it in your profile to see treaty-specific provisions."
        )

    # ── 2. Totalization ──────────────────────────────────────────────────────
    if result.totalization_eligible:
        result.notes.append(
            f"Totalization agreement with {treaty_country}: your contribution periods in both "
            "countries can be combined to meet Japan's 10-year minimum eligibility for nenkin. "
            "This avoids double pension contributions."
        )
    elif treaty_country and not result.totalization_eligible:
        result.warnings.append(
            f"No totalization agreement between Japan and {treaty_country}. "
            "You may be required to contribute to both countries' pension systems simultaneously. "
            "Consider professional advice to avoid unnecessary double contributions."
        )

    # ── 3. NHI eligibility ───────────────────────────────────────────────────
    if residency_status in _NHI_INELIGIBLE:
        result.warnings.append(
            "Your residency status may not qualify for National Health Insurance (NHI). "
            "NHI requires a residence card (在留カード) and registered domicile (住民票). "
            "Without NHI, healthcare costs are fully out-of-pocket — budget accordingly."
        )
    elif residency_status == "other":
        result.notes.append(
            "Residency status 'Other': verify NHI eligibility at your local ward office. "
            "Most holders of a residence card (在留カード) with 3-month+ stay are eligible."
        )

    # ── 4. Non-permanent resident rule (非永住者) ─────────────────────────────
    if residency_status in _POSSIBLY_NON_PR and years_in_japan < 5:
        result.non_permanent_resident = True
        result.notes.append(
            "Non-permanent resident rule (非永住者): you have been in Japan fewer than 5 of "
            "the past 10 years. You are only taxed in Japan on: (1) Japan-source income and "
            "(2) foreign-source income remitted to Japan. Foreign investment income kept abroad "
            "is generally NOT taxed in Japan. This can significantly reduce your effective tax rate "
            "on foreign portfolio income during the early years of residence."
        )
    elif is_tax_resident and years_in_japan >= 5:
        result.notes.append(
            "Worldwide income taxation: as a Japan tax resident for ≥5 years, you are taxed "
            "in Japan on your worldwide income — including foreign dividends, interest, capital "
            "gains, and pension income. Report all foreign income on your 確定申告."
        )

    # ── 5. Exit tax (国外転出時課税) ─────────────────────────────────────────
    _check_exit_tax(result, total_financial_assets_jpy, projected_fire_number_jpy, nisa_balance_jpy)

    # ── 6. Foreign pension income ────────────────────────────────────────────
    if foreign_pension_annual_jpy > 0:
        result.notes.append(
            f"Foreign pension income ¥{foreign_pension_annual_jpy:,}/year is included in your FIRE "
            "number calculation as a pension offset (reducing required portfolio size). "
            "In Japan, foreign government pensions qualify for the 公的年金等控除 deduction — "
            "confirm with your specific country's treaty classification."
        )

    # ── 7. NISA and overseas accounts ────────────────────────────────────────
    if foreign_assets_usd > 0:
        foreign_jpy = int(foreign_assets_usd * usd_jpy_rate)
        result.notes.append(
            f"Overseas brokerage/bank assets ¥{foreign_jpy:,} (${foreign_assets_usd:,.0f} USD): "
            "all income and gains from these accounts must be reported on your Japanese 確定申告. "
            "Use the foreign tax credit (外国税額控除) to offset any foreign withholding tax."
        )

    # ── 8. Residency status general note ────────────────────────────────────
    if residency_status == "permanent_resident":
        result.notes.append(
            "Permanent Resident (永住者): you have full NHI eligibility, worldwide income "
            "taxation applies, and you are eligible for all Japan pension benefits."
        )
    elif residency_status == "spouse_visa":
        result.notes.append(
            "Spouse Visa: NHI coverage applies. If your Japanese spouse's employer provides "
            "shakai hoken (社会保険), you may be covered as a dependent — verify with the employer."
        )

    return result


def _check_exit_tax(
    result: ForeignersAnalysis,
    total_financial_assets_jpy: int,
    projected_fire_number_jpy: int,
    nisa_balance_jpy: int,
) -> None:
    """Check exit tax risk and append warnings/notes as appropriate."""
    threshold = 100_000_000  # ¥100M

    if projected_fire_number_jpy >= threshold or total_financial_assets_jpy >= threshold:
        result.exit_tax_risk = True
        result.warnings.append(
            f"Exit Tax (国外転出時課税): your projected FIRE number or current assets may exceed "
            f"the ¥{threshold:,} threshold. If you plan to leave Japan after FIRE, unrealised gains "
            "on financial assets (stocks, investment trusts, bonds) are treated as realised on "
            "departure and taxed at 15.315% (national) + 5% (residence). NISA holdings lose "
            "tax-free status on exit. Seek professional tax advice before emigrating."
        )
        if nisa_balance_jpy > 0:
            result.warnings.append(
                f"NISA Exit Tax Interaction: your NISA balance ¥{nisa_balance_jpy:,} will lose "
                "its tax-free status if you leave Japan permanently. Unrealised NISA gains "
                "become subject to exit tax at departure."
            )
    elif total_financial_assets_jpy >= threshold * 0.5:
        # Approaching threshold
        result.notes.append(
            f"Exit Tax Watch: your current assets are approaching the ¥100M exit tax threshold. "
            "Monitor this if you plan to return to your home country after FIRE."
        )
