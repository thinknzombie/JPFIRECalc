"""
Japan public pension (年金) calculation engine.

Covers:
  - Kokumin Nenkin / Old-age Basic Pension (老齢基礎年金)
  - Kosei Nenkin / Employees' Pension (老齢厚生年金)
  - Early claim reduction and deferral bonus
  - Break-even age analysis for deferral decisions
  - After-tax pension income (using tax_calculator)
  - Foreign pension integration

Key facts for FIRE planning:
  - Minimum 10 years (120 months) of contributions to receive ANY benefit.
  - iDeCo/NISA contributions do NOT count toward nenkin.
  - Claiming at 65 is the baseline. Early (60) = -24%. Deferred to 75 = +84%.
  - Pension income reduces your FIRE number: FIRE# = (expenses - pension) / rate.
  - Pension income IS taxable but the public pension deduction (公的年金等控除)
    is generous — at moderate pension levels, effective tax is low.

Sources: 日本年金機構 (nenkin.go.jp) — FY2024 figures.
"""
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "pension_constants.json", encoding="utf-8") as _f:
    _PENSION = json.load(_f)

_KOKUMIN = _PENSION["kokumin_nenkin"]
_KOSEI = _PENSION["kosei_nenkin"]


# ---------------------------------------------------------------------------
# Kokumin Nenkin  (老齢基礎年金 — Basic / National Pension)
# ---------------------------------------------------------------------------

def calculate_kokumin_nenkin(
    contribution_months: int,
    claim_age: int = 65,
) -> dict:
    """
    Calculate annual Kokumin Nenkin benefit.

    Args:
        contribution_months: Months of qualifying contributions (max 480 = 40 years).
                             Includes kokumin nenkin and kosei nenkin periods.
        claim_age:           Age at which pension is claimed (60–75).

    Returns:
        dict with annual_benefit_jpy, monthly_benefit_jpy, contribution_months,
        full_benefit_jpy, pro_rate_factor, claim_modifier, claim_age,
        eligible (bool), early_claim (bool), deferred (bool).
    """
    full_benefit = _KOKUMIN["full_annual_benefit_jpy"]
    full_months = _KOKUMIN["full_contribution_months"]
    min_months = _KOKUMIN["min_contribution_years"] * 12

    eligible = contribution_months >= min_months
    capped_months = min(contribution_months, full_months)
    pro_rate = capped_months / full_months

    # Claim age modifier
    base_age = _KOKUMIN["eligible_from_age"]  # 65
    early_min = _KOKUMIN["early_claim_min_age"]  # 60
    defer_max = _KOKUMIN["deferral_max_age"]  # 75
    claim_age = max(early_min, min(claim_age, defer_max))

    if claim_age < base_age:
        # Early claim: 0.4% reduction per month before 65
        months_early = (base_age - claim_age) * 12
        modifier = 1.0 - _KOKUMIN["early_reduction_per_month"] * months_early
    elif claim_age > base_age:
        # Deferral: 0.7% increase per month after 65
        months_deferred = (claim_age - base_age) * 12
        modifier = 1.0 + _KOKUMIN["deferral_increase_per_month"] * months_deferred
    else:
        modifier = 1.0

    annual_benefit = int(full_benefit * pro_rate * modifier) if eligible else 0

    return {
        "annual_benefit_jpy": annual_benefit,
        "monthly_benefit_jpy": annual_benefit // 12,
        "contribution_months": contribution_months,
        "full_benefit_jpy": full_benefit,
        "pro_rate_factor": round(pro_rate, 4),
        "claim_modifier": round(modifier, 4),
        "claim_age": claim_age,
        "eligible": eligible,
        "early_claim": claim_age < base_age,
        "deferred": claim_age > base_age,
        "min_contribution_months": min_months,
    }


# ---------------------------------------------------------------------------
# Kosei Nenkin  (老齢厚生年金 — Employees' Pension)
# ---------------------------------------------------------------------------

