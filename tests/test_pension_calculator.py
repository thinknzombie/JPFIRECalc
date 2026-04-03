"""
Pension calculator tests — verified against nenkin.go.jp published figures
and official formula documentation.

Key reference figures (FY2024):
  - Full kokumin nenkin: 816,000 yen/year for 480 months
  - Early claim at 60: -24% (0.4% × 60 months) → × 0.76
  - Deferral to 70: +42% (0.7% × 60 months) → × 1.42
  - Deferral to 75: +84% (0.7% × 120 months) → × 1.84
  - Kosei nenkin post-2003 multiplier: 0.005481
  - Break-even for any deferral: ~11.9 years past deferral age
"""
import pytest
from engine.pension_calculator import (
    calculate_kokumin_nenkin,
    calculate_kosei_nenkin,
    calculate_total_pension,
    calculate_pension_after_tax,
    calculate_deferral_break_even,
    compare_deferral_options,
    check_totalization,
    calculate_pension_offset_on_fire_number,
)

FULL_BENEFIT = 816_000  # FY2024 full kokumin nenkin


# ---------------------------------------------------------------------------
# Kokumin Nenkin  (老齢基礎年金)
# ---------------------------------------------------------------------------

class TestKokuminNenkin:
    def test_full_benefit_480_months(self):
        result = calculate_kokumin_nenkin(480, claim_age=65)
        assert result["annual_benefit_jpy"] == FULL_BENEFIT
        assert result["pro_rate_factor"] == 1.0
        assert result["claim_modifier"] == 1.0

    def test_pro_rated_360_months(self):
        # 360/480 = 0.75 → 816,000 * 0.75 = 612,000
        result = calculate_kokumin_nenkin(360, claim_age=65)
        assert result["annual_benefit_jpy"] == 612_000
        assert result["pro_rate_factor"] == 0.75

    def test_pro_rated_120_months_minimum(self):
        # 120/480 = 0.25 → 816,000 * 0.25 = 204,000
        result = calculate_kokumin_nenkin(120, claim_age=65)
        assert result["annual_benefit_jpy"] == 204_000
        assert result["eligible"] is True

    def test_below_minimum_ineligible(self):
        # 119 months < 120 minimum → not eligible
        result = calculate_kokumin_nenkin(119, claim_age=65)
        assert result["eligible"] is False
        assert result["annual_benefit_jpy"] == 0

    def test_contribution_months_capped_at_480(self):
        # Extra months above 480 don't increase benefit
        at_480 = calculate_kokumin_nenkin(480)
        above_480 = calculate_kokumin_nenkin(500)
        assert above_480["annual_benefit_jpy"] == at_480["annual_benefit_jpy"]

    def test_early_claim_at_60(self):
        # 60 months early × 0.4% = 24% reduction → × 0.76
        result = calculate_kokumin_nenkin(480, claim_age=60)
        expected = int(FULL_BENEFIT * 0.76)
        assert result["annual_benefit_jpy"] == expected
        assert result["claim_modifier"] == pytest.approx(0.76)
        assert result["early_claim"] is True

    def test_early_claim_at_62(self):
        # 36 months early × 0.4% = 14.4% reduction → × 0.856
        result = calculate_kokumin_nenkin(480, claim_age=62)
        assert result["claim_modifier"] == pytest.approx(0.856)
        assert result["annual_benefit_jpy"] == int(FULL_BENEFIT * 0.856)

    def test_deferral_to_70(self):
        # 60 months deferred × 0.7% = 42% increase → × 1.42
        result = calculate_kokumin_nenkin(480, claim_age=70)
        expected = int(FULL_BENEFIT * 1.42)
        assert result["annual_benefit_jpy"] == expected
        assert result["claim_modifier"] == pytest.approx(1.42)
        assert result["deferred"] is True

    def test_deferral_to_75_max(self):
        # 120 months deferred × 0.7% = 84% increase → × 1.84
        result = calculate_kokumin_nenkin(480, claim_age=75)
        expected = int(FULL_BENEFIT * 1.84)
        assert result["annual_benefit_jpy"] == expected
        assert result["claim_modifier"] == pytest.approx(1.84)

    def test_claim_age_clamped_below_60(self):
        # Age below 60 should be clamped to 60
        result = calculate_kokumin_nenkin(480, claim_age=55)
        at_60 = calculate_kokumin_nenkin(480, claim_age=60)
        assert result["annual_benefit_jpy"] == at_60["annual_benefit_jpy"]

    def test_claim_age_clamped_above_75(self):
        result = calculate_kokumin_nenkin(480, claim_age=80)
        at_75 = calculate_kokumin_nenkin(480, claim_age=75)
        assert result["annual_benefit_jpy"] == at_75["annual_benefit_jpy"]

    def test_monthly_benefit_is_annual_divided_by_12(self):
        result = calculate_kokumin_nenkin(480, claim_age=65)
        assert result["monthly_benefit_jpy"] == result["annual_benefit_jpy"] // 12

    def test_result_structure(self):
        result = calculate_kokumin_nenkin(480)
        for key in ["annual_benefit_jpy", "monthly_benefit_jpy", "contribution_months",
                    "full_benefit_jpy", "pro_rate_factor", "claim_modifier",
                    "claim_age", "eligible", "early_claim", "deferred"]:
            assert key in result


