"""
iDeCo (Individual Defined Contribution Pension / 個人型確定拠出年金) calculator.

Key facts for FIRE planning:
  - Contributions are FULLY deductible from income (小規模企業共済等掛金控除).
  - Growth is completely tax-free within the account.
  - CANNOT be withdrawn before age 60 — no exceptions. This is the critical
    constraint for early retirees: if your FIRE target is before 60, your
    iDeCo balance must be excluded from your accessible portfolio.
  - Lump sum withdrawal (一時金): taxed as retirement income (退職所得),
    with the retirement income deduction applied and the result halved.
    Highly tax-advantaged — often near-zero tax for typical balances.
  - Annuity withdrawal (年金): taxed as miscellaneous income (雑所得),
    with the public pension deduction applied. Less tax-efficient for
    most retirees than lump sum.
  - Minimum 2 years of contributions required to access at 60.
  - Annual contribution limits vary by employment type (12,000–68,000 yen/month).

Sources: iDeCo公式サイト / 厚生労働省 — 2024 figures.
"""
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "ideco_limits.json", encoding="utf-8") as _f:
    _IDECO = json.load(_f)

_MONTHLY_LIMITS = _IDECO["monthly_limits_jpy"]
_ACCESS_AGE = _IDECO["access_age"]  # 60


# ---------------------------------------------------------------------------
# Contribution limit validation
# ---------------------------------------------------------------------------

def get_monthly_limit(employment_type: str) -> int:
    """
    Return the monthly iDeCo contribution limit for a given employment type.

    Args:
        employment_type: One of the keys in ideco_limits.json monthly_limits_jpy,
                         e.g. "self_employed", "company_no_pension",
                         "company_with_db_or_mutual_aid", "civil_servant".

    Returns:
        Monthly limit in JPY.

    Raises:
        ValueError if employment_type is not recognised.
    """
    key = employment_type.lower().replace(" ", "_").replace("-", "_")
    if key not in _MONTHLY_LIMITS:
        valid = [k for k in _MONTHLY_LIMITS if not k.startswith("_")]
        raise ValueError(
            f"Unknown employment_type '{employment_type}'. "
            f"Valid options: {valid}"
        )
    return _MONTHLY_LIMITS[key]


def validate_contribution(monthly_jpy: int, employment_type: str) -> dict:
    """
    Check whether a monthly contribution is within the legal limit.

    Returns:
        dict with is_valid, monthly_jpy, limit_jpy, annual_jpy, excess_jpy.
    """
    limit = get_monthly_limit(employment_type)
    capped = min(monthly_jpy, limit)
    return {
        "is_valid": monthly_jpy <= limit,
        "monthly_jpy": monthly_jpy,
        "limit_monthly_jpy": limit,
        "annual_jpy": capped * 12,
        "excess_monthly_jpy": max(0, monthly_jpy - limit),
    }


# ---------------------------------------------------------------------------
# Accumulation projection
# ---------------------------------------------------------------------------

