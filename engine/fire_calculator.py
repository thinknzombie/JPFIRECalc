"""
Core FIRE calculation engine.

Orchestrates all other engines to produce FIRE numbers, net worth
projections, and variant calculations (Coast, Barista).

Key Japan-specific design decisions:
  1. FIRE number uses NET pension income — pension offsets the portfolio need.
  2. NHI premium is solved iteratively (circular dependency with withdrawal).
  3. Year-1 residence tax shock is modelled as a one-time retirement expense.
  4. iDeCo is excluded from accessible portfolio if FIRE age < 60.
  5. Recommended withdrawal rate is 3.0–3.5% for Japan (not the US 4% rule).

All monetary values in JPY (int). Rates/percentages as floats (e.g. 0.05 = 5%).
"""
from __future__ import annotations
import math
from models.profile import FinancialProfile, UserProfile
from models.scenario import AssumptionSet, ScenarioResult, YearProjection
from models.region_data import get_region_template, get_nhi_municipality_key
from engine.tax_calculator import (
    calculate_income_tax,
    calculate_residence_tax,
    calculate_year1_retirement_tax_shock,
)
from engine.nhi_calculator import solve_withdrawal_with_nhi, calculate_nhi_for_retiree
from engine.pension_calculator import (
    calculate_kokumin_nenkin,
    calculate_kosei_nenkin,
    calculate_total_pension,
    calculate_pension_after_tax,
)
from engine.ideco_calculator import (
    calculate_ideco_accumulation,
    calculate_ideco_bridge_need,
)
from engine.nisa_calculator import calculate_nisa_growth


# ---------------------------------------------------------------------------
# FIRE number
# ---------------------------------------------------------------------------

def calculate_fire_number(
    annual_expenses_jpy: int,
    withdrawal_rate: float,
    net_pension_annual_jpy: int = 0,
) -> dict:
    """
    Calculate the target portfolio size (FIRE number).

    FIRE number = (annual_expenses - net_pension) / withdrawal_rate

    Net pension income reduces the portfolio needed because it covers part
    of expenses without requiring portfolio withdrawals.

    Args:
        annual_expenses_jpy:   Target annual retirement expenses (excluding NHI,
                               which is solved separately via the withdrawal solver).
        withdrawal_rate:       As a decimal, e.g. 0.035 for 3.5%.
        net_pension_annual_jpy: After-tax annual pension income (all sources).

    Returns:
        dict with fire_number_jpy, net_annual_need_jpy, pension_offset_jpy,
        withdrawal_rate_pct, warning_on_rate.
    """
    if withdrawal_rate <= 0:
        raise ValueError("withdrawal_rate must be positive.")

    net_need = max(0, annual_expenses_jpy - net_pension_annual_jpy)
    fire_number = int(net_need / withdrawal_rate) if net_need > 0 else 0
    pension_offset = int(net_pension_annual_jpy / withdrawal_rate) if net_pension_annual_jpy > 0 else 0

    warning = None
    if withdrawal_rate > 0.04:
        warning = (
            f"Withdrawal rate {withdrawal_rate*100:.1f}% exceeds 4%. "
            "Japan research suggests 3.0–3.5% for higher safety."
        )

    return {
        "fire_number_jpy": fire_number,
        "net_annual_need_jpy": net_need,
        "pension_offset_jpy": pension_offset,
        "withdrawal_rate_pct": withdrawal_rate * 100,
        "annual_expenses_jpy": annual_expenses_jpy,
        "net_pension_annual_jpy": net_pension_annual_jpy,
        "warning_on_rate": warning,
    }


# ---------------------------------------------------------------------------
# Retirement expense calculation
# ---------------------------------------------------------------------------

def calculate_retirement_expenses(
    profile: FinancialProfile,
    region_key: str,
    use_region_template: bool = True,
) -> dict:
    """
    Build the full annual retirement expense budget.

    If use_region_template is True, use the template as the base and
    add any known fixed costs (mortgage if still active). Otherwise
    use profile.monthly_expenses_jpy directly.

    Note: NHI is NOT included here — it is added separately via the
    withdrawal solver because it depends on withdrawal amount.

    Returns dict with annual_expenses_jpy and breakdown.
    """
    if use_region_template:
        template = get_region_template(region_key)
        base_monthly = template["total_monthly"]
    else:
        base_monthly = profile.monthly_expenses_jpy

    # Subtract mortgage if it'll be paid off by retirement
    mortgage_monthly = 0
    if profile.owns_property and not profile.property_paid_off_at_retirement:
        mortgage_monthly = profile.monthly_mortgage_payment_jpy

    # Add rental income (reduces expenses)
    rental_monthly = profile.rental_income_monthly_jpy
    rental_monthly += getattr(profile, 'foreign_property_rental_monthly_jpy', 0)

    net_monthly = base_monthly + mortgage_monthly - rental_monthly
    annual = max(0, net_monthly * 12)

    return {
        "annual_expenses_jpy": annual,
        "monthly_expenses_jpy": net_monthly,
        "base_monthly_jpy": base_monthly,
        "mortgage_monthly_jpy": mortgage_monthly,
        "rental_income_monthly_jpy": rental_monthly,
        "region_key": region_key,
    }


# ---------------------------------------------------------------------------
# Pension income at retirement
# ---------------------------------------------------------------------------