# ---------------------------------------------------------------------------
# Kosei Nenkin  (老齢厚生年金)
# ---------------------------------------------------------------------------

class TestKoseiNenkin:
    def test_formula_calculation(self):
        """
        350,000 avg remuneration × 240 months × 0.005481
        = 350,000 × 240 × 0.005481 = 460,404
        """
        result = calculate_kosei_nenkin(
            avg_standard_monthly_remuneration=350_000,
            contribution_months=240,
            claim_age=65,
        )
        assert result["base_annual_jpy"] == 460_404
        assert result["annual_benefit_jpy"] == 460_404  # no modifier at 65
        assert result["used_override"] is False

    def test_nenkin_net_override_bypasses_formula(self):
        """When NenkinNet figure is provided, formula is bypassed."""
        result = calculate_kosei_nenkin(
            avg_standard_monthly_remuneration=350_000,
            contribution_months=240,
            claim_age=65,
            nenkin_net_override_annual_jpy=500_000,
        )
        assert result["base_annual_jpy"] == 500_000
        assert result["annual_benefit_jpy"] == 500_000
        assert result["used_override"] is True

    def test_deferral_modifier_applied_to_override(self):
        """Deferral modifier applies regardless of whether override is used."""
        result = calculate_kosei_nenkin(
            avg_standard_monthly_remuneration=0,
            contribution_months=0,
            claim_age=70,
            nenkin_net_override_annual_jpy=600_000,
        )
        # 42% increase for deferral to 70
        assert result["annual_benefit_jpy"] == int(600_000 * 1.42)
        assert result["claim_modifier"] == pytest.approx(1.42)

    def test_early_claim_reduces_kosei(self):
        result = calculate_kosei_nenkin(350_000, 240, claim_age=60)
        base = calculate_kosei_nenkin(350_000, 240, claim_age=65)
        assert result["annual_benefit_jpy"] == int(base["base_annual_jpy"] * 0.76)

    def test_more_months_higher_benefit(self):
        short = calculate_kosei_nenkin(350_000, 120)
        long = calculate_kosei_nenkin(350_000, 300)
        assert long["annual_benefit_jpy"] > short["annual_benefit_jpy"]

    def test_higher_remuneration_higher_benefit(self):
        low = calculate_kosei_nenkin(250_000, 240)
        high = calculate_kosei_nenkin(500_000, 240)
        assert high["annual_benefit_jpy"] > low["annual_benefit_jpy"]


# ---------------------------------------------------------------------------
# Combined pension
# ---------------------------------------------------------------------------