def calculate_ideco_accumulation(
    monthly_contribution_jpy: int,
    years: int,
    annual_return_rate: float,
    existing_balance_jpy: int = 0,
) -> dict:
    """
    Project iDeCo account balance at end of accumulation period.

    Uses end-of-month contribution timing with annual compounding approximation.
    Formula: FV = existing_balance × (1+r)^n + PMT × ((1+r)^n - 1) / r
    where PMT = annual contribution = monthly × 12.

    Args:
        monthly_contribution_jpy: Monthly contribution (JPY). Will be capped at legal limit
                                  if you also validate separately.
        years:                    Number of years of contributions.
        annual_return_rate:       Expected annual return as decimal (e.g. 0.05 for 5%).
        existing_balance_jpy:     Current iDeCo balance (JPY).

    Returns:
        dict with final_balance_jpy, total_contributions_jpy, investment_gain_jpy,
        gain_pct, year_by_year (list of {year, balance, contributions_to_date}).
    """
    annual_contribution = monthly_contribution_jpy * 12
    r = annual_return_rate
    n = years

    if r == 0:
        # Edge case: zero return
        final_balance = existing_balance_jpy + annual_contribution * n
        gain = 0
    else:
        growth_factor = (1 + r) ** n
        final_balance = int(
            existing_balance_jpy * growth_factor
            + annual_contribution * (growth_factor - 1) / r
        )
        gain = final_balance - existing_balance_jpy - annual_contribution * n

    total_contributions = annual_contribution * n
    gain_pct = (gain / (existing_balance_jpy + total_contributions) * 100) if (existing_balance_jpy + total_contributions) > 0 else 0.0

    # Year-by-year trajectory
    year_by_year = []
    balance = existing_balance_jpy
    for yr in range(1, n + 1):
        balance = int(balance * (1 + r) + annual_contribution)
        year_by_year.append({
            "year": yr,
            "balance_jpy": balance,
            "contributions_to_date_jpy": existing_balance_jpy + annual_contribution * yr,
        })

    return {
        "monthly_contribution_jpy": monthly_contribution_jpy,
        "annual_contribution_jpy": annual_contribution,
        "years": years,
        "annual_return_rate_pct": annual_return_rate * 100,
        "existing_balance_jpy": existing_balance_jpy,
        "final_balance_jpy": final_balance,
        "total_contributions_jpy": total_contributions,
        "investment_gain_jpy": max(0, gain),
        "gain_pct": round(gain_pct, 1),
        "year_by_year": year_by_year,
    }


# ---------------------------------------------------------------------------
# Annual tax saving from iDeCo contributions
# ---------------------------------------------------------------------------

def calculate_ideco_tax_saving(
    monthly_contribution_jpy: int,
    marginal_income_tax_rate: float,
    residence_tax_rate: float = 0.10,
    years: int = 1,
) -> dict:
    """
    Calculate annual and cumulative tax savings from iDeCo contributions.

    iDeCo contributions are deducted from income before both income tax
    and residence tax are calculated. The saving is the deduction × combined rate.

    Args:
        monthly_contribution_jpy: Monthly iDeCo contribution.
        marginal_income_tax_rate: Marginal income tax rate as decimal (e.g. 0.20).
                                  Include the 2.1% surtax if needed (e.g. 0.2042).
        residence_tax_rate:       Residence tax rate (default 0.10 = 10%).
        years:                    Number of years (for cumulative calculation).

    Returns:
        dict with annual_deduction_jpy, annual_income_tax_saving_jpy,
        annual_residence_tax_saving_jpy, annual_total_saving_jpy,
        cumulative_saving_jpy (over `years`), effective_return_boost_pct.
    """
    annual_deduction = monthly_contribution_jpy * 12
    income_tax_saving = int(annual_deduction * marginal_income_tax_rate)
    residence_tax_saving = int(annual_deduction * residence_tax_rate)
    total_saving = income_tax_saving + residence_tax_saving

    # Effective return boost: tax saving as % of contribution
    effective_boost = (total_saving / annual_deduction * 100) if annual_deduction > 0 else 0.0

    return {
        "monthly_contribution_jpy": monthly_contribution_jpy,
        "annual_deduction_jpy": annual_deduction,
        "marginal_income_tax_rate_pct": marginal_income_tax_rate * 100,
        "annual_income_tax_saving_jpy": income_tax_saving,
        "annual_residence_tax_saving_jpy": residence_tax_saving,
        "annual_total_saving_jpy": total_saving,
        "cumulative_saving_jpy": total_saving * years,
        "effective_return_boost_pct": round(effective_boost, 1),
    }


# ---------------------------------------------------------------------------
# Withdrawal tax: lump sum vs annuity
# ---------------------------------------------------------------------------

