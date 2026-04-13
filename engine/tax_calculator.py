"""
Japan income tax and residence tax calculations.

All monetary values are in JPY (integer). Input gross_income is annual.
Sources: NTA (国税庁) — 2024 tax year figures.
"""
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Load once at module level
with open(DATA_DIR / "tax_brackets.json", encoding="utf-8") as _f:
    _TAX = json.load(_f)

_INCOME_TAX_BRACKETS = _TAX["income_tax_brackets"]
_EI_DEDUCTION = _TAX["employment_income_deduction"]["brackets"]
_BASIC_DEDUCTION = _TAX["basic_deduction"]["brackets"]
_PENSION_DEDUCTION_UNDER65 = _TAX["public_pension_income_deduction"]["under_65"]
_PENSION_DEDUCTION_65PLUS = _TAX["public_pension_income_deduction"]["age_65_plus"]
_RETIREMENT_DEDUCTION = _TAX["retirement_income_deduction"]
_SURTAX_RATE = _TAX["surtax_rate"]


# ---------------------------------------------------------------------------
# Employment income deduction  (給与所得控除)
# ---------------------------------------------------------------------------

def calculate_employment_income_deduction(gross_income: int) -> int:
    """Return the employment income deduction for a given gross salary.

    Formula per NTA 2024: deduction = income × rate + base
    https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1410.htm
    """
    for bracket in _EI_DEDUCTION:
        hi = bracket["max"]
        if hi is None or gross_income <= hi:
            if bracket["deduction"] is not None:
                return bracket["deduction"]
            # Rate-based bracket: income × rate + base (base may be negative)
            deduction = int(gross_income * bracket["rate"]) + bracket.get("base", 0)
            return max(deduction, 0)
    # Fallback: max deduction
    return 1_950_000


def calculate_employment_income(gross_income: int) -> int:
    """Return employment income (給与所得) after deduction."""
    return max(0, gross_income - calculate_employment_income_deduction(gross_income))


# ---------------------------------------------------------------------------
# Basic deduction  (基礎控除)
# ---------------------------------------------------------------------------

def calculate_basic_deduction(gross_income: int) -> int:
    """Return the basic deduction amount based on gross income."""
    for bracket in _BASIC_DEDUCTION:
        if bracket["max_income"] is None or gross_income <= bracket["max_income"]:
            return bracket["deduction"]
    return 0


# ---------------------------------------------------------------------------
# Public pension income deduction  (公的年金等控除)
# ---------------------------------------------------------------------------

def calculate_pension_income_deduction(pension_income: int, age: int) -> int:
    """Return the public pension income deduction for given pension income and age."""
    brackets = _PENSION_DEDUCTION_65PLUS if age >= 65 else _PENSION_DEDUCTION_UNDER65
    for b in brackets:
        lo = b["min"]
        hi = b["max"]
        if hi is None or pension_income <= hi:
            if b["deduction"] is not None:
                return b["deduction"]
            return int(pension_income * b["rate"]) + b["base"]
    return 0


def calculate_pension_taxable_income(pension_income: int, age: int) -> int:
    """Return pension taxable income after the public pension deduction."""
    return max(0, pension_income - calculate_pension_income_deduction(pension_income, age))


# ---------------------------------------------------------------------------
# Core income tax  (所得税)
# ---------------------------------------------------------------------------