class TestTotalPension:
    def test_sums_all_sources(self):
        result = calculate_total_pension(
            kokumin_annual_jpy=816_000,
            kosei_annual_jpy=460_000,
            foreign_pension_annual_jpy=300_000,
        )
        assert result["total_annual_jpy"] == 1_576_000
        assert result["total_monthly_jpy"] == 1_576_000 // 12

    def test_no_foreign_pension(self):
        result = calculate_total_pension(816_000, 460_000)
        assert result["foreign_pension_annual_jpy"] == 0
        assert result["total_annual_jpy"] == 1_276_000

    def test_zero_kosei(self):
        """Self-employed retiree with only kokumin."""
        result = calculate_total_pension(816_000, 0)
        assert result["total_annual_jpy"] == 816_000


# ---------------------------------------------------------------------------
# After-tax pension income
# ---------------------------------------------------------------------------

class TestPensionAfterTax:
    def test_65plus_deduction_applied(self):
        """At 65+, 1,100,000 yen deduction applies to pension ≤ 3,300,000."""
        result = calculate_pension_after_tax(2_000_000, age=65)
        assert result["pension_deduction"] == 1_100_000
        assert result["taxable_pension"] == 900_000

    def test_low_pension_below_deduction_floor(self):
        """Pension of 800,000 at 65+ → taxable is 0 (deduction > pension)."""
        result = calculate_pension_after_tax(800_000, age=65)
        assert result["taxable_pension"] == 0
        assert result["income_tax"] == 0
        assert result["net_pension_annual_jpy"] == 800_000 - result["total_tax"]

    def test_tax_increases_with_pension_income(self):
        low = calculate_pension_after_tax(1_500_000, age=65)
        high = calculate_pension_after_tax(3_000_000, age=65)
        assert high["total_tax"] > low["total_tax"]

    def test_effective_rate_low_at_typical_pension(self):
        """Typical Japanese pension should have low effective tax rate."""
        result = calculate_pension_after_tax(2_000_000, age=65)
        # Taxable is only 900,000 → very low tax
        assert result["effective_tax_rate_pct"] < 10.0

    def test_under65_smaller_deduction(self):
        """Under 65 gets smaller deduction (600,000 for pension ≤ 1,300,000)."""
        result = calculate_pension_after_tax(1_200_000, age=64)
        assert result["pension_deduction"] == 600_000

    def test_net_pension_monthly_consistent(self):
        result = calculate_pension_after_tax(2_000_000, age=65)
        assert result["net_pension_monthly_jpy"] == result["net_pension_annual_jpy"] // 12

    def test_result_structure(self):
        result = calculate_pension_after_tax(2_000_000, age=65)
        for key in ["gross_pension_annual_jpy", "pension_deduction", "taxable_pension",
                    "income_tax", "residence_tax", "total_tax",
                    "net_pension_annual_jpy", "effective_tax_rate_pct"]:
            assert key in result


# ---------------------------------------------------------------------------
# Deferral break-even
# ---------------------------------------------------------------------------

class TestDeferralBreakEven:
    def test_deferral_to_70_42pct_increase(self):
        result = calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=70)
        assert result["increase_pct"] == pytest.approx(42.0)
        assert result["deferred_annual_benefit_jpy"] == int(FULL_BENEFIT * 1.42)

    def test_deferral_to_75_84pct_increase(self):
        result = calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=75)
        assert result["increase_pct"] == pytest.approx(84.0)

    def test_break_even_to_70_approx_119_years(self):
        """
        Payments foregone = 5 × 816,000 = 4,080,000
        Annual gain = 816,000 × 0.42 = 342,720
        Break-even years = 4,080,000 / 342,720 ≈ 11.9 years
        Break-even age ≈ 81.9
        """
        result = calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=70)
        assert result["break_even_years_after_deferral"] == pytest.approx(11.9, abs=0.1)
        assert result["break_even_age"] == pytest.approx(81.9, abs=0.1)

    def test_break_even_to_75_approx_119_years(self):
        """Break-even period is the same ~11.9 years regardless of deferral length."""
        result = calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=75)
        assert result["break_even_years_after_deferral"] == pytest.approx(11.9, abs=0.1)
        assert result["break_even_age"] == pytest.approx(86.9, abs=0.1)

    def test_payments_foregone_correct(self):
        result = calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=70)
        assert result["payments_foregone_jpy"] == FULL_BENEFIT * 5

    def test_invalid_defer_age_raises(self):
        with pytest.raises(ValueError):
            calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=65)

    def test_defer_above_75_raises(self):
        with pytest.raises(ValueError):
            calculate_deferral_break_even(FULL_BENEFIT, defer_to_age=76)


