"""
Scenario, AssumptionSet, and ScenarioResult models.

A Scenario bundles a FinancialProfile with a named set of assumptions
and optional overrides. Running a scenario produces a ScenarioResult.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import types
import typing
import uuid


def _coerce_value(value, annotation):
    """Best-effort coercion of *value* to the declared *annotation* type.

    Mirrors the helper in models/profile.py — handles int, float, bool, str,
    and union-with-None variants.  Falls back to the raw value on any error.
    """
    if value is None:
        return None
    if isinstance(annotation, types.UnionType):
        non_none = [a for a in annotation.__args__ if a is not type(None)]
        annotation = non_none[0] if non_none else annotation
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
class AssumptionSet:
    """
    Market and economic assumptions for a FIRE scenario.

    Japan-specific defaults:
      - 5% return (global equity blend, yen-denominated)
      - 2% Japan inflation
      - 3.5% withdrawal rate (conservative vs US 4% rule)
      - 150 USD/JPY
    """
    # Returns
    investment_return_pct: float = 5.0            # pre-retirement annual return
    retirement_return_pct: float = 4.5            # post-retirement (more conservative)
    japan_inflation_pct: float = 2.0

    # Withdrawal
    withdrawal_rate_pct: float = 3.5              # 3.0–4.0 typical range for Japan

    # FX
    usd_jpy_rate: float = 150.0

    # Simulation
    monte_carlo_simulations: int = 10_000
    simulation_years: int = 40
    return_volatility_pct: float = 15.0           # annualised std dev (global equity)
    sequence_of_returns_risk: bool = True

    # NHI
    nhi_municipality_key: str = "tokyo_shinjuku"
    nhi_household_members: int = 1

    # FIRE variant
    fire_variant: str = "regular"                 # lean | regular | fat | coast | barista

    # Lean / Fat FIRE expense overrides (monthly)
    lean_monthly_expenses_jpy: int = 0            # leaner budget — if 0, uses 70% of region template
    fat_monthly_expenses_jpy: int = 0             # generous budget — if 0, uses 150% of region template

    # Barista FIRE
    barista_income_monthly_jpy: int = 0           # part-time income during semi-retirement

    # Coast FIRE target age (if fire_variant == "coast")
    coast_target_retirement_age: int = 65

    # Expense growth in retirement
    retirement_expense_growth_pct: float = 1.5   # typically below general inflation

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AssumptionSet":
        try:
            hints = typing.get_type_hints(cls)
        except Exception:
            hints = {}
        coerced = {
            k: _coerce_value(v, hints[k]) if k in hints else v
            for k, v in data.items()
            if k in cls.__dataclass_fields__
        }
        return cls(**coerced)


@dataclass
class Scenario:
    """
    A named FIRE scenario.

    Stores the assumption set and any profile-level overrides.
    The `overrides` dict can contain any key from FinancialProfile to
    temporarily replace its value for this specific scenario.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Scenario"
    description: str = ""
    region: str = "tokyo"                         # key into region_templates.json
    assumptions: AssumptionSet = field(default_factory=AssumptionSet)
    overrides: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        d = dict(data)
        if "assumptions" in d and isinstance(d["assumptions"], dict):
            d["assumptions"] = AssumptionSet.from_dict(d["assumptions"])
        try:
            hints = typing.get_type_hints(cls)
        except Exception:
            hints = {}
        coerced = {
            k: _coerce_value(v, hints[k]) if k in hints else v
            for k, v in d.items()
            if k in cls.__dataclass_fields__
        }
        return cls(**coerced)


@dataclass
class YearProjection:
    """Single year in the net worth projection trajectory."""
    year: int
    age: int
    phase: str                                    # "accumulation" | "retirement"
    portfolio_value_jpy: int
    # Accumulation phase
    annual_savings_jpy: int = 0
    investment_gain_jpy: int = 0
    # Retirement phase
    gross_withdrawal_jpy: int = 0
    nhi_premium_jpy: int = 0
    pension_income_jpy: int = 0
    net_from_portfolio_jpy: int = 0
    year1_residence_tax_jpy: int = 0


