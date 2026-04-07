"""
Global app settings persistence.

Stores user-configurable defaults in a JSON file.
Settings are loaded once at startup and cached in memory.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

from storage._filelock import file_lock

logger = logging.getLogger(__name__)

_SETTINGS_PATH: Path | None = None
_cache: "AppSettings | None" = None


@dataclass
class AppSettings:
    """User-configurable application defaults."""

    # --- Default scenario assumptions (applied to new scenarios) ------------
    default_investment_return_pct: float = 5.0
    default_retirement_return_pct: float = 4.5
    default_withdrawal_rate_pct: float = 3.5
    default_japan_inflation_pct: float = 2.0
    default_return_volatility_pct: float = 15.0
    default_monte_carlo_simulations: int = 10_000
    default_simulation_years: int = 40
    default_sequence_of_returns_risk: bool = True
    default_retirement_expense_growth_pct: float = 1.5
    default_foreign_inflation_pct: float = 2.5
    default_fire_variant: str = "regular"
    default_region: str = "tokyo"
    default_nhi_municipality_key: str = "tokyo_shinjuku"
    default_nhi_household_members: int = 1
    default_usd_jpy_rate: float = 150.0

    # --- Tax override rates ------------------------------------------------
    # These let the user override hardcoded tax rates when the law changes
    # or for scenario planning.  A value of 0 means "use built-in default".
    capital_gains_tax_rate_pct: float = 20.315       # income 15.315% + residence 5%
    reconstruction_surtax_pct: float = 2.1           # on income tax, until 2037
    residence_tax_rate_pct: float = 10.0             # flat municipal + prefectural
    residence_tax_per_capita_jpy: int = 5000         # annual per-capita levy
    mortgage_interest_rate_pct: float = 1.5          # assumed annual mortgage rate

    # --- Display preferences -----------------------------------------------
    currency_display: str = "compact"                # "compact" (億/万) or "full"
    default_language: str = "en"                     # "en" or "ja"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def init_settings(data_dir: Path) -> None:
    """Initialise settings store. Call once at app startup."""
    global _SETTINGS_PATH, _cache
    _SETTINGS_PATH = data_dir / "settings.json"
    _cache = _load()


def _load() -> AppSettings:
    """Load from disk, or return defaults if file doesn't exist."""
    if _SETTINGS_PATH and _SETTINGS_PATH.exists():
        try:
            raw = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            return AppSettings.from_dict(raw)
        except Exception:
            logger.exception("Failed to load settings — using defaults")
    return AppSettings()


def get() -> AppSettings:
    """Return the current settings (cached in memory)."""
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def save(settings: AppSettings) -> None:
    """Persist settings to disk atomically and update the cache."""
    global _cache
    _cache = settings
    if _SETTINGS_PATH:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = _SETTINGS_PATH.with_suffix(".tmp")
        with file_lock(_SETTINGS_PATH):
            try:
                tmp_path.write_text(
                    json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                os.replace(tmp_path, _SETTINGS_PATH)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                raise
