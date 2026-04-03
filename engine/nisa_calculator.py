"""
新NISA (Nippon Individual Savings Account) calculator.

New NISA structure (effective January 2024):
  - Tsumitate (積立) frame:  max 1,200,000 yen/year
  - Growth (成長投資) frame: max 2,400,000 yen/year
  - Combined annual cap:     max 3,600,000 yen/year
  - Lifetime acquisition cap: 18,000,000 yen (on cost basis, not market value)
  - No time limit on holding (unlike old NISA which had 5/20-year windows)
  - Tax-free growth AND withdrawals — completely tax-free
  - Re-contribution: selling restores lifetime cap equal to the acquisition cost
    of what was sold (not the proceeds — gains do NOT restore cap)
  - Fully liquid: withdraw any time, no penalties, no restrictions

Key advantages for FIRE:
  - Unlike iDeCo, NISA is completely accessible at any age — the primary
    tax-advantaged vehicle for pre-60 FIRE retirees.
  - Tax saving vs taxable: avoids 20.315% tax on gains and dividends.
  - With 18M lifetime cap and 5% returns over 20 years, a maxed NISA
    can grow to ~47M+ yen completely tax-free.

Sources: 金融庁 (FSA Japan) — 2024 figures.
"""
from __future__ import annotations
import math


# Constants
TSUMITATE_ANNUAL_MAX = 1_200_000
GROWTH_ANNUAL_MAX = 2_400_000
COMBINED_ANNUAL_MAX = TSUMITATE_ANNUAL_MAX + GROWTH_ANNUAL_MAX  # 3,600,000
LIFETIME_CAP = 18_000_000
CAPITAL_GAINS_TAX_RATE = 0.20315  # tax rate that NISA avoids


# ---------------------------------------------------------------------------
# Contribution validation
# ---------------------------------------------------------------------------

def validate_nisa_contribution(
    annual_tsumitate_jpy: int,
    annual_growth_jpy: int,
    lifetime_used_jpy: int = 0,
) -> dict:
    """
    Validate a planned annual NISA contribution against limits.

    Args:
        annual_tsumitate_jpy: Planned tsumitate frame contribution this year.
        annual_growth_jpy:    Planned growth frame contribution this year.
        lifetime_used_jpy:    Total acquisition cost already used (0–18,000,000).

    Returns:
        dict with is_valid, issues (list of str), effective contributions,
        remaining_lifetime_cap_jpy.
    """
    issues = []
    effective_tsumitate = annual_tsumitate_jpy
    effective_growth = annual_growth_jpy

    if annual_tsumitate_jpy > TSUMITATE_ANNUAL_MAX:
        issues.append(
            f"Tsumitate frame {annual_tsumitate_jpy:,} exceeds annual limit {TSUMITATE_ANNUAL_MAX:,}."
        )
        effective_tsumitate = TSUMITATE_ANNUAL_MAX

    if annual_growth_jpy > GROWTH_ANNUAL_MAX:
        issues.append(
            f"Growth frame {annual_growth_jpy:,} exceeds annual limit {GROWTH_ANNUAL_MAX:,}."
        )
        effective_growth = GROWTH_ANNUAL_MAX

    combined = effective_tsumitate + effective_growth
    remaining_lifetime = max(0, LIFETIME_CAP - lifetime_used_jpy)

    if combined > remaining_lifetime:
        issues.append(
            f"Combined contribution {combined:,} exceeds remaining lifetime cap {remaining_lifetime:,}."
        )
        # Scale down proportionally
        if combined > 0:
            scale = remaining_lifetime / combined
            effective_tsumitate = int(effective_tsumitate * scale)
            effective_growth = int(effective_growth * scale)

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "effective_tsumitate_jpy": effective_tsumitate,
        "effective_growth_jpy": effective_growth,
        "effective_combined_jpy": effective_tsumitate + effective_growth,
        "remaining_lifetime_cap_jpy": remaining_lifetime,
        "lifetime_used_jpy": lifetime_used_jpy,
    }


# ---------------------------------------------------------------------------
# Growth projection
# ---------------------------------------------------------------------------

