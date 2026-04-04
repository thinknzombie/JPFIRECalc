"""
JSON file-backed scenario store.

Each scenario is saved as a single JSON file named {scenario_id}.json in the
SCENARIOS_DIR. The profile (FinancialProfile) is stored alongside the scenario
so that a complete calculation can be re-run from disk.

Public API:
  save(profile, scenario)     → writes {id}.json atomically, returns scenario.id
  load(scenario_id)           → (FinancialProfile, Scenario)
  load_all()                  → list[(FinancialProfile, Scenario)] sorted by mtime desc
  delete(scenario_id)         → bool (True if deleted, False if not found)
  exists(scenario_id)         → bool
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from models.profile import FinancialProfile
from models.scenario import Scenario

logger = logging.getLogger(__name__)

# Sentinel — routes inject the real path via init_store()
_SCENARIOS_DIR: Path | None = None

# UUID4 pattern — all scenario IDs are generated with uuid.uuid4(), so any
# ID that doesn't match is either corrupt or a path-traversal attempt.
_UUID4_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def _validate_id(scenario_id: str) -> None:
    """Raise ValueError if scenario_id is not a valid UUID4 string."""
    if not isinstance(scenario_id, str) or not _UUID4_RE.match(scenario_id):
        raise ValueError(f"Invalid scenario ID: {scenario_id!r}")


def init_store(scenarios_dir: Path) -> None:
    """Call once from app factory after config is loaded."""
    global _SCENARIOS_DIR
    _SCENARIOS_DIR = scenarios_dir
    _SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)


def _dir() -> Path:
    if _SCENARIOS_DIR is None:
        raise RuntimeError("scenario_store not initialised — call init_store() first")
    return _SCENARIOS_DIR


def _path(scenario_id: str) -> Path:
    """Return the file path for a scenario ID, rejecting non-UUID4 values."""
    _validate_id(scenario_id)
    return _dir() / f"{scenario_id}.json"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save(profile: FinancialProfile, scenario: Scenario) -> str:
    """
    Persist profile + scenario to disk using an atomic write.

    Writes to a .tmp file first, then renames to the final path.
    On Linux (Railway), os.replace() is atomic at the filesystem level,
    so a crash mid-write never leaves a corrupt .json file behind.

    Returns the scenario ID so callers can redirect to the detail page.
    """
    payload = {
        "profile": profile.to_dict(),
        "scenario": scenario.to_dict(),
    }
    final_path = _path(scenario.id)
    tmp_path = final_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, final_path)  # atomic on POSIX; best-effort on Windows
    except Exception:
        # Clean up the temp file if anything went wrong before the rename
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
    return scenario.id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load(scenario_id: str) -> tuple[FinancialProfile, Scenario]:
    """Load a single scenario by ID. Raises FileNotFoundError if absent."""
    p = _path(scenario_id)
    if not p.exists():
        raise FileNotFoundError(f"Scenario {scenario_id!r} not found")
    payload = json.loads(p.read_text(encoding="utf-8"))
    profile = FinancialProfile.from_dict(payload["profile"])
    scenario = Scenario.from_dict(payload["scenario"])
    return profile, scenario


def load_all() -> list[tuple[FinancialProfile, Scenario]]:
    """
    Return all saved scenarios, newest first (by file mtime).

    Corrupt or unreadable files are skipped and logged as warnings so they
    show up in Railway logs without crashing the dashboard.
    """
    results: list[tuple[float, FinancialProfile, Scenario]] = []
    for p in _dir().glob("*.json"):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            profile = FinancialProfile.from_dict(payload["profile"])
            scenario = Scenario.from_dict(payload["scenario"])
            results.append((p.stat().st_mtime, profile, scenario))
        except Exception as exc:
            logger.warning("Skipping corrupt scenario file %s: %s", p.name, exc)
            continue
    results.sort(key=lambda x: x[0], reverse=True)
    return [(profile, scenario) for _, profile, scenario in results]


# ---------------------------------------------------------------------------
# Delete / existence
# ---------------------------------------------------------------------------

def delete(scenario_id: str) -> bool:
    """Delete a scenario file. Returns True if deleted, False if not found."""
    p = _path(scenario_id)
    if p.exists():
        p.unlink()
        return True
    return False


def exists(scenario_id: str) -> bool:
    return _path(scenario_id).exists()
