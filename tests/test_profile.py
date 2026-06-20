"""Tests for the new mortgage rate fields in FinancialProfile."""
import pytest
from dataclasses import asdict
from models.profile import FinancialProfile, MortgageEntry


def test_defaults_load():
    p = FinancialProfile()
    assert p.mortgage_interest_rate_pct == 0.7
    assert p.mortgage_type == "variable"
    assert p.mortgage_remaining_years == 25
    assert p.mortgage_tax_credit_remaining_years == 0
    assert p.mortgage_tax_credit_principal_cap_jpy == 30_000_000
    assert p.mortgage_tax_credit_rate_pct == 0.7
    assert p.mortgage_prepayment_fee_jpy == 0
    assert p.foreign_mortgage_interest_rate_pct == 0.0
    assert p.foreign_mortgage_type == "fixed"
    assert p.foreign_mortgage_remaining_years == 0


def test_round_trip_json():
    p = FinancialProfile(
        mortgage_interest_rate_pct=1.5,
        mortgage_type="fixed",
        mortgage_remaining_years=20,
        mortgage_tax_credit_remaining_years=5,
    )
    d = asdict(p)
    p2 = FinancialProfile.from_dict(d)
    assert p2.mortgage_interest_rate_pct == 1.5
    assert p2.mortgage_type == "fixed"
    assert p2.mortgage_remaining_years == 20
    assert p2.mortgage_tax_credit_remaining_years == 5


def test_invalid_mortgage_type_raises():
    with pytest.raises(ValueError, match="mortgage_type"):
        FinancialProfile(mortgage_type="interest_only")


def test_invalid_foreign_mortgage_type_raises():
    with pytest.raises(ValueError, match="foreign_mortgage_type"):
        FinancialProfile(foreign_mortgage_type="balloon")


def test_out_of_range_rate_raises():
    with pytest.raises(ValueError):
        FinancialProfile(mortgage_interest_rate_pct=25.0)


def test_negative_rate_raises():
    with pytest.raises(ValueError):
        FinancialProfile(mortgage_interest_rate_pct=-1.0)


def test_negative_remaining_years_raises():
    with pytest.raises(ValueError):
        FinancialProfile(mortgage_remaining_years=-1)


def test_old_profile_without_new_fields_still_loads():
    """Loading a pre-existing profile dict without the new fields should use defaults."""
    old_profile_dict = {
        "current_age": 40,
        "target_retirement_age": 55,
        "annual_gross_income_jpy": 8_000_000,
        "mortgage_balance_jpy": 50_000_000,
        "monthly_mortgage_payment_jpy": 200_000,
        # No mortgage_interest_rate_pct, mortgage_type, etc.
    }
    p = FinancialProfile.from_dict(old_profile_dict)
    assert p.current_age == 40
    assert p.mortgage_balance_jpy == 50_000_000
    # New fields should have defaults
    assert p.mortgage_interest_rate_pct == 0.7
    assert p.mortgage_type == "variable"
    assert p.mortgage_remaining_years == 25


# ---------------------------------------------------------------------------
# MortgageEntry — list-based mortgages (replaces legacy single-loan fields)
# ---------------------------------------------------------------------------

