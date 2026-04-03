"""
NISA calculator tests (新NISA structure from 2024).

Key constants:
  - Tsumitate annual max:   1,200,000 yen
  - Growth annual max:      2,400,000 yen
  - Combined annual max:    3,600,000 yen
  - Lifetime cap:          18,000,000 yen (acquisition cost basis)
  - Tax avoided:           20.315% on gains and dividends
"""
import pytest
from engine.nisa_calculator import (
    TSUMITATE_ANNUAL_MAX,
    GROWTH_ANNUAL_MAX,
    COMBINED_ANNUAL_MAX,
    LIFETIME_CAP,
    validate_nisa_contribution,
    calculate_nisa_growth,
    calculate_nisa_tax_saving,
    years_to_fill_lifetime_cap,
    calculate_cap_restoration,
    calculate_tax_advantaged_summary,
)


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------

class TestConstants:
    def test_tsumitate_annual_max(self):
        assert TSUMITATE_ANNUAL_MAX == 1_200_000

    def test_growth_annual_max(self):
        assert GROWTH_ANNUAL_MAX == 2_400_000

    def test_combined_is_sum(self):
        assert COMBINED_ANNUAL_MAX == 3_600_000

    def test_lifetime_cap(self):
        assert LIFETIME_CAP == 18_000_000


# ---------------------------------------------------------------------------
# Contribution validation
# ---------------------------------------------------------------------------

class TestValidateNisaContribution:
    def test_within_limits_valid(self):
        result = validate_nisa_contribution(1_200_000, 2_400_000)
        assert result["is_valid"] is True
        assert result["issues"] == []

    def test_tsumitate_over_limit_flagged(self):
        result = validate_nisa_contribution(1_500_000, 0)
        assert result["is_valid"] is False
        assert any("Tsumitate" in i for i in result["issues"])
        assert result["effective_tsumitate_jpy"] == TSUMITATE_ANNUAL_MAX

    def test_growth_over_limit_flagged(self):
        result = validate_nisa_contribution(0, 3_000_000)
        assert result["is_valid"] is False
        assert any("Growth" in i for i in result["issues"])
        assert result["effective_growth_jpy"] == GROWTH_ANNUAL_MAX

    def test_lifetime_cap_enforcement(self):
        # With only 500,000 cap remaining, contributions are scaled down
        result = validate_nisa_contribution(
            1_200_000, 2_400_000, lifetime_used_jpy=17_500_000
        )
        assert result["effective_combined_jpy"] <= 500_000

    def test_cap_fully_used_zero_contribution(self):
        result = validate_nisa_contribution(1_200_000, 2_400_000, lifetime_used_jpy=18_000_000)
        assert result["effective_combined_jpy"] == 0
        assert result["remaining_lifetime_cap_jpy"] == 0

    def test_remaining_cap_calculated(self):
        result = validate_nisa_contribution(1_000_000, 0, lifetime_used_jpy=5_000_000)
        assert result["remaining_lifetime_cap_jpy"] == 13_000_000


# ---------------------------------------------------------------------------
# Growth projection
# ---------------------------------------------------------------------------

