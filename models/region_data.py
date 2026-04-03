"""
Regional cost-of-living template loader.

Loads region templates from data/region_templates.json and provides
helper functions to retrieve and apply them.
"""
from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "region_templates.json", encoding="utf-8") as _f:
    _TEMPLATES = json.load(_f)["regions"]


def get_region_template(region_key: str) -> dict:
    """
    Return the COL template for a region key.
    Falls back to 'tokyo' if the key is not found.
    """
    return _TEMPLATES.get(region_key, _TEMPLATES["tokyo"])


def list_region_keys() -> list[str]:
    return list(_TEMPLATES.keys())


def get_monthly_expenses(region_key: str) -> int:
    """Return the total monthly expense estimate for a region."""
    return get_region_template(region_key)["total_monthly"]


def get_annual_expenses(region_key: str) -> int:
    return get_monthly_expenses(region_key) * 12


def get_nhi_municipality_key(region_key: str) -> str:
    """Return the NHI municipality key associated with a region."""
    return get_region_template(region_key).get("nhi_municipality_key", "national_average")
