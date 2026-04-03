"""
iDeCo calculator tests.

Key verified figures:
  - 23,000/month × 12 = 276,000/year contribution
  - FV of 276,000/year for 20yr at 5%: 276,000 × ((1.05^20 - 1) / 0.05)
    = 276,000 × 33.066 = 9,126,216 (approx, from existing balance 0)
  - Tax saving at 20% marginal + 10% residence: 276,000 × 0.30 = 82,800/year
  - Retirement income deduction for 20yr iDeCo: 20 × 400,000 = 8,000,000
  - Lump sum tax on 10M balance, 20yr: (10M - 8M) / 2 = 1M taxable
"""
import pytest
from engine.ideco_calculator import (
    get_monthly_limit,
    validate_contribution,
    calculate_ideco_accumulation,
    calculate_ideco_tax_saving,
    calculate_lump_sum_withdrawal_tax,
    calculate_annuity_withdrawal_tax,
    compare_withdrawal_methods,
    calculate_ideco_bridge_need,
)


# ---------------------------------------------------------------------------
# Contribution limits
# ---------------------------------------------------------------------------

class TestContributionLimits:
    def test_self_employed_limit(self):
        assert get_monthly_limit("self_employed") == 68_000

    def test_company_no_pension_limit(self):
        assert get_monthly_limit("company_no_pension") == 23_000

    def test_company_with_db_limit(self):
        assert get_monthly_limit("company_with_db_or_mutual_aid") == 12_000

    def test_civil_servant_limit(self):
        assert get_monthly_limit("civil_servant") == 20_000

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            get_monthly_limit("moon_farmer")

    def test_valid_contribution(self):
        result = validate_contribution(23_000, "company_no_pension")
        assert result["is_valid"] is True
        assert result["excess_monthly_jpy"] == 0

    def test_over_limit_invalid(self):
        result = validate_contribution(30_000, "company_no_pension")
        assert result["is_valid"] is False
        assert result["excess_monthly_jpy"] == 7_000

    def test_annual_contribution_capped_at_limit(self):
        result = validate_contribution(30_000, "company_no_pension")
        # Annual should reflect the capped amount (23,000 × 12)
        assert result["annual_jpy"] == 23_000 * 12


# ---------------------------------------------------------------------------
# Accumulation projection
# ---------------------------------------------------------------------------

class TestIdecoAccumulation:
    def test_zero_return_linear_growth(self):
        result = calculate_ideco_accumulation(
            monthly_contribution_jpy=23_000,
            years=20,
            annual_return_rate=0.0,
        )
        assert result["final_balance_jpy"] == 23_000 * 12 * 20
        assert result["investment_gain_jpy"] == 0

    def test_positive_return_grows_faster_than_linear(self):
        zero = calculate_ideco_accumulation(23_000, 20, 0.0)
        five = calculate_ideco_accumulation(23_000, 20, 0.05)
        assert five["final_balance_jpy"] > zero["final_balance_jpy"]

    def test_5pct_return_20yr_approx(self):
        # FV ≈ 276,000 × ((1.05^20 - 1) / 0.05) ≈ 9,126,000
        result = calculate_ideco_accumulation(23_000, 20, 0.05)
        assert 9_000_000 < result["final_balance_jpy"] < 9_300_000

    def test_existing_balance_compounds(self):
        without = calculate_ideco_accumulation(23_000, 10, 0.05)
        with_balance = calculate_ideco_accumulation(23_000, 10, 0.05, existing_balance_jpy=1_000_000)
        # With 1M existing: final should be higher by more than 1M (compounded)
        assert with_balance["final_balance_jpy"] > without["final_balance_jpy"] + 1_000_000

    def test_year_by_year_length(self):
        result = calculate_ideco_accumulation(23_000, 15, 0.05)
        assert len(result["year_by_year"]) == 15

    def test_year_by_year_balance_increases(self):
        result = calculate_ideco_accumulation(23_000, 10, 0.05)
        balances = [y["balance_jpy"] for y in result["year_by_year"]]
        assert balances == sorted(balances)

    def test_total_contributions_correct(self):
        result = calculate_ideco_accumulation(20_000, 15, 0.05)
        assert result["total_contributions_jpy"] == 20_000 * 12 * 15