def calculate_income_tax_from_taxable(taxable_income: int) -> int:
    """
    Calculate income tax (incl. 2.1% reconstruction surtax) from taxable income.
    Uses the bracket deduction formula: tax = taxable * rate - deduction_amount.
    Returns the tax rounded down to the nearest 100 yen (as per NTA rules).
    """
    if taxable_income <= 0:
        return 0

    base_tax = 0
    for b in _INCOME_TAX_BRACKETS:
        lo = b["min"]
        hi = b["max"]
        if hi is None or taxable_income <= hi:
            base_tax = int(taxable_income * b["rate"]) - b["deduction"]
            break

    base_tax = max(0, base_tax)
    surtax = math.floor(base_tax * _SURTAX_RATE)
    total = base_tax + surtax
    # Round down to nearest 100 yen
    return (total // 100) * 100


def calculate_income_tax(
    gross_income: int,
    employment_type: str = "company_employee",
    ideco_monthly_jpy: int = 0,
    num_dependents: int = 0,
    has_spouse: bool = False,
    spouse_income_jpy: int = 0,
    social_insurance_premium: int = 0,
    other_deductions: int = 0,
) -> dict:
    """
    Calculate income tax and supporting figures for an employed individual.

    Args:
        gross_income:           Annual gross employment income (JPY).
        employment_type:        "company_employee" | "self_employed" | "civil_servant"
        ideco_monthly_jpy:      Monthly iDeCo contribution (deductible).
        num_dependents:         Number of qualifying dependents (扶養控除).
        has_spouse:             Whether taxpayer has a qualifying spouse.
        spouse_income_jpy:      Spouse annual income (for spouse deduction eligibility).
        social_insurance_premium: Annual social insurance paid (社会保険料控除).
        other_deductions:       Any additional deductions.

    Returns:
        dict with keys:
            gross_income, employment_income, taxable_income, income_tax,
            basic_deduction, ideco_deduction, dependent_deduction,
            spouse_deduction, social_insurance_deduction, effective_rate_pct
    """
    # Step 1: employment income after deduction
    if employment_type in ("company_employee", "civil_servant"):
        emp_income = calculate_employment_income(gross_income)
    else:
        # Self-employed: gross_income is already net business income (事業所得)
        emp_income = gross_income

    # Step 2: build deductions
    basic_ded = calculate_basic_deduction(gross_income)
    ideco_ded = ideco_monthly_jpy * 12
    dependent_ded = num_dependents * _TAX["dependent_deduction_per_person"]

    spouse_ded = 0
    spouse_cfg = _TAX["spouse_deduction"]
    if (
        has_spouse
        and gross_income <= spouse_cfg["taxpayer_income_limit"]
        and spouse_income_jpy <= spouse_cfg["spouse_income_limit_full"]
    ):
        spouse_ded = spouse_cfg["full_deduction"]

    total_deductions = (
        basic_ded
        + ideco_ded
        + dependent_ded
        + spouse_ded
        + social_insurance_premium
        + other_deductions
    )

    taxable_income = max(0, emp_income - total_deductions)

    # Step 3: apply tax brackets
    income_tax = calculate_income_tax_from_taxable(taxable_income)

    effective_rate = (income_tax / gross_income * 100) if gross_income > 0 else 0.0

    return {
        "gross_income": gross_income,
        "employment_income": emp_income,
        "basic_deduction": basic_ded,
        "ideco_deduction": ideco_ded,
        "dependent_deduction": dependent_ded,
        "spouse_deduction": spouse_ded,
        "social_insurance_deduction": social_insurance_premium,
        "total_deductions": total_deductions,
        "taxable_income": taxable_income,
        "income_tax": income_tax,
        "effective_rate_pct": round(effective_rate, 2),
    }


# ---------------------------------------------------------------------------
# Residence tax  (住民税)
# ---------------------------------------------------------------------------

def calculate_residence_tax(
    taxable_income: int,
    per_capita_levy: int | None = None,
    residence_tax_rate_pct: float | None = None,
) -> dict:
    """
    Calculate residence tax (住民税).

    Residence tax = rate × taxable income + per-capita levy.
    Rate and levy can be overridden via app settings.

    Args:
        taxable_income:         Taxable income (same base used for income tax).
        per_capita_levy:        Annual per-capita charge 均等割 (None → use settings or 5,000).
        residence_tax_rate_pct: Flat rate in percent (None → use settings or 10.0%).

    Returns:
        dict with income_based, per_capita, total.
    """
    # Pull defaults from settings if not explicitly provided
    if per_capita_levy is None or residence_tax_rate_pct is None:
        try:
            import storage.settings_store as _ss
            s = _ss.get()
            if per_capita_levy is None:
                per_capita_levy = s.residence_tax_per_capita_jpy
            if residence_tax_rate_pct is None:
                residence_tax_rate_pct = s.residence_tax_rate_pct
        except Exception:
            if per_capita_levy is None:
                per_capita_levy = 5_000
            if residence_tax_rate_pct is None:
                residence_tax_rate_pct = 10.0

    rate = residence_tax_rate_pct / 100
    income_based = int(taxable_income * rate)
    total = income_based + per_capita_levy
    return {
        "income_based": income_based,
        "per_capita": per_capita_levy,
        "total": total,
    }


def calculate_year1_retirement_tax_shock(
    last_working_gross: int,
    employment_type: str = "company_employee",
    ideco_monthly_jpy: int = 0,
    num_dependents: int = 0,
    has_spouse: bool = False,
    spouse_income_jpy: int = 0,
    social_insurance_premium: int = 0,
    per_capita_levy: int = 5_000,
    liquidated_assets_jpy: int = 0,
) -> dict:
    """
    Calculate the residence tax owed in year 1 of retirement.

    In Japan, residence tax for year N is assessed on year N-1 income and
    billed/paid in year N (typically June–May). A retiree pays full residence
    tax on their last working year's income even though they have no salary.

    Any equity, RSU, or other assets liquidated in the FIRE year are treated
    as additional ordinary income (雑所得/分離課税) in that tax year, so this
    function adds them to the gross income used for the income-tax calculation
    that underlies the residence tax base.

    Args:
        liquidated_assets_jpy: Value of equity/RSU/other assets sold in the
            FIRE year (above and beyond regular salary). These are added to
            gross income for the shock calculation.

    Returns:
        dict with last_working_year_residence_tax, retirement_year_residence_tax,
        shock_amount (= last_working_year_residence_tax, since retirement year = 0)
    """
    last_year_result = calculate_income_tax(
        gross_income=last_working_gross + liquidated_assets_jpy,
        employment_type=employment_type,
        ideco_monthly_jpy=ideco_monthly_jpy,
        num_dependents=num_dependents,
        has_spouse=has_spouse,
        spouse_income_jpy=spouse_income_jpy,
        social_insurance_premium=social_insurance_premium,
    )
    residence_tax = calculate_residence_tax(
        last_year_result["taxable_income"], per_capita_levy
    )

    return {
        "last_working_year_gross": last_working_gross,
        "liquidated_assets_jpy": liquidated_assets_jpy,
        "last_working_year_taxable_income": last_year_result["taxable_income"],
        "year1_residence_tax": residence_tax["total"],
        "income_based_component": residence_tax["income_based"],
        "per_capita_component": residence_tax["per_capita"],
        "note": (
            "This full amount is owed in the first year of retirement "
            "even with zero salary income."
        ),
    }


# ---------------------------------------------------------------------------
# Retirement income tax  (退職所得 — for iDeCo lump sum)
# ---------------------------------------------------------------------------

def calculate_retirement_income_deduction(contribution_years: int) -> int:
    """
    Calculate the retirement income deduction (退職所得控除).

    Used for iDeCo lump-sum withdrawals and severance pay.

    Args:
        contribution_years: Number of years of contributions (iDeCo tenure).

    Returns:
        Deduction amount in JPY.
    """
    minimum = _RETIREMENT_DEDUCTION["minimum"]
    if contribution_years <= 20:
        deduction = contribution_years * _RETIREMENT_DEDUCTION["per_year_under_20"]
    else:
        deduction = (
            20 * _RETIREMENT_DEDUCTION["per_year_under_20"]
            + (contribution_years - 20) * _RETIREMENT_DEDUCTION["per_year_over_20"]
        )
    return max(deduction, minimum)


def calculate_retirement_income_tax(balance: int, contribution_years: int) -> dict:
    """
    Calculate income tax on an iDeCo lump-sum withdrawal.

    Formula:
        retirement_income = (balance - retirement_income_deduction) / 2
        tax = income_tax_brackets(retirement_income)

    This is highly tax-advantaged — the /2 halves the effective rate.

    Args:
        balance:             iDeCo account balance at withdrawal (JPY).
        contribution_years:  Years of iDeCo contributions.

    Returns:
        dict with deduction, taxable_retirement_income, income_tax, effective_rate_pct.
    """
    deduction = calculate_retirement_income_deduction(contribution_years)
    net = max(0, balance - deduction)
    taxable_retirement_income = net // 2  # the /2 rule
    tax = calculate_income_tax_from_taxable(taxable_retirement_income)
    effective_rate = (tax / balance * 100) if balance > 0 else 0.0
    return {
        "balance": balance,
        "contribution_years": contribution_years,
        "retirement_income_deduction": deduction,
        "net_after_deduction": net,
        "taxable_retirement_income": taxable_retirement_income,
        "income_tax": tax,
        "effective_rate_pct": round(effective_rate, 2),
    }


# ---------------------------------------------------------------------------
# Capital gains tax  (譲渡所得税 — for taxable brokerage)
# ---------------------------------------------------------------------------

def calculate_capital_gains_tax(gain: int) -> int:
    """
    Calculate capital gains tax at the flat 20.315% rate.
    Applies to gains from selling stocks/ETFs in a tokutei account.
    """
    return int(gain * _TAX["capital_gains_tax_rate"])
