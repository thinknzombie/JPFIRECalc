"""
FIRE calculator tests.

Tests cover the core mathematical correctness of each function,
as well as Japan-specific behaviours (pension offset, iDeCo lock,
year-1 shock, NHI inclusion in FIRE number).
"""
import math
import pytest
from models.profile import FinancialProfile
from models.scenario import AssumptionSet
from engine.fire_calculator import (
    calculate_fire_number,
    calculate_retirement_expenses,
    calculate_accessible_portfolio,
    calculate_years_to_fire,
    calculate_coast_fire_number,
    calculate_barista_fire_number,
    project_net_worth,
    run_fire_scenario,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def base_profile(**kwargs) -> FinancialProfile:
    """Standard test profile — 35yo, 8M income, targeting 50."""
    defaults = dict(
        current_age=35,
        target_retirement_age=50,
        employment_type="company_employee",
        annual_gross_income_jpy=8_000_000,
        monthly_expenses_jpy=250_000,
        monthly_nisa_contribution_jpy=100_000,
        nisa_growth_frame_annual_jpy=0,
        ideco_monthly_contribution_jpy=23_000,
        nisa_balance_jpy=5_000_000,
        ideco_balance_jpy=2_000_000,
        taxable_brokerage_jpy=3_000_000,
        cash_savings_jpy=1_000_000,
        nenkin_contribution_months=120,
        nenkin_claim_age=65,
    )
    defaults.update(kwargs)
    return FinancialProfile(**defaults)


def base_assumptions(**kwargs) -> AssumptionSet:
    defaults = dict(
        investment_return_pct=5.0,
        retirement_return_pct=4.0,
        withdrawal_rate_pct=3.5,
        monte_carlo_simulations=100,  # small for test speed
        nhi_municipality_key="national_average",
        nhi_household_members=1,
        barista_income_monthly_jpy=0,
    )
    defaults.update(kwargs)
    return AssumptionSet(**defaults)


# ---------------------------------------------------------------------------
# FIRE number
# ---------------------------------------------------------------------------

class TestCalculateFireNumber:
    def test_basic_fire_number(self):
        # 3,600,000 expenses / 0.035 = 102,857,142
        result = calculate_fire_number(3_600_000, 0.035)
        assert result["fire_number_jpy"] == int(3_600_000 / 0.035)

    def test_pension_reduces_fire_number(self):
        without = calculate_fire_number(3_600_000, 0.035)
        with_pension = calculate_fire_number(3_600_000, 0.035, net_pension_annual_jpy=1_200_000)
        assert with_pension["fire_number_jpy"] < without["fire_number_jpy"]
        # Net need = 3,600,000 - 1,200,000 = 2,400,000 → FIRE# = 2,400,000 / 0.035
        assert with_pension["fire_number_jpy"] == int(2_400_000 / 0.035)

    def test_full_pension_coverage_zero_fire_number(self):
        result = calculate_fire_number(2_000_000, 0.035, net_pension_annual_jpy=2_000_000)
        assert result["fire_number_jpy"] == 0

    def test_pension_exceeding_expenses_zero_fire_number(self):
        result = calculate_fire_number(1_500_000, 0.035, net_pension_annual_jpy=2_000_000)
        assert result["fire_number_jpy"] == 0

    def test_higher_withdrawal_rate_lower_fire_number(self):
        conservative = calculate_fire_number(3_600_000, 0.03)
        aggressive = calculate_fire_number(3_600_000, 0.04)
        assert conservative["fire_number_jpy"] > aggressive["fire_number_jpy"]

    def test_warning_above_4pct(self):
        result = calculate_fire_number(3_600_000, 0.045)
        assert result["warning_on_rate"] is not None

    def test_no_warning_at_3_5pct(self):
        result = calculate_fire_number(3_600_000, 0.035)
        assert result["warning_on_rate"] is None

    def test_invalid_rate_raises(self):
        with pytest.raises(ValueError):
            calculate_fire_number(3_600_000, 0.0)

    def test_result_structure(self):
        result = calculate_fire_number(3_600_000, 0.035)
        for key in ["fire_number_jpy", "net_annual_need_jpy", "pension_offset_jpy",
                    "withdrawal_rate_pct", "annual_expenses_jpy"]:
            assert key in result


# ---------------------------------------------------------------------------
# Retirement expenses
# ---------------------------------------------------------------------------

class TestCalculateRetirementExpenses:
    def test_region_template_used(self):
        profile = base_profile()
        result = calculate_retirement_expenses(profile, "tokyo")
        # Tokyo template = 257,000/month × 12 = 3,084,000
        assert result["annual_expenses_jpy"] == 257_000 * 12

    def test_rural_cheaper_than_tokyo(self):
        profile = base_profile()
        tokyo = calculate_retirement_expenses(profile, "tokyo")
        rural = calculate_retirement_expenses(profile, "rural")
        assert rural["annual_expenses_jpy"] < tokyo["annual_expenses_jpy"]

    def test_rental_income_reduces_expenses(self):
        profile_no_rental = base_profile(rental_income_monthly_jpy=0)
        profile_rental = base_profile(rental_income_monthly_jpy=100_000)
        no_rent = calculate_retirement_expenses(profile_no_rental, "tokyo")
        with_rent = calculate_retirement_expenses(profile_rental, "tokyo")
        assert with_rent["annual_expenses_jpy"] == no_rent["annual_expenses_jpy"] - 1_200_000

    def test_unpaid_mortgage_adds_to_expenses(self):
        no_mortgage = base_profile(
            owns_property=False,
            monthly_mortgage_payment_jpy=0,
            property_paid_off_at_retirement=False,
        )
        with_mortgage = base_profile(
            owns_property=True,
            monthly_mortgage_payment_jpy=80_000,
            property_paid_off_at_retirement=False,
        )
        base_exp = calculate_retirement_expenses(no_mortgage, "tokyo")
        mort_exp = calculate_retirement_expenses(with_mortgage, "tokyo")
        assert mort_exp["annual_expenses_jpy"] == base_exp["annual_expenses_jpy"] + 80_000 * 12

    def test_paid_off_mortgage_no_addition(self):
        profile = base_profile(
            owns_property=True,
            monthly_mortgage_payment_jpy=80_000,
            property_paid_off_at_retirement=True,
        )
        result = calculate_retirement_expenses(profile, "tokyo")
        assert result["mortgage_monthly_jpy"] == 0

    def test_expenses_never_negative(self):
        profile = base_profile(rental_income_monthly_jpy=1_000_000)
        result = calculate_retirement_expenses(profile, "rural")
        assert result["annual_expenses_jpy"] >= 0


# ---------------------------------------------------------------------------
# Accessible portfolio
# ---------------------------------------------------------------------------

class TestAccessiblePortfolio:
    def test_fire_at_60_ideco_included(self):
        profile = base_profile(
            target_retirement_age=60,
            nisa_balance_jpy=5_000_000,
            ideco_balance_jpy=3_000_000,
            taxable_brokerage_jpy=2_000_000,
            cash_savings_jpy=0,
        )
        result = calculate_accessible_portfolio(profile, fire_age=60)
        assert result["ideco_accessible"] is True
        assert result["total_accessible_jpy"] == 10_000_000

    def test_fire_before_60_ideco_excluded(self):
        profile = base_profile(
            target_retirement_age=45,
            nisa_balance_jpy=5_000_000,
            ideco_balance_jpy=3_000_000,
            taxable_brokerage_jpy=2_000_000,
            cash_savings_jpy=0,
        )
        result = calculate_accessible_portfolio(profile, fire_age=45)
        assert result["ideco_accessible"] is False
        assert result["total_accessible_jpy"] == 7_000_000  # no iDeCo

    def test_foreign_assets_converted_at_rate(self):
        profile = base_profile(
            foreign_assets_usd=10_000.0,
            usd_jpy_rate=150.0,
            nisa_balance_jpy=0,
            ideco_balance_jpy=0,
            taxable_brokerage_jpy=0,
            cash_savings_jpy=0,
        )
        result = calculate_accessible_portfolio(profile, fire_age=65)
        assert result["foreign_jpy"] == 1_500_000
        assert result["total_accessible_jpy"] == 1_500_000


# ---------------------------------------------------------------------------
# Years to FIRE
# ---------------------------------------------------------------------------

class TestYearsToFire:
    def test_already_at_fire_number(self):
        years = calculate_years_to_fire(10_000_000, 500_000, 10_000_000, 0.05)
        assert years == 0.0

    def test_above_fire_number_returns_zero(self):
        years = calculate_years_to_fire(15_000_000, 500_000, 10_000_000, 0.05)
        assert years == 0.0

    def test_zero_return_linear(self):
        # Need 5M more, saving 1M/year → 5 years
        years = calculate_years_to_fire(0, 1_000_000, 5_000_000, 0.0)
        assert years == pytest.approx(5.0)

    def test_positive_return_fewer_years(self):
        linear = calculate_years_to_fire(0, 1_000_000, 20_000_000, 0.0)
        with_return = calculate_years_to_fire(0, 1_000_000, 20_000_000, 0.05)
        assert with_return < linear

    def test_zero_savings_zero_return_inf(self):
        years = calculate_years_to_fire(5_000_000, 0, 20_000_000, 0.0)
        assert years == float("inf")

    def test_positive_portfolio_positive_return_no_savings(self):
        # Portfolio grows on its own
        years = calculate_years_to_fire(5_000_000, 0, 10_000_000, 0.05)
        assert math.isfinite(years)
        assert years > 0

    def test_higher_savings_fewer_years(self):
        low = calculate_years_to_fire(1_000_000, 500_000, 30_000_000, 0.05)
        high = calculate_years_to_fire(1_000_000, 1_500_000, 30_000_000, 0.05)
        assert high < low

    def test_higher_return_fewer_years(self):
        low_r = calculate_years_to_fire(1_000_000, 500_000, 30_000_000, 0.03)
        high_r = calculate_years_to_fire(1_000_000, 500_000, 30_000_000, 0.07)
        assert high_r < low_r


# ---------------------------------------------------------------------------
# Coast FIRE
# ---------------------------------------------------------------------------

class TestCoastFireNumber:
    def test_coast_pv_formula(self):
        # FIRE# 100M, 20yr, 5% return → 100M / 1.05^20 = 37,689,148 approx
        result = calculate_coast_fire_number(100_000_000, 20, 0.05)
        expected = int(100_000_000 / (1.05 ** 20))
        assert result["coast_fire_number_jpy"] == expected

    def test_zero_years_returns_fire_number(self):
        result = calculate_coast_fire_number(50_000_000, 0, 0.05)
        assert result["coast_fire_number_jpy"] == 50_000_000

    def test_higher_return_lower_coast_number(self):
        low = calculate_coast_fire_number(100_000_000, 20, 0.03)
        high = calculate_coast_fire_number(100_000_000, 20, 0.07)
        assert high["coast_fire_number_jpy"] < low["coast_fire_number_jpy"]

    def test_longer_horizon_lower_coast_number(self):
        short = calculate_coast_fire_number(100_000_000, 10, 0.05)
        long = calculate_coast_fire_number(100_000_000, 30, 0.05)
        assert long["coast_fire_number_jpy"] < short["coast_fire_number_jpy"]


# ---------------------------------------------------------------------------
# Barista FIRE
# ---------------------------------------------------------------------------

class TestBaristaFireNumber:
    def test_barista_lower_than_full_fire(self):
        full = calculate_barista_fire_number(3_600_000, 0.035)
        barista = calculate_barista_fire_number(
            3_600_000, 0.035, barista_income_annual_jpy=1_200_000
        )
        assert barista["barista_fire_number_jpy"] < full["full_fire_number_jpy"]

    def test_barista_income_equals_need_zero_fire_number(self):
        result = calculate_barista_fire_number(
            annual_expenses_jpy=2_000_000,
            withdrawal_rate=0.035,
            net_pension_annual_jpy=0,
            barista_income_annual_jpy=2_000_000,
        )
        assert result["barista_fire_number_jpy"] == 0

    def test_pension_plus_barista_covers_expenses(self):
        result = calculate_barista_fire_number(
            annual_expenses_jpy=3_000_000,
            withdrawal_rate=0.035,
            net_pension_annual_jpy=1_500_000,
            barista_income_annual_jpy=1_500_000,
        )
        assert result["barista_fire_number_jpy"] == 0

    def test_taxable_income_warning_above_threshold(self):
        result = calculate_barista_fire_number(
            3_600_000, 0.035, barista_income_annual_jpy=1_500_000
        )
        assert result["taxable_income_warning"] is not None

    def test_no_warning_below_threshold(self):
        result = calculate_barista_fire_number(
            3_600_000, 0.035, barista_income_annual_jpy=1_000_000
        )
        assert result["taxable_income_warning"] is None

    def test_portfolio_reduction_pct_calculated(self):
        result = calculate_barista_fire_number(
            3_600_000, 0.035, barista_income_annual_jpy=1_200_000
        )
        assert 0 < result["portfolio_reduction_pct"] <= 100


# ---------------------------------------------------------------------------
# Net worth projection
# ---------------------------------------------------------------------------

class TestProjectNetWorth:
    def test_projection_length(self):
        profile = base_profile()
        assumptions = base_assumptions()
        trajectory = project_net_worth(profile, assumptions, "tokyo", projection_years=30)
        assert len(trajectory) == 30

    def test_accumulation_phase_portfolio_grows(self):
        profile = base_profile(current_age=35, target_retirement_age=55)
        assumptions = base_assumptions()
        trajectory = project_net_worth(profile, assumptions, "national_average", projection_years=20)
        accum = [y for y in trajectory if y.phase == "accumulation"]
        assert len(accum) > 0
        # Portfolio should generally grow during accumulation
        assert accum[-1].portfolio_value_jpy > accum[0].portfolio_value_jpy

    def test_retirement_phase_present(self):
        profile = base_profile(current_age=48, target_retirement_age=50)
        assumptions = base_assumptions()
        trajectory = project_net_worth(profile, assumptions, "national_average", projection_years=10)
        retire = [y for y in trajectory if y.phase == "retirement"]
        assert len(retire) > 0

    def test_phases_are_correct(self):
        profile = base_profile(current_age=35, target_retirement_age=50)
        assumptions = base_assumptions()
        trajectory = project_net_worth(profile, assumptions, "national_average", projection_years=30)
        for yr in trajectory:
            expected_phase = "retirement" if yr.age >= 50 else "accumulation"
            assert yr.phase == expected_phase

    def test_year1_retirement_shock_applied(self):
        profile = base_profile(current_age=49, target_retirement_age=50)
        assumptions = base_assumptions()
        trajectory = project_net_worth(profile, assumptions, "national_average", projection_years=5)
        retire_years = [y for y in trajectory if y.phase == "retirement"]
        assert retire_years[0].year1_residence_tax_jpy > 0
        # Subsequent years should not have the shock
        if len(retire_years) > 1:
            assert retire_years[1].year1_residence_tax_jpy == 0

    def test_portfolio_never_negative(self):
        profile = base_profile(
            nisa_balance_jpy=100_000,
            ideco_balance_jpy=0,
            taxable_brokerage_jpy=0,
            cash_savings_jpy=0,
        )
        assumptions = base_assumptions(withdrawal_rate_pct=10.0)  # unsustainable
        trajectory = project_net_worth(profile, assumptions, "national_average", projection_years=30)
        for yr in trajectory:
            assert yr.portfolio_value_jpy >= 0

    def test_ages_sequential(self):
        profile = base_profile()
        trajectory = project_net_worth(profile, base_assumptions(), "national_average", 20)
        ages = [y.age for y in trajectory]
        assert ages == list(range(profile.current_age, profile.current_age + 20))


# ---------------------------------------------------------------------------
# Full scenario run
# ---------------------------------------------------------------------------

class TestRunFireScenario:
    def test_returns_scenario_result(self):
        from models.scenario import ScenarioResult
        profile = base_profile()
        assumptions = base_assumptions()
        result = run_fire_scenario(profile, "Test", "test-id", assumptions, "national_average")
        assert isinstance(result, ScenarioResult)

    def test_fire_number_positive(self):
        profile = base_profile()
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert result.fire_number_jpy > 0

    def test_progress_pct_between_0_and_100(self):
        profile = base_profile()
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert 0 <= result.progress_pct <= 100

    def test_ideco_warning_when_fire_before_60(self):
        profile = base_profile(target_retirement_age=45)
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert any("iDeCo" in w for w in result.warnings)
        assert result.ideco_accessible_at_fire is False

    def test_no_ideco_warning_at_60(self):
        profile = base_profile(target_retirement_age=60)
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert result.ideco_accessible_at_fire is True
        assert not any("locked" in w.lower() for w in result.warnings)

    def test_high_withdrawal_rate_warning(self):
        profile = base_profile()
        assumptions = base_assumptions(withdrawal_rate_pct=5.0)
        result = run_fire_scenario(profile, "Test", "test-id", assumptions, "national_average")
        assert any("4%" in w or "4.0%" in w or "withdrawal" in w.lower() for w in result.warnings)

    def test_trajectory_populated(self):
        profile = base_profile()
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert len(result.trajectory) == 50

    def test_nisa_ideco_at_retirement_positive(self):
        profile = base_profile()
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert result.nisa_at_retirement_jpy > 0
        assert result.ideco_at_retirement_jpy > 0

    def test_coast_fire_check(self):
        # A profile with a large existing portfolio should have coast FIRE reached
        wealthy = base_profile(
            nisa_balance_jpy=50_000_000,
            taxable_brokerage_jpy=20_000_000,
        )
        result = run_fire_scenario(wealthy, "Test", "test-id", base_assumptions(), "national_average")
        assert result.coast_fire_reached is True

    def test_year1_shock_positive(self):
        profile = base_profile()
        result = run_fire_scenario(profile, "Test", "test-id", base_assumptions(), "national_average")
        assert result.year1_residence_tax_shock_jpy > 0

    def test_regional_difference_affects_fire_number(self):
        profile = base_profile()
        assumptions = base_assumptions()
        tokyo = run_fire_scenario(profile, "Tokyo", "t", assumptions, "tokyo")
        rural = run_fire_scenario(profile, "Rural", "r", assumptions, "rural")
        assert rural.fire_number_jpy < tokyo.fire_number_jpy

    def test_pension_reduces_fire_number(self):
        no_pension = base_profile(nenkin_contribution_months=0)
        with_pension = base_profile(nenkin_contribution_months=480)
        assumptions = base_assumptions()
        r_no = run_fire_scenario(no_pension, "NP", "np", assumptions, "national_average")
        r_with = run_fire_scenario(with_pension, "WP", "wp", assumptions, "national_average")
        assert r_with.fire_number_jpy < r_no.fire_number_jpy