def calculate_nisa_growth(
    years: int,
    annual_return_rate: float,
    monthly_tsumitate_jpy: int = 0,
    annual_growth_frame_jpy: int = 0,
    existing_balance_jpy: int = 0,
    lifetime_cap_used_jpy: int = 0,
) -> dict:
    """
    Project NISA balance over time, respecting annual frame limits and lifetime cap.

    Tracks acquisition cost separately from market value to enforce the lifetime cap
    correctly (cap applies to cost basis, not market value).

    Args:
        years:                    Projection horizon (years).
        annual_return_rate:       Expected annual return as decimal (e.g. 0.05).
        monthly_tsumitate_jpy:    Monthly tsumitate frame contributions.
        annual_growth_frame_jpy:  Annual growth frame contributions (lump sum per year).
        existing_balance_jpy:     Current NISA market value.
        lifetime_cap_used_jpy:    Acquisition cost already used of the 18M lifetime cap.

    Returns:
        dict with final_balance_jpy, total_contributions_jpy, investment_gain_jpy,
        cap_exhausted_year (None if cap never hit), year_by_year (list).
    """
    annual_tsumitate = monthly_tsumitate_jpy * 12
    r = annual_return_rate
    balance = existing_balance_jpy
    cap_used = lifetime_cap_used_jpy
    total_contributed = 0
    cap_exhausted_year = None

    year_by_year = []

    for yr in range(1, years + 1):
        # Determine how much can be contributed this year
        remaining_cap = max(0, LIFETIME_CAP - cap_used)

        tsumitate_this_year = min(annual_tsumitate, TSUMITATE_ANNUAL_MAX, remaining_cap)
        remaining_cap_after_tsumitate = max(0, remaining_cap - tsumitate_this_year)
        growth_this_year = min(annual_growth_frame_jpy, GROWTH_ANNUAL_MAX, remaining_cap_after_tsumitate)

        annual_contribution = tsumitate_this_year + growth_this_year

        # Grow existing balance, then add contributions (simplified: add mid-year)
        balance = int(balance * (1 + r) + annual_contribution)
        cap_used = min(LIFETIME_CAP, cap_used + annual_contribution)

        if cap_used >= LIFETIME_CAP and cap_exhausted_year is None:
            cap_exhausted_year = yr
        total_contributed += annual_contribution

        year_by_year.append({
            "year": yr,
            "balance_jpy": balance,
            "cap_used_jpy": cap_used,
            "remaining_cap_jpy": max(0, LIFETIME_CAP - cap_used),
            "contribution_this_year_jpy": annual_contribution,
            "total_contributed_jpy": existing_balance_jpy + total_contributed,
        })

    gain = balance - existing_balance_jpy - total_contributed

    return {
        "years": years,
        "annual_return_rate_pct": annual_return_rate * 100,
        "monthly_tsumitate_jpy": monthly_tsumitate_jpy,
        "annual_growth_frame_jpy": annual_growth_frame_jpy,
        "existing_balance_jpy": existing_balance_jpy,
        "lifetime_cap_used_start_jpy": lifetime_cap_used_jpy,
        "final_balance_jpy": balance,
        "final_cap_used_jpy": cap_used,
        "remaining_lifetime_cap_jpy": max(0, LIFETIME_CAP - cap_used),
        "total_contributions_jpy": total_contributed,
        "investment_gain_jpy": max(0, gain),
        "cap_exhausted_year": cap_exhausted_year,
        "cap_fully_exhausted": cap_used >= LIFETIME_CAP,
        "year_by_year": year_by_year,
    }


# ---------------------------------------------------------------------------
# Tax saving vs taxable account
# ---------------------------------------------------------------------------

def calculate_nisa_tax_saving(
    projected_gain_jpy: int,
    annual_dividend_income_jpy: int = 0,
) -> dict:
    """
    Calculate tax saved by holding investments in NISA vs a taxable account.

    In a taxable account (特定口座):
      - Capital gains tax: 20.315% on realised gains
      - Dividend tax: 20.315% (withholding, or aggregate with income tax if lower)

    In NISA: 0% on both.

    Args:
        projected_gain_jpy:       Total capital gain over the holding period.
        annual_dividend_income_jpy: Annual dividend income within NISA.

    Returns:
        dict with capital_gains_tax_saved, dividend_tax_saved_annual,
        total_tax_saved_jpy, effective_return_boost_note.
    """
    cg_tax_saved = int(projected_gain_jpy * CAPITAL_GAINS_TAX_RATE)
    div_tax_saved_annual = int(annual_dividend_income_jpy * CAPITAL_GAINS_TAX_RATE)

    return {
        "projected_gain_jpy": projected_gain_jpy,
        "capital_gains_tax_saved_jpy": cg_tax_saved,
        "annual_dividend_income_jpy": annual_dividend_income_jpy,
        "annual_dividend_tax_saved_jpy": div_tax_saved_annual,
        "tax_rate_avoided_pct": CAPITAL_GAINS_TAX_RATE * 100,
        "note": (
            "NISA avoids 20.315% tax on both capital gains and dividends. "
            "For a long-term holder, this is equivalent to a ~0.3-0.5% annual "
            "return boost on a typical equity portfolio."
        ),
    }


# ---------------------------------------------------------------------------
# Years to fill the NISA lifetime cap
# ---------------------------------------------------------------------------

