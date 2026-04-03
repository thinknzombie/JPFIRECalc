"""
National Health Insurance (国民健康保険 / NHI) premium calculations.

NHI premiums apply to people not covered by company health insurance —
primarily the self-employed, retirees, and those between jobs.

Premium structure (varies by municipality):
  Medical component (医療分)    = income_rate × (income - 430,000) + per_capita × members
  Support component (支援分)   = income_rate × (income - 430,000) + per_capita × members
  Long-term care (介護分)      = income_rate × (income - 430,000) + per_capita × members
      → LTC only applies to household members aged 40–64.
      → Age 65+: LTC premium is collected separately via pension deduction.

The income used is the *prior year's* income (前年所得), reduced by a fixed
430,000 yen deduction before applying rates.

Annual caps (FY2024):
  Medical + Support combined: 1,060,000 yen
  Long-term care:               170,000 yen

Key complexity for FIRE planning:
  Higher withdrawal → higher NHI → need to withdraw more → higher NHI again.
  `solve_withdrawal_with_nhi()` handles this circular dependency iteratively.

Sources: Municipal websites, 厚生労働省 — approximate FY2024 rates.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "nhi_rates.json", encoding="utf-8") as _f:
    _NHI = json.load(_f)

_MUNICIPALITIES = _NHI["municipalities"]
_NATIONAL_AVG = _NHI["national_average"]
_INCOME_DEDUCTION = _NHI["income_deduction_for_nhi"]
_ANNUAL_CAP = _NHI["annual_cap_jpy"]
_LTC_CAP = _NHI["long_term_care_annual_cap_jpy"]


# ---------------------------------------------------------------------------
# Data lookup
# ---------------------------------------------------------------------------

def get_municipality_rates(municipality_key: str) -> dict:
    """
    Return NHI rate data for a municipality.
    Falls back to national average if key not found.
    """
    return _MUNICIPALITIES.get(municipality_key, _NATIONAL_AVG)


def list_municipality_keys() -> list[str]:
    """Return all available municipality keys."""
    return list(_MUNICIPALITIES.keys())


# ---------------------------------------------------------------------------
# Core premium calculation
# ---------------------------------------------------------------------------

def calculate_nhi_premium(
    annual_income: int,
    num_members: int,
    municipality_key: str,
    ltc_eligible_members: int = 0,
) -> dict:
    """
    Calculate annual NHI premium for a household.

    Args:
        annual_income:          Annual income used for NHI assessment (前年所得, JPY).
                                For retirees this is the portfolio withdrawal amount.
        num_members:            Total number of NHI-enrolled household members.
        municipality_key:       Key from nhi_rates.json (e.g. "tokyo_shinjuku").
        ltc_eligible_members:   Members aged 40–64 (who pay the LTC component).
                                Members 65+ have LTC collected separately.

    Returns:
        dict with medical, support, ltc, total, capped_total, breakdown.
    """
    rates = get_municipality_rates(municipality_key)

    # Base income for NHI = income - 430,000 deduction (floored at 0)
    assessed_income = max(0, annual_income - _INCOME_DEDUCTION)

    # Medical component (医療分)
    medical = (
        int(assessed_income * rates["medical_income_rate"])
        + rates["medical_per_capita"] * num_members
    )

    # Support component (支援分)
    support = (
        int(assessed_income * rates["support_income_rate"])
        + rates["support_per_capita"] * num_members
    )

    # Long-term care component (介護分) — only for members aged 40–64
    if ltc_eligible_members > 0:
        ltc = (
            int(assessed_income * rates["ltc_income_rate"])
            + rates["ltc_per_capita"] * ltc_eligible_members
        )
        ltc = min(ltc, _LTC_CAP)
    else:
        ltc = 0

    # Apply annual cap to medical + support combined
    medical_support = medical + support
    capped_medical_support = min(medical_support, _ANNUAL_CAP)

    total = capped_medical_support + ltc

    return {
        "municipality": rates["name"],
        "assessed_income": assessed_income,
        "medical": medical,
        "support": support,
        "medical_support_before_cap": medical_support,
        "medical_support_capped": capped_medical_support,
        "ltc": ltc,
        "total": total,
        "annual_cap_medical_support": _ANNUAL_CAP,
        "ltc_cap": _LTC_CAP,
        "cap_hit": medical_support > _ANNUAL_CAP,
    }


# ---------------------------------------------------------------------------
# Retirement-specific helpers
# ---------------------------------------------------------------------------

def calculate_nhi_for_retiree(
    withdrawal_jpy: int,
    num_members: int,
    municipality_key: str,
    age: int,
) -> dict:
    """
    Convenience wrapper for retirees.

    Determines LTC eligibility from age:
      - Under 40:  no LTC component
      - 40–64:     LTC component applies
      - 65+:       LTC collected via pension, not NHI

    Args:
        withdrawal_jpy:     Annual portfolio withdrawal (used as income for NHI).
        num_members:        Enrolled NHI household members.
        municipality_key:   Municipality rate key.
        age:                Age of the primary member (used for LTC eligibility).
    """
    ltc_eligible = 1 if 40 <= age <= 64 else 0
    result = calculate_nhi_premium(
        annual_income=withdrawal_jpy,
        num_members=num_members,
        municipality_key=municipality_key,
        ltc_eligible_members=ltc_eligible,
    )
    result["age"] = age
    result["ltc_via_pension"] = age >= 65
    return result


# ---------------------------------------------------------------------------
# Iterative solver: withdrawal needed given target expenses + NHI
# ---------------------------------------------------------------------------

def solve_withdrawal_with_nhi(
    target_net_expenses: int,
    num_members: int,
    municipality_key: str,
    age: int,
    max_iterations: int = 50,
    tolerance: int = 100,
) -> dict:
    """
    Solve for the gross withdrawal amount needed to cover expenses after NHI.

    The circular dependency:
        withdrawal = expenses + NHI(withdrawal)
        NHI = f(withdrawal)   [NHI rises with withdrawal]

    This iterates until the withdrawal converges (within `tolerance` yen).

    Args:
        target_net_expenses:  Annual expenses excluding NHI (JPY).
        num_members:          NHI household members.
        municipality_key:     Municipality rate key.
        age:                  Age of primary member (for LTC eligibility).
        max_iterations:       Safety limit on iterations.
        tolerance:            Convergence threshold in JPY (default 100 yen).

    Returns:
        dict with gross_withdrawal, nhi_premium, net_expenses, iterations,
        converged (bool).
    """
    # Seed: start with just the expenses, no NHI
    withdrawal = target_net_expenses

    for i in range(max_iterations):
        nhi_result = calculate_nhi_for_retiree(withdrawal, num_members, municipality_key, age)
        nhi = nhi_result["total"]
        new_withdrawal = target_net_expenses + nhi

        if abs(new_withdrawal - withdrawal) <= tolerance:
            return {
                "gross_withdrawal": new_withdrawal,
                "nhi_premium": nhi,
                "net_expenses": target_net_expenses,
                "total_cost": new_withdrawal,
                "nhi_as_pct_of_withdrawal": round(nhi / new_withdrawal * 100, 2) if new_withdrawal > 0 else 0,
                "iterations": i + 1,
                "converged": True,
                "municipality": nhi_result["municipality"],
                "cap_hit": nhi_result["cap_hit"],
            }
        withdrawal = new_withdrawal

    # Did not converge — return best estimate
    nhi_result = calculate_nhi_for_retiree(withdrawal, num_members, municipality_key, age)
    return {
        "gross_withdrawal": withdrawal,
        "nhi_premium": nhi_result["total"],
        "net_expenses": target_net_expenses,
        "total_cost": withdrawal,
        "nhi_as_pct_of_withdrawal": round(nhi_result["total"] / withdrawal * 100, 2) if withdrawal > 0 else 0,
        "iterations": max_iterations,
        "converged": False,
        "municipality": nhi_result["municipality"],
        "cap_hit": nhi_result["cap_hit"],
    }


# ---------------------------------------------------------------------------
# NHI reduction for low-income households (軽減制度)
# ---------------------------------------------------------------------------

def calculate_nhi_reduction(
    annual_income: int,
    num_members: int,
) -> float:
    """
    Return the per-capita levy reduction rate for low-income households.

    The per-capita component of NHI is reduced for households below income
    thresholds. Thresholds are approximate national standards.

    Returns:
        Reduction rate: 0.0 (no reduction), 0.2, 0.3, 0.5, or 0.7.
        Multiply the per-capita amount by (1 - reduction_rate).
    """
    # Approximate 2024 thresholds (vary slightly by municipality)
    # 7-wari (70%) reduction: income ≤ 430,000 + (10,000 × members)
    # 5-wari (50%) reduction: income ≤ 430,000 + (295,000 × members)
    # 2-wari (20%) reduction: income ≤ 430,000 + (545,000 × members)
    thresholds = [
        (0.7, 430_000 + 10_000 * num_members),
        (0.5, 430_000 + 295_000 * num_members),
        (0.2, 430_000 + 545_000 * num_members),
    ]
    for reduction_rate, threshold in thresholds:
        if annual_income <= threshold:
            return reduction_rate
    return 0.0