def calculate_kosei_nenkin(
    avg_standard_monthly_remuneration: int,
    contribution_months: int,
    claim_age: int = 65,
    nenkin_net_override_annual_jpy: int | None = None,
) -> dict:
    """
    Calculate annual Kosei Nenkin benefit.

    The NTA formula (post-2003): benefit = Σ(standard monthly remuneration) × 0.005481
    Simplified to: avg_remuneration × months × 0.005481

    In practice, users should input their NenkinNet estimate directly via
    nenkin_net_override_annual_jpy, which accounts for the pre/post-2003 split,
    bonuses, and other complexities this simplified formula cannot capture.

    Args:
        avg_standard_monthly_remuneration: Average 標準報酬月額 over career (JPY).
                                           This is the remuneration grade, not exact salary.
        contribution_months:               Months enrolled in kosei nenkin.
        claim_age:                         Age at which pension is claimed (60–75).
        nenkin_net_override_annual_jpy:    If provided, use this as the base annual
                                           benefit before applying the claim-age modifier.
                                           Recommended: get this from nenkin.go.jp.

    Returns:
        dict with annual_benefit_jpy, monthly_benefit_jpy, base_annual_jpy,
        claim_modifier, claim_age, used_override (bool).
    """
    base_age = _KOKUMIN["eligible_from_age"]  # 65 (same modifier as kokumin)
    early_min = _KOKUMIN["early_claim_min_age"]
    defer_max = _KOKUMIN["deferral_max_age"]
    claim_age = max(early_min, min(claim_age, defer_max))

    # Claim age modifier (same structure as kokumin nenkin)
    if claim_age < base_age:
        months_early = (base_age - claim_age) * 12
        modifier = 1.0 - _KOKUMIN["early_reduction_per_month"] * months_early
    elif claim_age > base_age:
        months_deferred = (claim_age - base_age) * 12
        modifier = 1.0 + _KOKUMIN["deferral_increase_per_month"] * months_deferred
    else:
        modifier = 1.0

    used_override = nenkin_net_override_annual_jpy is not None

    if used_override:
        base_annual = nenkin_net_override_annual_jpy
    else:
        # Simplified post-2003 formula
        base_annual = int(
            avg_standard_monthly_remuneration
            * contribution_months
            * _KOSEI["post_2003_multiplier"]
        )

    annual_benefit = int(base_annual * modifier)

    return {
        "annual_benefit_jpy": annual_benefit,
        "monthly_benefit_jpy": annual_benefit // 12,
        "base_annual_jpy": base_annual,
        "avg_standard_monthly_remuneration": avg_standard_monthly_remuneration,
        "contribution_months": contribution_months,
        "claim_modifier": round(modifier, 4),
        "claim_age": claim_age,
        "used_override": used_override,
        "formula_note": (
            "NenkinNet override used — recommended for accuracy." if used_override
            else "Simplified post-2003 formula. Use NenkinNet for accurate figures."
        ),
    }


# ---------------------------------------------------------------------------
# Combined pension income
# ---------------------------------------------------------------------------

def calculate_total_pension(
    kokumin_annual_jpy: int,
    kosei_annual_jpy: int,
    foreign_pension_annual_jpy: int = 0,
) -> dict:
    """
    Combine all pension income sources into a total annual figure.

    Args:
        kokumin_annual_jpy:       Annual kokumin nenkin benefit (JPY).
        kosei_annual_jpy:         Annual kosei nenkin benefit (JPY).
        foreign_pension_annual_jpy: Foreign pension income in JPY (e.g. US Social
                                   Security, Australian Super drawdown, UK state pension).
                                   Use assumed USD/JPY rate for USD-denominated pensions.

    Returns:
        dict with kokumin, kosei, foreign, total_annual_jpy, total_monthly_jpy.
    """
    total = kokumin_annual_jpy + kosei_annual_jpy + foreign_pension_annual_jpy
    return {
        "kokumin_annual_jpy": kokumin_annual_jpy,
        "kosei_annual_jpy": kosei_annual_jpy,
        "foreign_pension_annual_jpy": foreign_pension_annual_jpy,
        "total_annual_jpy": total,
        "total_monthly_jpy": total // 12,
    }


