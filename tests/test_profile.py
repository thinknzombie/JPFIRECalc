"""Tests for the new mortgage rate fields in FinancialProfile."""
import pytest
from dataclasses import asdict
from models.profile import FinancialProfile


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