class TestMortgageEntryBasics:
    """MortgageEntry dataclass: creation, defaults, helpers."""

    def test_defaults(self):
        m = MortgageEntry()
        assert m.id != ""
        assert m.label == "Mortgage"
        assert m.balance_jpy == 0
        assert m.interest_rate_pct == 0.7
        assert m.remaining_years == 25
        assert m.loan_type == "variable"
        assert m.is_foreign is False
        assert m.tax_credit_remaining_years == 0

    def test_unique_ids(self):
        m1, m2 = MortgageEntry(), MortgageEntry()
        assert m1.id != m2.id  # default factory generates fresh UUIDs

    def test_annual_interest(self):
        # 0.47% on ¥70.3M for 28y = ¥330,455/yr interest
        m = MortgageEntry(balance_jpy=70_309_716, interest_rate_pct=0.47)
        assert m.annual_interest_jpy == int(70_309_716 * 0.0047)

    def test_annual_principal(self):
        # monthly ¥256,174 × 12 - interest = principal
        m = MortgageEntry(
            balance_jpy=70_309_716, interest_rate_pct=0.47,
            monthly_payment_jpy=256_174,
        )
        expected_interest = int(70_309_716 * 0.0047)
        assert m.annual_principal_jpy == 256_174 * 12 - expected_interest

    def test_tax_credit_capped(self):
        # 0.7% × min(balance, cap) = annual credit
        m = MortgageEntry(
            balance_jpy=70_309_716,
            tax_credit_principal_cap_jpy=30_000_000,
            tax_credit_rate_pct=0.7,
            tax_credit_remaining_years=8,
        )
        assert m.annual_tax_credit_jpy == int(30_000_000 * 0.007)

    def test_foreign_loan_no_tax_credit(self):
        # Foreign loans can't claim 住宅ローン控除
        m = MortgageEntry(
            balance_jpy=25_811_695, interest_rate_pct=5.5,
            is_foreign=True, tax_credit_remaining_years=10,
        )
        assert m.annual_tax_credit_jpy == 0

    def test_effective_rate_with_credit(self):
        # JP loan with tax credit — effective rate should be lower than nominal
        m = MortgageEntry(
            balance_jpy=70_309_716, interest_rate_pct=0.47,
            tax_credit_principal_cap_jpy=30_000_000,
            tax_credit_rate_pct=0.7,
            tax_credit_remaining_years=8,
        )
        # Credit = 30M × 0.7% = ¥210k/yr
        # Credit as % of balance = 210000 / 70309716 × 100 ≈ 0.299%
        # Effective rate = 0.47 - 0.299 ≈ 0.171%
        assert m.effective_annual_rate_pct < m.interest_rate_pct
        assert m.effective_annual_rate_pct > 0

    def test_effective_rate_no_credit(self):
        # No tax credit → effective == nominal
        m = MortgageEntry(balance_jpy=70_309_716, interest_rate_pct=0.47)
        assert m.effective_annual_rate_pct == 0.47


