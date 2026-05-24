"""
Mortgage rate analysis engine.

Provides three main capabilities:
  1. Break-even rate: at what mortgage rate does paying off the loan beat investing?
  2. Payoff-vs-invest NPV: compare lump-sum payoff against keeping it invested.
  3. Rate scenarios: run the full FIRE scenario at a set of mortgage rates.
  4. Stochastic rate paths: Vasicek mean-reverting rate paths for Monte Carlo.

All monetary values in JPY (int). Rates/percentages as floats (e.g. 0.7 means 0.7%).
"""
from __future__ import annotations
import math
import numpy as np
from models.profile import FinancialProfile
from models.scenario import AssumptionSet

CAPITAL_GAINS_TAX = 0.20315  # Japan flat rate on financial gains (所得税 + 住民税)


# ---------------------------------------------------------------------------
# Helper formulas
# ---------------------------------------------------------------------------

def _monthly_payment(balance_jpy: int, annual_rate_pct: float, years_remaining: int) -> int:
    """Recompute monthly payment given balance, annual rate %, and remaining years."""
    n = years_remaining * 12
    if n <= 0:
        return balance_jpy
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return balance_jpy // n
    payment = balance_jpy * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return int(round(payment))


def _annual_loan_tax_credit_jpy(
    mortgage_balance_jpy: int,
    credit_rate: float = 0.007,
    principal_cap_jpy: int = 30_000_000,
) -> int:
    """Annual 住宅ローン控除 credit. Applied against income tax first, overflow to residence tax."""
    capped = min(mortgage_balance_jpy, principal_cap_jpy)
    return int(capped * credit_rate)


def _after_tax_return(gross_return: float, account_type: str) -> float:
    """After-tax investment return given account type."""
    if account_type in ("nisa", "ideco"):
        return gross_return
    if account_type == "taxable":
        return gross_return * (1.0 - CAPITAL_GAINS_TAX)
    # "mixed" — 80% taxable / 20% NISA assumed
    return 0.8 * gross_return * (1.0 - CAPITAL_GAINS_TAX) + 0.2 * gross_return


def _amortise_year(
    balance: float,
    annual_rate_pct: float,
    monthly_payment: int,
) -> float:
    """Advance the mortgage balance by one year of payments. Returns new balance (>= 0)."""
    r_monthly = annual_rate_pct / 100 / 12
    for _ in range(12):
        interest = balance * r_monthly
        principal = monthly_payment - interest
        if principal <= 0:
            break
        balance = max(0.0, balance - principal)
    return balance


# ---------------------------------------------------------------------------
# 1. Break-even rate calculator
# ---------------------------------------------------------------------------