def calculate_lump_sum_withdrawal_tax(
    balance_jpy: int,
    contribution_years: int,
) -> dict:
    """
    Calculate tax on iDeCo lump-sum withdrawal (一時金方式 / 退職所得).

    Formula:
        1. Apply retirement income deduction (退職所得控除)
        2. Net = max(0, balance - deduction)
        3. Taxable retirement income = net / 2  (the key tax advantage)
        4. Apply income tax brackets to taxable amount
        5. Apply residence tax (10%) to same taxable amount

    Args:
        balance_jpy:         Total iDeCo account balance at withdrawal.
        contribution_years:  Number of years contributions were made.

    Returns:
        dict with full tax breakdown and effective rates.
    """
    from engine.tax_calculator import (
        calculate_retirement_income_deduction,
        calculate_income_tax_from_taxable,
        calculate_residence_tax,
    )

    deduction = calculate_retirement_income_deduction(contribution_years)
    net = max(0, balance_jpy - deduction)
    taxable = net // 2

    income_tax = calculate_income_tax_from_taxable(taxable)
    residence_tax_result = calculate_residence_tax(taxable)
    residence_tax = residence_tax_result["total"]

    total_tax = income_tax + residence_tax
    net_receipt = balance_jpy - total_tax
    effective_rate = (total_tax / balance_jpy * 100) if balance_jpy > 0 else 0.0

    return {
        "balance_jpy": balance_jpy,
        "contribution_years": contribution_years,
        "retirement_income_deduction": deduction,
        "net_after_deduction": net,
        "taxable_retirement_income": taxable,
        "income_tax": income_tax,
        "residence_tax": residence_tax,
        "total_tax": total_tax,
        "net_receipt_jpy": net_receipt,
        "effective_tax_rate_pct": round(effective_rate, 2),
        "method": "lump_sum",
    }


def calculate_annuity_withdrawal_tax(
    annual_withdrawal_jpy: int,
    age: int,
    other_pension_income_jpy: int = 0,
) -> dict:
    """
    Calculate annual tax on iDeCo annuity withdrawal (年金方式 / 雑所得).

    iDeCo annuity income is treated as miscellaneous income (雑所得) classified
    as public pension etc., so the public pension income deduction applies.
    Combined with other pension income (kokumin/kosei) for the deduction calculation.

    Args:
        annual_withdrawal_jpy:   Annual iDeCo annuity drawdown.
        age:                     Recipient age (affects pension deduction).
        other_pension_income_jpy: Other pension income (kokumin + kosei).

    Returns:
        dict with deduction, taxable, income_tax, residence_tax, net_annual.
    """
    from engine.tax_calculator import (
        calculate_pension_income_deduction,
        calculate_income_tax_from_taxable,
        calculate_residence_tax,
    )

    total_pension_type_income = annual_withdrawal_jpy + other_pension_income_jpy
    deduction = calculate_pension_income_deduction(total_pension_type_income, age)
    taxable = max(0, total_pension_type_income - deduction)

    income_tax = calculate_income_tax_from_taxable(taxable)
    residence_tax = calculate_residence_tax(taxable)["total"]
    total_tax = income_tax + residence_tax
    net = annual_withdrawal_jpy - total_tax

    return {
        "annual_withdrawal_jpy": annual_withdrawal_jpy,
        "other_pension_income_jpy": other_pension_income_jpy,
        "total_pension_type_income": total_pension_type_income,
        "pension_income_deduction": deduction,
        "taxable_income": taxable,
        "income_tax": income_tax,
        "residence_tax": residence_tax,
        "total_tax": total_tax,
        "net_annual_jpy": net,
        "effective_tax_rate_pct": round(total_tax / annual_withdrawal_jpy * 100, 2) if annual_withdrawal_jpy > 0 else 0.0,
        "method": "annuity",
    }