class TestCalculateNisaGrowth:
    def test_zero_return_linear_growth(self):
        result = calculate_nisa_growth(
            years=5,
            annual_return_rate=0.0,
            annual_growth_frame_jpy=2_400_000,
        )
        # 5 years × 2,400,000 = 12,000,000
        assert result["total_contributions_jpy"] == 12_000_000
        assert result["investment_gain_jpy"] == 0

    def test_positive_return_grows_faster(self):
        zero = calculate_nisa_growth(10, 0.0, annual_growth_frame_jpy=1_000_000)
        five = calculate_nisa_growth(10, 0.05, annual_growth_frame_jpy=1_000_000)
        assert five["final_balance_jpy"] > zero["final_balance_jpy"]

    def test_lifetime_cap_limits_total_contributions(self):
        # Max out at 3.6M/yr — cap should be exhausted after 5 years (18M / 3.6M)
        result = calculate_nisa_growth(
            years=10,
            annual_return_rate=0.0,
            monthly_tsumitate_jpy=100_000,
            annual_growth_frame_jpy=2_400_000,
        )
        assert result["cap_fully_exhausted"] is True
        assert result["total_contributions_jpy"] == LIFETIME_CAP

    def test_cap_exhausted_year_tracked(self):
        result = calculate_nisa_growth(
            years=10,
            annual_return_rate=0.0,
            monthly_tsumitate_jpy=100_000,
            annual_growth_frame_jpy=2_400_000,
        )
        # Full annual = 1,200,000 + 2,400,000 = 3,600,000
        # 18,000,000 / 3,600,000 = 5 years
        assert result["cap_exhausted_year"] == 5

    def test_cap_not_exhausted_below_limit(self):
        result = calculate_nisa_growth(
            years=5,
            annual_return_rate=0.05,
            monthly_tsumitate_jpy=50_000,  # 600,000/yr — well under limit
        )
        assert result["cap_fully_exhausted"] is False
        assert result["cap_exhausted_year"] is None

    def test_existing_balance_included(self):
        without = calculate_nisa_growth(10, 0.05, annual_growth_frame_jpy=1_000_000)
        with_bal = calculate_nisa_growth(10, 0.05, annual_growth_frame_jpy=1_000_000, existing_balance_jpy=2_000_000)
        assert with_bal["final_balance_jpy"] > without["final_balance_jpy"] + 2_000_000

    def test_year_by_year_length(self):
        result = calculate_nisa_growth(15, 0.05, monthly_tsumitate_jpy=100_000)
        assert len(result["year_by_year"]) == 15

    def test_cap_used_never_exceeds_18m(self):
        result = calculate_nisa_growth(20, 0.05, monthly_tsumitate_jpy=100_000, annual_growth_frame_jpy=2_400_000)
        for yr in result["year_by_year"]:
            assert yr["cap_used_jpy"] <= LIFETIME_CAP

    def test_tsumitate_capped_at_1200000_annually(self):
        # 200,000/month would be 2,400,000/yr — capped at 1,200,000
        result = calculate_nisa_growth(
            years=1,
            annual_return_rate=0.0,
            monthly_tsumitate_jpy=200_000,
        )
        assert result["total_contributions_jpy"] == TSUMITATE_ANNUAL_MAX

    def test_remaining_cap_decreases_each_year(self):
        result = calculate_nisa_growth(5, 0.0, annual_growth_frame_jpy=1_000_000)
        caps = [yr["remaining_cap_jpy"] for yr in result["year_by_year"]]
        assert caps == sorted(caps, reverse=True)


# ---------------------------------------------------------------------------
# Tax saving
# ---------------------------------------------------------------------------

class TestNisaTaxSaving:
    def test_capital_gains_tax_rate_avoided(self):
        result = calculate_nisa_tax_saving(projected_gain_jpy=1_000_000)
        assert result["capital_gains_tax_saved_jpy"] == int(1_000_000 * 0.20315)

    def test_zero_gain_zero_tax_saved(self):
        result = calculate_nisa_tax_saving(0)
        assert result["capital_gains_tax_saved_jpy"] == 0

    def test_dividend_tax_also_saved(self):
        result = calculate_nisa_tax_saving(
            projected_gain_jpy=1_000_000,
            annual_dividend_income_jpy=50_000,
        )
        assert result["annual_dividend_tax_saved_jpy"] == int(50_000 * 0.20315)

    def test_larger_gain_more_tax_saved(self):
        small = calculate_nisa_tax_saving(500_000)
        large = calculate_nisa_tax_saving(5_000_000)
        assert large["capital_gains_tax_saved_jpy"] > small["capital_gains_tax_saved_jpy"]

    def test_tax_rate_avoided_is_20315(self):
        result = calculate_nisa_tax_saving(1_000_000)
        assert result["tax_rate_avoided_pct"] == pytest.approx(20.315)


# ---------------------------------------------------------------------------
# Years to fill cap
# ---------------------------------------------------------------------------

