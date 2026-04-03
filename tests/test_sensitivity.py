"""
Sensitivity analysis tests.

Verifies that the tornado chart data is correctly generated:
  - All expected variables are present
  - Direction of impact is correct (higher return → optimistic, etc.)
  - Items sorted by total swing (largest first)
  - Base years is consistent across all items
"""
import pytest
from models.profile import FinancialProfile
from models.scenario import AssumptionSet, SensitivityItem
from engine.sensitivity import run_sensitivity_analysis


def base_profile() -> FinancialProfile:
    return FinancialProfile(
        current_age=35,
        target_retirement_age=55,
        annual_gross_income_jpy=8_000_000,
        monthly_expenses_jpy=250_000,
        monthly_nisa_contribution_jpy=100_000,
        ideco_monthly_contribution_jpy=23_000,
        nisa_balance_jpy=5_000_000,
        ideco_balance_jpy=2_000_000,
        taxable_brokerage_jpy=3_000_000,
        cash_savings_jpy=1_000_000,
        nenkin_contribution_months=120,
        nenkin_claim_age=65,
    )


def base_assumptions() -> AssumptionSet:
    return AssumptionSet(
        investment_return_pct=5.0,
        withdrawal_rate_pct=3.5,
        japan_inflation_pct=2.0,
        monte_carlo_simulations=100,
        nhi_municipality_key="national_average",
        nhi_household_members=1,
    )


class TestRunSensitivityAnalysis:
    def test_returns_list_of_sensitivity_items(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        assert isinstance(items, list)
        assert len(items) > 0
        assert all(isinstance(i, SensitivityItem) for i in items)

    def test_expected_variables_present(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        variables = {i.variable for i in items}
        assert "investment_return" in variables
        assert "withdrawal_rate" in variables
        assert "monthly_savings" in variables
        assert "monthly_expenses" in variables

    def test_sorted_by_total_swing_descending(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        swings = [abs(i.delta_pessimistic) + abs(i.delta_optimistic) for i in items]
        assert swings == sorted(swings, reverse=True)

    def test_base_years_consistent(self):
        """All items should have the same base_years (same profile/assumptions)."""
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        base_years_set = {i.base_years for i in items}
        assert len(base_years_set) == 1

    def test_base_years_positive(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        assert items[0].base_years > 0

    def test_higher_return_optimistic_fewer_years(self):
        """Higher investment return → optimistic scenario → fewer years to FIRE."""
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        ret_item = next(i for i in items if i.variable == "investment_return")
        # Optimistic years should be less than or equal to base
        assert ret_item.optimistic_years <= ret_item.base_years

    def test_lower_return_pessimistic_more_years(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        ret_item = next(i for i in items if i.variable == "investment_return")
        assert ret_item.pessimistic_years >= ret_item.base_years

    def test_higher_expenses_pessimistic(self):
        """Higher expenses → larger FIRE number → more years."""
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        exp_item = next(i for i in items if i.variable == "monthly_expenses")
        assert exp_item.pessimistic_years >= exp_item.base_years

    def test_more_savings_optimistic(self):
        """More savings → fewer years to FIRE."""
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        sav_item = next(i for i in items if i.variable == "monthly_savings")
        assert sav_item.optimistic_years <= sav_item.base_years

    def test_delta_fields_populated(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        for item in items:
            # delta_pessimistic = pessimistic - base (positive = worse)
            assert abs(item.delta_pessimistic - (item.pessimistic_years - item.base_years)) < 0.01
            # delta_optimistic = base - optimistic (positive = better)
            assert abs(item.delta_optimistic - (item.base_years - item.optimistic_years)) < 0.01

    def test_fx_variable_only_if_foreign_assets(self):
        """USD/JPY variable should only appear when the profile has foreign assets."""
        no_fx = base_profile()
        no_fx.foreign_assets_usd = 0.0
        items_no_fx = run_sensitivity_analysis(no_fx, base_assumptions(), "national_average")
        variables_no_fx = {i.variable for i in items_no_fx}
        assert "usd_jpy" not in variables_no_fx

        with_fx = base_profile()
        with_fx.foreign_assets_usd = 100_000.0
        items_fx = run_sensitivity_analysis(with_fx, base_assumptions(), "national_average")
        variables_fx = {i.variable for i in items_fx}
        assert "usd_jpy" in variables_fx

    def test_regional_differences_in_sensitivity(self):
        """Tokyo vs rural should give different base years."""
        tokyo_items = run_sensitivity_analysis(base_profile(), base_assumptions(), "tokyo")
        rural_items = run_sensitivity_analysis(base_profile(), base_assumptions(), "rural")
        assert tokyo_items[0].base_years != rural_items[0].base_years

    def test_sensitivity_item_structure(self):
        items = run_sensitivity_analysis(base_profile(), base_assumptions(), "national_average")
        item = items[0]
        assert hasattr(item, "variable")
        assert hasattr(item, "label")
        assert hasattr(item, "base_years")
        assert hasattr(item, "pessimistic_years")
        assert hasattr(item, "optimistic_years")
        assert hasattr(item, "delta_pessimistic")
        assert hasattr(item, "delta_optimistic")