def calculate_pension_at_retirement(
    profile: FinancialProfile,
    years_accumulated_by_retirement: int,
) -> dict:
    """
    Estimate combined after-tax pension income at retirement age.

    Uses contribution months accumulated to retirement date.
    """
    total_months_by_retirement = (
        profile.nenkin_contribution_months + years_accumulated_by_retirement * 12
    )

    kokumin = calculate_kokumin_nenkin(total_months_by_retirement, profile.nenkin_claim_age)

    if profile.nenkin_net_kosei_annual_jpy is not None:
        kosei = calculate_kosei_nenkin(
            avg_standard_monthly_remuneration=0,
            contribution_months=0,
            claim_age=profile.nenkin_claim_age,
            nenkin_net_override_annual_jpy=profile.nenkin_net_kosei_annual_jpy,
        )
    else:
        kosei = calculate_kosei_nenkin(
            avg_standard_monthly_remuneration=profile.avg_standard_monthly_remuneration_jpy,
            contribution_months=total_months_by_retirement,
            claim_age=profile.nenkin_claim_age,
        )

    total = calculate_total_pension(
        kokumin["annual_benefit_jpy"],
        kosei["annual_benefit_jpy"],
        profile.foreign_pension_annual_jpy,
    )

    # Tax on pension at claim age
    after_tax = calculate_pension_after_tax(
        total["total_annual_jpy"],
        age=profile.nenkin_claim_age,
    )

    return {
        "kokumin_annual_jpy": kokumin["annual_benefit_jpy"],
        "kosei_annual_jpy": kosei["annual_benefit_jpy"],
        "foreign_pension_annual_jpy": profile.foreign_pension_annual_jpy,
        "gross_pension_annual_jpy": total["total_annual_jpy"],
        "net_pension_annual_jpy": after_tax["net_pension_annual_jpy"],
        "pension_tax_jpy": after_tax["total_tax"],
        "nenkin_claim_age": profile.nenkin_claim_age,
        "pension_income_deduction": after_tax["pension_deduction"],
    }


# ---------------------------------------------------------------------------
# Property sale proceeds
# ---------------------------------------------------------------------------

def _amortise_mortgage(
    balance_jpy: int,
    monthly_payment_jpy: int,
    years: int,
    annual_rate: float | None = None,
) -> int:
    """
    Estimate remaining mortgage balance after *years* of regular payments.

    Uses a standard amortisation schedule at the given annual interest rate.
    Falls back to the original balance if inputs are zero/implausible.

    Args:
        balance_jpy:        Current outstanding principal.
        monthly_payment_jpy: Regular monthly payment amount.
        years:              Number of years of payments to simulate.
        annual_rate:        Assumed annual interest rate (None → use settings, default 1.5%).

    Returns:
        Estimated remaining balance (floored at 0).
    """
    if annual_rate is None:
        try:
            import storage.settings_store as _ss
            annual_rate = _ss.get().mortgage_interest_rate_pct / 100
        except Exception:
            annual_rate = 0.015
    if balance_jpy <= 0 or monthly_payment_jpy <= 0 or years <= 0:
        return max(0, balance_jpy)
    monthly_rate = annual_rate / 12
    balance = float(balance_jpy)
    for _ in range(years * 12):
        interest = balance * monthly_rate
        principal = monthly_payment_jpy - interest
        if principal <= 0:
            break  # payment doesn't cover interest — balance stays (unusual edge case)
        balance = max(0.0, balance - principal)
    return int(balance)


def calculate_property_sale_proceeds(
    current_value_jpy: int,
    mortgage_balance_jpy: int,
    years_until_sale: int,
    appreciation_pct: float,
    monthly_mortgage_payment_jpy: int = 0,
    transaction_cost_pct: float = 4.0,
    held_long_term: bool = True,
) -> dict:
    """
    Estimate net cash proceeds from a planned property sale.

    Appreciation is compounded annually from the current market value.
    Capital gains tax applies to the appreciation portion only (using the
    current value as a proxy for acquisition cost — conservative if the
    property was bought higher, optimistic if bought lower).

    The mortgage balance is amortised over years_until_sale using a standard
    schedule at an assumed 1.5 % annual rate (Japan average). Pass
    monthly_mortgage_payment_jpy=0 to skip amortisation and use the raw balance.

    Japan CGT rates:
      - Long-term (> 5 years held): 20.315%  (所得税15.315% + 住民税5%)
      - Short-term (≤ 5 years):    39.63%   (所得税30.63% + 住民税9%)

    The 3,000万円 primary-residence special deduction is NOT modelled here
    (it requires knowing whether the property is a primary residence and how
    long the owner lived there). Users should factor this in manually.

    Args:
        current_value_jpy:          Current market value.
        mortgage_balance_jpy:       Current outstanding mortgage principal.
        years_until_sale:           Years between now and the planned sale.
        appreciation_pct:           Expected annual appreciation (e.g. 1.0 = 1 %).
        monthly_mortgage_payment_jpy: Monthly payment; used to amortise balance.
                                    0 = use balance as-is (no amortisation).
        transaction_cost_pct:       Agent/stamp/misc costs as % of sale price (default 4 %).
        held_long_term:             True → 20.315 % rate; False → 39.63 % rate.

    Returns:
        dict with sale_value_jpy, capital_gain_jpy, capital_gains_tax_jpy,
        transaction_costs_jpy, mortgage_cleared_jpy, net_proceeds_jpy, tax_rate_pct.
    """
    sale_value = int(current_value_jpy * (1 + appreciation_pct / 100) ** years_until_sale)
    capital_gain = max(0, sale_value - current_value_jpy)
    cg_rate = 0.20315 if held_long_term else 0.39630
    cg_tax = int(capital_gain * cg_rate)
    tx_costs = int(sale_value * transaction_cost_pct / 100)

    # Amortise mortgage to sale date
    remaining_mortgage = _amortise_mortgage(
        balance_jpy=mortgage_balance_jpy,
        monthly_payment_jpy=monthly_mortgage_payment_jpy,
        years=years_until_sale,
    ) if monthly_mortgage_payment_jpy > 0 else mortgage_balance_jpy

    net = max(0, sale_value - remaining_mortgage - cg_tax - tx_costs)
    return {
        "sale_value_jpy": sale_value,
        "capital_gain_jpy": capital_gain,
        "capital_gains_tax_jpy": cg_tax,
        "transaction_costs_jpy": tx_costs,
        "mortgage_cleared_jpy": remaining_mortgage,
        "net_proceeds_jpy": net,
        "tax_rate_pct": round(cg_rate * 100, 3),
    }