class TestYearsToFillLifetimeCap:
    def test_max_contributions_fill_in_5_years(self):
        # 3,600,000/year → 18,000,000 / 3,600,000 = 5 years
        result = years_to_fill_lifetime_cap(
            monthly_tsumitate_jpy=100_000,
            annual_growth_frame_jpy=2_400_000,
        )
        assert result["years_to_fill"] == 5

    def test_tsumitate_only_takes_15_years(self):
        # 1,200,000/year → 18M / 1.2M = 15 years
        result = years_to_fill_lifetime_cap(monthly_tsumitate_jpy=100_000)
        assert result["years_to_fill"] == 15

    def test_partial_cap_used_reduces_years(self):
        full = years_to_fill_lifetime_cap(monthly_tsumitate_jpy=100_000)
        partial = years_to_fill_lifetime_cap(
            monthly_tsumitate_jpy=100_000,
            lifetime_cap_used_jpy=6_000_000,
        )
        assert partial["years_to_fill"] < full["years_to_fill"]

    def test_no_contributions_returns_none(self):
        result = years_to_fill_lifetime_cap(monthly_tsumitate_jpy=0)
        assert result["years_to_fill"] is None

    def test_over_limit_tsumitate_capped(self):
        # 200,000/month would be 2.4M/yr — capped at 1.2M/yr → 15 years
        result = years_to_fill_lifetime_cap(monthly_tsumitate_jpy=200_000)
        assert result["years_to_fill"] == 15


# ---------------------------------------------------------------------------
# Cap restoration
# ---------------------------------------------------------------------------

class TestCapRestoration:
    def test_restoration_equals_acquisition_cost(self):
        result = calculate_cap_restoration(
            acquisition_cost_sold_jpy=1_000_000,
            market_value_sold_jpy=1_500_000,
        )
        assert result["cap_restored_jpy"] == 1_000_000

    def test_gain_not_restored(self):
        result = calculate_cap_restoration(1_000_000, 1_500_000)
        assert result["gain_not_restorable_jpy"] == 500_000
        assert result["capital_gain_jpy"] == 500_000

    def test_no_gain_full_restoration(self):
        result = calculate_cap_restoration(1_000_000, 1_000_000)
        assert result["cap_restored_jpy"] == 1_000_000
        assert result["gain_not_restorable_jpy"] == 0

    def test_can_recontribute_next_year(self):
        result = calculate_cap_restoration(1_000_000, 1_500_000)
        assert result["can_recontribute_next_year"] is True


# ---------------------------------------------------------------------------
# Combined iDeCo + NISA summary
# ---------------------------------------------------------------------------

class TestTaxAdvantagedSummary:
    def test_fire_before_60_ideco_locked(self):
        result = calculate_tax_advantaged_summary(
            nisa_balance_jpy=5_000_000,
            ideco_balance_jpy=3_000_000,
            nisa_annual_contribution_jpy=1_200_000,
            ideco_monthly_contribution_jpy=23_000,
            years_to_retirement=10,
            annual_return_rate=0.05,
            fire_age=50,
        )
        assert result["ideco_accessible_at_fire"] is False
        assert result["locked_ideco_jpy"] > 0
        assert result["warning"] is not None
        assert result["accessible_total_jpy"] == result["nisa_at_retirement_jpy"]

    def test_fire_at_60_ideco_accessible(self):
        result = calculate_tax_advantaged_summary(
            nisa_balance_jpy=5_000_000,
            ideco_balance_jpy=3_000_000,
            nisa_annual_contribution_jpy=1_200_000,
            ideco_monthly_contribution_jpy=23_000,
            years_to_retirement=10,
            annual_return_rate=0.05,
            fire_age=60,
        )
        assert result["ideco_accessible_at_fire"] is True
        assert result["locked_ideco_jpy"] == 0
        assert result["warning"] is None
        assert result["accessible_total_jpy"] == (
            result["nisa_at_retirement_jpy"] + result["ideco_at_retirement_jpy"]
        )

    def test_totals_positive(self):
        result = calculate_tax_advantaged_summary(
            nisa_balance_jpy=2_000_000,
            ideco_balance_jpy=1_000_000,
            nisa_annual_contribution_jpy=1_200_000,
            ideco_monthly_contribution_jpy=20_000,
            years_to_retirement=20,
            annual_return_rate=0.05,
            fire_age=65,
        )
        assert result["nisa_at_retirement_jpy"] > 0
        assert result["ideco_at_retirement_jpy"] > 0
