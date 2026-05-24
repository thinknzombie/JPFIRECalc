"""
Monte Carlo simulation engine for FIRE portfolio projections.

Generates stochastic return sequences and models portfolio survival
over the retirement horizon. Key outputs:

  - Percentile trajectory bands (p10/p25/p50/p75/p90) for chart rendering
  - Success rate: % of simulations where portfolio never hits zero
  - Sequence-of-returns risk: amplified volatility in the first 5 years
    of retirement (the most dangerous period for early retirees)

Return model:
  - Log-normal returns: ln(1+r) ~ N(mu, sigma)
  - mu = ln(1 + mean_return) - 0.5 * sigma^2  (adjusted for log-normal)
  - sigma = annual volatility (std dev of log returns)
  - For global equity: ~15% annualised volatility is a reasonable default

Inflation:
  - Expenses grow at japan_inflation_pct each year
  - Pension income is assumed to grow at 1% (nenkin is partially CPI-linked)

Performance:
  - 10,000 paths × 40 years completes in ~2s on a standard laptop with numpy
  - Uses vectorised numpy operations — no Python loops over paths

Sources:
  - Kitces, ERN (earlyretirementnow.com) SWR research
  - Japan-specific: Pfau (2011), "Safe Savings Rates" with Japan data
"""
from __future__ import annotations
import numpy as np
from models.scenario import MonteCarloResult


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def run_simulation(
    initial_portfolio_jpy: int,
    annual_withdrawal_jpy: int,
    annual_pension_jpy: int,
    pension_start_year: int,
    simulation_years: int,
    n_simulations: int,
    mean_return: float,
    volatility: float,
    inflation_rate: float = 0.02,
    pension_growth_rate: float = 0.01,
    sequence_of_returns_risk: bool = True,
    sor_amplifier: float = 1.5,
    sor_years: int = 5,
    seed: int | None = None,
    lump_sums: list[tuple[int, int]] | None = None,
    withdrawal_reductions: list[tuple[int, int]] | None = None,
    foreign_pension_annual_jpy: int = 0,
    foreign_pension_start_year: int | None = None,
    foreign_pension_growth_rate: float | None = None,
    mortgage_rate_path: np.ndarray | None = None,
    mortgage_balance_initial_jpy: int = 0,
    mortgage_remaining_years_initial: int = 0,
    mortgage_tax_credit_remaining_years: int = 0,
    mortgage_tax_credit_rate: float = 0.007,
    mortgage_tax_credit_cap_jpy: int = 30_000_000,
) -> dict:
    """
    Run N Monte Carlo simulations of portfolio drawdown over retirement.

    Args:
        initial_portfolio_jpy:  Starting portfolio value at retirement.
        annual_withdrawal_jpy:  Base annual withdrawal (expenses - pension at start).
        annual_pension_jpy:     Annual pension income (net of tax, Japan pensions only
                                if foreign pension is provided separately).
        pension_start_year:     Year within simulation when Japan pension begins (0-indexed).
        simulation_years:       Number of years to simulate.
        n_simulations:          Number of random paths to generate.
        mean_return:            Expected annual return (decimal, e.g. 0.05).
        volatility:             Annual return std dev (decimal, e.g. 0.15).
        inflation_rate:         Annual expense inflation (decimal).
        pension_growth_rate:    Annual growth in Japan pension benefit (decimal).
        sequence_of_returns_risk: If True, amplify volatility in early retirement.
        sor_amplifier:          Volatility multiplier for SOR years (default 1.5×).
        sor_years:              Number of early retirement years with amplified vol.
        seed:                   Random seed for reproducibility (None = random).
        lump_sums:              Optional list of (year_into_retirement, amount_jpy) tuples.
                                At the specified year, amount_jpy is added to ALL paths
                                (e.g. net proceeds from a planned property sale).
        withdrawal_reductions:  Optional list of (start_year, annual_reduction_jpy) tuples.
                                From start_year onward, net_withdrawal is reduced by
                                annual_reduction_jpy (e.g. mortgage payment stops after sale).
        foreign_pension_annual_jpy: Annual foreign pension income (e.g. US Social Security).
                                Tracked separately from Japan pension to allow a different
                                inflation/growth rate.
        foreign_pension_start_year: Year within simulation when foreign pension begins.
                                If None, same as pension_start_year.
        foreign_pension_growth_rate: Annual growth rate for foreign pension (decimal).
                                If None, uses pension_growth_rate.
        mortgage_rate_path:     Optional ndarray of shape (n_simulations, simulation_years)
                                with annual mortgage rates in percentage points (not decimal).
                                When provided, mortgage payment is recomputed each year and the
                                delta vs. the base payment is added to net_withdrawal. Japan only.
        mortgage_balance_initial_jpy: Mortgage balance at start of retirement.
        mortgage_remaining_years_initial: Remaining loan term in years at retirement.
        mortgage_tax_credit_remaining_years: Years of 住宅ローン控除 remaining.
        mortgage_tax_credit_rate: Annual credit rate (decimal, e.g. 0.007).
        mortgage_tax_credit_cap_jpy: Principal cap for the credit.

    Returns:
        dict with:
          portfolios: ndarray shape (n_simulations, simulation_years+1)
          success_rate_pct: float
          percentiles: dict of p10/p25/p50/p75/p90 arrays
          ruin_year_median: median year of ruin for failed paths (or None)
    """
    rng = np.random.default_rng(seed)

    # Log-normal parameters (exact conversion from arithmetic mean to log-space)
    # If R ~ LogNormal then: mu_log = ln(1+r) - 0.5*sigma_log^2
    sigma_log = np.log(1 + volatility)
    mu_log = np.log(1 + mean_return) - 0.5 * sigma_log ** 2

    # Generate return matrix: shape (n_simulations, simulation_years)
    log_returns = rng.normal(mu_log, sigma_log, size=(n_simulations, simulation_years))

    # Apply sequence-of-returns risk: amplify volatility in early years
    if sequence_of_returns_risk and sor_years > 0:
        sor_sigma = sigma_log * sor_amplifier
        sor_mu = np.log(1 + mean_return) - 0.5 * sor_sigma ** 2
        sor_returns = rng.normal(sor_mu, sor_sigma, size=(n_simulations, sor_years))
        log_returns[:, :sor_years] = sor_returns

    gross_returns = np.exp(log_returns)  # 1 + r each year

    # Build expense schedule: grows with inflation each year
    # Pension offsets withdrawal from pension_start_year onwards.
    # Foreign pension (if any) may start at a different year and grow at a
    # different rate (tracking home-country CPI rather than Japan CPI).
    fp_start = foreign_pension_start_year if foreign_pension_start_year is not None else pension_start_year
    fp_growth = foreign_pension_growth_rate if foreign_pension_growth_rate is not None else pension_growth_rate

    expense_schedule = np.zeros(simulation_years)
    pension_schedule = np.zeros(simulation_years)
    for yr in range(simulation_years):
        inflation_factor = (1 + inflation_rate) ** yr
        expense_schedule[yr] = annual_withdrawal_jpy * inflation_factor
        # Japan pension
        if yr >= pension_start_year:
            jp_factor = (1 + pension_growth_rate) ** (yr - pension_start_year)
            pension_schedule[yr] += annual_pension_jpy * jp_factor
        # Foreign pension (separate start year and growth rate)
        if foreign_pension_annual_jpy > 0 and yr >= fp_start:
            fp_factor = (1 + fp_growth) ** (yr - fp_start)
            pension_schedule[yr] += foreign_pension_annual_jpy * fp_factor

    net_withdrawal = expense_schedule - pension_schedule  # net from portfolio each year

    # Apply withdrawal reductions (e.g. mortgage stops after property sale)
    if withdrawal_reductions:
        for start_year, annual_reduction in withdrawal_reductions:
            if 0 < start_year <= simulation_years:
                net_withdrawal[start_year:] -= annual_reduction

    # Stochastic mortgage rate adjustment (shape: n_simulations × simulation_years)
    # Tracks how variable mortgage payments change net withdrawals per simulation path.
    mortgage_delta: np.ndarray | None = None
    if (
        mortgage_rate_path is not None
        and mortgage_balance_initial_jpy > 0
        and mortgage_remaining_years_initial > 0
    ):
        mortgage_delta = np.zeros((n_simulations, simulation_years))
        base_payment_monthly = (
            net_withdrawal[0] * 0  # placeholder — compute below
        )
        # Compute base monthly payment from fixed schedule (rate_path[:, 0] would give year-0 rate)
        # We use the initial rates from the path; base payment = payment at initial_rate_pct (year 0 mean).
        from engine.mortgage_analysis import _monthly_payment, _annual_loan_tax_credit_jpy
        initial_rate_pct = float(mortgage_rate_path[:, 0].mean())
        base_monthly_pmt = _monthly_payment(mortgage_balance_initial_jpy, initial_rate_pct, mortgage_remaining_years_initial)

        # Track per-simulation mortgage state: vectorised would require per-path loops anyway
        # since balance changes per path with different rates. We accept O(n_sims) here
        # because this path is optional and rarely active with large n_sims.
        # For typical use (stochastic_mortgage_rate=True), users can reduce n_sims via the UI.
        balances = np.full(n_simulations, float(mortgage_balance_initial_jpy))
        years_rem = np.full(n_simulations, float(mortgage_remaining_years_initial))
        credit_yrs = np.full(n_simulations, float(mortgage_tax_credit_remaining_years))

        for yr in range(simulation_years):
            rate_yr = mortgage_rate_path[:, yr]  # shape (n_simulations,)
            still_active = (balances > 0) & (years_rem > 0)
            if not still_active.any():
                break

            # Monthly payment this year per path
            pmts = np.where(
                still_active,
                np.vectorize(lambda b, r, y: _monthly_payment(int(b), float(r), int(max(1, y))))(
                    balances, rate_yr, years_rem
                ),
                0,
            )
            annual_pmts = pmts * 12

            # Tax credit refund (reduces net withdrawal)
            credits = np.where(
                (credit_yrs > 0) & (balances > 0),
                np.vectorize(lambda b: _annual_loan_tax_credit_jpy(
                    int(b), mortgage_tax_credit_rate, mortgage_tax_credit_cap_jpy
                ))(balances),
                0,
            )

            # Delta vs. base payment (only the change in mortgage cost)
            # Positive delta = rate rose = more from portfolio; negative = rate fell
            mortgage_delta[:, yr] = (annual_pmts - base_monthly_pmt * 12) - credits

            # Amortise balances (vectorised approximation — monthly compound)
            r_monthly = rate_yr / 100 / 12
            factor = np.where(
                r_monthly > 0,
                (1 + r_monthly) ** 12,
                1.0,
            )
            interest_annual = np.where(r_monthly > 0, balances * (factor - 1), 0.0)
            principal_annual = annual_pmts - interest_annual
            balances = np.maximum(0.0, balances - np.maximum(0.0, principal_annual))
            years_rem = np.maximum(0.0, years_rem - 1)
            credit_yrs = np.maximum(0.0, credit_yrs - 1)

    # Build lump-sum lookup: year_index → total_amount
    lump_sum_map: dict[int, int] = {}
    if lump_sums:
        for yr_idx, amount in lump_sums:
            if 0 < yr_idx <= simulation_years:  # must be within the simulated window
                lump_sum_map[yr_idx] = lump_sum_map.get(yr_idx, 0) + int(amount)

    # Simulate portfolios: vectorised over all paths simultaneously
    # portfolios[i, 0] = initial value; portfolios[i, t+1] after year t
    portfolios = np.zeros((n_simulations, simulation_years + 1))
    portfolios[:, 0] = initial_portfolio_jpy

    for yr in range(simulation_years):
        # Grow, then withdraw (withdraw at end of year)
        base_net = net_withdrawal[yr]
        if mortgage_delta is not None and yr < mortgage_delta.shape[1]:
            # Per-simulation extra cost from stochastic mortgage rate (positive = higher cost)
            effective_withdrawal = base_net + mortgage_delta[:, yr]
        else:
            effective_withdrawal = base_net
        portfolios[:, yr + 1] = portfolios[:, yr] * gross_returns[:, yr] - effective_withdrawal
        # Inject property-sale lump sum (same amount on all paths — deterministic event)
        if yr + 1 in lump_sum_map:
            portfolios[:, yr + 1] += lump_sum_map[yr + 1]
        # Floor at zero — portfolio cannot go negative (ruin state)
        portfolios[:, yr + 1] = np.maximum(portfolios[:, yr + 1], 0)

    # Success rate: paths that never hit zero
    min_portfolio = portfolios[:, 1:].min(axis=1)
    successes = (min_portfolio > 0).sum()
    success_rate = float(successes / n_simulations * 100)

    # Median ruin year for failed paths
    failed_mask = min_portfolio <= 0
    ruin_year_median = None
    if failed_mask.any():
        failed_portfolios = portfolios[failed_mask, 1:]
        # Ruin year = first year where portfolio hits zero
        ruin_years = (failed_portfolios == 0).argmax(axis=1) + 1
        ruin_year_median = int(np.median(ruin_years))

    # Percentile trajectories (shape: simulation_years+1 each)
    percentiles = {
        "p10": np.percentile(portfolios, 10, axis=0).astype(int).tolist(),
        "p25": np.percentile(portfolios, 25, axis=0).astype(int).tolist(),
        "p50": np.percentile(portfolios, 50, axis=0).astype(int).tolist(),
        "p75": np.percentile(portfolios, 75, axis=0).astype(int).tolist(),
        "p90": np.percentile(portfolios, 90, axis=0).astype(int).tolist(),
    }

    return {
        "portfolios": portfolios,
        "success_rate_pct": round(success_rate, 1),
        "percentiles": percentiles,
        "ruin_year_median": ruin_year_median,
        "n_simulations": n_simulations,
        "simulation_years": simulation_years,
        "mean_return_pct": mean_return * 100,
        "volatility_pct": volatility * 100,
    }