# ---------------------------------------------------------------------------
# Accessible portfolio today
# ---------------------------------------------------------------------------

def calculate_accessible_portfolio(
    profile: FinancialProfile,
    fire_age: int,
) -> dict:
    """
    Calculate the currently accessible portfolio for FIRE progress tracking.

    iDeCo is excluded from accessible assets if FIRE age < 60.
    """
    foreign_jpy = int(profile.foreign_assets_usd * profile.usd_jpy_rate)
    ideco_accessible = fire_age >= 60

    # Liquid / semi-liquid assets
    gold    = getattr(profile, 'gold_silver_value_jpy', 0)
    crypto  = getattr(profile, 'crypto_value_jpy', 0)
    rsu     = getattr(profile, 'rsu_unvested_value_jpy', 0)
    other   = getattr(profile, 'other_assets_jpy', 0)

    liquid = (
        profile.nisa_balance_jpy
        + profile.taxable_brokerage_jpy
        + profile.cash_savings_jpy
        + foreign_jpy
        + (profile.ideco_balance_jpy if ideco_accessible else 0)
        + gold + crypto + rsu + other
    )

    return {
        "nisa_jpy": profile.nisa_balance_jpy,
        "ideco_jpy": profile.ideco_balance_jpy,
        "taxable_jpy": profile.taxable_brokerage_jpy,
        "cash_jpy": profile.cash_savings_jpy,
        "foreign_jpy": foreign_jpy,
        "ideco_accessible": ideco_accessible,
        "total_accessible_jpy": liquid,
        "total_including_locked_ideco_jpy": liquid + (0 if ideco_accessible else profile.ideco_balance_jpy),
        "gold_jpy":   gold,
        "crypto_jpy": crypto,
        "rsu_jpy":    rsu,
        "other_jpy":  other,
    }


# ---------------------------------------------------------------------------
# Years to FIRE (analytical + iterative)
# ---------------------------------------------------------------------------

def calculate_years_to_fire(
    current_portfolio_jpy: int,
    annual_savings_jpy: int,
    fire_number_jpy: int,
    annual_return_rate: float,
) -> float:
    """
    Calculate years until the portfolio reaches the FIRE number.

    Uses the analytical solution where possible:
        FV = PV*(1+r)^n + PMT*((1+r)^n - 1)/r = FIRE_number
    Rearranged: (1+r)^n = (FIRE_number + PMT/r) / (PV + PMT/r)
    So:         n = log(ratio) / log(1+r)

    Falls back to iteration if the formula breaks down.

    Args:
        current_portfolio_jpy: Current accessible portfolio value.
        annual_savings_jpy:    Annual amount added to the portfolio.
        fire_number_jpy:       Target portfolio size.
        annual_return_rate:    Expected annual return (decimal).

    Returns:
        Years to FIRE (float). Returns inf if never reachable.
    """
    if fire_number_jpy <= 0:
        return 0.0
    if current_portfolio_jpy >= fire_number_jpy:
        return 0.0

    r = annual_return_rate

    if r == 0:
        if annual_savings_jpy <= 0:
            return float("inf")
        return (fire_number_jpy - current_portfolio_jpy) / annual_savings_jpy

    # Analytical solution
    pmt_r = annual_savings_jpy / r
    numerator = fire_number_jpy + pmt_r
    denominator = current_portfolio_jpy + pmt_r

    if denominator <= 0:
        return float("inf")

    ratio = numerator / denominator
    if ratio <= 0:
        return float("inf")

    years = math.log(ratio) / math.log(1 + r)
    return max(0.0, years)


# ---------------------------------------------------------------------------
# Coast FIRE number
# ---------------------------------------------------------------------------

def calculate_coast_fire_number(
    fire_number_jpy: int,
    years_until_retirement: int,
    annual_return_rate: float,
) -> dict:
    """
    Calculate the Coast FIRE number — the lump sum needed today that will
    grow to the FIRE number by retirement without additional contributions.

    Coast FIRE = FIRE_number / (1 + r)^n

    If your current portfolio >= coast_fire_number, you can stop contributing
    and just let it grow.

    Args:
        fire_number_jpy:       Target portfolio at retirement.
        years_until_retirement: Years until target retirement age.
        annual_return_rate:    Expected annual return (decimal).

    Returns:
        dict with coast_fire_number_jpy, already_coasting (bool), years_until_retirement.
    """
    if years_until_retirement <= 0:
        return {
            "coast_fire_number_jpy": fire_number_jpy,
            "years_until_retirement": 0,
            "annual_return_pct": annual_return_rate * 100,
        }

    coast = int(fire_number_jpy / (1 + annual_return_rate) ** years_until_retirement)

    return {
        "coast_fire_number_jpy": coast,
        "fire_number_jpy": fire_number_jpy,
        "years_until_retirement": years_until_retirement,
        "annual_return_pct": annual_return_rate * 100,
    }


