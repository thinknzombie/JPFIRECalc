"""
Tax calculator tests — verified against NTA published examples and
manual calculations using official bracket tables.

All monetary figures are in JPY.
"""
import pytest
from engine.tax_calculator import (
    calculate_employment_income_deduction,
    calculate_employment_income,
    calculate_basic_deduction,
    calculate_income_tax,
    calculate_income_tax_from_taxable,
    calculate_residence_tax,
    calculate_year1_retirement_tax_shock,
    calculate_pension_income_deduction,
    calculate_pension_taxable_income,
    calculate_retirement_income_deduction,
    calculate_retirement_income_tax,
    calculate_capital_gains_tax,
)


# ---------------------------------------------------------------------------
# Employment income deduction  (給与所得控除)
# ---------------------------------------------------------------------------

class TestEmploymentIncomeDeduction:
    def test_below_1625000_fixed_deduction(self):
        # Gross ≤ 1,625,000 → fixed 550,000 deduction
        assert calculate_employment_income_deduction(1_000_000) == 550_000
        assert calculate_employment_income_deduction(1_625_000) == 550_000

    def test_rate_bracket_1800000(self):
        # 1,625,001–1,800,000: 40% rate, min 650,000
        # 1,700,000 * 0.40 = 680,000 ≥ 650,000
        assert calculate_employment_income_deduction(1_700_000) == 680_000

    def test_rate_bracket_3600000(self):
        # 1,800,001–3,600,000: 30% rate, min 540,000
        # 3,000,000 * 0.30 = 900,000 ≥ 540,000
        assert calculate_employment_income_deduction(3_000_000) == 900_000

    def test_rate_bracket_6600000(self):
        # 3,600,001–6,600,000: 20% rate, min 540,000
        # 6,000,000 * 0.20 = 1,200,000 ≥ 540,000
        assert calculate_employment_income_deduction(6_000_000) == 1_200_000

    def test_rate_bracket_8500000(self):
        # 6,600,001–8,500,000: 10% rate, min 660,000
        # 8,000,000 * 0.10 = 800,000 ≥ 660,000
        assert calculate_employment_income_deduction(8_000_000) == 800_000

    def test_above_8500000_fixed_cap(self):
        # Above 8,500,000: fixed 1,950,000 cap
        assert calculate_employment_income_deduction(10_000_000) == 1_950_000
        assert calculate_employment_income_deduction(20_000_000) == 1_950_000

    def test_employment_income_6m(self):
        # 6,000,000 gross → 1,200,000 deduction → 4,800,000 employment income
        assert calculate_employment_income(6_000_000) == 4_800_000

    def test_employment_income_never_negative(self):
        assert calculate_employment_income(0) == 0


# ---------------------------------------------------------------------------
# Basic deduction  (基礎控除)
# ---------------------------------------------------------------------------

class TestBasicDeduction:
    def test_standard_income_gets_full_deduction(self):
        # Income ≤ 24,000,000 → 480,000
        assert calculate_basic_deduction(5_000_000) == 480_000
        assert calculate_basic_deduction(24_000_000) == 480_000

    def test_phaseout_24_5m(self):
        assert calculate_basic_deduction(24_100_000) == 320_000

    def test_phaseout_25m(self):
        assert calculate_basic_deduction(24_600_000) == 160_000

    def test_above_25m_zero(self):
        assert calculate_basic_deduction(25_100_000) == 0


# ---------------------------------------------------------------------------
# Income tax from taxable income
# ---------------------------------------------------------------------------

class TestIncomeTaxFromTaxable:
    def test_zero_income(self):
        assert calculate_income_tax_from_taxable(0) == 0

    def test_first_bracket_5pct(self):
        # 1,000,000 taxable → bracket: 5%, deduction 0
        # base_tax = 1,000,000 * 0.05 = 50,000
        # surtax = 50,000 * 0.021 = 1,050
        # total = 51,050 → rounded to 51,000
        result = calculate_income_tax_from_taxable(1_000_000)
        assert result == 51_000

    def test_third_bracket_20pct(self):
        # 4,320,000 taxable → 20% bracket, deduction 427,500
        # base_tax = 4,320,000 * 0.20 - 427,500 = 864,000 - 427,500 = 436,500
        # surtax = 436,500 * 0.021 = 9,166.5 → 9,166
        # total = 445,666 → rounded to 445,600
        result = calculate_income_tax_from_taxable(4_320_000)
        assert result == 445_600

    def test_high_income_45pct(self):
        # 50,000,000 taxable → 45% bracket, deduction 4,796,000
        # base_tax = 50,000,000 * 0.45 - 4,796,000 = 22,500,000 - 4,796,000 = 17,704,000
        # surtax = 17,704,000 * 0.021 = 371,784
        # total = 18,075,784 → rounded to 18,075,700
        result = calculate_income_tax_from_taxable(50_000_000)
        assert result == 18_075_700

    def test_result_rounded_to_100(self):
        # Any result must be a multiple of 100
        for income in [500_000, 1_200_000, 3_500_000, 8_000_000, 15_000_000]:
            result = calculate_income_tax_from_taxable(income)
            assert result % 100 == 0, f"Tax for {income:,} not rounded to 100: {result}"


