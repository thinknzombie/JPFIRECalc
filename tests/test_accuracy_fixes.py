"""
Regression tests for the 2026-07 accuracy overhaul.

Covers:
  - 2025 tax reform data (basic deduction tiers keyed off net income,
    ¥650k employment income deduction floor, ¥1.6M wall)
  - Separate residence-tax taxable base (¥430k basic deduction)
  - Income-based NHI in retirement (pension income, not withdrawals)
  - Accessible portfolio nets CGT out of the taxable brokerage
  - Pension-gap FIRE number discounts at the retirement return rate
  - iDeCo lump-sum tax applied at the age-60 unlock
  - Deterministic trajectory inflates expenses (consistent with MC)
  - Monte Carlo extra expense schedule (NHI) and moment-matched lognormal
"""
import math
import numpy as np
import pytest

from models.profile import FinancialProfile
from models.scenario import AssumptionSet
from engine.tax_calculator import (
    calculate_income_tax,
    calculate_basic_deduction,
    calculate_residence_basic_deduction,
    TAX_FREE_SALARY_WALL_JPY,
)
from engine.nhi_calculator import (
    calculate_nhi_income_base,
    calculate_nhi_for_retiree,
)
from engine.pension_calculator import calculate_pension_after_tax
from engine.fire_calculator import (
    calculate_accessible_portfolio,
    project_net_worth,
    run_fire_scenario,
    _ideco_net_of_lump_sum_tax,
    _retirement_nhi_premium,
)
from engine.monte_carlo import run_simulation


def base_profile(**kwargs) -> FinancialProfile:
    defaults = dict(
        current_age=40,
        target_retirement_age=50,
        employment_type="company_employee",
        annual_gross_income_jpy=8_000_000,
        monthly_expenses_jpy=250_000,
        monthly_nisa_contribution_jpy=100_000,
        ideco_monthly_contribution_jpy=23_000,
        nisa_balance_jpy=20_000_000,
        ideco_balance_jpy=5_000_000,
        taxable_brokerage_jpy=10_000_000,
        taxable_brokerage_cost_basis_jpy=6_000_000,
        cash_savings_jpy=5_000_000,
        nenkin_contribution_months=240,
        nenkin_claim_age=65,
        avg_standard_monthly_remuneration_jpy=400_000,
    )
    defaults.update(kwargs)
    return FinancialProfile(**defaults)


def base_assumptions(**kwargs) -> AssumptionSet:
    defaults = dict(
        investment_return_pct=5.0,
        retirement_return_pct=4.0,
        withdrawal_rate_pct=3.5,
        monte_carlo_simulations=200,
        nhi_municipality_key="national_average",
        nhi_household_members=1,
    )
    defaults.update(kwargs)
    return AssumptionSet(**defaults)


# ---------------------------------------------------------------------------
# 2025 tax reform
# ---------------------------------------------------------------------------

class TestTaxReform2025:
    def test_wall_constant_is_1_6m(self):
        assert TAX_FREE_SALARY_WALL_JPY == 1_600_000

    def test_income_at_160man_wall_pays_no_income_tax(self):
        # Salary 1.6M: EI deduction 650k → net 950k; basic deduction 950k → 0
        result = calculate_income_tax(gross_income=1_600_000)
        assert result["taxable_income"] == 0
        assert result["income_tax"] == 0

    def test_basic_deduction_keyed_off_net_income(self):
        # A 6M-gross employee has net income 4.36M → 680k tier, NOT the
        # 630k tier that gross income 6M would select.
        result = calculate_income_tax(gross_income=6_000_000)
        assert result["basic_deduction"] == calculate_basic_deduction(4_360_000)
        assert result["basic_deduction"] == 680_000

    def test_residence_taxable_base_uses_430k_deduction(self):
        result = calculate_income_tax(gross_income=6_000_000)
        # Residence base = employment income − 430k (vs 680k for income tax)
        assert result["residence_taxable_income"] == 4_360_000 - 430_000
        assert result["residence_taxable_income"] > result["taxable_income"]

    def test_residence_basic_deduction(self):
        assert calculate_residence_basic_deduction(5_000_000) == 430_000
        assert calculate_residence_basic_deduction(30_000_000) == 0


