"""Tests for engine/mortgage_analysis.py."""
import pytest
import numpy as np
from models.profile import FinancialProfile
from models.scenario import AssumptionSet
from engine.mortgage_analysis import (
    calculate_breakeven_mortgage_rate,
    calculate_payoff_vs_invest_npv,
    run_mortgage_rate_scenarios,
    generate_rate_paths,
    _monthly_payment,
    _annual_loan_tax_credit_jpy,
    _after_tax_return,
)


# ---------------------------------------------------------------------------
# Helper formula tests
# ---------------------------------------------------------------------------

def test_monthly_payment_zero_rate():
    pmt = _monthly_payment(10_000_000, 0.0, 20)
    expected = 10_000_000 // (20 * 12)
    assert pmt == expected


def test_monthly_payment_nonzero_rate():
    # ¥50M, 0.7%, 25 years — should be roughly ¥195k–¥200k
    pmt = _monthly_payment(50_000_000, 0.7, 25)
    assert 180_000 < pmt < 220_000


def test_monthly_payment_zero_years():
    pmt = _monthly_payment(5_000_000, 1.0, 0)
    assert pmt == 5_000_000  # due immediately


def test_annual_tax_credit_capped():
    credit = _annual_loan_tax_credit_jpy(50_000_000, 0.007, 30_000_000)
    assert credit == int(30_000_000 * 0.007)


def test_annual_tax_credit_below_cap():
    credit = _annual_loan_tax_credit_jpy(10_000_000, 0.007, 30_000_000)
    assert credit == int(10_000_000 * 0.007)


def test_after_tax_return_nisa():
    gross = 0.06
    assert _after_tax_return(gross, "nisa") == gross


def test_after_tax_return_taxable():
    gross = 0.06
    assert abs(_after_tax_return(gross, "taxable") - gross * (1 - 0.20315)) < 1e-9


def test_after_tax_return_mixed():
    gross = 0.06
    expected = 0.8 * gross * (1 - 0.20315) + 0.2 * gross
    assert abs(_after_tax_return(gross, "mixed") - expected) < 1e-9


# ---------------------------------------------------------------------------
# Break-even rate tests
# ---------------------------------------------------------------------------

def _make_profile(**kwargs):
    defaults = dict(
        current_age=40,
        target_retirement_age=55,
        mortgage_balance_jpy=50_000_000,
        monthly_mortgage_payment_jpy=200_000,
        mortgage_interest_rate_pct=0.7,
        mortgage_remaining_years=25,
        mortgage_tax_credit_remaining_years=0,
        mortgage_tax_credit_principal_cap_jpy=30_000_000,
        mortgage_tax_credit_rate_pct=0.7,
    )
    defaults.update(kwargs)
    return FinancialProfile(**defaults)


def _make_assumptions(**kwargs):
    defaults = dict(investment_return_pct=6.0, retirement_return_pct=4.5)
    defaults.update(kwargs)
    return AssumptionSet(**defaults)


def test_breakeven_investing_wins_low_mortgage():
    """0.7% mortgage + 6% taxable return → break-even ~5.5%, investing wins."""
    p = _make_profile(mortgage_interest_rate_pct=0.7)
    a = _make_assumptions(investment_return_pct=6.0)
    result = calculate_breakeven_mortgage_rate(p, a, "taxable")
    assert result["investing_wins"] is True
    # break-even ≈ 6.0% * (1 - 0.20315) ≈ 4.78%
    assert 4.0 < result["break_even_rate_pct"] < 6.0
    assert result["delta_pct"] < 0  # effective cost < break-even → investing wins


def test_breakeven_payoff_wins_high_mortgage():
    """5% mortgage + 4% NISA → payoff wins."""
    p = _make_profile(mortgage_interest_rate_pct=5.0)
    a = _make_assumptions(investment_return_pct=4.0)
    result = calculate_breakeven_mortgage_rate(p, a, "nisa")
    assert result["investing_wins"] is False
    assert result["delta_pct"] > 0


def test_breakeven_nisa_no_tax():
    """NISA: break-even = full gross return (no tax)."""
    p = _make_profile(mortgage_interest_rate_pct=0.7)
    a = _make_assumptions(investment_return_pct=4.0)
    result = calculate_breakeven_mortgage_rate(p, a, "nisa")
    # break-even ≈ 4.0% (NISA return, no tax)
    assert abs(result["break_even_rate_pct"] - 4.0) < 0.1
    assert result["investing_wins"] is True


