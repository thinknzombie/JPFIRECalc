# JPFIRECalc

**A Japan-specific FIRE calculator for people living and working in Japan.**

Generic FIRE calculators assume a 4% withdrawal rate, ignore pension systems, and treat taxes as a flat percentage. Japan has none of that luxury. JPFIRECalc models the variables that actually matter for Japan-based FIRE planning.

🌐 **Live app:** [web-production-362fcc.up.railway.app](https://web-production-362fcc.up.railway.app)

---

## What it models

### Japan Tax System
- Progressive income tax with actual NTA brackets
- Residence tax (10% flat on the prior year's income — including the **year-1 retirement shock**)
- Effective tax rate calculation for current income

### Investment Accounts
- **新NISA** — lifetime investment cap tracking (¥18M), tax-free growth and withdrawal, fully liquid
- **iDeCo** — lock-up until age 60, bridge funding calculation if FIRE target is pre-60
- **Taxable brokerage** — 20.315% capital gains tax on realised gains

### National Health Insurance (NHI / 国民健康保険)
- NHI premium is a non-linear function of your withdrawal amount — JPFIRECalc solves this iteratively
- Municipality-specific rates: Tokyo (Shinjuku/Setagaya), Osaka, Nagoya, Fukuoka, Sapporo, Kyoto, Hiroshima, national average, rural average

### Pension (年金)
- Kokumin nenkin (国民年金) flat-rate estimate from contribution months
- Kosei nenkin (厚生年金) estimate from average standard monthly remuneration
- Manual override for MyNenkin estimated figures
- Deferral modelling: claim age 60–75
- Foreign pension income support

### FIRE Variants
| Variant | Description |
|---|---|
| Regular FIRE | Full portfolio withdrawal at safe withdrawal rate |
| Lean FIRE | Minimal lifestyle, lower expense target |
| Fat FIRE | Generous lifestyle, higher expense target |
| Coast FIRE | Invest enough now; let compounding do the rest |
| Barista FIRE | Part-time income supplements portfolio withdrawals |

### Monte Carlo Simulation
- Up to 10,000 simulation paths
- Sequence-of-returns risk modelling (amplified early-retirement volatility)
- p10 / p25 / p50 / p75 / p90 percentile fan chart
- Portfolio survival success rate

### Sensitivity Analysis
- Tornado chart showing impact of key variables (return rate, withdrawal rate, inflation, expenses, pension) on years to FIRE

### Foreign Residents Mode
- Non-permanent resident (非永住者) tax rules for foreign-source income
- Double Tax Agreement (DTA) treaty notes for 60+ countries
- Totalization agreement detection (reduces double social insurance)
- Exit tax (国外転出時課税) risk warning for portfolios ≥ ¥100M
- NHI eligibility check by residency status

### Cost-of-Living Regions
| Region | Monthly baseline |
|---|---|
| Tokyo | ¥257,000 |
| Osaka | ¥200,000 |
| Nagoya | ¥183,000 |
| Fukuoka / Sapporo | ¥170,000 |
| Secondary city | ¥155,000 |
| Rural (田舎) | ¥127,000 |

---

## Running locally

```bash
git clone https://github.com/thinknzombie/JPFIRECalc.git
cd JPFIRECalc
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

Python 3.12+ recommended.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask 3.1 |
| Calculation engine | NumPy, SciPy, pandas |
| Frontend | Jinja2, Plotly.js, vanilla JS |
| Storage | JSON files (no database) |
| Deployment | Railway (gunicorn, 2 workers) |
| i18n | Client-side EN/JA toggle (localStorage) |

---

## Project structure

```
engine/
  fire_calculator.py      # Core FIRE number, years-to-FIRE, progress
  tax_calculator.py       # Income tax, residence tax, effective rate
  nhi_calculator.py       # NHI premium iterative solver
  pension_calculator.py   # Nenkin estimates, deferral, foreign pension
  ideco_calculator.py     # iDeCo growth, lock-up, bridge calculation
  nisa_calculator.py      # 新NISA cap tracking, growth projection
  monte_carlo.py          # 10,000-path simulation, percentile bands
  sensitivity.py          # Tornado / sensitivity analysis
  foreigners.py           # DTA, exit tax, non-PR, totalization

models/                   # UserProfile, Scenario, AssumptionSet, ScenarioResult
data/                     # tax_brackets.json, nhi_rates.json, pension_constants.json,
                          # region_templates.json (update annually from NTA / nenkin.go.jp)
storage/                  # JSON file CRUD for saved scenarios
routes/                   # Flask blueprints: main, profile, scenarios, api, compare
web/
  templates/              # Jinja2 templates + partials + components
  static/css/style.css    # Design tokens + all styles (dark theme)
  static/js/
    i18n.js               # EN/JA translation dictionary + auto-label translation
    charts.js             # Plotly wrappers: Monte Carlo, tornado, trajectory, comparison
scenarios/                # User scenario JSON files (gitignored)
tests/                    # Per-engine unit tests (pytest)
```

---

## Key Japan FIRE rules of thumb

> These are baked into the calculator's defaults and warnings.

- **Safe withdrawal rate: 3–3.5%** — lower than the US 4% rule due to Japan's historically lower equity returns and higher home-country bias toward JGBs
- **Residence tax shock** — in year 1 of retirement you still pay full residence tax on your last salary; budget an extra ¥200,000–¥600,000
- **iDeCo lock-up** — completely illiquid before age 60; pre-60 FIRE requires 新NISA + taxable brokerage to bridge the gap
- **NHI is withdrawal-dependent** — unlike shakai hoken, NHI is calculated on your declared income, which is driven by how much you withdraw

---

## Data sources (update annually)

| File | Source |
|---|---|
| `data/tax_brackets.json` | [NTA (国税庁)](https://www.nta.go.jp) |
| `data/nhi_rates.json` | Municipal government websites |
| `data/pension_constants.json` | [nenkin.go.jp](https://www.nenkin.go.jp) |
| `data/region_templates.json` | MIC household expenditure survey |

---

## Deployment

Deployed on [Railway](https://railway.app) with auto-deploy on push to `main`.

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "gunicorn 'app:create_app()' --workers 2 --threads 2 --timeout 120"
healthcheckPath = "/"
```

> **Note:** The free Railway plan resets the filesystem on each deploy. Scenarios stored server-side will be lost. Export important scenarios before pushing updates, or upgrade to a persistent volume.

---

## Disclaimer

JPFIRECalc is a planning tool, not financial or tax advice. Tax laws, NHI rates, and pension rules change annually — always verify figures with a Japan-registered tax accountant (税理士) for your specific situation.