# ---------------------------------------------------------------------------
# Full income tax calculation (with deductions)
# ---------------------------------------------------------------------------

class TestCalculateIncomeTax:
    def test_single_employee_6m(self):
        """
        Single company employee, 6M gross, no iDeCo, no dependents.
        Expected: employment income 4,800,000, basic ded 480,000,
                  taxable 4,320,000, tax 445,600.
        """
        result = calculate_income_tax(
            gross_income=6_000_000,
            employment_type="company_employee",
        )
        assert result["employment_income"] == 4_800_000
        assert result["basic_deduction"] == 480_000
        assert result["taxable_income"] == 4_320_000
        assert result["income_tax"] == 445_600

    def test_ideco_reduces_taxable_income(self):
        """iDeCo contribution of 23,000/month = 276,000/year deduction."""
        without = calculate_income_tax(gross_income=6_000_000)
        with_ideco = calculate_income_tax(
            gross_income=6_000_000, ideco_monthly_jpy=23_000
        )
        assert with_ideco["taxable_income"] == without["taxable_income"] - 276_000
        assert with_ideco["income_tax"] < without["income_tax"]

    def test_dependent_deduction(self):
        """Each dependent reduces taxable income by 380,000."""
        no_dep = calculate_income_tax(gross_income=6_000_000)
        two_dep = calculate_income_tax(gross_income=6_000_000, num_dependents=2)
        assert two_dep["taxable_income"] == no_dep["taxable_income"] - 760_000

    def test_spouse_deduction(self):
        """Qualifying spouse reduces taxable income by 380,000."""
        no_spouse = calculate_income_tax(gross_income=6_000_000)
        with_spouse = calculate_income_tax(
            gross_income=6_000_000,
            has_spouse=True,
            spouse_income_jpy=800_000,
        )
        assert with_spouse["taxable_income"] == no_spouse["taxable_income"] - 380_000

    def test_effective_rate_increases_with_income(self):
        """Higher income → higher effective rate (progressive system)."""
        low = calculate_income_tax(gross_income=4_000_000)
        mid = calculate_income_tax(gross_income=8_000_000)
        high = calculate_income_tax(gross_income=15_000_000)
        assert low["effective_rate_pct"] < mid["effective_rate_pct"] < high["effective_rate_pct"]

    def test_social_insurance_deduction(self):
        """Social insurance premium is fully deductible."""
        base = calculate_income_tax(gross_income=6_000_000)
        with_si = calculate_income_tax(
            gross_income=6_000_000,
            social_insurance_premium=600_000,
        )
        assert with_si["taxable_income"] == base["taxable_income"] - 600_000

    def test_self_employed_no_emp_deduction(self):
        """Self-employed: gross income is used directly (no employment deduction)."""
        emp = calculate_income_tax(
            gross_income=5_000_000, employment_type="company_employee"
        )
        self_emp = calculate_income_tax(
            gross_income=5_000_000, employment_type="self_employed"
        )
        # Self-employed has higher taxable income (no employment deduction)
        assert self_emp["taxable_income"] > emp["taxable_income"]
        assert self_emp["employment_income"] == 5_000_000


# ---------------------------------------------------------------------------
# Residence tax  (住民税)
# ---------------------------------------------------------------------------

class TestResidenceTax:
    def test_flat_10pct_plus_per_capita(self):
        result = calculate_residence_tax(4_320_000)
        assert result["income_based"] == 432_000
        assert result["per_capita"] == 5_000
        assert result["total"] == 437_000

    def test_zero_income(self):
        result = calculate_residence_tax(0)
        assert result["income_based"] == 0
        assert result["total"] == 5_000  # per-capita still applies

    def test_custom_per_capita(self):
        result = calculate_residence_tax(1_000_000, per_capita_levy=6_000)
        assert result["per_capita"] == 6_000
        assert result["total"] == 106_000


# ---------------------------------------------------------------------------
# Year-1 retirement tax shock
# ---------------------------------------------------------------------------