# ---------------------------------------------------------------------------
# After-tax pension income
# ---------------------------------------------------------------------------

def calculate_pension_after_tax(
    total_pension_annual_jpy: int,
    age: int,
    other_deductions: int = 0,
    per_capita_levy: int = 5_000,
) -> dict:
    """
    Calculate after-tax pension income, including income tax and residence tax.

    Uses the public pension income deduction (公的年金等控除) from tax_calculator.

    Args:
        total_pension_annual_jpy: Combined annual pension from all sources (JPY).
        age:                      Age of recipient (affects pension deduction).
        other_deductions:         Additional deductions (e.g. medical expenses).
        per_capita_levy:          Annual residence tax per-capita levy.

    Returns:
        dict with gross_pension, pension_deduction, taxable_pension,
        income_tax, residence_tax, total_tax, net_pension, effective_tax_rate_pct.
    """
    from engine.tax_calculator import (
        calculate_pension_income_deduction,
        calculate_income_tax_from_taxable,
        calculate_residence_tax,
    )

    deduction = calculate_pension_income_deduction(total_pension_annual_jpy, age)
    taxable = max(0, total_pension_annual_jpy - deduction - other_deductions)

    income_tax = calculate_income_tax_from_taxable(taxable)
    residence_tax_result = calculate_residence_tax(taxable, per_capita_levy)
    residence_tax = residence_tax_result["total"]

    total_tax = income_tax + residence_tax
    net_pension = total_pension_annual_jpy - total_tax
    effective_rate = (total_tax / total_pension_annual_jpy * 100) if total_pension_annual_jpy > 0 else 0.0

    return {
        "gross_pension_annual_jpy": total_pension_annual_jpy,
        "pension_deduction": deduction,
        "other_deductions": other_deductions,
        "taxable_pension": taxable,
        "income_tax": income_tax,
        "residence_tax": residence_tax,
        "total_tax": total_tax,
        "net_pension_annual_jpy": net_pension,
        "net_pension_monthly_jpy": net_pension // 12,
        "effective_tax_rate_pct": round(effective_rate, 2),
    }


# ---------------------------------------------------------------------------
# Deferral break-even analysis
# ---------------------------------------------------------------------------

def calculate_deferral_break_even(
    base_annual_benefit_jpy: int,
    defer_to_age: int,
    start_age: int = 65,
) -> dict:
    """
    Calculate the break-even age for deferring pension claims.

    At the break-even age, cumulative lifetime pension payments are equal
    whether you claimed at start_age or deferred to defer_to_age.
    This calculation ignores taxation and investment returns (see note).

    Args:
        base_annual_benefit_jpy: Annual benefit if claimed at start_age (65).
        defer_to_age:            Age you plan to defer until (66–75).
        start_age:               Age at which baseline benefit would start (default 65).

    Returns:
        dict with deferred_annual_benefit, deferral_years, increase_pct,
        break_even_years_after_deferral, break_even_age, payments_foregone_jpy.

    Note:
        A more conservative break-even should account for:
        - Investment returns on foregone payments (pushes break-even later)
        - Tax differences (pension deduction is large — low-tax pension)
        - Longevity risk (are you likely to live to break-even?)
    """
    if defer_to_age <= start_age:
        raise ValueError(f"defer_to_age ({defer_to_age}) must be > start_age ({start_age})")
    if defer_to_age > _KOKUMIN["deferral_max_age"]:
        raise ValueError(f"Maximum deferral age is {_KOKUMIN['deferral_max_age']}")

    months_deferred = (defer_to_age - start_age) * 12
    modifier = 1.0 + _KOKUMIN["deferral_increase_per_month"] * months_deferred
    deferred_benefit = int(base_annual_benefit_jpy * modifier)

    deferral_years = defer_to_age - start_age
    payments_foregone = base_annual_benefit_jpy * deferral_years
    annual_gain = deferred_benefit - base_annual_benefit_jpy

    # Break-even: foregone / annual_gain = years to recover from deferral start age
    break_even_years = payments_foregone / annual_gain if annual_gain > 0 else float("inf")
    break_even_age = defer_to_age + break_even_years

    increase_pct = (modifier - 1.0) * 100

    return {
        "base_annual_benefit_jpy": base_annual_benefit_jpy,
        "deferred_annual_benefit_jpy": deferred_benefit,
        "start_age": start_age,
        "defer_to_age": defer_to_age,
        "deferral_years": deferral_years,
        "increase_pct": round(increase_pct, 1),
        "payments_foregone_jpy": payments_foregone,
        "annual_gain_jpy": annual_gain,
        "break_even_years_after_deferral": round(break_even_years, 1),
        "break_even_age": round(break_even_age, 1),
        "break_even_calendar_year_note": (
            "Ignores investment returns on foregone payments and tax effects. "
            "Actual break-even is typically 1-3 years later when these are included."
        ),
    }


