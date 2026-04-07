"""
NHI calculator tests.

NHI premiums are highly municipality-dependent. Tests use Tokyo Shinjuku
rates (from nhi_rates.json) as the reference case, with manual calculations
to verify. National average rates are used for portability checks.
"""
import pytest
from engine.nhi_calculator import (
    calculate_nhi_premium,
    calculate_nhi_for_retiree,
    solve_withdrawal_with_nhi,
    calculate_nhi_reduction,
    get_municipality_rates,
    list_municipality_keys,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

class TestDataLoading:
    def test_municipality_keys_available(self):
        keys = list_municipality_keys()
        assert "tokyo_shinjuku" in keys
        assert "national_average" not in keys  # national avg is separate

    def test_unknown_key_falls_back_to_national_average(self):
        rates = get_municipality_rates("nonexistent_city")
        assert rates["name"] == "National Average"

    def test_tokyo_shinjuku_rates_loaded(self):
        rates = get_municipality_rates("tokyo_shinjuku")
        assert rates["medical_income_rate"] > 0
        assert rates["medical_per_capita"] > 0


# ---------------------------------------------------------------------------
# Core premium calculation
# ---------------------------------------------------------------------------

class TestCalculateNhiPremium:
    """
    Manual verification for Tokyo Shinjuku rates (FY2024):
      medical_income_rate = 7.58%, medical_per_capita = 47,300
      support_income_rate = 2.29%, support_per_capita = 14,000
      ltc_income_rate = 1.70%, ltc_per_capita = 16,200

    For 3,000,000 income, 1 member, LTC eligible:
      assessed = 3,000,000 - 430,000 = 2,570,000
      medical  = 2,570,000 * 0.0758 + 47,300 = 194,806 + 47,300 = 242,106
      support  = 2,570,000 * 0.0229 + 14,000 = 58,853 + 14,000 = 72,853
      ltc      = 2,570,000 * 0.0170 + 16,200 = 43,690 + 16,200 = 59,890
      med+sup  = 314,959 (below 1,060,000 cap)
      total    = 314,959 + 59,890 = 374,849
    """
    INCOME = 3_000_000
    MUNICIPALITY = "tokyo_shinjuku"

    def test_assessed_income_subtracts_deduction(self):
        result = calculate_nhi_premium(self.INCOME, 1, self.MUNICIPALITY)
        assert result["assessed_income"] == 2_570_000

    def test_medical_component(self):
        result = calculate_nhi_premium(self.INCOME, 1, self.MUNICIPALITY)
        assert result["medical"] == 242_106

    def test_support_component(self):
        result = calculate_nhi_premium(self.INCOME, 1, self.MUNICIPALITY)
        assert result["support"] == 72_853

    def test_ltc_component_with_eligible_member(self):
        result = calculate_nhi_premium(
            self.INCOME, 1, self.MUNICIPALITY, ltc_eligible_members=1
        )
        assert result["ltc"] == 59_890

    def test_no_ltc_without_eligible_members(self):
        result = calculate_nhi_premium(
            self.INCOME, 1, self.MUNICIPALITY, ltc_eligible_members=0
        )
        assert result["ltc"] == 0

    def test_total_with_ltc(self):
        result = calculate_nhi_premium(
            self.INCOME, 1, self.MUNICIPALITY, ltc_eligible_members=1
        )
        assert result["total"] == 374_849

    def test_total_without_ltc(self):
        result = calculate_nhi_premium(
            self.INCOME, 1, self.MUNICIPALITY, ltc_eligible_members=0
        )
        assert result["total"] == 314_959

    def test_zero_income_only_per_capita(self):
        result = calculate_nhi_premium(0, 1, self.MUNICIPALITY)
        # assessed_income = max(0, 0 - 430,000) = 0
        assert result["assessed_income"] == 0
        # Zero income qualifies for 70% low-income reduction (軽減制度) on per-capita
        assert result["low_income_reduction_rate"] == 0.7
        # Per-capita charges reduced to 30%: 47,300 * 0.3 = 14,190
        assert result["medical"] == int(47_300 * 0.3)
        assert result["support"] == int(14_000 * 0.3)

    def test_annual_cap_applied(self):
        # Very high income should hit the cap
        result = calculate_nhi_premium(20_000_000, 1, self.MUNICIPALITY)
        assert result["cap_hit"] is True
        assert result["medical_support_capped"] == 1_060_000

    def test_no_cap_at_moderate_income(self):
        result = calculate_nhi_premium(3_000_000, 1, self.MUNICIPALITY)
        assert result["cap_hit"] is False

    def test_two_members_doubles_per_capita(self):
        one = calculate_nhi_premium(3_000_000, 1, self.MUNICIPALITY)
        two = calculate_nhi_premium(3_000_000, 2, self.MUNICIPALITY)
        # Per-capita doubles; income-based stays the same
        per_capita_diff = (
            two["medical"] - one["medical"]
            + two["support"] - one["support"]
        )
        assert per_capita_diff == 47_300 + 14_000  # one extra member's per-capita

    def test_premium_increases_with_income(self):
        low = calculate_nhi_premium(2_000_000, 1, self.MUNICIPALITY)
        high = calculate_nhi_premium(5_000_000, 1, self.MUNICIPALITY)
        assert high["total"] > low["total"]


# ---------------------------------------------------------------------------
# Retiree convenience wrapper
# ---------------------------------------------------------------------------

class TestCalculateNhiForRetiree:
    def test_age_50_gets_ltc(self):
        result = calculate_nhi_for_retiree(3_000_000, 1, "tokyo_shinjuku", age=50)
        assert result["ltc"] > 0
        assert result["ltc_via_pension"] is False

    def test_age_65_no_ltc_in_nhi(self):
        result = calculate_nhi_for_retiree(3_000_000, 1, "tokyo_shinjuku", age=65)
        assert result["ltc"] == 0
        assert result["ltc_via_pension"] is True

    def test_age_35_no_ltc(self):
        result = calculate_nhi_for_retiree(3_000_000, 1, "tokyo_shinjuku", age=35)
        assert result["ltc"] == 0
        assert result["ltc_via_pension"] is False

    def test_age_64_boundary_gets_ltc(self):
        result = calculate_nhi_for_retiree(3_000_000, 1, "tokyo_shinjuku", age=64)
        assert result["ltc"] > 0

    def test_national_average_rates_work(self):
        result = calculate_nhi_for_retiree(3_000_000, 1, "national_average", age=50)
        assert result["total"] > 0


# ---------------------------------------------------------------------------
# Iterative solver
# ---------------------------------------------------------------------------

class TestSolveWithdrawalWithNhi:
    def test_gross_withdrawal_exceeds_expenses(self):
        """Gross withdrawal must cover both expenses and NHI."""
        result = solve_withdrawal_with_nhi(
            target_net_expenses=2_400_000,
            num_members=1,
            municipality_key="tokyo_shinjuku",
            age=55,
        )
        assert result["gross_withdrawal"] > 2_400_000
        assert result["nhi_premium"] > 0

    def test_withdrawal_equals_expenses_plus_nhi(self):
        """gross_withdrawal ≈ expenses + NHI(gross_withdrawal) to within tolerance."""
        result = solve_withdrawal_with_nhi(
            target_net_expenses=2_400_000,
            num_members=1,
            municipality_key="tokyo_shinjuku",
            age=55,
        )
        assert result["converged"] is True
        # Verify self-consistency: NHI on the gross withdrawal ≈ the computed NHI
        from engine.nhi_calculator import calculate_nhi_for_retiree
        check = calculate_nhi_for_retiree(
            result["gross_withdrawal"], 1, "tokyo_shinjuku", age=55
        )
        # Allow 200 yen tolerance
        diff = abs(check["total"] - result["nhi_premium"])
        assert diff <= 200, f"NHI inconsistency: {diff} yen"

    def test_higher_expenses_higher_withdrawal(self):
        low = solve_withdrawal_with_nhi(2_000_000, 1, "national_average", age=55)
        high = solve_withdrawal_with_nhi(3_000_000, 1, "national_average", age=55)
        assert high["gross_withdrawal"] > low["gross_withdrawal"]

    def test_converges_quickly(self):
        result = solve_withdrawal_with_nhi(
            target_net_expenses=2_400_000,
            num_members=1,
            municipality_key="tokyo_shinjuku",
            age=55,
        )
        # Should converge in well under 20 iterations
        assert result["iterations"] < 20

    def test_age_65_lower_withdrawal_than_50(self):
        """65+ retirees have no LTC in NHI → lower total premium → less withdrawal needed."""
        age50 = solve_withdrawal_with_nhi(2_400_000, 1, "tokyo_shinjuku", age=50)
        age65 = solve_withdrawal_with_nhi(2_400_000, 1, "tokyo_shinjuku", age=65)
        assert age65["gross_withdrawal"] < age50["gross_withdrawal"]

    def test_result_structure(self):
        result = solve_withdrawal_with_nhi(2_400_000, 1, "national_average", age=55)
        for key in ["gross_withdrawal", "nhi_premium", "net_expenses", "total_cost",
                    "nhi_as_pct_of_withdrawal", "iterations", "converged", "municipality"]:
            assert key in result


# ---------------------------------------------------------------------------
# Low-income reduction
# ---------------------------------------------------------------------------

class TestNhiReduction:
    def test_very_low_income_gets_70pct_reduction(self):
        # Income ≤ 430,000 + (10,000 × 1 member) = 440,000
        assert calculate_nhi_reduction(400_000, num_members=1) == 0.7

    def test_moderate_low_income_50pct(self):
        # 430,000 < income ≤ 430,000 + 295,000*1 = 725,000
        assert calculate_nhi_reduction(600_000, num_members=1) == 0.5

    def test_higher_low_income_20pct(self):
        # 725,000 < income ≤ 430,000 + 545,000*1 = 975,000
        assert calculate_nhi_reduction(850_000, num_members=1) == 0.2

    def test_normal_income_no_reduction(self):
        assert calculate_nhi_reduction(3_000_000, num_members=1) == 0.0

    def test_reduction_thresholds_scale_with_members(self):
        # With 3 members, thresholds are higher
        single_threshold = 430_000 + 10_000 * 1
        family_threshold = 430_000 + 10_000 * 3
        assert calculate_nhi_reduction(single_threshold + 1, num_members=1) != 0.7
        assert calculate_nhi_reduction(single_threshold + 1, num_members=3) == 0.7

    def test_reduction_applied_in_premium_calculation(self):
        """Verify that calculate_nhi_premium integrates the low-income reduction."""
        # Zero income → 70% reduction on per-capita levies
        reduced = calculate_nhi_premium(0, 1, "tokyo_shinjuku")
        assert reduced["low_income_reduction_rate"] == 0.7
        # Normal income → no reduction
        normal = calculate_nhi_premium(3_000_000, 1, "tokyo_shinjuku")
        assert normal["low_income_reduction_rate"] == 0.0
        # Per-capita portion should be higher when not reduced
        assert normal["medical"] > reduced["medical"]

    def test_reduction_50pct_applied_in_premium(self):
        """50% reduction cuts per-capita in half."""
        # Income ¥600k, 1 member → 50% reduction band
        result = calculate_nhi_premium(600_000, 1, "tokyo_shinjuku")
        assert result["low_income_reduction_rate"] == 0.5
        # Medical = income_rate * assessed_income + per_capita * 0.5
        # assessed_income = 600,000 - 430,000 = 170,000
        assert result["assessed_income"] == 170_000