# ---------------------------------------------------------------------------
# High-level wrapper: produces MonteCarloResult from scenario inputs
# ---------------------------------------------------------------------------

def run_monte_carlo(
    initial_portfolio_jpy: int,
    annual_expenses_jpy: int,
    net_pension_annual_jpy: int,
    pension_start_year: int,
    simulation_years: int,
    n_simulations: int,
    mean_return: float,
    volatility: float,
    inflation_rate: float = 0.02,
    sequence_of_returns_risk: bool = True,
    seed: int | None = None,
    lump_sums: list[tuple[int, int]] | None = None,
    withdrawal_reductions: list[tuple[int, int]] | None = None,
    foreign_pension_annual_jpy: int = 0,
    foreign_pension_start_year: int | None = None,
    foreign_pension_growth_rate: float | None = None,
    mortgage_rate_path: "np.ndarray | None" = None,
    mortgage_balance_initial_jpy: int = 0,
    mortgage_remaining_years_initial: int = 0,
    mortgage_tax_credit_remaining_years: int = 0,
    mortgage_tax_credit_rate: float = 0.007,
    mortgage_tax_credit_cap_jpy: int = 30_000_000,
) -> MonteCarloResult:
    """
    Run Monte Carlo and return a MonteCarloResult ready for the ScenarioResult.

    The annual withdrawal is the net portfolio need:
        withdrawal = annual_expenses - pension (before pension starts)
        withdrawal = annual_expenses - pension (after pension starts, already offset)

    Before pension start: full expenses from portfolio
    After pension start: pension covers part, portfolio covers the rest
    """
    # Net from portfolio before pension starts
    pre_pension_withdrawal = annual_expenses_jpy

    raw = run_simulation(
        initial_portfolio_jpy=initial_portfolio_jpy,
        annual_withdrawal_jpy=pre_pension_withdrawal,
        annual_pension_jpy=net_pension_annual_jpy,
        pension_start_year=pension_start_year,
        simulation_years=simulation_years,
        n_simulations=n_simulations,
        mean_return=mean_return,
        volatility=volatility,
        inflation_rate=inflation_rate,
        sequence_of_returns_risk=sequence_of_returns_risk,
        seed=seed,
        lump_sums=lump_sums,
        withdrawal_reductions=withdrawal_reductions,
        foreign_pension_annual_jpy=foreign_pension_annual_jpy,
        foreign_pension_start_year=foreign_pension_start_year,
        foreign_pension_growth_rate=foreign_pension_growth_rate,
        mortgage_rate_path=mortgage_rate_path,
        mortgage_balance_initial_jpy=mortgage_balance_initial_jpy,
        mortgage_remaining_years_initial=mortgage_remaining_years_initial,
        mortgage_tax_credit_remaining_years=mortgage_tax_credit_remaining_years,
        mortgage_tax_credit_rate=mortgage_tax_credit_rate,
        mortgage_tax_credit_cap_jpy=mortgage_tax_credit_cap_jpy,
    )

    return MonteCarloResult(
        p10=raw["percentiles"]["p10"],
        p25=raw["percentiles"]["p25"],
        p50=raw["percentiles"]["p50"],
        p75=raw["percentiles"]["p75"],
        p90=raw["percentiles"]["p90"],
        success_rate_pct=raw["success_rate_pct"],
        n_simulations=n_simulations,
    )