# ---------------------------------------------------------------------------
# Tax saving calculation
# ---------------------------------------------------------------------------

class TestIdecoTaxSaving:
    def test_combined_rate_saving(self):
        """23,000/month, 20% income tax + 10% residence tax = 30% total."""
        result = calculate_ideco_tax_saving(
            monthly_contribution_jpy=23_000,
            marginal_income_tax_rate=0.20,
            residence_tax_rate=0.10,
        )
        expected = int(276_000 * 0.20) + int(276_000 * 0.10)
        assert result["annual_total_saving_jpy"] == expected

    def test_high_earner_saves_more(self):
        low = calculate_ideco_tax_saving(23_000, marginal_income_tax_rate=0.10)
        high = calculate_ideco_tax_saving(23_000, marginal_income_tax_rate=0.33)
        assert high["annual_total_saving_jpy"] > low["annual_total_saving_jpy"]

    def test_cumulative_saving_scales_with_years(self):
        result = calculate_ideco_tax_saving(23_000, 0.20, years=20)
        single_year = calculate_ideco_tax_saving(23_000, 0.20, years=1)
        assert result["cumulative_saving_jpy"] == single_year["annual_total_saving_jpy"] * 20

    def test_effective_return_boost_positive(self):
        result = calculate_ideco_tax_saving(23_000, 0.20)
        assert result["effective_return_boost_pct"] > 0

    def test_self_employed_max_contribution_saves_more(self):
        company = calculate_ideco_tax_saving(23_000, 0.20)
        self_emp = calculate_ideco_tax_saving(68_000, 0.20)
        assert self_emp["annual_total_saving_jpy"] > company["annual_total_saving_jpy"]


# ---------------------------------------------------------------------------
# Lump sum withdrawal tax
# ---------------------------------------------------------------------------

class TestLumpSumWithdrawalTax:
    def test_balance_below_deduction_zero_tax(self):
        """
        20yr iDeCo → 8M deduction. Balance 7M → taxable 0 → income tax 0.
        Residence tax per-capita levy (5,000) still applies even at zero income,
        so net receipt = 7,000,000 - 5,000 = 6,995,000.
        """
        result = calculate_lump_sum_withdrawal_tax(7_000_000, contribution_years=20)
        assert result["taxable_retirement_income"] == 0
        assert result["income_tax"] == 0
        assert result["residence_tax"] == 5_000  # per-capita levy only
        assert result["net_receipt_jpy"] == 6_995_000

    def test_10m_balance_20yr_low_tax(self):
        """
        10M balance, 20yr:
          deduction = 8,000,000
          net = 2,000,000
          taxable = 1,000,000
          income tax on 1M: 5% bracket → 1,000,000 × 0.05 = 50,000 + surtax = 51,000
          residence tax: 1,000,000 × 10% + 5,000 = 105,000
          total tax ≈ 156,000
          effective rate ≈ 1.56%
        """
        result = calculate_lump_sum_withdrawal_tax(10_000_000, contribution_years=20)
        assert result["retirement_income_deduction"] == 8_000_000
        assert result["taxable_retirement_income"] == 1_000_000
        assert result["effective_tax_rate_pct"] < 5.0

    def test_longer_tenure_larger_deduction(self):
        short = calculate_lump_sum_withdrawal_tax(15_000_000, contribution_years=15)
        long = calculate_lump_sum_withdrawal_tax(15_000_000, contribution_years=25)
        assert long["retirement_income_deduction"] > short["retirement_income_deduction"]
        assert long["total_tax"] < short["total_tax"]

    def test_net_receipt_equals_balance_minus_tax(self):
        result = calculate_lump_sum_withdrawal_tax(10_000_000, contribution_years=20)
        assert result["net_receipt_jpy"] == result["balance_jpy"] - result["total_tax"]

    def test_result_structure(self):
        result = calculate_lump_sum_withdrawal_tax(10_000_000, 20)
        for key in ["balance_jpy", "retirement_income_deduction", "taxable_retirement_income",
                    "income_tax", "residence_tax", "total_tax", "net_receipt_jpy",
                    "effective_tax_rate_pct", "method"]:
            assert key in result

    def test_method_is_lump_sum(self):
        result = calculate_lump_sum_withdrawal_tax(10_000_000, 20)
        assert result["method"] == "lump_sum"