def test_breakeven_tax_credit_lowers_effective_cost():
    """With active tax credit, effective cost < nominal rate."""
    p = _make_profile(
        mortgage_interest_rate_pct=1.0,
        mortgage_tax_credit_remaining_years=5,
        mortgage_tax_credit_rate_pct=0.7,
        mortgage_tax_credit_principal_cap_jpy=30_000_000,
    )
    a = _make_assumptions(investment_return_pct=3.0)
    result = calculate_breakeven_mortgage_rate(p, a, "taxable")
    # Effective cost should be less than 1.0% due to the tax credit
    assert result["effective_mortgage_cost_pct"] < result["current_mortgage_rate_pct"]
    assert result["annual_tax_credit_jpy"] > 0


def test_breakeven_zero_balance_no_crash():
    """No mortgage → should still return a result without crashing."""
    p = _make_profile(mortgage_balance_jpy=0)
    a = _make_assumptions()
    result = calculate_breakeven_mortgage_rate(p, a, "taxable")
    assert "break_even_rate_pct" in result


# ---------------------------------------------------------------------------
# Payoff-vs-invest tests
# ---------------------------------------------------------------------------

def test_payoff_vs_invest_low_rate_invest_wins():
    """At 0.7% mortgage and 5% return, investing should win over 30 years."""
    p = _make_profile(
        mortgage_balance_jpy=50_000_000,
        mortgage_interest_rate_pct=0.7,
        mortgage_remaining_years=25,
        cash_savings_jpy=20_000_000,
        taxable_brokerage_jpy=100_000_000,
    )
    a = _make_assumptions(investment_return_pct=5.0)
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=10_000_000, horizon_years=30)
    assert result["path_b_terminal_jpy"] > result["path_a_terminal_jpy"]
    assert result["recommendation"] in ("invest", "neutral")


def test_payoff_vs_invest_high_rate_payoff_wins():
    """At 4% mortgage and 4% gross taxable (3.19% after tax), paying off is comparable or wins."""
    p = _make_profile(
        mortgage_balance_jpy=50_000_000,
        mortgage_interest_rate_pct=4.0,
        mortgage_remaining_years=25,
        cash_savings_jpy=20_000_000,
        taxable_brokerage_jpy=100_000_000,
    )
    a = _make_assumptions(investment_return_pct=4.0)
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=10_000_000, horizon_years=30)
    # Within 10% of each other or payoff wins
    ratio = abs(result["advantage_jpy"]) / max(abs(result["path_a_terminal_jpy"]), 1)
    assert ratio < 0.15 or result["recommendation"] == "payoff"


def test_payoff_vs_invest_lump_capped_at_balance():
    """Lump sum > balance should be capped — no negative mortgage balance."""
    p = _make_profile(
        mortgage_balance_jpy=5_000_000,
        mortgage_remaining_years=5,
        cash_savings_jpy=20_000_000,
        taxable_brokerage_jpy=50_000_000,
    )
    a = _make_assumptions()
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=20_000_000, horizon_years=10)
    # Path A should never have a negative mortgage balance
    for row in result["trajectory_a"]:
        assert row["mortgage_balance_jpy"] >= 0


def test_payoff_vs_invest_payoff_year_past_term():
    """If payoff_year > mortgage_remaining_years, Path A is a no-op (loan already done)."""
    p = _make_profile(
        mortgage_balance_jpy=10_000_000,
        mortgage_remaining_years=5,
        cash_savings_jpy=20_000_000,
        taxable_brokerage_jpy=50_000_000,
    )
    a = _make_assumptions()
    # payoff_year=10 is past the 5-year remaining term
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=5_000_000, payoff_year=10, horizon_years=15)
    # Should not crash
    assert "path_a_terminal_jpy" in result


def test_payoff_vs_invest_returns_expected_keys():
    p = _make_profile(cash_savings_jpy=20_000_000, taxable_brokerage_jpy=100_000_000)
    a = _make_assumptions()
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=10_000_000)
    expected_keys = {
        "path_a_terminal_jpy", "path_b_terminal_jpy", "advantage_jpy", "advantage_pct",
        "recommendation", "trajectory_a", "trajectory_b", "lost_tax_credit_jpy",
    }
    assert expected_keys.issubset(result.keys())