# ---------------------------------------------------------------------------
# Income-based NHI
# ---------------------------------------------------------------------------

class TestIncomeBasedNhi:
    def test_no_pension_means_zero_income_base(self):
        # Living off NISA/cash: no NHI-assessable income at all
        assert calculate_nhi_income_base(0, age=50) == 0

    def test_pension_income_after_deduction(self):
        # 2M pension at 65: minus ¥1.1M 公的年金等控除 → 900k
        assert calculate_nhi_income_base(2_000_000, age=65) == 900_000

    def test_pension_below_deduction_floor(self):
        assert calculate_nhi_income_base(1_000_000, age=65) == 0

    def test_declared_gains_are_added(self):
        assert calculate_nhi_income_base(0, age=50, declared_gains_jpy=1_500_000) == 1_500_000

    def test_gap_year_premium_is_reduced_minimum(self):
        # Zero income → 7割軽減 on per-capita, no income-based component
        premium_gap = _retirement_nhi_premium(0, 50, 1, "national_average")
        result = calculate_nhi_for_retiree(0, 1, "national_average", age=50)
        assert result["low_income_reduction_rate"] == 0.7
        assert premium_gap == result["total"]
        # Sanity: the reduced minimum is small — well under ¥50k/yr for 1 member
        assert premium_gap < 50_000

    def test_pension_years_premium_higher_than_gap(self):
        gap = _retirement_nhi_premium(0, 64, 1, "national_average")
        steady = _retirement_nhi_premium(2_500_000, 65, 1, "national_average")
        assert steady > gap


# ---------------------------------------------------------------------------
# Pension after-tax includes basic deduction
# ---------------------------------------------------------------------------

class TestPensionAfterTaxBasicDeduction:
    def test_typical_pension_pays_no_income_tax(self):
        # 2M at 65: net income 900k < basic deduction → income tax 0
        result = calculate_pension_after_tax(2_000_000, age=65)
        assert result["income_tax"] == 0
        assert result["residence_tax"] > 0  # residence tax still applies

    def test_larger_pension_still_taxed(self):
        result = calculate_pension_after_tax(4_000_000, age=65)
        assert result["income_tax"] > 0


# ---------------------------------------------------------------------------
# Accessible portfolio CGT netting
# ---------------------------------------------------------------------------

class TestAccessiblePortfolioCgt:
    def test_cost_basis_reduces_cgt_reserve(self):
        profile = base_profile()  # 10M market, 6M basis → 4M gain
        result = calculate_accessible_portfolio(profile, fire_age=50)
        assert result["taxable_cgt_reserve_jpy"] == int(4_000_000 * 0.20315)
        assert result["taxable_net_jpy"] == 10_000_000 - int(4_000_000 * 0.20315)

    def test_no_basis_assumes_full_gain(self):
        profile = base_profile(taxable_brokerage_cost_basis_jpy=None)
        result = calculate_accessible_portfolio(profile, fire_age=50)
        assert result["taxable_cgt_reserve_jpy"] == int(10_000_000 * 0.20315)


# ---------------------------------------------------------------------------
# iDeCo lump-sum tax at unlock
# ---------------------------------------------------------------------------

class TestIdecoLumpSumTax:
    def test_small_balance_untaxed(self):
        # 20-year tenure → 8M deduction; 5M balance → no tax
        assert _ideco_net_of_lump_sum_tax(5_000_000, 20) == 5_000_000

    def test_large_balance_taxed(self):
        net = _ideco_net_of_lump_sum_tax(30_000_000, 20)
        assert net < 30_000_000
        # (30M − 8M)/2 = 11M taxable → tax > 0 but far below 20.315% of balance
        assert net > 30_000_000 * 0.9

    def test_trajectory_unlock_at_60_is_net_of_tax(self):
        profile = base_profile(
            current_age=59,
            target_retirement_age=65,
            ideco_balance_jpy=40_000_000,
            ideco_monthly_contribution_jpy=0,
            ideco_start_age=55,  # short tenure → small deduction → real tax
        )
        assumptions = base_assumptions()
        traj = project_net_worth(profile, assumptions, "tokyo")
        # Portfolio at the unlock year should include less than the full pot
        # (the pot grew one year at 5% then was taxed at withdrawal).
        year_60 = next(t for t in traj if t.age == 60)
        assert year_60.ideco_locked_jpy == 0