def years_to_fill_lifetime_cap(
    monthly_tsumitate_jpy: int = 100_000,
    annual_growth_frame_jpy: int = 0,
    lifetime_cap_used_jpy: int = 0,
) -> dict:
    """
    Calculate how many years until the 18M lifetime cap is exhausted.

    Args:
        monthly_tsumitate_jpy:    Monthly tsumitate contributions.
        annual_growth_frame_jpy:  Annual growth frame contributions.
        lifetime_cap_used_jpy:    Already-used portion of the lifetime cap.

    Returns:
        dict with years_to_fill, annual_rate, remaining_cap.
    """
    annual_tsumitate = min(monthly_tsumitate_jpy * 12, TSUMITATE_ANNUAL_MAX)
    annual_growth = min(annual_growth_frame_jpy, GROWTH_ANNUAL_MAX)
    annual_total = annual_tsumitate + annual_growth
    remaining = max(0, LIFETIME_CAP - lifetime_cap_used_jpy)

    if annual_total <= 0:
        return {
            "years_to_fill": None,
            "annual_contribution_jpy": 0,
            "remaining_cap_jpy": remaining,
            "note": "No contributions planned — cap will never be filled.",
        }

    years = math.ceil(remaining / annual_total)

    return {
        "years_to_fill": years,
        "annual_contribution_jpy": annual_total,
        "monthly_tsumitate_jpy": monthly_tsumitate_jpy,
        "annual_growth_frame_jpy": annual_growth_frame_jpy,
        "remaining_cap_jpy": remaining,
        "lifetime_cap_jpy": LIFETIME_CAP,
        "note": (
            f"At ¥{annual_total:,}/year, the 18M lifetime cap fills in {years} years. "
            "Remaining cap is restored when NISA holdings are sold."
        ),
    }


# ---------------------------------------------------------------------------
# Re-contribution: cap restoration after selling
# ---------------------------------------------------------------------------

def calculate_cap_restoration(
    acquisition_cost_sold_jpy: int,
    market_value_sold_jpy: int,
) -> dict:
    """
    Calculate how much lifetime cap is restored when NISA holdings are sold.

    Cap restoration = ACQUISITION COST of what was sold (not the proceeds).
    The gain portion does NOT restore cap.

    This is the key difference from the old NISA: in 新NISA, selling allows
    re-contribution of the original cost basis from the next year.

    Args:
        acquisition_cost_sold_jpy: Original purchase cost of the sold holdings.
        market_value_sold_jpy:     Actual sale proceeds.

    Returns:
        dict with cap_restored_jpy, gain_not_restorable_jpy, can_recontribute_next_year.
    """
    gain = max(0, market_value_sold_jpy - acquisition_cost_sold_jpy)
    return {
        "acquisition_cost_sold_jpy": acquisition_cost_sold_jpy,
        "market_value_sold_jpy": market_value_sold_jpy,
        "capital_gain_jpy": gain,
        "cap_restored_jpy": acquisition_cost_sold_jpy,
        "gain_not_restorable_jpy": gain,
        "can_recontribute_next_year": True,
        "note": (
            f"Selling restores ¥{acquisition_cost_sold_jpy:,} of lifetime cap "
            f"(the acquisition cost). The ¥{gain:,} gain does not restore cap. "
            "Re-contribution can begin the following calendar year."
        ),
    }


# ---------------------------------------------------------------------------
# Combined iDeCo + NISA overview for a profile
# ---------------------------------------------------------------------------

def calculate_tax_advantaged_summary(
    nisa_balance_jpy: int,
    ideco_balance_jpy: int,
    nisa_annual_contribution_jpy: int,
    ideco_monthly_contribution_jpy: int,
    years_to_retirement: int,
    annual_return_rate: float,
    lifetime_cap_used_jpy: int = 0,
    fire_age: int = 65,
) -> dict:
    """
    High-level summary of NISA + iDeCo balances at retirement.

    Returns accessible vs locked balances, making the pre-60 bridge situation clear.
    """
    from engine.ideco_calculator import calculate_ideco_accumulation, calculate_ideco_bridge_need

    nisa_result = calculate_nisa_growth(
        years=years_to_retirement,
        annual_return_rate=annual_return_rate,
        annual_growth_frame_jpy=nisa_annual_contribution_jpy,
        existing_balance_jpy=nisa_balance_jpy,
        lifetime_cap_used_jpy=lifetime_cap_used_jpy,
    )

    ideco_result = calculate_ideco_accumulation(
        monthly_contribution_jpy=ideco_monthly_contribution_jpy,
        years=years_to_retirement,
        annual_return_rate=annual_return_rate,
        existing_balance_jpy=ideco_balance_jpy,
    )

    nisa_at_retirement = nisa_result["final_balance_jpy"]
    ideco_at_retirement = ideco_result["final_balance_jpy"]

    ideco_accessible = fire_age >= 60
    accessible_total = nisa_at_retirement + (ideco_at_retirement if ideco_accessible else 0)
    locked_ideco = ideco_at_retirement if not ideco_accessible else 0

    return {
        "fire_age": fire_age,
        "years_to_retirement": years_to_retirement,
        "nisa_at_retirement_jpy": nisa_at_retirement,
        "ideco_at_retirement_jpy": ideco_at_retirement,
        "ideco_accessible_at_fire": ideco_accessible,
        "accessible_total_jpy": accessible_total,
        "locked_ideco_jpy": locked_ideco,
        "warning": (
            f"iDeCo (¥{locked_ideco:,}) is locked until age 60. "
            f"Only NISA (¥{nisa_at_retirement:,}) is accessible at FIRE age {fire_age}."
            if not ideco_accessible else None
        ),
    }