class TestCompareDeferralOptions:
    def test_returns_10_options(self):
        # Ages 66 through 75 = 10 options
        options = compare_deferral_options(FULL_BENEFIT)
        assert len(options) == 10

    def test_ordered_by_defer_age(self):
        options = compare_deferral_options(FULL_BENEFIT)
        ages = [o["defer_to_age"] for o in options]
        assert ages == list(range(66, 76))

    def test_benefit_increases_with_deferral(self):
        options = compare_deferral_options(FULL_BENEFIT)
        benefits = [o["deferred_annual_benefit_jpy"] for o in options]
        assert benefits == sorted(benefits)


# ---------------------------------------------------------------------------
# Totalization
# ---------------------------------------------------------------------------

class TestTotalization:
    def test_us_has_agreement(self):
        result = check_totalization("United States")
        assert result["has_agreement"] is True

    def test_australia_has_agreement(self):
        result = check_totalization("Australia")
        assert result["has_agreement"] is True

    def test_unknown_country_no_agreement(self):
        result = check_totalization("Wakanda")
        assert result["has_agreement"] is False

    def test_case_insensitive(self):
        result = check_totalization("united states")
        assert result["has_agreement"] is True


# ---------------------------------------------------------------------------
# FIRE number pension offset
# ---------------------------------------------------------------------------

class TestPensionOffsetOnFireNumber:
    def test_pension_reduces_fire_number(self):
        result = calculate_pension_offset_on_fire_number(
            annual_expenses_jpy=3_600_000,
            net_pension_annual_jpy=1_200_000,
            withdrawal_rate=0.035,
        )
        # Without pension: 3,600,000 / 0.035 = 102,857,142
        # With pension:    2,400,000 / 0.035 = 68,571,428
        assert result["fire_number_without_pension_jpy"] > result["fire_number_with_pension_jpy"]
        assert result["pension_offset_jpy"] > 0

    def test_full_pension_coverage_zero_fire_number(self):
        """If pension covers all expenses, FIRE number is zero."""
        result = calculate_pension_offset_on_fire_number(
            annual_expenses_jpy=2_000_000,
            net_pension_annual_jpy=2_000_000,
        )
        assert result["fire_number_with_pension_jpy"] == 0

    def test_pension_over_coverage_clamps_to_zero(self):
        """Pension exceeding expenses doesn't produce negative FIRE number."""
        result = calculate_pension_offset_on_fire_number(
            annual_expenses_jpy=1_500_000,
            net_pension_annual_jpy=2_000_000,
        )
        assert result["fire_number_with_pension_jpy"] == 0

    def test_withdrawal_rate_affects_fire_number(self):
        conservative = calculate_pension_offset_on_fire_number(3_000_000, 1_000_000, 0.03)
        aggressive = calculate_pension_offset_on_fire_number(3_000_000, 1_000_000, 0.04)
        assert conservative["fire_number_with_pension_jpy"] > aggressive["fire_number_with_pension_jpy"]

    def test_portfolio_reduction_pct_calculated(self):
        result = calculate_pension_offset_on_fire_number(3_600_000, 1_200_000, 0.035)
        # pension covers 1/3 of expenses → ~33% portfolio reduction
        assert result["portfolio_reduction_pct"] == pytest.approx(33.3, abs=1.0)

    def test_result_structure(self):
        result = calculate_pension_offset_on_fire_number(3_600_000, 1_200_000)
        for key in ["annual_expenses_jpy", "net_pension_annual_jpy", "withdrawal_rate_pct",
                    "fire_number_without_pension_jpy", "pension_offset_jpy",
                    "fire_number_with_pension_jpy", "portfolio_reduction_pct",
                    "pension_covers_expenses_pct"]:
            assert key in result