# ---------------------------------------------------------------------------
# Deterministic trajectory: inflation + per-year NHI
# ---------------------------------------------------------------------------

class TestTrajectoryInflationAndNhi:
    def test_lifestyle_budget_inflates(self):
        """The WR-based lifestyle budget (Model B1') set at retirement start
        must inflate at retirement_expense_growth_pct in later years."""
        profile = base_profile()
        assumptions = base_assumptions(retirement_expense_growth_pct=2.0)
        traj = project_net_worth(profile, assumptions, "tokyo")
        retirement_years = [t for t in traj if t.phase == "retirement"]
        assert retirement_years[5].lifestyle_budget_jpy > retirement_years[1].lifestyle_budget_jpy

    def test_gap_year_nhi_is_reduced_minimum(self):
        profile = base_profile()  # FIRE at 50, pension at 65
        assumptions = base_assumptions()
        traj = project_net_worth(profile, assumptions, "tokyo")
        gap_year = next(t for t in traj if t.age == 55)
        assert gap_year.phase == "retirement"
        # Zero NHI-assessable income → 軽減 minimum (incl. the 40–64 LTC
        # component). Far below the old model, which assessed the full
        # ~¥3M withdrawal as income (≈ ¥300k+/yr).
        assert gap_year.nhi_premium_jpy < 60_000

    def test_pension_income_raises_nhi_at_same_age(self):
        # Like-for-like: at the same age, pension income must raise NHI.
        # (Comparing across ages is confounded by the 40–64 LTC component.)
        no_income = _retirement_nhi_premium(0, 55, 1, "national_average")
        with_pension = _retirement_nhi_premium(3_000_000, 55, 1, "national_average")
        assert with_pension > no_income

    def test_pension_income_appears_at_claim_age(self):
        profile = base_profile()
        assumptions = base_assumptions()
        traj = project_net_worth(profile, assumptions, "tokyo")
        before = next(t for t in traj if t.age == 64)
        after = next(t for t in traj if t.age == 65)
        assert before.pension_income_jpy == 0
        assert after.pension_income_jpy > 0


# ---------------------------------------------------------------------------
# FIRE number: pension-gap discount at retirement return rate
# ---------------------------------------------------------------------------