def compare_deferral_options(
    base_annual_benefit_jpy: int,
    start_age: int = 65,
) -> list[dict]:
    """
    Compare all deferral options (66 through 75) for a given base benefit.

    Returns a list of dicts sorted by defer_to_age, each containing
    the full break-even analysis.
    """
    options = []
    for defer_age in range(start_age + 1, _KOKUMIN["deferral_max_age"] + 1):
        options.append(
            calculate_deferral_break_even(base_annual_benefit_jpy, defer_age, start_age)
        )
    return options


# ---------------------------------------------------------------------------
# Totalization check
# ---------------------------------------------------------------------------

def check_totalization(country: str) -> dict:
    """
    Check whether a country has a totalization agreement with Japan.

    Totalization agreements (社会保障協定) allow contribution periods in both
    countries to be combined to meet the 10-year minimum for nenkin eligibility.

    Args:
        country: Country name (English) to check.

    Returns:
        dict with country, has_agreement, note.
    """
    countries = _PENSION.get("totalization_countries", [])
    has_agreement = any(country.lower() in c.lower() for c in countries)

    return {
        "country": country,
        "has_agreement": has_agreement,
        "note": (
            "Contribution periods can be combined to meet the 10-year minimum. "
            "Check the specific treaty for benefit calculation rules."
            if has_agreement
            else "No totalization agreement. Separate 10-year minimums apply in each country."
        ),
    }


# ---------------------------------------------------------------------------
# FIRE-specific helper: pension offset
# ---------------------------------------------------------------------------

def calculate_pension_offset_on_fire_number(
    annual_expenses_jpy: int,
    net_pension_annual_jpy: int,
    withdrawal_rate: float = 0.035,
) -> dict:
    """
    Calculate the FIRE number reduction from pension income.

    FIRE number = (expenses - pension_income) / withdrawal_rate

    For Japan, the recommended safe withdrawal rate is 3–3.5% (lower than
    the US 4% rule due to Japan's lower expected equity returns).

    Args:
        annual_expenses_jpy:   Target annual retirement expenses (JPY).
        net_pension_annual_jpy: After-tax annual pension income (JPY).
        withdrawal_rate:        Withdrawal rate as decimal (e.g. 0.035 for 3.5%).

    Returns:
        dict with fire_number_without_pension, pension_offset, fire_number_with_pension,
        portfolio_reduction, withdrawal_rate_pct.
    """
    fire_without = int(annual_expenses_jpy / withdrawal_rate)
    net_need = max(0, annual_expenses_jpy - net_pension_annual_jpy)
    fire_with = int(net_need / withdrawal_rate) if net_need > 0 else 0
    reduction = fire_without - fire_with

    return {
        "annual_expenses_jpy": annual_expenses_jpy,
        "net_pension_annual_jpy": net_pension_annual_jpy,
        "withdrawal_rate_pct": withdrawal_rate * 100,
        "fire_number_without_pension_jpy": fire_without,
        "pension_offset_jpy": reduction,
        "fire_number_with_pension_jpy": fire_with,
        "portfolio_reduction_pct": round(reduction / fire_without * 100, 1) if fire_without > 0 else 0,
        "pension_covers_expenses_pct": round(net_pension_annual_jpy / annual_expenses_jpy * 100, 1) if annual_expenses_jpy > 0 else 0,
    }
