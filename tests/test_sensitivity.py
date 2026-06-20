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


# ---------------------------------------------------------------------------
# Mortgage rate sensitivity — one row per loan in profile.mortgages
# ---------------------------------------------------------------------------

class TestMortgageRateSensitivity:
    """When profile.mortgages has multiple loans, sensitivity emits one row per loan."""

    def _andrew_like_profile(self) -> FinancialProfile:
        """3-loan profile (柿ノ木坂 split + Crozier foreign) at FIRE."""
        return FinancialProfile.from_dict({
            "current_age": 52,
            "target_retirement_age": 53,
            "monthly_expenses_jpy": 570_000,
            "monthly_nisa_contribution_jpy": 100_000,
            "ideco_monthly_contribution_jpy": 23_000,
            "nisa_balance_jpy": 20_686_781,
            "ideco_balance_jpy": 17_644_665,
            "taxable_brokerage_jpy": 60_150_992,
            "cash_savings_jpy": 65_440_929,
            "foreign_assets_usd": 1_442_701.0,
            "usd_jpy_rate": 161.30,
            "owns_property": True,
            "property_value_jpy": 120_000_000,
            "property_paid_off_at_retirement": False,
            "owns_foreign_property": True,
            "foreign_property_value_jpy": 100_000_000,
            "foreign_property_rental_monthly_jpy": 315_789,
            "rent_income": 0,
            "mortgages": [
                {"label": "land", "balance_jpy": 70_309_716, "interest_rate_pct": 0.47, "monthly_payment_jpy": 256_174, "remaining_years": 28, "is_foreign": False},
                {"label": "building", "balance_jpy": 23_200_519, "interest_rate_pct": 0.67, "monthly_payment_jpy": 99_905, "remaining_years": 24, "is_foreign": False},
                {"label": "crozier", "balance_jpy": 25_811_695, "interest_rate_pct": 5.5, "monthly_payment_jpy": 130_000, "remaining_years": 22, "is_foreign": True},
            ],
        })

    def test_emits_one_row_per_loan(self):
        items = run_sensitivity_analysis(
            self._andrew_like_profile(),
            base_assumptions(),
            "tokyo_shinjuku",
        )
        mortgage_items = [i for i in items if i.variable.startswith("mortgage_rate_")]
        assert len(mortgage_items) == 3
        labels = {i.label for i in mortgage_items}
        assert any("land" in l for l in labels)
        assert any("building" in l for l in labels)
        assert any("crozier" in l for l in labels)

    def test_per_loan_delta_is_nonzero(self):
        """Each mortgage row should show a real sensitivity delta (not 0)."""
        items = run_sensitivity_analysis(
            self._andrew_like_profile(),
            base_assumptions(),
            "tokyo_shinjuku",
        )
        for item in items:
            if item.variable.startswith("mortgage_rate_"):
                # At least one of pess or opt should be nonzero for a real
                # perturbation to flow through
                assert item.delta_pessimistic != 0 or item.delta_optimistic != 0, (
                    f"{item.label}: zero sensitivity — perturbation isn't "
                    f"flowing through the engine"
                )

    def test_larger_loan_higher_impact(self):
        """Bigger balance → bigger surplus swing (loosely)."""
        items = run_sensitivity_analysis(
            self._andrew_like_profile(),
            base_assumptions(),
            "tokyo_shinjuku",
        )
        by_loan = {i.label: i for i in items if i.variable.startswith("mortgage_rate_")}
        land = next(i for i in items if "land" in i.label and i.variable.startswith("mortgage_rate_"))
        building = next(i for i in items if "building" in i.label and i.variable.startswith("mortgage_rate_"))
        crozier = next(i for i in items if "crozier" in i.label and i.variable.startswith("mortgage_rate_"))
        # Land (¥70M) is bigger than building (¥23M) — should have larger absolute swing
        land_swing = abs(land.delta_pessimistic) + abs(land.delta_optimistic)
        building_swing = abs(building.delta_pessimistic) + abs(building.delta_optimistic)
        assert land_swing > building_swing, (
            f"Land swing {land_swing:.2f} should exceed building swing {building_swing:.2f}"
        )

    def test_legacy_single_loan_still_works(self):
        """Old profiles without `mortgages` list — sensitivity still emits a row.

        The legacy path skips the row if the actual payment differs >5% from
        a fresh single-rate amortisation (proxy for detecting split-rate
        scenarios that should have used the new list format). We use a
        payment that matches the helper's output to exercise the happy path.
        """
        # _monthly_payment(50M, 1.5%, 20y) ≈ ¥239,782
        p = FinancialProfile(
            current_age=40,
            target_retirement_age=55,
            mortgage_balance_jpy=50_000_000,
            monthly_mortgage_payment_jpy=239_782,
            mortgage_interest_rate_pct=1.5,
            mortgage_remaining_years=20,
        )
        items = run_sensitivity_analysis(p, base_assumptions(), "national_average")
        mortgage_items = [i for i in items if i.variable == "mortgage_rate"]
        assert len(mortgage_items) == 1
        assert "1.50%" in mortgage_items[0].label

    def test_legacy_split_payment_skipped(self):
        """When legacy payment doesn't match single-rate amortisation (e.g.
        split-rate scenario), the legacy path skips the row. Use the new
        list format instead — that's the documented path."""
        p = FinancialProfile(
            current_age=40,
            target_retirement_age=55,
            mortgage_balance_jpy=50_000_000,
            monthly_mortgage_payment_jpy=200_000,   # doesn't match fresh loan at 1.5%
            mortgage_interest_rate_pct=1.5,
            mortgage_remaining_years=20,
        )
        items = run_sensitivity_analysis(p, base_assumptions(), "national_average")
        mortgage_items = [i for i in items if i.variable == "mortgage_rate"]
        assert len(mortgage_items) == 0  # legacy path correctly skips
