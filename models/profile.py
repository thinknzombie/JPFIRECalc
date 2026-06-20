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
import uuid as _uuid


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


# ---------------------------------------------------------------------------
# MortgageEntry — one row per loan (supports split-rate mortgages like
# 柿ノ木坂 land 0.47% + building 0.67% + Crozier 5.5% etc.)
# ---------------------------------------------------------------------------

@dataclass
class MortgageEntry:
    """A single mortgage loan.

    The FinancialProfile model keeps legacy single-loan fields
    (mortgage_balance_jpy, monthly_mortgage_payment_jpy, etc.) for backward
    compatibility. When `FinancialProfile.mortgages` is non-empty, the list
    takes precedence and the engine uses the aggregate properties below.

    For Japanese mortgages, 住宅ローン控除 fields apply; for foreign
    mortgages (is_foreign=True), the tax credit fields are ignored.
    """
    id: str = field(default_factory=lambda: _uuid.uuid4().hex[:8])
    label: str = "Mortgage"
    balance_jpy: int = 0
    interest_rate_pct: float = 0.7
    monthly_payment_jpy: int = 0
    remaining_years: int = 25
    loan_type: str = "variable"                   # "variable" or "fixed"
    is_foreign: bool = False

    # 住宅ローン控除 (Japanese mortgage tax credit) — only used when is_foreign=False
    tax_credit_remaining_years: int = 0
    tax_credit_principal_cap_jpy: int = 30_000_000
    tax_credit_rate_pct: float = 0.7
    prepayment_fee_jpy: int = 0

    @property
    def annual_interest_jpy(self) -> int:
        """Approximate annual interest paid this year (balance × rate)."""
        return int(self.balance_jpy * self.interest_rate_pct / 100)

    @property
    def annual_principal_jpy(self) -> int:
        """Approximate annual principal paid (payment × 12 − interest)."""
        return max(0, self.monthly_payment_jpy * 12 - self.annual_interest_jpy)

    @property
    def annual_tax_credit_jpy(self) -> int:
        """Annual 住宅ローン控除 credit. Only meaningful for Japanese mortgages."""
        if self.is_foreign or self.tax_credit_remaining_years <= 0:
            return 0
        capped_balance = min(self.balance_jpy, self.tax_credit_principal_cap_jpy)
        return int(capped_balance * self.tax_credit_rate_pct / 100)

    @property
    def effective_annual_rate_pct(self) -> float:
        """Net effective rate after tax credit (for Japanese mortgages)."""
        if self.is_foreign or self.balance_jpy <= 0:
            return self.interest_rate_pct
        annual_credit = self.annual_tax_credit_jpy
        if annual_credit <= 0:
            return self.interest_rate_pct
        return max(0.0, self.interest_rate_pct - (annual_credit / self.balance_jpy) * 100)


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
    taxable_brokerage_cost_basis_jpy: int | None = None  # optional cost basis; if None, gains assumed = full balance
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

    # --- Japan mortgage rate & terms ----------------------------------------
    mortgage_interest_rate_pct: float = 0.7          # current annual rate, e.g. 0.7%
    mortgage_type: str = "variable"                   # "variable" or "fixed"
    mortgage_remaining_years: int = 25                # years left on the loan
    mortgage_tax_credit_remaining_years: int = 0      # 住宅ローン控除 years left (0 if expired)
    mortgage_tax_credit_principal_cap_jpy: int = 30_000_000  # ¥30M default, up to ¥50M for 認定長期優良
    mortgage_tax_credit_rate_pct: float = 0.7         # 0.7% standard (2024+ rules)
    mortgage_prepayment_fee_jpy: int = 0              # one-time fee for lump-sum payoff

    # --- Foreign mortgage rate & terms --------------------------------------
    foreign_mortgage_interest_rate_pct: float = 0.0
    foreign_mortgage_type: str = "fixed"
    foreign_mortgage_remaining_years: int = 0

    # --- Mortgages list (per-loan) ------------------------------------------
    # When non-empty, this list takes precedence over the legacy single-loan
    # fields above. The aggregate properties below read from this list.
    # Each entry supports split-rate scenarios like
    # 柿ノ木坂 land 0.47% + building 0.67% + Crozier 5.5%.
    mortgages: list[MortgageEntry] = field(default_factory=list)

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
    rsu_liquidated_at_fire_jpy: int = 0          # equity/RSU shares liquidated in FIRE year (sold to fund retirement)
    other_assets_jpy: int = 0                    # other (business equity, art, collectibles…)

    # --- Validation ---------------------------------------------------------

    def __post_init__(self):
        valid_types = {"variable", "fixed"}
        if self.mortgage_type not in valid_types:
            raise ValueError(f"mortgage_type must be one of {valid_types}, got {self.mortgage_type!r}")
        if self.foreign_mortgage_type not in valid_types:
            raise ValueError(f"foreign_mortgage_type must be one of {valid_types}, got {self.foreign_mortgage_type!r}")
        for attr in ("mortgage_interest_rate_pct", "mortgage_tax_credit_rate_pct",
                     "foreign_mortgage_interest_rate_pct"):
            v = getattr(self, attr)
            if not (0 <= v <= 20):
                raise ValueError(f"{attr} must be between 0 and 20, got {v}")
        if self.mortgage_remaining_years < 0:
            raise ValueError(f"mortgage_remaining_years must be >= 0, got {self.mortgage_remaining_years}")
        if self.foreign_mortgage_remaining_years < 0:
            raise ValueError(f"foreign_mortgage_remaining_years must be >= 0, got {self.foreign_mortgage_remaining_years}")

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

    # --- Aggregate mortgage properties (single source of truth for the engine) ---
    # These read from the per-loan `mortgages` list if populated, otherwise
    # fall back to the legacy single-loan fields. Engine callers should
    # always use these properties instead of reading the legacy fields
    # directly — this guarantees split-rate mortgages are modelled correctly.

    @property
    def total_mortgage_balance_jpy(self) -> int:
        """Sum of all mortgage balances across the list (or legacy single field)."""
        if self.mortgages:
            return sum(max(0, m.balance_jpy) for m in self.mortgages)
        return max(0, self.mortgage_balance_jpy)

    @property
    def total_mortgage_payment_monthly_jpy(self) -> int:
        """Sum of all monthly mortgage payments (list or legacy single field)."""
        if self.mortgages:
            return sum(max(0, m.monthly_payment_jpy) for m in self.mortgages)
        return max(0, self.monthly_mortgage_payment_jpy)

    @property
    def weighted_avg_mortgage_rate_pct(self) -> float:
        """Balance-weighted average interest rate across all loans.

        Returns 0.0 if no balance. For a single loan, this equals its rate.
        For split-rate mortgages, this gives the true cost of capital.
        """
        if self.mortgages:
            total = self.total_mortgage_balance_jpy
            if total <= 0:
                return 0.0
            return sum(
                max(0, m.balance_jpy) * m.interest_rate_pct for m in self.mortgages
            ) / total
        return self.mortgage_interest_rate_pct

    @property
    def total_annual_mortgage_tax_credit_jpy(self) -> int:
        """Sum of 住宅ローン控除 credits across all Japanese mortgages in the list."""
        if self.mortgages:
            return sum(m.annual_tax_credit_jpy for m in self.mortgages if not m.is_foreign)
        # Legacy single-loan: compute manually
        if self.mortgage_tax_credit_remaining_years > 0 and self.mortgage_balance_jpy > 0:
            capped = min(self.mortgage_balance_jpy, self.mortgage_tax_credit_principal_cap_jpy)
            return int(capped * self.mortgage_tax_credit_rate_pct / 100)
        return 0

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
        coerced: dict = {}
        for k, v in data.items():
            if k not in cls.__dataclass_fields__:
                continue
            # Special-case: nested MortgageEntry list — coerce each dict entry
            if k == "mortgages":
                coerced[k] = _coerce_mortgage_list(v)
                continue
            coerced[k] = _coerce_value(v, hints[k]) if k in hints else v
        # Back-compat: if mortgages list is empty but legacy single-loan
        # fields are populated, synthesise a single-entry list so engine
        # aggregate properties work uniformly. Skip if mortgage_balance is 0.
        if not coerced.get("mortgages") and (
            coerced.get("mortgage_balance_jpy", 0) > 0
            or coerced.get("monthly_mortgage_payment_jpy", 0) > 0
        ):
            coerced["mortgages"] = [_synthesise_legacy_mortgage(coerced)]
        return cls(**coerced)