def test_payoff_vs_invest_zero_rate_zero_return_neutral():
    """With no interest, no returns, and no tax credit, payoff vs invest should conserve net worth."""
    p = _make_profile(
        mortgage_balance_jpy=10_000_000,
        mortgage_interest_rate_pct=0.0,
        mortgage_remaining_years=10,
        cash_savings_jpy=10_000_000,
        taxable_brokerage_jpy=0,
        property_value_jpy=10_000_000,
    )
    a = _make_assumptions(investment_return_pct=0.0)
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=10_000_000, horizon_years=10)
    assert abs(result["advantage_jpy"]) < 10_000
    assert result["recommendation"] == "neutral"


def test_payoff_vs_invest_fee_larger_than_lump_does_not_increase_balance():
    p = _make_profile(
        mortgage_balance_jpy=10_000_000,
        mortgage_interest_rate_pct=1.0,
        mortgage_remaining_years=10,
        cash_savings_jpy=1_000_000,
        mortgage_prepayment_fee_jpy=2_000_000,
    )
    a = _make_assumptions(investment_return_pct=0.0)
    result = calculate_payoff_vs_invest_npv(p, a, lump_sum_jpy=1_000_000, horizon_years=1)
    assert result["trajectory_a"][0]["mortgage_balance_jpy"] <= p.mortgage_balance_jpy


# ---------------------------------------------------------------------------
# Rate scenarios tests
# ---------------------------------------------------------------------------

def test_rate_scenarios_returns_one_row_per_rate():
    p = _make_profile(cash_savings_jpy=20_000_000, taxable_brokerage_jpy=200_000_000)
    a = _make_assumptions()
    rates = [0.5, 1.0, 2.0]
    rows = run_mortgage_rate_scenarios(p, a, "tokyo", rates_pct=rates, mc_simulations_override=100)
    assert len(rows) == len(rates)
    for row, rate in zip(rows, rates):
        assert row["mortgage_rate_pct"] == rate


def test_rate_scenarios_payment_increases_with_rate():
    p = _make_profile(cash_savings_jpy=20_000_000, taxable_brokerage_jpy=200_000_000)
    a = _make_assumptions()
    rows = run_mortgage_rate_scenarios(p, a, "tokyo", rates_pct=[0.5, 2.0, 4.0], mc_simulations_override=100)
    payments = [r["monthly_payment_jpy"] for r in rows]
    assert payments[0] < payments[1] < payments[2]


def test_rate_scenarios_no_mortgage_returns_empty():
    p = _make_profile(mortgage_balance_jpy=0)
    a = _make_assumptions()
    rows = run_mortgage_rate_scenarios(p, a, "tokyo")
    assert rows == []


# ---------------------------------------------------------------------------
# Vasicek rate path tests
# ---------------------------------------------------------------------------

def test_generate_rate_paths_shape():
    paths = generate_rate_paths(
        initial_rate_pct=0.7,
        long_term_mean_pct=2.0,
        mean_reversion_speed=0.15,
        volatility_pct=0.3,
        n_simulations=100,
        n_years=30,
        seed=42,
    )
    assert paths.shape == (100, 30)
    assert np.all(paths[:, 0] == 0.7)


def test_generate_rate_paths_floor_cap():
    paths = generate_rate_paths(
        initial_rate_pct=0.7,
        long_term_mean_pct=2.0,
        mean_reversion_speed=0.15,
        volatility_pct=2.0,  # high volatility to stress the floor/cap
        n_simulations=500,
        n_years=40,
        seed=99,
        floor_pct=0.0,
        cap_pct=10.0,
    )
    assert paths.min() >= 0.0
    assert paths.max() <= 10.0


def test_generate_rate_paths_mean_reversion():
    """Long-run mean of paths should converge toward long_term_mean_pct."""
    paths = generate_rate_paths(
        initial_rate_pct=0.1,
        long_term_mean_pct=3.0,
        mean_reversion_speed=0.5,
        volatility_pct=0.1,
        n_simulations=2000,
        n_years=50,
        seed=7,
    )
    terminal_mean = paths[:, -1].mean()
    assert abs(terminal_mean - 3.0) < 0.5


def test_generate_rate_paths_reproducibility():
    paths1 = generate_rate_paths(0.7, 2.0, 0.15, 0.3, 100, 20, seed=42)
    paths2 = generate_rate_paths(0.7, 2.0, 0.15, 0.3, 100, 20, seed=42)
    np.testing.assert_array_equal(paths1, paths2)


def test_generate_rate_paths_different_seeds():
    paths1 = generate_rate_paths(0.7, 2.0, 0.15, 0.3, 100, 20, seed=1)
    paths2 = generate_rate_paths(0.7, 2.0, 0.15, 0.3, 100, 20, seed=2)
    assert not np.array_equal(paths1, paths2)
