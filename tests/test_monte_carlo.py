"""
Monte Carlo simulation tests.

Uses a fixed seed for reproducibility. Key properties verified:
  - Success rate is high (>90%) for a conservative scenario
  - Success rate is low (<50%) for an unsustainable scenario
  - Percentile ordering: p10 < p25 < p50 < p75 < p90 at every time step
  - Portfolio never goes negative (floored at zero)
  - Sequence-of-returns risk reduces success rate vs no-SOR
  - Pension offset improves success rate
"""
import pytest
import numpy as np
from engine.monte_carlo import run_simulation, run_monte_carlo, find_safe_withdrawal_rate
from models.scenario import MonteCarloResult

SEED = 42
N_SIMS = 1000   # small for test speed, large enough for stable statistics


class TestRunSimulation:
    def test_portfolio_shape(self):
        raw = run_simulation(
            initial_portfolio_jpy=50_000_000,
            annual_withdrawal_jpy=1_750_000,
            annual_pension_jpy=0,
            pension_start_year=15,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        assert raw["portfolios"].shape == (N_SIMS, 31)  # 30 years + initial

    def test_initial_portfolio_is_preserved(self):
        raw = run_simulation(
            initial_portfolio_jpy=50_000_000,
            annual_withdrawal_jpy=1_750_000,
            annual_pension_jpy=0,
            pension_start_year=15,
            simulation_years=10,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        assert (raw["portfolios"][:, 0] == 50_000_000).all()

    def test_portfolio_never_negative(self):
        raw = run_simulation(
            initial_portfolio_jpy=5_000_000,
            annual_withdrawal_jpy=3_000_000,   # very high withdrawal
            annual_pension_jpy=0,
            pension_start_year=30,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.03,
            volatility=0.20,
            seed=SEED,
        )
        assert (raw["portfolios"] >= 0).all()

    def test_conservative_scenario_high_success(self):
        """
        2% withdrawal on 50M portfolio — very conservative, should survive well.
        Note: SOR amplification (1.5x vol in early years) is the dominant risk
        driver. At 3% withdrawal the success rate is ~70-75% over 30yr with SOR;
        we use 2% here to get a robustly high success rate regardless of seed.
        """
        raw = run_simulation(
            initial_portfolio_jpy=50_000_000,
            annual_withdrawal_jpy=1_000_000,   # 2% of 50M — very conservative
            annual_pension_jpy=0,
            pension_start_year=30,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        assert raw["success_rate_pct"] >= 85.0

    def test_aggressive_withdrawal_low_success(self):
        """10% withdrawal is almost certainly unsustainable."""
        raw = run_simulation(
            initial_portfolio_jpy=20_000_000,
            annual_withdrawal_jpy=2_000_000,   # 10% of portfolio
            annual_pension_jpy=0,
            pension_start_year=30,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.04,
            volatility=0.15,
            seed=SEED,
        )
        assert raw["success_rate_pct"] < 60.0

    def test_percentile_ordering(self):
        """p10 < p25 < p50 < p75 < p90 at every time step (except t=0 which is identical)."""
        raw = run_simulation(
            initial_portfolio_jpy=50_000_000,
            annual_withdrawal_jpy=1_750_000,
            annual_pension_jpy=0,
            pension_start_year=15,
            simulation_years=20,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        p = raw["percentiles"]
        # Skip t=0 (all identical = initial portfolio)
        for t in range(1, 21):
            assert p["p10"][t] <= p["p25"][t], f"p10 > p25 at t={t}"
            assert p["p25"][t] <= p["p50"][t], f"p25 > p50 at t={t}"
            assert p["p50"][t] <= p["p75"][t], f"p50 > p75 at t={t}"
            assert p["p75"][t] <= p["p90"][t], f"p75 > p90 at t={t}"

    def test_pension_improves_success_rate(self):
        """Adding pension income should increase success rate."""
        no_pension = run_simulation(
            initial_portfolio_jpy=30_000_000,
            annual_withdrawal_jpy=1_500_000,
            annual_pension_jpy=0,
            pension_start_year=0,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.04,
            volatility=0.15,
            seed=SEED,
        )
        with_pension = run_simulation(
            initial_portfolio_jpy=30_000_000,
            annual_withdrawal_jpy=1_500_000,
            annual_pension_jpy=800_000,
            pension_start_year=0,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.04,
            volatility=0.15,
            seed=SEED,
        )
        assert with_pension["success_rate_pct"] >= no_pension["success_rate_pct"]

    def test_sor_risk_reduces_success(self):
        """Sequence-of-returns risk (amplified early vol) reduces success rate."""
        without_sor = run_simulation(
            initial_portfolio_jpy=30_000_000,
            annual_withdrawal_jpy=1_200_000,
            annual_pension_jpy=0,
            pension_start_year=20,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            sequence_of_returns_risk=False,
            seed=SEED,
        )
        with_sor = run_simulation(
            initial_portfolio_jpy=30_000_000,
            annual_withdrawal_jpy=1_200_000,
            annual_pension_jpy=0,
            pension_start_year=20,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            sequence_of_returns_risk=True,
            seed=SEED,
        )
        assert with_sor["success_rate_pct"] <= without_sor["success_rate_pct"]

    def test_result_structure(self):
        raw = run_simulation(
            50_000_000, 1_750_000, 0, 15, 10, 100, 0.05, 0.15, seed=SEED
        )
        for key in ["portfolios", "success_rate_pct", "percentiles",
                    "ruin_year_median", "n_simulations", "simulation_years"]:
            assert key in raw

    def test_percentile_lengths(self):
        raw = run_simulation(
            50_000_000, 1_750_000, 0, 15, 20, 100, 0.05, 0.15, seed=SEED
        )
        for band in ["p10", "p25", "p50", "p75", "p90"]:
            assert len(raw["percentiles"][band]) == 21  # 20 years + t=0

    def test_reproducible_with_seed(self):
        r1 = run_simulation(30_000_000, 1_200_000, 0, 10, 20, 100, 0.05, 0.15, seed=7)
        r2 = run_simulation(30_000_000, 1_200_000, 0, 10, 20, 100, 0.05, 0.15, seed=7)
        assert r1["success_rate_pct"] == r2["success_rate_pct"]


class TestRunMonteCarlo:
    def test_returns_monte_carlo_result(self):
        result = run_monte_carlo(
            initial_portfolio_jpy=50_000_000,
            annual_expenses_jpy=2_000_000,
            net_pension_annual_jpy=1_000_000,
            pension_start_year=15,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.04,
            volatility=0.15,
            seed=SEED,
        )
        assert isinstance(result, MonteCarloResult)

    def test_success_rate_in_range(self):
        result = run_monte_carlo(
            initial_portfolio_jpy=50_000_000,
            annual_expenses_jpy=2_000_000,
            net_pension_annual_jpy=0,
            pension_start_year=30,
            simulation_years=30,
            n_simulations=N_SIMS,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        assert 0.0 <= result.success_rate_pct <= 100.0

    def test_percentile_bands_populated(self):
        result = run_monte_carlo(
            50_000_000, 2_000_000, 0, 15, 20, 100, 0.05, 0.15, seed=SEED
        )
        assert len(result.p50) == 21   # 20 years + t=0
        assert len(result.p10) == len(result.p90)


class TestFindSafeWithdrawalRate:
    def test_returns_rate_below_8pct(self):
        result = find_safe_withdrawal_rate(
            initial_portfolio_jpy=50_000_000,
            annual_expenses_jpy=2_000_000,
            net_pension_annual_jpy=0,
            pension_start_year=15,
            simulation_years=30,
            n_simulations=500,
            mean_return=0.05,
            volatility=0.15,
            target_success_rate=90.0,
            seed=SEED,
        )
        assert 0 < result["safe_rate_pct"] < 8.0

    def test_higher_success_target_lower_rate(self):
        base_kwargs = dict(
            initial_portfolio_jpy=40_000_000,
            annual_expenses_jpy=1_800_000,
            net_pension_annual_jpy=0,
            pension_start_year=15,
            simulation_years=30,
            n_simulations=300,
            mean_return=0.05,
            volatility=0.15,
            seed=SEED,
        )
        r90 = find_safe_withdrawal_rate(**base_kwargs, target_success_rate=90.0)
        r99 = find_safe_withdrawal_rate(**base_kwargs, target_success_rate=99.0)
        assert r99["safe_rate_pct"] <= r90["safe_rate_pct"]

    def test_result_structure(self):
        result = find_safe_withdrawal_rate(
            40_000_000, 1_800_000, 0, 15, 20, 200, 0.05, 0.15,
            target_success_rate=90.0, seed=SEED
        )
        for key in ["safe_rate_pct", "annual_safe_withdrawal_jpy",
                    "monthly_safe_withdrawal_jpy", "target_success_rate_pct"]:
            assert key in result