def calculate_breakeven_mortgage_rate(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    investment_account_type: str = "taxable",
) -> dict:
    """
    Returns the mortgage rate at which paying off the loan equals investing the same money.

    Args:
        profile: FinancialProfile with mortgage_interest_rate_pct and tax-credit fields.
        assumptions: AssumptionSet with investment_return_pct (pre-retirement return).
        investment_account_type: "nisa" | "ideco" | "taxable" | "mixed"

    Returns:
        {
          "break_even_rate_pct": float,
          "current_mortgage_rate_pct": float,
          "delta_pct": float,           # current_effective_cost - break_even (negative => investing wins)
          "investing_wins": bool,
          "after_tax_investment_return_pct": float,
          "effective_mortgage_cost_pct": float,
          "tax_credit_active": bool,
          "annual_tax_credit_jpy": int,
          "explanation": str,
        }
    """
    gross_return = assumptions.investment_return_pct / 100.0
    after_tax = _after_tax_return(gross_return, investment_account_type)
    after_tax_pct = after_tax * 100.0

    mortgage_rate = profile.mortgage_interest_rate_pct / 100.0
    tax_credit_active = profile.mortgage_tax_credit_remaining_years > 0

    annual_credit_jpy = 0
    effective_deduction = 0.0

    if tax_credit_active and profile.mortgage_balance_jpy > 0:
        annual_credit_jpy = _annual_loan_tax_credit_jpy(
            profile.mortgage_balance_jpy,
            profile.mortgage_tax_credit_rate_pct / 100.0,
            profile.mortgage_tax_credit_principal_cap_jpy,
        )
        deduction_rate = profile.mortgage_tax_credit_rate_pct / 100.0
        cap_ratio = min(profile.mortgage_balance_jpy, profile.mortgage_tax_credit_principal_cap_jpy) / profile.mortgage_balance_jpy
        effective_deduction = deduction_rate * cap_ratio

    effective_mortgage_cost = mortgage_rate - effective_deduction
    effective_mortgage_cost_pct = effective_mortgage_cost * 100.0

    # Break-even mortgage rate = after-tax return + effective deduction (credit offsets cost)
    break_even_rate = after_tax + effective_deduction
    break_even_rate_pct = break_even_rate * 100.0

    investing_wins = effective_mortgage_cost < after_tax
    delta_pct = effective_mortgage_cost_pct - break_even_rate_pct

    # Human-readable explanation
    if tax_credit_active:
        credit_note = (
            f"住宅ローン控除 reduces your effective rate to {effective_mortgage_cost_pct:.2f}% "
            f"({profile.mortgage_interest_rate_pct:.2f}% rate minus {effective_deduction*100:.2f}% credit). "
        )
    else:
        credit_note = ""

    if investing_wins:
        action = (
            f"Investing wins at your current effective mortgage cost of {effective_mortgage_cost_pct:.2f}%. "
            f"The break-even is {break_even_rate_pct:.2f}% — you would only benefit from paying off "
            f"if your mortgage rate rose to that level."
        )
    else:
        action = (
            f"Paying off the mortgage wins at your current effective mortgage cost of {effective_mortgage_cost_pct:.2f}%. "
            f"The break-even is {break_even_rate_pct:.2f}% — you would only benefit from investing "
            f"if your after-tax returns exceed that rate."
        )

    explanation = credit_note + action

    return {
        "break_even_rate_pct": round(break_even_rate_pct, 3),
        "current_mortgage_rate_pct": profile.mortgage_interest_rate_pct,
        "delta_pct": round(delta_pct, 3),
        "investing_wins": investing_wins,
        "after_tax_investment_return_pct": round(after_tax_pct, 3),
        "effective_mortgage_cost_pct": round(effective_mortgage_cost_pct, 3),
        "tax_credit_active": tax_credit_active,
        "annual_tax_credit_jpy": annual_credit_jpy,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# 2. Payoff-vs-invest comparison
# ---------------------------------------------------------------------------

def calculate_payoff_vs_invest_npv(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    lump_sum_jpy: int,
    payoff_year: int = 0,
    horizon_years: int = 30,
    investment_account_type: str = "taxable",
) -> dict:
    """
    Compare two paths over horizon_years:
      Path A (payoff): apply lump_sum_jpy against mortgage at payoff_year.
      Path B (invest): keep lump_sum_jpy invested, mortgage continues normally.

    Args:
        profile: FinancialProfile with mortgage fields populated.
        assumptions: AssumptionSet with investment_return_pct.
        lump_sum_jpy: Amount to either pay off or invest.
        payoff_year: Years from now to make the decision (0 = now).
        horizon_years: Total simulation length in years.
        investment_account_type: Account where the lump sum is invested in Path B.

    Returns:
        {
          "path_a_terminal_jpy": int,
          "path_b_terminal_jpy": int,
          "advantage_jpy": int,       # path_b - path_a (positive => investing wins)
          "advantage_pct": float,
          "recommendation": str,      # "payoff" | "invest" | "neutral"
          "trajectory_a": list[dict],
          "trajectory_b": list[dict],
          "lost_tax_credit_jpy": int,
        }
    """
    gross_return = assumptions.investment_return_pct / 100.0
    after_tax = _after_tax_return(gross_return, investment_account_type)

    mortgage_rate_pct = profile.mortgage_interest_rate_pct
    remaining_years_start = max(1, profile.mortgage_remaining_years)
    prepayment_fee = profile.mortgage_prepayment_fee_jpy

    # Initial portfolio: use total liquid assets as baseline (not FIRE-adjusted)
    from engine.fire_calculator import calculate_accessible_portfolio
    portfolio_info = calculate_accessible_portfolio(profile, profile.target_retirement_age)
    initial_portfolio = portfolio_info["total_accessible_jpy"]

    # Simulate two paths
    trajectory_a: list[dict] = []
    trajectory_b: list[dict] = []

    # Shared state
    bal_a = float(profile.mortgage_balance_jpy)
    bal_b = float(profile.mortgage_balance_jpy)
    portfolio_a = float(initial_portfolio)
    portfolio_b = float(initial_portfolio)
    years_remaining_a = remaining_years_start
    years_remaining_b = remaining_years_start
    credit_years_a = profile.mortgage_tax_credit_remaining_years
    credit_years_b = profile.mortgage_tax_credit_remaining_years
    lost_credit_jpy = 0

    for yr in range(horizon_years):
        # Monthly payments this year
        pmt_a = _monthly_payment(int(bal_a), mortgage_rate_pct, years_remaining_a) if bal_a > 0 and years_remaining_a > 0 else 0
        pmt_b = _monthly_payment(int(bal_b), mortgage_rate_pct, years_remaining_b) if bal_b > 0 and years_remaining_b > 0 else 0

        # Tax credits this year (added back to portfolio as annual refund)
        credit_a = _annual_loan_tax_credit_jpy(int(bal_a), profile.mortgage_tax_credit_rate_pct / 100.0, profile.mortgage_tax_credit_principal_cap_jpy) if credit_years_a > 0 and bal_a > 0 else 0
        credit_b = _annual_loan_tax_credit_jpy(int(bal_b), profile.mortgage_tax_credit_rate_pct / 100.0, profile.mortgage_tax_credit_principal_cap_jpy) if credit_years_b > 0 and bal_b > 0 else 0

        # Lump-sum payoff in Path A at payoff_year
        if yr == payoff_year and bal_a > 0:
            payoff_amount = min(lump_sum_jpy, int(bal_a) + prepayment_fee)
            principal_paid = min(lump_sum_jpy - prepayment_fee, int(bal_a))
            portfolio_a = max(0.0, portfolio_a - payoff_amount)
            bal_a = max(0.0, bal_a - principal_paid)
            years_remaining_a = max(0, years_remaining_a)
            # Forgo tax credits on the cleared portion
            if credit_years_a > 0:
                for ry in range(credit_years_a):
                    proj_bal = bal_a * (0.95 ** ry)  # rough amortisation proxy
                    lost_credit_jpy += _annual_loan_tax_credit_jpy(
                        int(proj_bal),
                        profile.mortgage_tax_credit_rate_pct / 100.0,
                        profile.mortgage_tax_credit_principal_cap_jpy,
                    )
                credit_years_a = 0  # credit forfeited if loan cleared

        # Grow portfolios
        portfolio_a = portfolio_a * (1 + after_tax) - pmt_a * 12 + credit_a
        portfolio_b = portfolio_b * (1 + after_tax) - pmt_b * 12 + credit_b

        # Invest the lump sum in Path B at payoff_year (no cost removed from portfolio)
        if yr == payoff_year:
            portfolio_b = portfolio_b + lump_sum_jpy  # lump sum goes into investments in B

        # Amortise mortgage balances
        if bal_a > 0 and years_remaining_a > 0:
            bal_a = _amortise_year(bal_a, mortgage_rate_pct, pmt_a)
            years_remaining_a = max(0, years_remaining_a - 1)
        if bal_b > 0 and years_remaining_b > 0:
            bal_b = _amortise_year(bal_b, mortgage_rate_pct, pmt_b)
            years_remaining_b = max(0, years_remaining_b - 1)

        if credit_years_a > 0:
            credit_years_a -= 1
        if credit_years_b > 0:
            credit_years_b -= 1

        age = profile.current_age + yr + 1
        nw_a = int(portfolio_a) + profile.property_value_jpy - int(bal_a)
        nw_b = int(portfolio_b) + profile.property_value_jpy - int(bal_b)

        trajectory_a.append({
            "year": yr + 1,
            "age": age,
            "portfolio_jpy": int(max(0, portfolio_a)),
            "mortgage_balance_jpy": int(max(0, bal_a)),
            "net_worth_jpy": nw_a,
        })
        trajectory_b.append({
            "year": yr + 1,
            "age": age,
            "portfolio_jpy": int(max(0, portfolio_b)),
            "mortgage_balance_jpy": int(max(0, bal_b)),
            "net_worth_jpy": nw_b,
        })

    path_a_terminal = trajectory_a[-1]["net_worth_jpy"] if trajectory_a else 0
    path_b_terminal = trajectory_b[-1]["net_worth_jpy"] if trajectory_b else 0
    advantage_jpy = path_b_terminal - path_a_terminal
    advantage_pct = (advantage_jpy / abs(path_a_terminal) * 100) if path_a_terminal != 0 else 0.0

    if abs(advantage_jpy) < 500_000:
        recommendation = "neutral"
    elif advantage_jpy > 0:
        recommendation = "invest"
    else:
        recommendation = "payoff"

    return {
        "path_a_terminal_jpy": path_a_terminal,
        "path_b_terminal_jpy": path_b_terminal,
        "advantage_jpy": advantage_jpy,
        "advantage_pct": round(advantage_pct, 1),
        "recommendation": recommendation,
        "trajectory_a": trajectory_a,
        "trajectory_b": trajectory_b,
        "lost_tax_credit_jpy": lost_credit_jpy,
    }


# ---------------------------------------------------------------------------
# 3. Multi-rate scenario runner
# ---------------------------------------------------------------------------

def run_mortgage_rate_scenarios(
    profile: FinancialProfile,
    assumptions: AssumptionSet,
    region_key: str,
    rates_pct: list[float] | None = None,
    mc_simulations_override: int | None = None,
) -> list[dict]:
    """
    Run the full FIRE scenario at each mortgage rate and return a table of key metrics.

    Args:
        profile: Base FinancialProfile.
        assumptions: Base AssumptionSet.
        region_key: Region for expense template.
        rates_pct: List of rates to test (default [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]).
        mc_simulations_override: Override MC simulations for speed (default: use assumptions).

    Returns:
        List of dicts (one per rate):
          {
            "mortgage_rate_pct": float,
            "monthly_payment_jpy": int,
            "fire_number_jpy": int,
            "years_to_fire": float,
            "mc_survival_pct": float,
            "annual_expenses_jpy": int,
          }
        Returns [] if profile has no mortgage balance.
    """
    if profile.mortgage_balance_jpy <= 0:
        return []

    if rates_pct is None:
        rates_pct = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]

    from dataclasses import replace
    from engine.fire_calculator import run_fire_scenario

    rows = []
    n_sims = mc_simulations_override if mc_simulations_override is not None else min(assumptions.monte_carlo_simulations, 2_000)

    for rate in rates_pct:
        new_monthly = _monthly_payment(
            profile.mortgage_balance_jpy,
            rate,
            max(1, profile.mortgage_remaining_years),
        )
        rate_profile = replace(
            profile,
            mortgage_interest_rate_pct=rate,
            monthly_mortgage_payment_jpy=new_monthly,
        )
        rate_assumptions = replace(assumptions, monte_carlo_simulations=n_sims)

        try:
            result = run_fire_scenario(
                profile=rate_profile,
                scenario_name=f"Rate {rate}%",
                scenario_id=f"rate_{rate}",
                assumptions=rate_assumptions,
                region_key=region_key,
                _skip_mortgage_rate_scenarios=True,
            )
            mc_survival = result.monte_carlo.success_rate_pct if result.monte_carlo else 0.0
            rows.append({
                "mortgage_rate_pct": rate,
                "monthly_payment_jpy": new_monthly,
                "fire_number_jpy": result.fire_number_jpy,
                "years_to_fire": result.years_to_fire,
                "mc_survival_pct": mc_survival,
                "annual_expenses_jpy": result.annual_expenses_jpy,
            })
        except Exception:
            rows.append({
                "mortgage_rate_pct": rate,
                "monthly_payment_jpy": new_monthly,
                "fire_number_jpy": 0,
                "years_to_fire": 0.0,
                "mc_survival_pct": 0.0,
                "annual_expenses_jpy": 0,
            })

    return rows