# ---------------------------------------------------------------------------
# Safe withdrawal rate finder
# ---------------------------------------------------------------------------

def find_safe_withdrawal_rate(
    initial_portfolio_jpy: int,
    annual_expenses_jpy: int,
    net_pension_annual_jpy: int,
    pension_start_year: int,
    simulation_years: int,
    n_simulations: int,
    mean_return: float,
    volatility: float,
    target_success_rate: float = 95.0,
    min_rate: float = 0.01,
    max_rate: float = 0.08,
    precision: float = 0.001,
    seed: int | None = None,
) -> dict:
    """
    Binary search for the maximum withdrawal rate that achieves target_success_rate.

    Useful for showing "your safe withdrawal rate given your portfolio and expenses".

    Returns:
        dict with safe_rate_pct, success_rate_pct, annual_withdrawal_jpy.
    """
    lo, hi = min_rate, max_rate

    for _ in range(20):  # binary search, converges in ~20 steps
        mid = (lo + hi) / 2
        test_withdrawal = int(initial_portfolio_jpy * mid) - net_pension_annual_jpy

        if test_withdrawal <= 0:
            hi = mid
            continue

        raw = run_simulation(
            initial_portfolio_jpy=initial_portfolio_jpy,
            annual_withdrawal_jpy=max(0, test_withdrawal),
            annual_pension_jpy=net_pension_annual_jpy,
            pension_start_year=pension_start_year,
            simulation_years=simulation_years,
            n_simulations=n_simulations,
            mean_return=mean_return,
            volatility=volatility,
            sequence_of_returns_risk=True,
            seed=seed,
        )

        if raw["success_rate_pct"] >= target_success_rate:
            lo = mid
        else:
            hi = mid

        if (hi - lo) < precision:
            break

    safe_rate = (lo + hi) / 2
    annual_safe_withdrawal = int(initial_portfolio_jpy * safe_rate)

    return {
        "safe_rate_pct": round(safe_rate * 100, 2),
        "target_success_rate_pct": target_success_rate,
        "annual_safe_withdrawal_jpy": annual_safe_withdrawal,
        "monthly_safe_withdrawal_jpy": annual_safe_withdrawal // 12,
        "simulation_years": simulation_years,
        "n_simulations": n_simulations,
    }
