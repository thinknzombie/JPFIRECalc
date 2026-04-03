"""
Sensitivity analysis engine — tornado chart data.

Varies each input assumption ±N% from its base value, runs the FIRE
calculation, and measures the impact on years-to-FIRE.

Variables analysed:
  1. Investment return
  2. Withdrawal rate
  3. Monthly savings
  4. Annual expenses
  5. Inflation rate
  6. USD/JPY rate (affects foreign asset value)
  7. NHI municipality (switch to cheap vs expensive)

Output is a sorted list of SensitivityItems — the UI renders these as
a horizontal tornado chart. Items are sorted by total impact (largest
swing at top), which is the standard tornado chart ordering.
"""
from __future__ import annotations
from dataclasses import replace
from models.profile import FinancialProfile
from models.scenario import AssumptionSet, SensitivityItem
from engine.fire_calculator import (
    calculate_years_to_fire,
    calculate_fire_number,
    calculate_retirement_expenses,
    calculate_accessible_portfolio,
    calculate_pension_at_retirement,
)
from engine.nhi_calculator import solve_withdrawal_with_nhi
from models.region_data import get_nhi_municipality_key


def _years_for_params(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
) -> float:
    """
    Compute years-to-FIRE for a given profile + assumptions combination.
    Reuses the same logic as run_fire_scenario but returns just the scalar.
    """
    r = assumptions.investment_return_pct / 100
    withdrawal_rate = assumptions.withdrawal_rate_pct / 100
    municipality_key = get_nhi_municipality_key(region_key)

    expense_result = calculate_retirement_expenses(profile, region_key)
    annual_expenses = expense_result["annual_expenses_jpy"]

    pension_info = calculate_pension_at_retirement(profile, profile.years_to_retirement)
    net_pension = pension_info["net_pension_annual_jpy"]

    fire_info = calculate_fire_number(annual_expenses, withdrawal_rate, net_pension)

    nhi_solve = solve_withdrawal_with_nhi(
        target_net_expenses=fire_info["net_annual_need_jpy"],
        num_members=assumptions.nhi_household_members,
        municipality_key=municipality_key,
        age=profile.target_retirement_age,
    )

    annual_need_with_nhi = fire_info["net_annual_need_jpy"] + nhi_solve["nhi_premium"]
    fire_number = int(annual_need_with_nhi / withdrawal_rate)

    portfolio_info = calculate_accessible_portfolio(profile, profile.target_retirement_age)
    current_portfolio = portfolio_info["total_accessible_jpy"]

    annual_savings = (
        profile.monthly_nisa_contribution_jpy + profile.ideco_monthly_contribution_jpy
    ) * 12

    return calculate_years_to_fire(current_portfolio, annual_savings, fire_number, r)