# ---------------------------------------------------------------------------
# Barista FIRE number
# ---------------------------------------------------------------------------

def calculate_barista_fire_number(
    annual_expenses_jpy: int,
    withdrawal_rate: float,
    net_pension_annual_jpy: int = 0,
    barista_income_annual_jpy: int = 0,
) -> dict:
    """
    Calculate the Barista FIRE number — reduced FIRE target when supplemented
    by part-time income (e.g. café work, teaching, consulting).

    Barista FIRE number = (expenses - pension - barista_income) / withdrawal_rate

    This lets you retire earlier with a smaller portfolio by covering some
    expenses through enjoyable/low-stress part-time work.

    Note: Part-time income above 1,030,000 yen/year affects tax and NHI.
    Income below the non-taxable threshold (103万円) has minimal tax impact.

    Args:
        annual_expenses_jpy:    Target retirement expenses.
        withdrawal_rate:        Portfolio withdrawal rate (decimal).
        net_pension_annual_jpy: After-tax pension income.
        barista_income_annual_jpy: Gross annual part-time income.

    Returns:
        dict with barista_fire_number_jpy, portfolio_reduction_vs_full_fire_jpy.
    """
    full_fire = int(max(0, annual_expenses_jpy - net_pension_annual_jpy) / withdrawal_rate)
    net_need = max(0, annual_expenses_jpy - net_pension_annual_jpy - barista_income_annual_jpy)
    barista_number = int(net_need / withdrawal_rate) if net_need > 0 else 0

    # Warn if barista income exceeds the non-taxable threshold
    taxable_warning = None
    if barista_income_annual_jpy > 1_030_000:
        taxable_warning = (
            f"Part-time income ¥{barista_income_annual_jpy:,} exceeds the ¥1,030,000 "
            "non-taxable threshold — income tax and NHI implications apply."
        )

    return {
        "annual_expenses_jpy": annual_expenses_jpy,
        "net_pension_annual_jpy": net_pension_annual_jpy,
        "barista_income_annual_jpy": barista_income_annual_jpy,
        "net_need_jpy": net_need,
        "withdrawal_rate_pct": withdrawal_rate * 100,
        "barista_fire_number_jpy": barista_number,
        "full_fire_number_jpy": full_fire,
        "portfolio_reduction_jpy": full_fire - barista_number,
        "portfolio_reduction_pct": round((full_fire - barista_number) / full_fire * 100, 1) if full_fire > 0 else 0.0,
        "taxable_income_warning": taxable_warning,
    }


# ---------------------------------------------------------------------------
# Net worth projection
# ---------------------------------------------------------------------------