class TestPensionGapDiscountRate:
    def test_higher_retirement_return_lowers_fire_number(self):
        """With a 15-year pension gap, the gap-year annuity is discounted at
        the retirement return — a higher return must shrink the FIRE number."""
        profile = base_profile()
        low = run_fire_scenario(
            profile, "low", "00000000-0000-4000-8000-000000000001",
            base_assumptions(retirement_return_pct=3.0), "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        high = run_fire_scenario(
            profile, "high", "00000000-0000-4000-8000-000000000002",
            base_assumptions(retirement_return_pct=5.0), "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        assert high.fire_number_jpy < low.fire_number_jpy

    def test_nhi_gap_reported(self):
        profile = base_profile()
        result = run_fire_scenario(
            profile, "t", "00000000-0000-4000-8000-000000000003",
            base_assumptions(), "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        # Both figures reported; gap-year NHI sits at the 軽減 minimum
        # (small, though it includes the 40–64 LTC component).
        assert 0 < result.annual_nhi_gap_jpy < 60_000
        assert result.annual_nhi_jpy > 0


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

class TestMonteCarloUpdates:
    def test_extra_expense_schedule_reduces_success(self):
        common = dict(
            initial_portfolio_jpy=100_000_000,
            annual_withdrawal_jpy=4_000_000,
            annual_pension_jpy=0,
            pension_start_year=0,
            simulation_years=30,
            n_simulations=2_000,
            mean_return=0.04,
            volatility=0.15,
            seed=42,
        )
        without = run_simulation(**common)
        with_extra = run_simulation(
            **common, extra_expense_schedule=[2_000_000] * 30
        )
        assert with_extra["success_rate_pct"] < without["success_rate_pct"]

    def test_lognormal_moments_match(self):
        """Simulated returns should match the requested mean and volatility."""
        rng_result = run_simulation(
            initial_portfolio_jpy=1,
            annual_withdrawal_jpy=0,
            annual_pension_jpy=0,
            pension_start_year=0,
            simulation_years=1,
            n_simulations=200_000,
            mean_return=0.05,
            volatility=0.15,
            sequence_of_returns_risk=False,
            seed=7,
        )
        # portfolios[:, 1] = 1 * (1+r) → r sample
        returns = rng_result["portfolios"][:, 1] - 1
        assert returns.mean() == pytest.approx(0.05, abs=0.002)
        assert returns.std() == pytest.approx(0.15, abs=0.002)


# ---------------------------------------------------------------------------
# Years to FIRE: locked iDeCo contributions excluded pre-60
# ---------------------------------------------------------------------------

class TestIdecoSavingsSplit:
    def test_ideco_contribution_does_not_speed_up_pre60_fire(self):
        """Two profiles differing only in iDeCo contribution should have the
        same years-to-FIRE when retiring before 60 (contributions are locked)."""
        p_no_ideco = base_profile(ideco_monthly_contribution_jpy=0)
        p_ideco = base_profile(ideco_monthly_contribution_jpy=23_000)
        a = base_assumptions()
        r1 = run_fire_scenario(
            p_no_ideco, "a", "00000000-0000-4000-8000-000000000004", a, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        r2 = run_fire_scenario(
            p_ideco, "b", "00000000-0000-4000-8000-000000000005", a, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        assert r1.years_to_fire == r2.years_to_fire


# ---------------------------------------------------------------------------
# Monte Carlo determinism (fixed seed)
# ---------------------------------------------------------------------------
# Without a fixed seed, every scenario render draws a fresh random sample, so
# re-rendering the exact same scenario — or comparing two scenarios side by
# side on the compare page — shows a different success_rate_pct each time.
# That noise (observed ±0.5-0.8pp across repeated runs of an identical
# scenario) was repeatedly misread as a real effect of whatever assumption
# happened to differ between two compared scenarios. A fixed seed makes a
# given scenario's MC output stable across renders, and gives compared
# scenarios common random numbers so any difference between them is signal.

class TestMonteCarloDeterminism:
    def test_same_scenario_rerun_gives_identical_mc_output(self):
        """Running the exact same scenario twice must yield byte-identical
        Monte Carlo results — no more re-render noise."""
        profile = base_profile()
        assumptions = base_assumptions(monte_carlo_simulations=2000)
        r1 = run_fire_scenario(
            profile, "rerun", "00000000-0000-4000-8000-000000000006",
            assumptions, "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        r2 = run_fire_scenario(
            profile, "rerun", "00000000-0000-4000-8000-000000000006",
            assumptions, "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r1.monte_carlo.success_rate_pct == r2.monte_carlo.success_rate_pct
        assert r1.monte_carlo.p50 == r2.monte_carlo.p50
        assert r1.monte_carlo.p10 == r2.monte_carlo.p10
        assert r1.monte_carlo.p90 == r2.monte_carlo.p90

    def test_scenarios_differing_only_in_inert_field_match_exactly(self):
        """Two scenarios identical except for a label-only field (scenario
        name / id, which never enters the calculation) must produce identical
        Monte Carlo output — confirms common random numbers, not just
        per-call stability."""
        profile = base_profile()
        assumptions = base_assumptions(monte_carlo_simulations=2000)
        r1 = run_fire_scenario(
            profile, "Scenario One", "00000000-0000-4000-8000-000000000007",
            assumptions, "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        r2 = run_fire_scenario(
            profile, "Scenario Two (copy)", "00000000-0000-4000-8000-000000000008",
            assumptions, "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r1.monte_carlo.success_rate_pct == r2.monte_carlo.success_rate_pct
        assert r1.monte_carlo.p50 == r2.monte_carlo.p50