def compare_withdrawal_methods(
    balance_jpy: int,
    contribution_years: int,
    age_at_withdrawal: int = 60,
    annuity_years: int = 20,
    other_pension_income_jpy: int = 0,
    annual_return_during_annuity: float = 0.0,
) -> dict:
    """
    Compare lump sum vs annuity withdrawal for the same iDeCo balance.

    For annuity, assumes balance is drawn down equally over annuity_years
    (simplified — ignores growth during drawdown by default).

    Returns:
        dict with lump_sum, annuity, recommended (str), reason (str).
    """
    lump = calculate_lump_sum_withdrawal_tax(balance_jpy, contribution_years)

    annual_draw = balance_jpy // annuity_years
    annuity_result = calculate_annuity_withdrawal_tax(
        annual_draw, age_at_withdrawal, other_pension_income_jpy
    )
    annuity_total_tax = annuity_result["total_tax"] * annuity_years
    annuity_net = balance_jpy - annuity_total_tax

    lump_is_better = lump["net_receipt_jpy"] >= annuity_net

    return {
        "balance_jpy": balance_jpy,
        "lump_sum": {
            "net_receipt_jpy": lump["net_receipt_jpy"],
            "total_tax_jpy": lump["total_tax"],
            "effective_rate_pct": lump["effective_tax_rate_pct"],
        },
        "annuity": {
            "annual_withdrawal_jpy": annual_draw,
            "annuity_years": annuity_years,
            "annual_tax_jpy": annuity_result["total_tax"],
            "total_tax_jpy": annuity_total_tax,
            "net_receipt_jpy": annuity_net,
            "effective_rate_pct": round(annuity_total_tax / balance_jpy * 100, 2) if balance_jpy > 0 else 0.0,
        },
        "recommended": "lump_sum" if lump_is_better else "annuity",
        "reason": (
            "Lump sum applies the retirement income deduction and halves taxable income — "
            "usually more tax-efficient for typical iDeCo balances."
            if lump_is_better
            else "Annuity may be more efficient when other pension income is low enough "
                 "to stay under the public pension deduction threshold."
        ),
    }


# ---------------------------------------------------------------------------
# FIRE-specific: iDeCo bridge calculation
# ---------------------------------------------------------------------------

def calculate_ideco_bridge_need(
    fire_age: int,
    annual_expenses_jpy: int,
    annual_return_rate: float = 0.04,
) -> dict:
    """
    Calculate how much liquid portfolio is needed to bridge from FIRE to iDeCo access at 60.

    If retiring before 60, iDeCo is completely inaccessible. The liquid portfolio
    (NISA + taxable brokerage) must fund 100% of expenses during the gap.

    Args:
        fire_age:             Target early retirement age.
        annual_expenses_jpy:  Annual retirement expenses (pre-NHI for simplicity).
        annual_return_rate:   Expected portfolio return during bridge period.

    Returns:
        dict with gap_years, bridge_portfolio_needed_jpy, warning (if applicable).
    """
    if fire_age >= _ACCESS_AGE:
        return {
            "fire_age": fire_age,
            "ideco_access_age": _ACCESS_AGE,
            "gap_years": 0,
            "bridge_needed": False,
            "bridge_portfolio_needed_jpy": 0,
            "warning": None,
        }

    gap_years = _ACCESS_AGE - fire_age

    # Present value of expenses needed over the gap, accounting for portfolio growth
    # PV = PMT × (1 - (1+r)^-n) / r
    r = annual_return_rate
    if r == 0:
        pv = annual_expenses_jpy * gap_years
    else:
        pv = int(annual_expenses_jpy * (1 - (1 + r) ** -gap_years) / r)

    return {
        "fire_age": fire_age,
        "ideco_access_age": _ACCESS_AGE,
        "gap_years": gap_years,
        "bridge_needed": True,
        "bridge_portfolio_needed_jpy": pv,
        "annual_expenses_jpy": annual_expenses_jpy,
        "assumed_return_pct": annual_return_rate * 100,
        "warning": (
            f"iDeCo is locked until age 60. You need {gap_years} years of liquid "
            f"portfolio (NISA + taxable) to bridge the gap. "
            f"iDeCo balance cannot be counted toward your accessible FIRE number."
        ),
    }
