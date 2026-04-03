# JPFIRECalc — Claude Code Project Guide

## Repository
https://github.com/thinknzombie/JPFIRECalc

## What This Is
A Japan-focused FIRE (Financial Independence, Retire Early) calculator built for people living and working in Japan. Supports scenario comparison, Monte Carlo simulation, and Japan-specific tax/pension/account modeling.

## Running Locally
```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

## Architecture
- **Backend**: Python 3.12 + Flask 3.x
- **Frontend**: Jinja2 templates + HTMX (partial updates) + Plotly.js (charts)
- **Storage**: JSON files in `scenarios/` (no database)
- **Calculation engine**: `engine/` — zero Flask imports, pure Python dataclasses

## Key Principle
The `engine/` directory must never import Flask. All calculation modules accept plain Python dataclasses and return dataclasses. This keeps the math independently testable.

## Project Structure
```
engine/          # Tax, NHI, pension, iDeCo, NISA, FIRE, Monte Carlo, sensitivity
models/          # UserProfile, FinancialProfile, Scenario, AssumptionSet, ScenarioResult
data/            # Static JSON: tax brackets, NHI rates, pension constants (update annually)
storage/         # JSON file CRUD for saved scenarios
routes/          # Flask blueprints: main, profile, scenarios, api
web/templates/   # Jinja2 templates + partials + components
web/static/      # CSS (design tokens), JS, vendor (htmx, plotly)
scenarios/       # User-saved scenario JSON files (gitignored)
tests/           # Per-engine unit tests
scripts/         # Data update and validation scripts
```

## Japan Tax Notes (Critical)
- Residence tax is billed **one year in arrears** — year-1 retirement shock must be modeled
- NHI premium is a **function of withdrawal amount** — requires iterative solve
- iDeCo is **illiquid until age 60** — warn if FIRE target < 60
- FIRE number = (expenses − pension income) / withdrawal rate — pension offset is critical
- NISA (新NISA) is the primary pre-60 FIRE vehicle: fully liquid, no tax on gains

## Data Files (update annually)
- `data/tax_brackets.json` — income tax brackets and rates
- `data/nhi_rates.json` — NHI rates by municipality
- `data/pension_constants.json` — nenkin calculation constants
- `data/region_templates.json` — COL templates by region
- Sources: NTA (国税庁), municipal websites, nenkin.go.jp