class TestFinancialProfileMortgageAggregation:
    """FinancialProfile aggregate properties: read from list, fall back to legacy."""

    def test_legacy_fields_synthesize_single_entry(self):
        """Old profiles without `mortgages` get a synthesized 1-entry list."""
        data = {
            "current_age": 40,
            "target_retirement_age": 55,
            "mortgage_balance_jpy": 50_000_000,
            "monthly_mortgage_payment_jpy": 200_000,
            "mortgage_interest_rate_pct": 1.5,
            "mortgage_remaining_years": 20,
            "mortgage_tax_credit_remaining_years": 5,
            "mortgage_tax_credit_rate_pct": 0.7,
        }
        p = FinancialProfile.from_dict(data)
        assert len(p.mortgages) == 1
        assert p.mortgages[0].balance_jpy == 50_000_000
        assert p.mortgages[0].interest_rate_pct == 1.5
        assert p.mortgages[0].remaining_years == 20
        # Aggregate properties read from the synthesized entry
        assert p.total_mortgage_balance_jpy == 50_000_000
        assert p.total_mortgage_payment_monthly_jpy == 200_000
        assert p.weighted_avg_mortgage_rate_pct == 1.5

    def test_list_takes_precedence_over_legacy(self):
        """When `mortgages` is non-empty, aggregates read from the list only."""
        data = {
            "current_age": 40,
            "target_retirement_age": 55,
            "mortgage_balance_jpy": 999_999,        # legacy: should be IGNORED
            "monthly_mortgage_payment_jpy": 999_999, # legacy: should be IGNORED
            "mortgage_interest_rate_pct": 5.0,      # legacy: should be IGNORED
            "mortgages": [
                {"balance_jpy": 30_000_000, "interest_rate_pct": 0.5, "monthly_payment_jpy": 100_000, "remaining_years": 25},
                {"balance_jpy": 20_000_000, "interest_rate_pct": 1.0, "monthly_payment_jpy": 80_000, "remaining_years": 20},
            ],
        }
        p = FinancialProfile.from_dict(data)
        assert len(p.mortgages) == 2
        assert p.total_mortgage_balance_jpy == 50_000_000   # sum, not 999,999
        assert p.total_mortgage_payment_monthly_jpy == 180_000  # sum
        # Weighted avg: (30M×0.5 + 20M×1.0) / 50M = 0.7%
        assert abs(p.weighted_avg_mortgage_rate_pct - 0.7) < 1e-9

    def test_no_mortgages_returns_zeros(self):
        """Empty mortgages + no legacy fields → balances and payments are 0,
        but weighted_avg_rate falls back to the legacy field's default (0.7)."""
        p = FinancialProfile()
        assert p.total_mortgage_balance_jpy == 0
        assert p.total_mortgage_payment_monthly_jpy == 0
        # Fall-back: with no list, use legacy single-loan rate (0.7 default)
        assert p.weighted_avg_mortgage_rate_pct == 0.7

    def test_andrew_split_mortgage_scenario(self):
        """The real-world case: 3 separate loans with different rates."""
        data = {
            "current_age": 52,
            "target_retirement_age": 53,
            "mortgages": [
                {"label": "kakinoki_tochi", "balance_jpy": 70_309_716, "interest_rate_pct": 0.47, "monthly_payment_jpy": 256_174, "remaining_years": 28, "is_foreign": False, "tax_credit_remaining_years": 8},
                {"label": "kakinoki_tatemono", "balance_jpy": 23_200_519, "interest_rate_pct": 0.67, "monthly_payment_jpy": 99_905, "remaining_years": 24, "is_foreign": False, "tax_credit_remaining_years": 8},
                {"label": "crozier_ave", "balance_jpy": 25_811_695, "interest_rate_pct": 5.5, "monthly_payment_jpy": 130_000, "remaining_years": 22, "is_foreign": True, "tax_credit_remaining_years": 0},
            ],
        }
        p = FinancialProfile.from_dict(data)
        # Totals
        assert p.total_mortgage_balance_jpy == 119_321_930
        assert p.total_mortgage_payment_monthly_jpy == 486_079
        # Weighted-avg rate: (70.3M×0.47 + 23.2M×0.67 + 25.8M×5.5) / 119.3M ≈ 1.597%
        assert abs(p.weighted_avg_mortgage_rate_pct - 1.597) < 0.01
        # Tax credits only from JP loans (capped at ¥30M each)
        # Land: 30M × 0.7% = ¥210k; Building: 23.2M × 0.7% = ¥162k; total ¥372k
        assert abs(p.total_annual_mortgage_tax_credit_jpy - 372_403) < 1

    def test_malformed_mortgage_entries_skipped(self):
        """Garbage entries in the list get silently dropped (caller validates)."""
        data = {
            "current_age": 40,
            "target_retirement_age": 55,
            "mortgages": [
                "not a dict",
                {"balance_jpy": 50_000_000, "interest_rate_pct": 1.0, "monthly_payment_jpy": 200_000, "remaining_years": 20},
                {"this is invalid": True},
            ],
        }
        p = FinancialProfile.from_dict(data)
        assert len(p.mortgages) == 1  # only the valid one survives
        assert p.mortgages[0].balance_jpy == 50_000_000

    def test_round_trip_json(self):
        """Mortgages list serializes and deserializes intact."""
        data = {
            "current_age": 52,
            "target_retirement_age": 53,
            "mortgages": [
                {"id": "loan_a", "label": "Loan A", "balance_jpy": 10_000_000, "interest_rate_pct": 0.5, "monthly_payment_jpy": 50_000, "remaining_years": 20, "loan_type": "variable", "is_foreign": False},
                {"id": "loan_b", "label": "Loan B", "balance_jpy": 5_000_000, "interest_rate_pct": 4.0, "monthly_payment_jpy": 30_000, "remaining_years": 15, "loan_type": "fixed", "is_foreign": True},
            ],
        }
        p1 = FinancialProfile.from_dict(data)
        d = p1.to_dict()
        p2 = FinancialProfile.from_dict(d)
        assert len(p2.mortgages) == 2
        assert p2.mortgages[0].id == "loan_a"
        assert p2.mortgages[1].is_foreign is True
        assert p2.mortgages[1].interest_rate_pct == 4.0


# ---------------------------------------------------------------------------
# routes/profile.py form parsing — _parse_mortgages_from_form
# ---------------------------------------------------------------------------