# ---------------------------------------------------------------------------
# 4. Vasicek stochastic rate path generator
# ---------------------------------------------------------------------------

def generate_rate_paths(
    initial_rate_pct: float,
    long_term_mean_pct: float,
    mean_reversion_speed: float,
    volatility_pct: float,
    n_simulations: int,
    n_years: int,
    seed: int | None = None,
    floor_pct: float = 0.0,
    cap_pct: float = 10.0,
) -> np.ndarray:
    """
    Generate a (n_simulations, n_years) array of rate paths using a discretised Vasicek process:

      r_{t+1} = r_t + kappa * (theta - r_t) + sigma * sqrt(dt) * N(0,1)

    All inputs and output are in percentage points (e.g. 0.7 means 0.7%, not 0.007).

    Args:
        initial_rate_pct: Starting rate in percentage points.
        long_term_mean_pct: Mean reversion target (theta) in percentage points.
        mean_reversion_speed: Speed of mean reversion (kappa), annual.
        volatility_pct: Annual std dev in absolute percentage points (sigma).
        n_simulations: Number of independent paths.
        n_years: Simulation horizon in years.
        seed: Random seed for reproducibility.
        floor_pct: Minimum rate (clip at this value each step).
        cap_pct: Maximum rate (clip at this value each step).

    Returns:
        np.ndarray of shape (n_simulations, n_years) with rates in percentage points.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0  # annual steps

    paths = np.empty((n_simulations, n_years))
    r_t = np.full(n_simulations, float(initial_rate_pct))

    for t in range(n_years):
        shock = rng.standard_normal(n_simulations)
        r_t = r_t + mean_reversion_speed * (long_term_mean_pct - r_t) * dt + volatility_pct * math.sqrt(dt) * shock
        r_t = np.clip(r_t, floor_pct, cap_pct)
        paths[:, t] = r_t

    return paths