def project_net_worth(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
    projection_years: int = 50,
) -> list[YearProjection]:
    """
    Generate a year-by-year net worth projection through accumulation and retirement.

    Accumulation phase (current_age → target_retirement_age):
      - Portfolio grows at investment_return_pct
      - Annual savings added (NISA + iDeCo + residual)

    Retirement phase (target_retirement_age → end):
      - Portfolio grows at retirement_return_pct
      - Withdrawals made (solved iteratively with NHI)
      - Pension income offsets withdrawals from pension start age
      - Year-1 residence tax shock added in first retirement year

    The iDeCo balance unlocks at age 60 (added to portfolio at that point).

    Returns:
        List of YearProjection dataclasses (one per year).
    """
    r_accum = assumptions.investment_return_pct / 100
    r_retire = assumptions.retirement_return_pct / 100
    withdrawal_rate = assumptions.withdrawal_rate_pct / 100

    municipality_key = get_nhi_municipality_key(region_key)
    nhi_members = assumptions.nhi_household_members

    # Expense base in retirement
    expense_result = calculate_retirement_expenses(profile, region_key)
    annual_expenses = expense_result["annual_expenses_jpy"]

    # Pension details — project forward to retirement
    years_to_ret = profile.years_to_retirement
    pension_info = calculate_pension_at_retirement(profile, years_to_ret)
    net_pension = pension_info["net_pension_annual_jpy"]
    pension_start_age = profile.nenkin_claim_age

    # FIRE number and NHI solve at target withdrawal level
    fire_info = calculate_fire_number(annual_expenses, withdrawal_rate, net_pension)
    nhi_solve = solve_withdrawal_with_nhi(
        target_net_expenses=fire_info["net_annual_need_jpy"],
        num_members=nhi_members,
        municipality_key=municipality_key,
        age=profile.target_retirement_age,
    )
    gross_withdrawal_at_fire = nhi_solve["gross_withdrawal"]
    nhi_at_fire = nhi_solve["nhi_premium"]

    # Year-1 retirement residence tax shock
    shock_result = calculate_year1_retirement_tax_shock(
        last_working_gross=profile.annual_gross_income_jpy,
        employment_type=profile.employment_type,
        ideco_monthly_jpy=profile.ideco_monthly_contribution_jpy,
        social_insurance_premium=profile.social_insurance_annual_jpy,
    )
    year1_shock = shock_result["year1_residence_tax"]

    # Starting portfolio (accessible only)
    ideco_accessible_at_fire = profile.target_retirement_age >= 60
    foreign_jpy = int(profile.foreign_assets_usd * profile.usd_jpy_rate)
    portfolio = (
        profile.nisa_balance_jpy
        + profile.taxable_brokerage_jpy
        + profile.cash_savings_jpy
        + foreign_jpy
        + (profile.ideco_balance_jpy if ideco_accessible_at_fire else 0)
    )
    locked_ideco = 0 if ideco_accessible_at_fire else profile.ideco_balance_jpy

    annual_savings = (
        (profile.monthly_nisa_contribution_jpy + profile.ideco_monthly_contribution_jpy) * 12
        + profile.nisa_growth_frame_annual_jpy
        + getattr(profile, 'rsu_vesting_annual_jpy', 0)
    )

    # Build property-sale lump sum map: age → net_proceeds_jpy
    _prop_sale_by_age: dict[int, int] = {}
    for (prop_value, prop_mortgage, prop_monthly_pmt2, sale_age_attr, appr_attr) in [
        (
            profile.property_value_jpy,
            profile.mortgage_balance_jpy,
            profile.monthly_mortgage_payment_jpy,
            getattr(profile, "property_planned_sale_age", None),
            getattr(profile, "property_appreciation_pct", 0.0),
        ),
        (
            getattr(profile, "foreign_property_value_jpy", 0),
            getattr(profile, "foreign_property_mortgage_jpy", 0),
            0,
            getattr(profile, "foreign_property_planned_sale_age", None),
            getattr(profile, "foreign_property_appreciation_pct", 0.0),
        ),
    ]:
        if prop_value and sale_age_attr:
            yrs = sale_age_attr - profile.current_age
            if yrs >= 0:
                proc = calculate_property_sale_proceeds(
                    current_value_jpy=prop_value,
                    mortgage_balance_jpy=prop_mortgage,
                    years_until_sale=yrs,
                    appreciation_pct=appr_attr,
                    monthly_mortgage_payment_jpy=prop_monthly_pmt2,
                )
                _prop_sale_by_age[sale_age_attr] = (
                    _prop_sale_by_age.get(sale_age_attr, 0) + proc["net_proceeds_jpy"]
                )

    trajectory: list[YearProjection] = []

    for i in range(projection_years):
        age = profile.current_age + i
        year = i + 1
        in_retirement = age >= profile.target_retirement_age

        if not in_retirement:
            # --- Accumulation phase ---
            gain = int(portfolio * r_accum)
            portfolio = int(portfolio * (1 + r_accum)) + annual_savings

            # Property sale proceeds injected at sale age
            if age in _prop_sale_by_age:
                portfolio += _prop_sale_by_age[age]

            # iDeCo unlocks at 60 during accumulation (edge case: FIRE > 60 but age hits 60)
            if age == 60 and not ideco_accessible_at_fire and locked_ideco > 0:
                portfolio += locked_ideco
                locked_ideco = 0

            trajectory.append(YearProjection(
                year=year,
                age=age,
                phase="accumulation",
                portfolio_value_jpy=portfolio,
                annual_savings_jpy=annual_savings,
                investment_gain_jpy=gain,
            ))

        else:
            # --- Retirement phase ---
            retirement_year = age - profile.target_retirement_age

            # Mortgage payoff at the start of retirement
            if retirement_year == 0 and profile.owns_property and profile.property_paid_off_at_retirement:
                payoff = _amortise_mortgage(
                    balance_jpy=profile.mortgage_balance_jpy,
                    monthly_payment_jpy=profile.monthly_mortgage_payment_jpy,
                    years=profile.years_to_retirement,
                )
                portfolio = max(0, portfolio - payoff)

            # iDeCo unlocks at 60 (if FIRE was before 60 and we're crossing 60)
            if age == 60 and locked_ideco > 0:
                portfolio += locked_ideco
                locked_ideco = 0

            # Pension income (zero before claim age)
            pension_this_year = net_pension if age >= pension_start_age else 0

            # NHI: re-solve at current portfolio size (simplified — use FIRE-level NHI)
            nhi_this_year = nhi_at_fire if portfolio > 0 else 0

            # Gross from portfolio = expenses - pension + NHI
            net_need_this_year = max(0, annual_expenses - pension_this_year)
            net_from_portfolio = net_need_this_year + nhi_this_year

            # Year-1 residence tax shock
            shock_this_year = year1_shock if retirement_year == 0 else 0
            net_from_portfolio += shock_this_year

            # Property sale proceeds injected at sale age (retirement phase)
            if age in _prop_sale_by_age:
                portfolio += _prop_sale_by_age[age]

            # Grow then withdraw
            gain = int(portfolio * r_retire)
            portfolio = int(portfolio * (1 + r_retire)) - net_from_portfolio
            portfolio = max(0, portfolio)  # floor at zero — ruin scenario

            trajectory.append(YearProjection(
                year=year,
                age=age,
                phase="retirement",
                portfolio_value_jpy=portfolio,
                gross_withdrawal_jpy=net_from_portfolio,
                nhi_premium_jpy=nhi_this_year,
                pension_income_jpy=pension_this_year,
                net_from_portfolio_jpy=net_from_portfolio,
                year1_residence_tax_jpy=shock_this_year,
                investment_gain_jpy=gain,
            ))

    return trajectory


# ---------------------------------------------------------------------------
# Full scenario runner (orchestrator)
# ---------------------------------------------------------------------------