def _coerce_mortgage_list(value):
    """Convert raw list of dicts into list[MortgageEntry]."""
    if not value:
        return []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, MortgageEntry):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            out.append(MortgageEntry(**item))
        except (TypeError, ValueError):
            # Drop malformed entries silently — caller's validation
            # surfaces the real error if needed
            continue
    return out


def _synthesise_legacy_mortgage(coerced: dict) -> MortgageEntry:
    """Build a single MortgageEntry from the legacy single-loan fields."""
    return MortgageEntry(
        id="legacy",
        label="Primary mortgage (legacy)",
        balance_jpy=coerced.get("mortgage_balance_jpy", 0),
        interest_rate_pct=coerced.get("mortgage_interest_rate_pct", 0.7),
        monthly_payment_jpy=coerced.get("monthly_mortgage_payment_jpy", 0),
        remaining_years=coerced.get("mortgage_remaining_years", 25),
        loan_type=coerced.get("mortgage_type", "variable"),
        is_foreign=False,
        tax_credit_remaining_years=coerced.get("mortgage_tax_credit_remaining_years", 0),
        tax_credit_principal_cap_jpy=coerced.get("mortgage_tax_credit_principal_cap_jpy", 30_000_000),
        tax_credit_rate_pct=coerced.get("mortgage_tax_credit_rate_pct", 0.7),
        prepayment_fee_jpy=coerced.get("mortgage_prepayment_fee_jpy", 0),
    )