class TestParseMortgagesFromForm:
    """Round-trip the form POST data → list[MortgageEntry]."""

    def _call_parse(self, form_data):
        # We test via dict that mimics the form key/value structure
        from routes.profile import _parse_mortgages_from_form
        # Werkzeug MultiDict is what request.form returns; simulate it
        # with a plain dict (the parser only uses .get() and .keys())
        return _parse_mortgages_from_form(form_data)

    def test_no_mortgage_fields_returns_empty(self):
        """Legacy form posts (no mortgages_N_*) → empty list."""
        form_data = {
            "current_age": "40",
            "mortgage_balance_jpy": "50_000_000",  # legacy field present
        }
        result = self._call_parse(form_data)
        assert result == []

    def test_single_complete_row(self):
        form_data = {
            "current_age": "52",
            "mortgages_0_label": "柿ノ木坂 土地",
            "mortgages_0_balance_jpy": "70309716",
            "mortgages_0_interest_rate_pct": "0.47",
            "mortgages_0_monthly_payment_jpy": "256174",
            "mortgages_0_remaining_years": "28",
            "mortgages_0_loan_type": "variable",
            "mortgages_0_is_foreign": "",  # unchecked
            "mortgages_0_tax_credit_remaining_years": "8",
            "mortgages_0_tax_credit_principal_cap_jpy": "30000000",
            "mortgages_0_tax_credit_rate_pct": "0.7",
        }
        result = self._call_parse(form_data)
        assert len(result) == 1
        m = result[0]
        assert m.label == "柿ノ木坂 土地"
        assert m.balance_jpy == 70309716
        assert m.interest_rate_pct == 0.47
        assert m.monthly_payment_jpy == 256174
        assert m.remaining_years == 28
        assert m.loan_type == "variable"
        assert m.is_foreign is False
        assert m.tax_credit_remaining_years == 8
        assert m.id != ""  # auto-generated

    def test_multiple_rows_in_order(self):
        form_data = {
            "mortgages_0_label": "land",
            "mortgages_0_balance_jpy": "70309716",
            "mortgages_0_monthly_payment_jpy": "256174",
            "mortgages_1_label": "building",
            "mortgages_1_balance_jpy": "23200519",
            "mortgages_1_monthly_payment_jpy": "99905",
            "mortgages_1_interest_rate_pct": "0.67",
            "mortgages_2_label": "Crozier",
            "mortgages_2_balance_jpy": "25811695",
            "mortgages_2_monthly_payment_jpy": "130000",
            "mortgages_2_interest_rate_pct": "5.5",
            "mortgages_2_is_foreign": "on",  # checked
        }
        result = self._call_parse(form_data)
        assert len(result) == 3
        assert result[0].label == "land"
        assert result[1].label == "building"
        assert result[1].interest_rate_pct == 0.67
        assert result[2].label == "Crozier"
        assert result[2].is_foreign is True
        assert result[2].interest_rate_pct == 5.5

    def test_blank_row_is_skipped(self):
        """A freshly-added blank row (all empty) gets dropped."""
        form_data = {
            "mortgages_0_label": "real loan",
            "mortgages_0_balance_jpy": "10000000",
            "mortgages_0_monthly_payment_jpy": "50000",
            # Row 1: completely empty (user clicked Add then didn't fill)
            "mortgages_1_label": "",
            "mortgages_1_balance_jpy": "",
            "mortgages_1_monthly_payment_jpy": "",
            "mortgages_2_label": "another real loan",
            "mortgages_2_balance_jpy": "5000000",
            "mortgages_2_monthly_payment_jpy": "30000",
        }
        result = self._call_parse(form_data)
        assert len(result) == 2
        assert result[0].label == "real loan"
        assert result[1].label == "another real loan"

    def test_partial_data_row_is_kept(self):
        """A row with label but no balance is kept (user is filling it in)."""
        form_data = {
            "mortgages_0_label": "in progress",
            # No balance, no payment
        }
        result = self._call_parse(form_data)
        assert len(result) == 1
        assert result[0].label == "in progress"

    def test_invalid_loan_type_falls_back_to_variable(self):
        form_data = {
            "mortgages_0_label": "weird",
            "mortgages_0_balance_jpy": "1000000",
            "mortgages_0_monthly_payment_jpy": "10000",
            "mortgages_0_loan_type": "floating",  # not in allowed set
        }
        result = self._call_parse(form_data)
        assert result[0].loan_type == "variable"

    def test_mortgage_id_field_is_preserved(self):
        form_data = {
            "mortgages_0_id": "kakinoki_tochi",
            "mortgages_0_label": "kakinoki tochi",
            "mortgages_0_balance_jpy": "70309716",
            "mortgages_0_monthly_payment_jpy": "256174",
        }
        result = self._call_parse(form_data)
        assert result[0].id == "kakinoki_tochi"
