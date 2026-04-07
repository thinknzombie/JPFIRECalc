"""
Data models for user profile and financial profile.

All monetary values are in JPY (int). Percentages are floats (e.g. 5.0 = 5%).
These are plain dataclasses with no Flask dependency — fully serialisable to JSON.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json
import types
import typing


def _coerce_value(value, annotation):
    """Best-effort coercion of *value* to the declared *annotation* type.

    Handles the most common field types used in the dataclasses:
      int, float, bool, str, int | None  (Python 3.10 union syntax)
    Falls back to returning the original value on any error so callers
    never raise — bad values surface as validation errors later.
    """
    if value is None:
        return None
    # Unwrap  X | None  (Python 3.10+ UnionType)
    if isinstance(annotation, types.UnionType):
        non_none = [a for a in annotation.__args__ if a is not type(None)]
        annotation = non_none[0] if non_none else annotation
    # Unwrap  Optional[X]  / Union[X, None]  (typing module)
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        non_none = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = non_none[0] if non_none else annotation
    if annotation is int:
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return value
    if annotation is float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    if annotation is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if annotation is str:
        return str(value)
    return value


@dataclass
class UserProfile:
    """Personal and residency details."""
    name: str = "My Profile"
    nationality: str = "JP"                       # ISO 3166-1 alpha-2
    residency_status: str = "permanent_resident"  # citizen | permanent_resident | long_term | spouse_visa | other
    is_tax_resident: bool = True
    treaty_country: str | None = None             # e.g. "United States" — for totalization / DTA notes
    prefecture: str = "Tokyo"
    municipality_key: str = "tokyo_shinjuku"      # key into nhi_rates.json


@dataclass
class FinancialProfile:
    """
    Complete financial snapshot for FIRE calculations.

    Fields are grouped by phase:
      - Identity / timing
      - Current income and taxes
      - Current assets (by account type)
      - Monthly cash flows
      - Japan pension details
      - iDeCo
      - NISA
      - Foreign assets and FX
      - Real estate
    """
    # --- Identity / timing --------------------------------------------------
    current_age: int = 35
    target_retirement_age: int = 50
    employment_type: str = "company_employee"     # matches iDeCo limit keys

    # --- Income -------------------------------------------------------------
    annual_gross_income_jpy: int = 8_000_000
    has_spouse: bool = False
    spouse_income_jpy: int = 0
    num_dependents: int = 0

    # Social insurance paid (社会保険料) — used as income deduction.
    # Approximate: ~14% of gross for a standard company employee.
    social_insurance_annual_jpy: int = 0

    # --- Current assets (market value) ------------------------------------
    nisa_balance_jpy: int = 0
    nisa_lifetime_used_jpy: int = 0               # acquisition cost used of the 18M cap
    ideco_balance_jpy: int = 0
    taxable_brokerage_jpy: int = 0
    cash_savings_jpy: int = 0
    foreign_assets_usd: float = 0.0               # USD-denominated (e.g. US ETFs, foreign bank)

    # --- Monthly cash flows ------------------------------------------------
    monthly_expenses_jpy: int = 250_000
    monthly_nisa_contribution_jpy: int = 100_000  # tsumitate (積立) frame — max ¥120k/mo
    nisa_growth_frame_annual_jpy: int = 0         # growth (成長投資枠) frame — max ¥2.4M/yr
    # Note: the new NISA (2024+) has two frames:
    #   - Tsumitate (monthly_nisa_contribution_jpy): up to ¥1.2M/yr for index funds
    #   - Growth (nisa_growth_frame_annual_jpy): up to ¥2.4M/yr for stocks/ETFs
    # Combined lifetime cap is ¥18M. These are separate from iDeCo.
    ideco_monthly_contribution_jpy: int = 23_000

    # --- Japan pension ------------------------------------------------------
    # Months paying into kokumin or kosei nenkin up to today.
    nenkin_contribution_months: int = 0
    # If user has a NenkinNet estimate for kosei nenkin, use it directly.
    # Otherwise we estimate from avg_standard_remuneration × remaining months.
    nenkin_net_kosei_annual_jpy: int | None = None
    avg_standard_monthly_remuneration_jpy: int = 0  # 標準報酬月額 for kosei formula
    nenkin_claim_age: int = 65                    # when to start drawing (60–75)

    # Foreign pension income (e.g. US Social Security, UK state pension)
    foreign_pension_annual_jpy: int = 0
    foreign_pension_start_age: int = 67

    # --- Foreigners mode ----------------------------------------------------
    nationality: str = "JP"                       # ISO 3166-1 alpha-2 (e.g. "US", "GB", "JP")
    residency_status: str = "permanent_resident"  # citizen | permanent_resident | long_term_resident | spouse_visa | work_visa | student_visa | other
    treaty_country: str = ""                      # e.g. "United States" — for DTA/totalization notes
    years_in_japan: int = 10                      # approximate years resident in Japan

    # --- iDeCo --------------------------------------------------------------
    ideco_start_age: int | None = None            # if None, assumed current_age

    # --- NISA ---------------------------------------------------------------
    # (contributions defined in monthly cash flows above)

    # --- Foreign assets / FX ------------------------------------------------
    usd_jpy_rate: float = 150.0

    # --- Real estate --------------------------------------------------------
    owns_property: bool = False
    property_value_jpy: int = 0
    mortgage_balance_jpy: int = 0
    monthly_mortgage_payment_jpy: int = 0
    rental_income_monthly_jpy: int = 0
    property_paid_off_at_retirement: bool = False
    property_planned_sale_age: int | None = None  # age to sell Japan property (None = keep)
    property_appreciation_pct: float = 0.0        # expected annual appreciation % (e.g. 1.0 = 1%)

    # --- Foreign real estate ------------------------------------------------
    owns_foreign_property: bool = False
    foreign_property_value_jpy: int = 0          # combined market value in JPY
    foreign_property_mortgage_jpy: int = 0       # outstanding mortgage in JPY
    foreign_property_rental_monthly_jpy: int = 0  # monthly net rental income in JPY
    foreign_property_planned_sale_age: int | None = None  # age to sell overseas property
    foreign_property_appreciation_pct: float = 0.0        # expected annual appreciation %

    # --- Other / alternative assets -----------------------------------------
    gold_silver_value_jpy: int = 0               # gold, silver, precious metals
    crypto_value_jpy: int = 0                    # cryptocurrency (BTC, ETH, etc.)
    rsu_unvested_value_jpy: int = 0              # current fair-market value of unvested RSUs
    rsu_vesting_annual_jpy: int = 0              # expected annual vest while still employed
    other_assets_jpy: int = 0                    # other (business equity, art, collectibles…)

    # --- Helpers ------------------------------------------------------------

    @property
    def years_to_retirement(self) -> int:
        return max(0, self.target_retirement_age - self.current_age)

    @property
    def total_liquid_assets_jpy(self) -> int:
        """Liquid and semi-liquid investable assets at current prices (excludes real estate)."""
        foreign_jpy = int(self.foreign_assets_usd * self.usd_jpy_rate)
        return (
            self.nisa_balance_jpy
            + self.ideco_balance_jpy
            + self.taxable_brokerage_jpy
            + self.cash_savings_jpy
            + foreign_jpy
            + self.gold_silver_value_jpy
            + self.crypto_value_jpy
            + self.rsu_unvested_value_jpy
            + self.other_assets_jpy
        )

    @property
    def monthly_savings_jpy(self) -> int:
        """Estimated monthly investable savings (contributions to tax-advantaged + residual)."""
        return self.monthly_nisa_contribution_jpy + self.ideco_monthly_contribution_jpy

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FinancialProfile":
        try:
            hints = typing.get_type_hints(cls)
        except (TypeError, NameError, AttributeError):
            # TypeError: bad annotation syntax; NameError: unresolved forward ref;
            # AttributeError: broken module-level import in annotation.
            hints = {}
        coerced = {
            k: _coerce_value(v, hints[k]) if k in hints else v
            for k, v in data.items()
            if k in cls.__dataclass_fields__
        }
        return cls(**coerced)