@dataclass
class MonteCarloResult:
    """Percentile bands from Monte Carlo simulation."""
    p10: list[int] = field(default_factory=list)
    p25: list[int] = field(default_factory=list)
    p50: list[int] = field(default_factory=list)
    p75: list[int] = field(default_factory=list)
    p90: list[int] = field(default_factory=list)
    success_rate_pct: float = 0.0
    n_simulations: int = 0


@dataclass
class SensitivityItem:
    """Single variable result from sensitivity analysis.

    Two modes controlled by ``surplus_mode``:
      - **years mode** (default): base/pess/opt are years-to-FIRE.
        Higher = worse, so delta_pessimistic is positive when pess > base.
      - **surplus mode**: base/pess/opt are FIRE surplus %.
        Higher = better, so delta_pessimistic is positive when pess < base
        (surplus dropped).
    """
    variable: str
    label: str
    base_years: float
    pessimistic_years: float
    optimistic_years: float
    delta_pessimistic: float = 0.0
    delta_optimistic: float = 0.0
    surplus_mode: bool = False

    def __post_init__(self):
        if self.surplus_mode:
            # Surplus %: higher = better.
            # Pessimistic delta = how much surplus DROPS (positive = bad).
            self.delta_pessimistic = self.base_years - self.pessimistic_years
            # Optimistic delta = how much surplus RISES (positive = good).
            self.delta_optimistic = self.optimistic_years - self.base_years
        else:
            # Years: higher = worse.
            self.delta_pessimistic = self.pessimistic_years - self.base_years
            self.delta_optimistic = self.base_years - self.optimistic_years


@dataclass
class ScenarioResult:
    """
    Complete output from running a scenario through all engines.

    This is the single object the UI renders.
    """
    scenario_id: str
    scenario_name: str

    # --- Core FIRE metrics --------------------------------------------------
    fire_number_jpy: int = 0                      # target portfolio size
    current_portfolio_jpy: int = 0                # accessible portfolio today
    progress_pct: float = 0.0                     # current / FIRE number
    years_to_fire: float = 0.0
    fire_age: float = 0.0

    # --- FIRE variant -------------------------------------------------------
    fire_variant: str = "regular"                 # which mode drives the hero display

    # --- Coast / Barista / Lean / Fat variants ------------------------------
    coast_fire_number_jpy: int = 0                # needed today to coast to retirement
    coast_fire_reached: bool = False
    barista_fire_number_jpy: int = 0
    barista_income_annual_jpy: int = 0            # part-time income used in barista calc
    lean_fire_number_jpy: int = 0                 # FIRE number at lean budget
    lean_annual_expenses_jpy: int = 0
    fat_fire_number_jpy: int = 0                  # FIRE number at fat budget
    fat_annual_expenses_jpy: int = 0

    # --- Retirement cash flow breakdown ------------------------------------
    annual_expenses_jpy: int = 0
    annual_pension_net_jpy: int = 0               # after-tax pension
    annual_nhi_jpy: int = 0                       # NHI premium at FIRE withdrawal level
    annual_withdrawal_needed_jpy: int = 0         # net from portfolio per year
    year1_residence_tax_shock_jpy: int = 0

    # --- Account balances at retirement ------------------------------------
    nisa_at_retirement_jpy: int = 0
    ideco_at_retirement_jpy: int = 0
    taxable_at_retirement_jpy: int = 0
    ideco_accessible_at_fire: bool = True
    ideco_bridge_needed_jpy: int = 0

    # --- Tax summary --------------------------------------------------------
    current_income_tax_jpy: int = 0
    current_residence_tax_jpy: int = 0
    current_nhi_jpy: int = 0                      # if self-employed / between jobs
    current_effective_tax_rate_pct: float = 0.0

    # --- Projection ---------------------------------------------------------
    trajectory: list[YearProjection] = field(default_factory=list)

    # --- Simulation results -------------------------------------------------
    monte_carlo: MonteCarloResult | None = None
    sensitivity: list[SensitivityItem] = field(default_factory=list)

    # --- Foreigners mode ----------------------------------------------------
    foreigners_warnings: list[str] = field(default_factory=list)
    foreigners_notes: list[str] = field(default_factory=list)
    foreigners_dta_country: str = ""
    foreigners_totalization: bool = False
    foreigners_non_pr: bool = False
    foreigners_exit_tax_risk: bool = False

    # --- Warnings -----------------------------------------------------------
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