# ---------------------------------------------------------------------------
# Annuity withdrawal tax
# ---------------------------------------------------------------------------

class TestAnnuityWithdrawalTax:
    def test_low_withdrawal_under_deduction_low_tax(self):
        """At 65+, pension deduction is 1,100,000. Annual draw of 1M should have low tax."""
        result = calculate_annuity_withdrawal_tax(1_000_000, age=65)
        assert result["taxable_income"] == 0
        assert result["income_tax"] == 0

    def test_higher_withdrawal_taxed(self):
        result = calculate_annuity_withdrawal_tax(2_000_000, age=65)
        # 2M + 0 other = 2M total, deduction 1.1M, taxable 900,000
        assert result["taxable_income"] == 900_000

    def test_combined_with_other_pension(self):
        """Combined income pushes into higher taxable bracket."""
        no_other = calculate_annuity_withdrawal_tax(1_500_000, age=65)
        with_other = calculate_annuity_withdrawal_tax(1_500_000, age=65, other_pension_income_jpy=800_000)
        assert with_other["taxable_income"] > no_other["taxable_income"]

    def test_method_is_annuity(self):
        result = calculate_annuity_withdrawal_tax(1_000_000, age=65)
        assert result["method"] == "annuity"


# ---------------------------------------------------------------------------
# Compare withdrawal methods
# ---------------------------------------------------------------------------

class TestCompareWithdrawalMethods:
    def test_lump_sum_usually_better(self):
        """For typical iDeCo balances, lump sum is usually more tax-efficient."""
        result = compare_withdrawal_methods(
            balance_jpy=15_000_000,
            contribution_years=25,
            age_at_withdrawal=60,
        )
        assert result["recommended"] == "lump_sum"

    def test_result_contains_both_methods(self):
        result = compare_withdrawal_methods(10_000_000, 20)
        assert "lump_sum" in result
        assert "annuity" in result
        assert "recommended" in result

    def test_lump_sum_net_is_positive(self):
        result = compare_withdrawal_methods(10_000_000, 20)
        assert result["lump_sum"]["net_receipt_jpy"] > 0


# ---------------------------------------------------------------------------
# iDeCo bridge calculation
# ---------------------------------------------------------------------------

class TestIDecoBridgeNeed:
    def test_fire_at_60_no_bridge_needed(self):
        result = calculate_ideco_bridge_need(60, 3_000_000)
        assert result["bridge_needed"] is False
        assert result["gap_years"] == 0
        assert result["bridge_portfolio_needed_jpy"] == 0

    def test_fire_at_65_no_bridge_needed(self):
        result = calculate_ideco_bridge_need(65, 3_000_000)
        assert result["bridge_needed"] is False

    def test_fire_at_50_10yr_gap(self):
        result = calculate_ideco_bridge_need(50, 3_000_000, annual_return_rate=0.0)
        assert result["gap_years"] == 10
        assert result["bridge_needed"] is True
        # At 0% return: PV = 3,000,000 × 10 = 30,000,000
        assert result["bridge_portfolio_needed_jpy"] == 30_000_000

    def test_fire_at_45_15yr_gap(self):
        result = calculate_ideco_bridge_need(45, 2_400_000, annual_return_rate=0.0)
        assert result["gap_years"] == 15
        assert result["bridge_portfolio_needed_jpy"] == 2_400_000 * 15

    def test_positive_return_reduces_bridge_need(self):
        """With portfolio returns, less capital is needed upfront."""
        no_return = calculate_ideco_bridge_need(50, 3_000_000, annual_return_rate=0.0)
        with_return = calculate_ideco_bridge_need(50, 3_000_000, annual_return_rate=0.05)
        assert with_return["bridge_portfolio_needed_jpy"] < no_return["bridge_portfolio_needed_jpy"]

    def test_warning_message_present_when_bridge_needed(self):
        result = calculate_ideco_bridge_need(45, 3_000_000)
        assert result["warning"] is not None
        assert "60" in result["warning"]

    def test_no_warning_when_no_bridge_needed(self):
        result = calculate_ideco_bridge_need(60, 3_000_000)
        assert result["warning"] is None