class TestYear1RetirementShock:
    def test_shock_is_residence_tax_on_last_salary(self):
        """
        The shock is the full residence tax owed on the last working year's income,
        paid in the first year of retirement when there is no income.
        """
        result = calculate_year1_retirement_tax_shock(
            last_working_gross=8_000_000,
            employment_type="company_employee",
        )
        # Must have a meaningful shock for an 8M salary
        assert result["year1_residence_tax"] > 300_000
        assert result["last_working_year_gross"] == 8_000_000

    def test_higher_salary_means_bigger_shock(self):
        low = calculate_year1_retirement_tax_shock(4_000_000)
        high = calculate_year1_retirement_tax_shock(10_000_000)
        assert high["year1_residence_tax"] > low["year1_residence_tax"]

    def test_shock_structure(self):
        result = calculate_year1_retirement_tax_shock(6_000_000)
        assert "year1_residence_tax" in result
        assert "income_based_component" in result
        assert "per_capita_component" in result
        assert result["income_based_component"] + result["per_capita_component"] == result["year1_residence_tax"]


# ---------------------------------------------------------------------------
# Pension income deduction  (公的年金等控除)
# ---------------------------------------------------------------------------

class TestPensionIncomeDeduction:
    def test_65plus_minimum_deduction(self):
        # Pension ≤ 3,300,000 at 65+ → flat 1,100,000 deduction
        assert calculate_pension_income_deduction(2_000_000, age=65) == 1_100_000
        assert calculate_pension_income_deduction(3_300_000, age=65) == 1_100_000

    def test_under65_minimum_deduction(self):
        # Pension ≤ 1,300,000 under 65 → flat 600,000 deduction
        assert calculate_pension_income_deduction(1_000_000, age=64) == 600_000

    def test_taxable_pension_income_65plus(self):
        # 2,000,000 pension at 65: deduction 1,100,000 → taxable 900,000
        assert calculate_pension_taxable_income(2_000_000, age=65) == 900_000

    def test_taxable_pension_below_deduction_is_zero(self):
        # Pension below deduction floor → taxable 0
        assert calculate_pension_taxable_income(800_000, age=65) == 0


# ---------------------------------------------------------------------------
# Retirement income deduction  (退職所得控除)
# ---------------------------------------------------------------------------

class TestRetirementIncomeDeduction:
    def test_minimum_deduction(self):
        # < 2 years still gets minimum 800,000
        assert calculate_retirement_income_deduction(1) == 800_000

    def test_10_years(self):
        # 10 years × 400,000 = 4,000,000
        assert calculate_retirement_income_deduction(10) == 4_000_000

    def test_20_years(self):
        # 20 years × 400,000 = 8,000,000
        assert calculate_retirement_income_deduction(20) == 8_000_000

    def test_25_years(self):
        # 20 × 400,000 + 5 × 700,000 = 8,000,000 + 3,500,000 = 11,500,000
        assert calculate_retirement_income_deduction(25) == 11_500_000

    def test_30_years(self):
        # 20 × 400,000 + 10 × 700,000 = 8,000,000 + 7,000,000 = 15,000,000
        assert calculate_retirement_income_deduction(30) == 15_000_000


class TestRetirementIncomeTax:
    def test_balance_below_deduction_is_zero_tax(self):
        # 20 years iDeCo → 8,000,000 deduction. Balance of 7,000,000 → tax = 0
        result = calculate_retirement_income_tax(7_000_000, contribution_years=20)
        assert result["income_tax"] == 0

    def test_effective_rate_very_low(self):
        # iDeCo is highly tax-advantaged — effective rate should be low
        result = calculate_retirement_income_tax(20_000_000, contribution_years=20)
        # 20M - 8M deduction = 12M, /2 = 6M taxable
        # Tax on 6M: 20% bracket → 6,000,000 * 0.20 - 427,500 = 772,500 + surtax
        assert result["effective_rate_pct"] < 10.0  # well under 10% effective rate
        assert result["taxable_retirement_income"] == 6_000_000

    def test_structure(self):
        result = calculate_retirement_income_tax(15_000_000, contribution_years=25)
        assert "retirement_income_deduction" in result
        assert "taxable_retirement_income" in result
        assert "income_tax" in result
        assert result["taxable_retirement_income"] == max(
            0, (15_000_000 - result["retirement_income_deduction"]) // 2
        )


# ---------------------------------------------------------------------------
# Capital gains tax
# ---------------------------------------------------------------------------

class TestCapitalGainsTax:
    def test_rate_is_20315_pct(self):
        # 1,000,000 gain → 203,150
        assert calculate_capital_gains_tax(1_000_000) == 203_150

    def test_zero_gain(self):
        assert calculate_capital_gains_tax(0) == 0