def run_fire_scenario(
    profile: FinancialProfile,
    scenario_name: str,
    scenario_id: str,
    assumptions: AssumptionSet,
    region_key: str,
) -> ScenarioResult:
    """
    Run a complete FIRE scenario and return a ScenarioResult.

    Orchestrates all sub-engines:
      tax → NHI → pension → iDeCo/NISA projections → FIRE number → trajectory
    """
    warnings: list[str] = []
    withdrawal_rate = assumptions.withdrawal_rate_pct / 100
    r_accum = assumptions.investment_return_pct / 100
    municipality_key = get_nhi_municipality_key(region_key)

    # --- Current tax position -----------------------------------------------
    tax_result = calculate_income_tax(
        gross_income=profile.annual_gross_income_jpy,
        employment_type=profile.employment_type,
        ideco_monthly_jpy=profile.ideco_monthly_contribution_jpy,
        num_dependents=profile.num_dependents,
        has_spouse=profile.has_spouse,
        spouse_income_jpy=profile.spouse_income_jpy,
        social_insurance_premium=profile.social_insurance_annual_jpy,
    )
    residence_tax = calculate_residence_tax(tax_result["taxable_income"])

    # --- Retirement expenses -------------------------------------------------
    expense_result = calculate_retirement_expenses(profile, region_key)
    annual_expenses = expense_result["annual_expenses_jpy"]

    # --- Pension at retirement -----------------------------------------------
    pension_info = calculate_pension_at_retirement(profile, profile.years_to_retirement)
    net_pension = pension_info["net_pension_annual_jpy"]

    # --- NHI in retirement (iterative solve) --------------------------------
    fire_info = calculate_fire_number(annual_expenses, withdrawal_rate, net_pension)
    nhi_solve = solve_withdrawal_with_nhi(
        target_net_expenses=fire_info["net_annual_need_jpy"],
        num_members=assumptions.nhi_household_members,
        municipality_key=municipality_key,
        age=profile.target_retirement_age,
    )
    if not nhi_solve.get("converged", True):
        warnings.append(
            "NHI premium calculation did not fully converge. "
            "The withdrawal estimate is approximate — consider adjusting municipality or household size."
        )

    # --- Year-1 residence tax shock -----------------------------------------
    shock = calculate_year1_retirement_tax_shock(
        last_working_gross=profile.annual_gross_income_jpy,
        employment_type=profile.employment_type,
        ideco_monthly_jpy=profile.ideco_monthly_contribution_jpy,
        social_insurance_premium=profile.social_insurance_annual_jpy,
    )

    # --- Accessible portfolio today -----------------------------------------
    portfolio_info = calculate_accessible_portfolio(profile, profile.target_retirement_age)
    current_portfolio = portfolio_info["total_accessible_jpy"]

    # --- Mortgage payoff deduction -------------------------------------------
    # If the user plans to pay off the mortgage by retirement, the remaining
    # balance at retirement must be deducted from the accessible portfolio.
    # The checkbox already removes the monthly payment from retirement expenses;
    # this ensures the lump-sum cost of actually clearing the mortgage is also
    # accounted for.
    mortgage_payoff_jpy = 0
    if profile.owns_property and profile.property_paid_off_at_retirement:
        mortgage_payoff_jpy = _amortise_mortgage(
            balance_jpy=profile.mortgage_balance_jpy,
            monthly_payment_jpy=profile.monthly_mortgage_payment_jpy,
            years=profile.years_to_retirement,
        )
        if mortgage_payoff_jpy > 0:
            current_portfolio = max(0, current_portfolio - mortgage_payoff_jpy)
            warnings.append(
                f"Mortgage payoff at retirement: ¥{mortgage_payoff_jpy:,} deducted from portfolio "
                f"(remaining balance after {profile.years_to_retirement} years of payments)."
            )

    # --- FIRE number ---------------------------------------------------------
    # Include NHI in annual need (NHI is paid from portfolio in retirement)
    annual_need_with_nhi = fire_info["net_annual_need_jpy"] + nhi_solve["nhi_premium"]
    fire_number = int(annual_need_with_nhi / withdrawal_rate)
    progress_pct = (current_portfolio / fire_number * 100) if fire_number > 0 else 100.0

    # --- Years to FIRE -------------------------------------------------------
    annual_savings = (
        profile.monthly_nisa_contribution_jpy + profile.ideco_monthly_contribution_jpy
    ) * 12 + profile.nisa_growth_frame_annual_jpy + getattr(profile, 'rsu_vesting_annual_jpy', 0)
    years_to_fire = calculate_years_to_fire(
        current_portfolio_jpy=current_portfolio,
        annual_savings_jpy=annual_savings,
        fire_number_jpy=fire_number,
        annual_return_rate=r_accum,
    )
    fire_age = profile.current_age + years_to_fire

    # --- Coast FIRE ---------------------------------------------------------
    coast = calculate_coast_fire_number(
        fire_number_jpy=fire_number,
        years_until_retirement=profile.years_to_retirement,
        annual_return_rate=r_accum,
    )

    # --- Barista FIRE -------------------------------------------------------
    barista = calculate_barista_fire_number(
        annual_expenses_jpy=annual_expenses,
        withdrawal_rate=withdrawal_rate,
        net_pension_annual_jpy=net_pension,
        barista_income_annual_jpy=assumptions.barista_income_monthly_jpy * 12,
    )

    # --- iDeCo projections --------------------------------------------------
    ideco_accum = calculate_ideco_accumulation(
        monthly_contribution_jpy=profile.ideco_monthly_contribution_jpy,
        years=profile.years_to_retirement,
        annual_return_rate=r_accum,
        existing_balance_jpy=profile.ideco_balance_jpy,
    )
    ideco_at_retirement = ideco_accum["final_balance_jpy"]
    ideco_accessible = profile.target_retirement_age >= 60

    bridge = calculate_ideco_bridge_need(
        fire_age=profile.target_retirement_age,
        annual_expenses_jpy=annual_expenses,
        annual_return_rate=r_accum,
    )

    # --- NISA projections ---------------------------------------------------
    nisa_result = calculate_nisa_growth(
        years=profile.years_to_retirement,
        annual_return_rate=r_accum,
        monthly_tsumitate_jpy=profile.monthly_nisa_contribution_jpy,
        annual_growth_frame_jpy=profile.nisa_growth_frame_annual_jpy,
        existing_balance_jpy=profile.nisa_balance_jpy,
        lifetime_cap_used_jpy=profile.nisa_lifetime_used_jpy,
    )
    nisa_at_retirement = nisa_result["final_balance_jpy"]

    # --- Warnings -----------------------------------------------------------
    if profile.target_retirement_age < 60:
        warnings.append(
            f"iDeCo is locked until age 60. Your ¥{ideco_at_retirement:,} iDeCo balance "
            f"is not accessible at your target FIRE age of {profile.target_retirement_age}. "
            f"NISA + taxable must cover the {60 - profile.target_retirement_age}-year gap."
        )
    if assumptions.withdrawal_rate_pct > 4.0:
        warnings.append(
            f"Withdrawal rate {assumptions.withdrawal_rate_pct}% is above 4%. "
            "Japan research suggests 3.0–3.5% for long-term safety."
        )
    if years_to_fire == float("inf"):
        warnings.append(
            "With current savings rate and return assumptions, the FIRE number "
            "is never reached. Increase savings, reduce expenses, or adjust assumptions."
        )
    if getattr(profile, 'rsu_unvested_value_jpy', 0) > 0:
        warnings.append(
            f"Unvested RSUs (¥{profile.rsu_unvested_value_jpy:,}) are included in your accessible "
            "portfolio, but vest only while employed — they disappear the moment you FIRE. "
            "Consider excluding them from your FIRE number if you plan to leave before full vesting."
        )
    if getattr(profile, 'rsu_vesting_annual_jpy', 0) > 0:
        warnings.append(
            f"Annual RSU vesting (¥{profile.rsu_vesting_annual_jpy:,}) is counted as savings "
            "during accumulation but stops entirely at retirement. "
            "RSU income is taxed as ordinary income (総合課税) in Japan."
        )
    if getattr(profile, 'crypto_value_jpy', 0) > 0:
        warnings.append(
            "Cryptocurrency is included in your accessible portfolio at current value. "
            "Crypto gains in Japan are taxed as miscellaneous income (雑所得) at up to 55% — "
            "factor in the tax cost when planning liquidation."
        )
    if math.isfinite(years_to_fire) and fire_age > 75:
        warnings.append(
            f"Projected FIRE age {fire_age:.1f} is late. Consider increasing savings rate "
            "or reducing target expenses."
        )

    # --- Net worth trajectory -----------------------------------------------
    trajectory = project_net_worth(profile, assumptions, region_key, projection_years=50)

    # --- Property sale lump sums (pre-retirement: boost portfolio; post: MC inject) ---
    property_lump_sums: list[tuple[int, int]] = []      # (year_into_retirement, net_proceeds)
    mc_withdrawal_reductions: list[tuple[int, int]] = []  # (start_year, annual_reduction)

    def _property_sale(value, mortgage, monthly_payment, sale_age, appreciation_pct):
        """Return (sale_age, net_proceeds_jpy), handling pre/post-retirement timing."""
        if not value or not sale_age:
            return None
        years_until_sale = sale_age - profile.current_age
        if years_until_sale < 0:
            return None  # already sold
        proceeds = calculate_property_sale_proceeds(
            current_value_jpy=value,
            mortgage_balance_jpy=mortgage,
            years_until_sale=years_until_sale,
            appreciation_pct=appreciation_pct,
            monthly_mortgage_payment_jpy=monthly_payment,
        )
        return sale_age, proceeds["net_proceeds_jpy"]

    for (prop_value, prop_mortgage, prop_monthly_pmt, sale_age_field, appr_field) in [
        (
            profile.property_value_jpy,
            profile.mortgage_balance_jpy,
            profile.monthly_mortgage_payment_jpy,
            getattr(profile, "property_planned_sale_age", None),
            getattr(profile, "property_appreciation_pct", 0.0),
        ),
        (
            getattr(profile, "foreign_property_value_jpy", 0),
            getattr(profile, "foreign_property_mortgage_jpy", 0),
            0,  # no monthly payment field for foreign property — no amortisation
            getattr(profile, "foreign_property_planned_sale_age", None),
            getattr(profile, "foreign_property_appreciation_pct", 0.0),
        ),
    ]:
        result = _property_sale(prop_value, prop_mortgage, prop_monthly_pmt, sale_age_field, appr_field)
        if result is None:
            continue
        sale_age_val, net_proceeds = result
        if sale_age_val <= profile.target_retirement_age:
            # Pre-retirement sale: the proceeds are invested and compound to FIRE date
            years_to_reinvest = profile.target_retirement_age - sale_age_val
            future_proceeds = int(net_proceeds * (1 + r_accum) ** years_to_reinvest)
            current_portfolio += future_proceeds
            warnings.append(
                f"Property sale (age {sale_age_val}): estimated net proceeds ¥{net_proceeds:,} "
                f"added to portfolio and grown to ¥{future_proceeds:,} by retirement."
            )
        else:
            # Post-retirement sale: inject as lump sum into Monte Carlo
            year_into_retirement = sale_age_val - profile.target_retirement_age
            property_lump_sums.append((year_into_retirement, net_proceeds))
            # Also reduce ongoing withdrawal if property had a mortgage payment
            if prop_monthly_pmt > 0:
                annual_mortgage = prop_monthly_pmt * 12
                mc_withdrawal_reductions.append((year_into_retirement, annual_mortgage))
            warnings.append(
                f"Property sale (age {sale_age_val}): estimated net proceeds ¥{net_proceeds:,} "
                f"injected into portfolio in Monte Carlo at retirement year {year_into_retirement}."
            )

    # Recalculate progress after any pre-retirement sale boosts
    progress_pct = (current_portfolio / fire_number * 100) if fire_number > 0 else 100.0

    # --- Monte Carlo simulation ---------------------------------------------
    from engine.monte_carlo import run_monte_carlo
    pension_start_year = max(0, profile.nenkin_claim_age - profile.target_retirement_age)
    mc_result = run_monte_carlo(
        initial_portfolio_jpy=current_portfolio,
        annual_expenses_jpy=fire_info["net_annual_need_jpy"] + nhi_solve["nhi_premium"],
        net_pension_annual_jpy=net_pension,
        pension_start_year=pension_start_year,
        simulation_years=assumptions.simulation_years,
        n_simulations=min(assumptions.monte_carlo_simulations, 10_000),  # engine-level safety cap
        mean_return=assumptions.retirement_return_pct / 100,
        volatility=assumptions.return_volatility_pct / 100,
        inflation_rate=assumptions.japan_inflation_pct / 100,
        sequence_of_returns_risk=assumptions.sequence_of_returns_risk,
        lump_sums=property_lump_sums or None,
        withdrawal_reductions=mc_withdrawal_reductions or None,
        seed=None,
    )

    # --- Sensitivity analysis -----------------------------------------------
    from engine.sensitivity import run_sensitivity_analysis
    sensitivity = run_sensitivity_analysis(profile, assumptions, region_key)

    # --- Foreigners mode ----------------------------------------------------
    from engine.foreigners import analyse_foreigners
    foreigners = analyse_foreigners(
        nationality=getattr(profile, "nationality", "JP"),
        residency_status=getattr(profile, "residency_status", "permanent_resident"),
        treaty_country=getattr(profile, "treaty_country", "") or None,
        is_tax_resident=True,
        years_in_japan=getattr(profile, "years_in_japan", 10),
        current_age=profile.current_age,
        target_retirement_age=profile.target_retirement_age,
        total_financial_assets_jpy=current_portfolio,
        projected_fire_number_jpy=fire_number,
        foreign_pension_annual_jpy=profile.foreign_pension_annual_jpy,
        foreign_assets_usd=profile.foreign_assets_usd,
        usd_jpy_rate=profile.usd_jpy_rate,
        nisa_balance_jpy=profile.nisa_balance_jpy,
    )

    return ScenarioResult(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        fire_number_jpy=fire_number,
        current_portfolio_jpy=current_portfolio,
        progress_pct=round(min(progress_pct, 100.0), 1),
        years_to_fire=round(years_to_fire, 1) if math.isfinite(years_to_fire) else 999.0,
        fire_age=round(fire_age, 1) if math.isfinite(years_to_fire) else 999.0,
        coast_fire_number_jpy=coast["coast_fire_number_jpy"],
        coast_fire_reached=current_portfolio >= coast["coast_fire_number_jpy"],
        barista_fire_number_jpy=barista["barista_fire_number_jpy"],
        annual_expenses_jpy=annual_expenses,
        annual_pension_net_jpy=net_pension,
        annual_nhi_jpy=nhi_solve["nhi_premium"],
        annual_withdrawal_needed_jpy=nhi_solve["gross_withdrawal"],
        year1_residence_tax_shock_jpy=shock["year1_residence_tax"],
        nisa_at_retirement_jpy=nisa_at_retirement,
        ideco_at_retirement_jpy=ideco_at_retirement,
        taxable_at_retirement_jpy=profile.taxable_brokerage_jpy,
        ideco_accessible_at_fire=ideco_accessible,
        ideco_bridge_needed_jpy=bridge["bridge_portfolio_needed_jpy"],
        current_income_tax_jpy=tax_result["income_tax"],
        current_residence_tax_jpy=residence_tax["total"],
        current_effective_tax_rate_pct=round(
            (tax_result["income_tax"] + residence_tax["total"] + profile.social_insurance_annual_jpy)
            / profile.annual_gross_income_jpy * 100, 1
        ) if profile.annual_gross_income_jpy > 0 else 0.0,
        trajectory=trajectory,
        monte_carlo=mc_result,
        sensitivity=sensitivity,
        foreigners_warnings=foreigners.warnings,
        foreigners_notes=foreigners.notes,
        foreigners_dta_country=getattr(profile, "treaty_country", ""),
        foreigners_totalization=foreigners.totalization_eligible,
        foreigners_non_pr=foreigners.non_permanent_resident,
        foreigners_exit_tax_risk=foreigners.exit_tax_risk,
        warnings=list(dict.fromkeys(warnings)),  # deduplicate, preserve order
    )