def run_sensitivity_analysis(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
    delta: float = 0.20,
) -> list[SensitivityItem]:
    """
    Vary each key input ±delta (default ±20%) and measure impact on years-to-FIRE.

    Args:
        profile:      Base financial profile.
        assumptions:  Base assumption set.
        region_key:   Region for expense template.
        delta:        Fractional change applied to each variable (0.20 = ±20%).

    Returns:
        List of SensitivityItem sorted by total swing (largest impact first).
        This is the standard tornado chart ordering.
    """
    base_years = _years_for_params(profile, assumptions, region_key)
    items: list[SensitivityItem] = []

    def _item(variable, label, pessimistic_assumptions_or_profile, optimistic_assumptions_or_profile,
               is_profile_change=False):
        """Helper: compute pess/opt years and build SensitivityItem."""
        if is_profile_change:
            pess_profile, pess_assumptions = pessimistic_assumptions_or_profile, assumptions
            opt_profile, opt_assumptions = optimistic_assumptions_or_profile, assumptions
        else:
            pess_profile, pess_assumptions = profile, pessimistic_assumptions_or_profile
            opt_profile, opt_assumptions = profile, optimistic_assumptions_or_profile

        pess_years = _years_for_params(pess_profile, pess_assumptions, region_key)
        opt_years = _years_for_params(opt_profile, opt_assumptions, region_key)

        # Cap at a reasonable maximum to avoid inf dominating the chart
        cap = base_years * 5 if base_years > 0 and base_years != float("inf") else 100.0
        pess_years = min(pess_years, cap) if pess_years != float("inf") else cap
        opt_years = min(opt_years, cap) if opt_years != float("inf") else cap

        return SensitivityItem(
            variable=variable,
            label=label,
            base_years=round(base_years, 1) if base_years != float("inf") else cap,
            pessimistic_years=round(pess_years, 1),
            optimistic_years=round(opt_years, 1),
        )

    # 1. Investment return  ±delta
    r_base = assumptions.investment_return_pct
    items.append(_item(
        "investment_return",
        f"Investment return ({r_base:.1f}%)",
        replace(assumptions, investment_return_pct=r_base * (1 - delta)),   # pessimistic = lower return
        replace(assumptions, investment_return_pct=r_base * (1 + delta)),   # optimistic  = higher return
    ))

    # 2. Withdrawal rate  ±delta (pessimistic = lower rate → need more portfolio)
    wr_base = assumptions.withdrawal_rate_pct
    items.append(_item(
        "withdrawal_rate",
        f"Withdrawal rate ({wr_base:.1f}%)",
        replace(assumptions, withdrawal_rate_pct=max(0.5, wr_base * (1 - delta))),
        replace(assumptions, withdrawal_rate_pct=min(8.0, wr_base * (1 + delta))),
    ))

    # 3. Monthly savings (NISA + iDeCo combined)  ±delta
    nisa_base = profile.monthly_nisa_contribution_jpy
    ideco_base = profile.ideco_monthly_contribution_jpy
    items.append(_item(
        "monthly_savings",
        f"Monthly savings (¥{(nisa_base + ideco_base):,})",
        replace(profile,
                monthly_nisa_contribution_jpy=int(nisa_base * (1 - delta)),
                ideco_monthly_contribution_jpy=int(ideco_base * (1 - delta))),
        replace(profile,
                monthly_nisa_contribution_jpy=int(nisa_base * (1 + delta)),
                ideco_monthly_contribution_jpy=int(ideco_base * (1 + delta))),
        is_profile_change=True,
    ))

    # 4. Annual expenses: ±delta on the region template base
    # We model this as adjusting monthly_expenses_jpy in the profile
    # and switching to use_region_template=False path via the assumption
    # Simpler: vary the expenses directly by adjusting template via profile override
    exp_base = profile.monthly_expenses_jpy
    items.append(_item(
        "monthly_expenses",
        f"Monthly expenses (¥{exp_base:,})",
        replace(profile, monthly_expenses_jpy=int(exp_base * (1 + delta))),  # higher expenses = pessimistic
        replace(profile, monthly_expenses_jpy=int(exp_base * (1 - delta))),  # lower expenses = optimistic
        is_profile_change=True,
    ))

    # 5. Inflation  ±delta
    inf_base = assumptions.japan_inflation_pct
    items.append(_item(
        "inflation",
        f"Japan inflation ({inf_base:.1f}%)",
        replace(assumptions, japan_inflation_pct=inf_base * (1 + delta)),
        replace(assumptions, japan_inflation_pct=max(0.1, inf_base * (1 - delta))),
    ))

    # 6. USD/JPY rate  ±delta (affects foreign asset value)
    if profile.foreign_assets_usd > 0:
        fx_base = profile.usd_jpy_rate
        items.append(_item(
            "usd_jpy",
            f"USD/JPY ({fx_base:.0f})",
            replace(profile, usd_jpy_rate=fx_base * (1 - delta)),   # yen stronger = foreign assets worth less = pessimistic
            replace(profile, usd_jpy_rate=fx_base * (1 + delta)),   # yen weaker = foreign assets worth more = optimistic
            is_profile_change=True,
        ))

    # 7. NHI municipality: expensive vs cheap (Tokyo Shinjuku vs rural average)
    nhi_expensive = replace(assumptions, nhi_municipality_key="tokyo_shinjuku")
    nhi_cheap = replace(assumptions, nhi_municipality_key="rural_average")
    nhi_item = _item(
        "nhi_municipality",
        "NHI municipality (cheap vs expensive)",
        nhi_expensive,   # pessimistic = more expensive NHI
        nhi_cheap,       # optimistic  = cheaper NHI
    )
    # Only include if there's meaningful difference
    if abs(nhi_item.delta_pessimistic) > 0.1 or abs(nhi_item.delta_optimistic) > 0.1:
        items.append(nhi_item)

    # Sort by total swing (|pessimistic delta| + |optimistic delta|), largest first
    items.sort(key=lambda x: abs(x.delta_pessimistic) + abs(x.delta_optimistic), reverse=True)

    return items
