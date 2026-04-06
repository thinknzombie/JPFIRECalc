"""
Sensitivity analysis engine — tornado chart data.

Varies each input assumption ±N% from its base value, runs the FIRE
calculation, and measures the impact on the key metric.

Two modes:
  - **Accumulation mode** (years_to_fire > 0): measures impact on years-to-FIRE.
  - **Surplus mode** (already at FIRE): measures impact on FIRE surplus %
    (portfolio / FIRE number × 100 − 100). This keeps the tornado chart
    meaningful when all years-to-FIRE deltas would otherwise be zero.

Variables analysed:
  1. Investment return
  2. Withdrawal rate
  3. Monthly savings
  4. Annual expenses
  5. USD/JPY rate (affects foreign asset value)
  6. NHI municipality (switch to cheap vs expensive)

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
    _amortise_mortgage,
)
from engine.nhi_calculator import solve_withdrawal_with_nhi
from models.region_data import get_nhi_municipality_key


def _compute_for_params(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
    annual_expenses_override: int | None = None,
) -> tuple[float, float]:
    """
    Compute years-to-FIRE and FIRE surplus % for a given profile + assumptions.

    Returns:
        (years_to_fire, surplus_pct) where surplus_pct =
        (current_portfolio / fire_number - 1) * 100.
    """
    r = assumptions.investment_return_pct / 100
    withdrawal_rate = assumptions.withdrawal_rate_pct / 100
    municipality_key = get_nhi_municipality_key(region_key)

    if annual_expenses_override is not None:
        annual_expenses = annual_expenses_override
    else:
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

    # Mortgage payoff deduction (mirrors run_fire_scenario logic)
    if profile.owns_property and profile.property_paid_off_at_retirement:
        payoff = _amortise_mortgage(
            balance_jpy=profile.mortgage_balance_jpy,
            monthly_payment_jpy=profile.monthly_mortgage_payment_jpy,
            years=profile.years_to_retirement,
        )
        current_portfolio = max(0, current_portfolio - payoff)

    annual_savings = (
        profile.monthly_nisa_contribution_jpy + profile.ideco_monthly_contribution_jpy
    ) * 12 + profile.nisa_growth_frame_annual_jpy + getattr(profile, 'rsu_vesting_annual_jpy', 0)

    years = calculate_years_to_fire(current_portfolio, annual_savings, fire_number, r)
    surplus_pct = ((current_portfolio / fire_number) - 1) * 100 if fire_number > 0 else 0.0

    return years, surplus_pct


def run_sensitivity_analysis(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
    delta: float = 0.20,
) -> list[SensitivityItem]:
    """
    Vary each key input ±delta (default ±20%) and measure impact.

    When the user is still accumulating (years_to_fire > 0), measures impact
    on years-to-FIRE. When already at FIRE (years == 0), switches to FIRE
    surplus % so the tornado chart remains meaningful.

    Args:
        profile:      Base financial profile.
        assumptions:  Base assumption set.
        region_key:   Region for expense template.
        delta:        Fractional change applied to each variable (0.20 = ±20%).

    Returns:
        List of SensitivityItem sorted by total swing (largest impact first).
        This is the standard tornado chart ordering.
    """
    base_years, base_surplus = _compute_for_params(profile, assumptions, region_key)
    surplus_mode = base_years == 0.0
    items: list[SensitivityItem] = []

    # Get the base annual expenses from the region template (what the engine actually uses)
    base_expense_result = calculate_retirement_expenses(profile, region_key)
    base_annual_expenses = base_expense_result["annual_expenses_jpy"]

    def _item(variable, label, pessimistic_assumptions_or_profile, optimistic_assumptions_or_profile,
               is_profile_change=False, pess_expenses=None, opt_expenses=None):
        """Helper: compute pess/opt metric and build SensitivityItem.

        In surplus mode, the metric is FIRE surplus % (higher = better).
        In years mode, the metric is years-to-FIRE (lower = better).

        pess_expenses / opt_expenses: override annual_expenses directly (for
        the expenses sensitivity which bypasses the region template).
        """
        if is_profile_change:
            pess_profile, pess_assumptions = pessimistic_assumptions_or_profile, assumptions
            opt_profile, opt_assumptions = optimistic_assumptions_or_profile, assumptions
        else:
            pess_profile, pess_assumptions = profile, pessimistic_assumptions_or_profile
            opt_profile, opt_assumptions = profile, optimistic_assumptions_or_profile

        pess_years, pess_surplus = _compute_for_params(
            pess_profile, pess_assumptions, region_key,
            annual_expenses_override=pess_expenses)
        opt_years, opt_surplus = _compute_for_params(
            opt_profile, opt_assumptions, region_key,
            annual_expenses_override=opt_expenses)

        if surplus_mode:
            return SensitivityItem(
                variable=variable,
                label=label,
                base_years=round(base_surplus, 1),
                pessimistic_years=round(pess_surplus, 1),
                optimistic_years=round(opt_surplus, 1),
                surplus_mode=True,
            )

        # Years-to-FIRE mode (original behaviour)
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
    #    Label shows monthly equivalent of all annual savings (including growth frame)
    nisa_base = profile.monthly_nisa_contribution_jpy
    ideco_base = profile.ideco_monthly_contribution_jpy
    growth_frame_monthly = profile.nisa_growth_frame_annual_jpy // 12
    total_monthly_savings = nisa_base + ideco_base + growth_frame_monthly
    items.append(_item(
        "monthly_savings",
        f"Monthly savings (¥{total_monthly_savings:,})",
        replace(profile,
                monthly_nisa_contribution_jpy=int(nisa_base * (1 - delta)),
                ideco_monthly_contribution_jpy=int(ideco_base * (1 - delta)),
                nisa_growth_frame_annual_jpy=int(profile.nisa_growth_frame_annual_jpy * (1 - delta))),
        replace(profile,
                monthly_nisa_contribution_jpy=int(nisa_base * (1 + delta)),
                ideco_monthly_contribution_jpy=int(ideco_base * (1 + delta)),
                nisa_growth_frame_annual_jpy=int(profile.nisa_growth_frame_annual_jpy * (1 + delta))),
        is_profile_change=True,
    ))

    # 4. Annual expenses: ±delta — vary the region-template base directly via override
    #    (varying monthly_expenses_jpy has no effect because the engine uses the region
    #    template; we must override annual_expenses at the _years_for_params level)
    exp_monthly_display = base_annual_expenses // 12
    items.append(_item(
        "monthly_expenses",
        f"Monthly expenses (¥{exp_monthly_display:,})",
        assumptions, assumptions,  # assumptions unchanged — expenses come from override
        is_profile_change=False,
        pess_expenses=int(base_annual_expenses * (1 + delta)),  # higher expenses = pessimistic
        opt_expenses=int(base_annual_expenses * (1 - delta)),   # lower expenses = optimistic
    ))

    # Note: Japan inflation has zero impact on *years-to-FIRE* (accumulation phase)
    # because the FIRE number is calculated in today's nominal terms and the withdrawal
    # rate implicitly handles inflation. Inflation does affect retirement drawdown survival
    # (Monte Carlo success rate), but that is not what this tornado chart measures.
    # We therefore omit inflation from this chart to avoid confusing users with a 0-bar.

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
