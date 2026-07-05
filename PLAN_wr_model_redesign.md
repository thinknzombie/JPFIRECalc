# PLAN: Withdrawal-Rate Model Redesign ("Model B1'")

**Author:** Fable 5 (strategic architect) — 2026-07-05
**Implementer:** Sonnet 5 — one phase per session/prompt, in order
**Status:** Approved direction from Andrew (B1 + deemed-WR check); decisions D1–D6 below
carry recommended defaults — confirm any deviation with Andrew before coding.

---

## 1. Problem statement

The app currently runs **two unrelated spending models** and lets them contradict each other:

- **Model A (what the engine simulates):** the user types `monthly_expenses_jpy`; Monte
  Carlo and the deterministic trajectory withdraw *that stated amount* every year. The
  Withdrawal Rate (WR) is used **only** as a divisor to size the FIRE Number
  (`(expenses − pension + NHI) / WR`) and never reaches the simulation.
- **Model B (what parts of the UI imply):** the "Monthly Drawdown Capacity" panel
  (`results.html` ~line 117) computes `current_portfolio × WR` and presents it as "Max
  monthly spend" — implying WR defines the actual draw. Monte Carlo never tests that number.

Consequences observed and reproduced this session:
- Changing WR does not move MC success at all (correct under Model A, baffling to the user).
- Two scenarios differing only in WR (5.0% vs 3.5%) showed MC success 91.0% vs 90.7% —
  pure sampling noise (`seed=None`, ±0.5pp per render) misread as "higher WR is safer."
- `find_safe_withdrawal_rate()` (`engine/monte_carlo.py:422`) **ignores its
  `annual_expenses_jpy` parameter entirely** (verified: identical output for expenses from
  ¥1M to ¥500M). It tests `portfolio × rate` as the draw — accidentally Model B — so the
  "MC-implied safe WR" warning compares a Model-B number against a Model-A simulation.
  A ¥500M portfolio spending ¥3M/yr (99.9% real success) gets told its 3.5% WR is unsafe.

**Andrew's decision:** adopt **B1** — WR defines the actual portfolio draw
(`portfolio × WR` = "the amount of cash the user withdraws from their nest egg… the upper
limit… show the user how much money they can hope to live on and then model that across
the MCs") — plus a **deemed-WR check**: if stated expenses exceed what the chosen WR
supports, warn and tell the user what WR their actual spending implies.

---

## 2. Target model spec ("B1' — WR sets the lifestyle budget")

Let:
- `P₀` = accessible portfolio at retirement start (for MC: `current_portfolio`, the
  retire-now framing — see D3)
- `WR` = `assumptions.withdrawal_rate_pct / 100`
- `g` = `assumptions.retirement_expense_growth_pct / 100`
- `pension_t` = nominal net pension in retirement year t (Japan grows 1%/yr from claim
  start; foreign at `foreign_inflation_pct` — existing mechanics, unchanged)
- `NHI_t` = existing income-based NHI schedule (unchanged)

**Core formulas:**

```
wr_budget_annual   = int(P₀ × WR)                      # the lifestyle the WR funds, set once
lifestyle_t        = wr_budget_annual × (1+g)^t         # inflated thereafter (constant-real)
portfolio_draw_t   = max(0, lifestyle_t + NHI_t − pension_t)
portfolio_{t+1}    = portfolio_t × R_t − portfolio_draw_t   (+ lump sums / emergency logic, unchanged)
```

**Deemed WR (the check Andrew asked for):**

```
deemed_wr_gap_pct    = (active_stated_expenses + NHI_gap) / P₀ × 100          # pre-pension years
deemed_wr_steady_pct = max(0, active_stated_expenses + NHI_steady − net_pension) / P₀ × 100
```

Warning fires when `deemed_wr_gap_pct > withdrawal_rate_pct` (gap years are the binding
constraint). Message must state: stated spending ¥X/yr, WR budget ¥Y/yr at Z%, and "your
actual spending implies a ~W% withdrawal rate." When under budget, show the surplus as
positive info instead (¥/mo headroom).

**What `monthly_expenses_jpy` (stated expenses) is still for:** FIRE-number sizing (goal:
grow the portfolio until `expenses ≤ portfolio × WR + pension`), the deemed-WR check, and
lifestyle-vs-budget displays. It **never** drives MC or trajectory draws again.

**Key implementation insight (verified):** `run_simulation()` already implements exactly
these mechanics — `annual_withdrawal_jpy` inflated by `inflation_rate`, minus pension
schedules, plus `extra_expense_schedule` (NHI). The engine change is *which value* is
passed (`wr_budget_annual` instead of `active_mc_expenses`), not new simulation code.

---

## 3. Design decisions (defaults chosen; deviate only with Andrew's sign-off)

| # | Decision | Default | Rationale / risk |
|---|---|---|---|
| **D1** | MC success semantics change from "will my stated spending survive" to "**is this WR policy sustainable**." Success becomes ~scale-invariant (a 15%-progress user drawing 3.5% of a small pot can show high success while unable to live on it). | Accept. | This is exactly what Andrew asked for, and it finally makes the WR slider move MC success in the intuitive direction. **The deemed-WR check carries the "but can you actually live on it" message — UI copy must pair the two or users will misread high success as "plan funded."** |
| **D2** | Pension **offsets the draw** when it starts (lifestyle held constant-real; portfolio outflow drops at claim age). | Accept. | Alternative (keep drawing full WR% and let pension boost lifestyle) would make pension irrelevant to MC survival — contradicts the app's core "pension offset is critical" philosophy. |
| **D3** | MC keeps the **retire-now framing**: `P₀ = current_portfolio`, year 0 = retirement. Pre-FIRE users see "if you retired today on this WR." | Accept for now. | Full lifecycle MC (stochastic accumulation → per-path draw at target age) is the eventual right model — Phase-5 backlog, not this redesign. Label the chart/copy honestly. |
| **D4** | Income streams active at retirement start (barista, rental) are considered baked into the lifestyle the user chose; they offset the draw while active, so they **net-cancel in MC** while running. Mid-retirement *changes* (rental ceasing at property sale) still adjust the draw via the existing `withdrawal_reductions` plumbing. Lean/Fat variants affect **only** FIRE-number targets and the deemed-WR check — MC becomes variant-independent (barista/coast included). | Accept. | Removes the variant/expense entanglement that caused two bugs already. `active_annual_expenses_jpy` fields stay (deemed-WR + display), but `active_mc_expenses` stops feeding MC. |
| **D5** | `monthly_expenses_jpy` retained with the roles listed in §2. No schema change, no migration. | Accept. | Old saved scenarios load unchanged; cached dashboard summaries self-heal on next view. |
| **D6** | **Fix the seed:** default `seed=42` for all engine MC calls (main run + safe-WR search). Same scenario re-rendered → identical numbers; compared scenarios share random paths (common-random-numbers → WR deltas are pure signal). | Accept. | Optional later: `mc_seed` assumption field + "re-roll" UI. Phase-5 backlog. |

---

## 4. Current-state anchor map (verified 2026-07-05)

| Concern | Location |
|---|---|
| WR → FIRE number only | `engine/fire_calculator.py:632,912,1014,1098,1117` |
| MC receives stated expenses | `fire_calculator.py` `active_mc_expenses` branch (~1161–1197) → `run_monte_carlo(annual_expenses_jpy=…)` (~1474) |
| MC mechanics (reusable as-is) | `engine/monte_carlo.py:run_simulation` — `annual_withdrawal_jpy` (~41), inflation (~150), pension schedules, `extra_expense_schedule` |
| Trajectory draw = stated expenses | `fire_calculator.py:project_net_worth` `net_need_this_year` (~859) |
| Broken safe-WR finder | `monte_carlo.py:422` — `annual_expenses_jpy` unused; hardcoded `inflation_rate` default; no NHI schedule/foreign pension |
| Safe-WR warning (apples/oranges today) | `fire_calculator.py:~1500–1551` |
| seed=None (noise) | `fire_calculator.py:1488` (main MC); safe-WR call uses seed=42 already |
| "Max monthly spend" panel (Model-B display) | `web/templates/partials/results.html:111–151` |
| Retirement Cash Flow card | `results.html:~236` |
| Year-by-year table + CSV | `results.html:~605`; `routes/scenarios.py:cashflow_csv`; `YearProjection.expenses_jpy` |
| Compare page rows | `web/templates/compare.html` (+ `routes/compare.py` `/api`) |
| Report | `engine/report_generator.py:146–190` (drawdown capacity), `~290–310` (FIRE breakdown), `~345–410` (MC section incl. "levers") |
| i18n | `web/static/js/i18n.js` — EN ~40–360, JA ~570–770; **gotcha:** `applyTranslations()` wipes dynamic Jinja content inside `data-i18n` elements — keep dynamic text in sibling spans |
| Sensitivity (unaffected mechanically) | `engine/sensitivity.py` |
| Settings/API (unaffected) | `routes/settings.py`, `routes/api.py:/fire-number` |

---

## 5. Phased implementation — prompts for Sonnet 5

Run phases in order. After each: full `pytest` (currently 391 passing), then browser
verification via preview tools. Commit per phase with the established message style
(`Co-Authored-By: Claude <model> <noreply@anthropic.com>`). Do not push until Andrew says so.

---

### Phase 0 — Determinism (small, independent, ship first)

> **Prompt for Sonnet 5:**
>
> In `E:\Programming\JPFIRECalc`, read `PLAN_wr_model_redesign.md` §1–§4 for context.
> Task: make Monte Carlo results deterministic per scenario render.
>
> 1. In `engine/fire_calculator.py`, define `DEFAULT_MC_SEED = 42` at module level and
>    pass `seed=DEFAULT_MC_SEED` to the main `run_monte_carlo(...)` call (currently
>    `seed=None` around line 1488). Leave the `find_safe_withdrawal_rate` call's existing
>    `seed=42` as is.
> 2. Add a comment explaining *why*: stable numbers across re-renders, and common random
>    numbers across compared scenarios so deltas between scenarios are signal, not noise.
> 3. Tests (`tests/test_accuracy_fixes.py` or a new file): (a) running `run_fire_scenario`
>    twice on identical inputs yields identical `monte_carlo.success_rate_pct` and `p50`;
>    (b) two scenarios differing only in an inert field also match each other exactly.
> 4. Full pytest; browser-verify one scenario page reloads with an unchanged MC success rate.
>
> Acceptance: same scenario re-rendered → byte-identical MC outputs; suite green.

---

### Phase 1 — Engine core: B1' draw model, deemed WR, safe-WR rewrite

> **Prompt for Sonnet 5:**
>
> In `E:\Programming\JPFIRECalc`, read `PLAN_wr_model_redesign.md` **in full** — especially
> §2 (formulas) and §3 (decisions D1–D6). Implement the engine side of Model B1'.
> `run_simulation()` mechanics must not change — only what is passed into it.
>
> **1. `run_fire_scenario` (`engine/fire_calculator.py`):**
>    - Compute `wr_budget_annual = int(current_portfolio * withdrawal_rate)` after the
>      portfolio is final (after property-sale pre-retirement boosts, ~line 1400).
>    - Pass `annual_expenses_jpy=wr_budget_annual` to `run_monte_carlo` instead of
>      `active_mc_expenses`. Keep pension args, `nhi_schedule`, lump sums, withdrawal
>      reductions, mortgage args unchanged. Per D4: `mc_nhi_extra_income` (barista salary
>      → NHI base) stays; barista income no longer subtracts from MC expenses.
>    - Keep every FIRE-number / variant computation exactly as-is (Model A remains the
>      goal-sizing layer). `active_annual_expenses_jpy` etc. stay on ScenarioResult.
>    - New `ScenarioResult` fields (`models/scenario.py`, with defaults so old cached
>      summaries load): `wr_budget_annual_jpy: int = 0`,
>      `deemed_wr_gap_pct: float = 0.0`, `deemed_wr_steady_pct: float = 0.0`.
>      Compute per §2 using `active_annual_expenses_jpy`, `annual_nhi_gap_jpy`,
>      `annual_nhi_jpy`, `annual_pension_net_jpy`, `current_portfolio` (guard ÷0).
>    - Warnings: if `deemed_wr_gap_pct > withdrawal_rate_pct + 0.05`, append the
>      deemed-WR warning (state all three numbers: stated spend, WR budget, deemed WR).
>      Otherwise append the headroom info line (¥/mo surplus). Replace the old
>      "MC-implied safe rate" warning pair with a comparison of chosen WR vs the (now
>      coherent) safe WR from step 3.
>
> **2. `project_net_worth` (`engine/fire_calculator.py`):**
>    - At the first retirement year, set `lifestyle_base = int(portfolio_at_that_point *
>      withdrawal_rate)` (portfolio value in the trajectory at that year, before the draw).
>    - Replace the expense side: `lifestyle_t = lifestyle_base × (1+g)^retirement_year`;
>      `net_need_this_year = max(0, lifestyle_t − pension_this_year)`;
>      `net_from_portfolio = net_need_this_year + nhi_this_year (+ year-1 shock)`.
>      Rental-cessation adjustments keep working: add `rental_adjustment` (inflated the
>      same way it is today) to `lifestyle_t` — an income stream ending raises the draw.
>    - Rename `YearProjection.expenses_jpy` → `lifestyle_budget_jpy` (grep-update every
>      consumer: results.html table, `routes/scenarios.py` CSV, report generator).
>      Semantics: "the WR-funded lifestyle for this year."
>
> **3. Rewrite `find_safe_withdrawal_rate` (`engine/monte_carlo.py:422`):**
>    - Binary search over `wr`; per iteration the draw is `int(initial_portfolio_jpy*wr)`
>      passed as `annual_withdrawal_jpy`, with pension args, and NEW pass-through params:
>      `inflation_rate`, `extra_expense_schedule`, `foreign_pension_*` — mirroring
>      `run_monte_carlo`. Drop the now-meaningless `annual_expenses_jpy` param (update the
>      one call site in `fire_calculator.py` ~1507 to pass the NHI schedule +
>      `retirement_expense_growth_pct` + foreign pension args; and update
>      `tests/test_monte_carlo.py::TestFindSafeWithdrawalRate` signatures).
>    - Result: "safe WR" and chosen WR are finally the same kind of number.
>
> **4. Tests (new class in `tests/test_accuracy_fixes.py` or `tests/test_wr_model.py`):**
>    - **WR monotonicity:** identical inputs, fixed seed — `success(5.0%) <
>      success(3.0%)` strictly.
>    - **Pension helps:** same inputs ± pension — success higher with pension.
>    - **Scale ~invariance (documents D1):** pension=0, same WR, P₀=¥50M vs ¥500M —
>      success within ~1pp.
>    - **Deemed WR arithmetic:** hand-computed case; warning present when stated > budget,
>      headroom line when under.
>    - **Safe-WR coherence:** run the main MC at the returned safe rate → success within
>      ~2pp of the target.
>    - **Trajectory:** first retirement year's `net_from_portfolio ≈ lifestyle_base +
>      NHI − pension (floor 0) + year-1 shock`; `lifestyle_budget_jpy` inflates at g.
>    - Update any existing tests that assert Model-A MC behavior (expense-driven draws) —
>      they should be updated to the new semantics, not deleted; keep the emergency-
>      liquidation and extra-expense-schedule tests passing unchanged.
>
> Full pytest must pass. Do NOT touch templates/i18n/report yet (Phase 2) beyond the
> mechanical `lifestyle_budget_jpy` rename.
>
> Acceptance: WR slider now moves MC success in the intuitive direction; deemed-WR fields
> populated; safe-WR warning compares like-for-like; suite green.

---

### Phase 2 — Surfaces: results page, compare page, report, i18n

> **Prompt for Sonnet 5:**
>
> Read `PLAN_wr_model_redesign.md` §2–§3 (especially D1's UX risk) and the Phase-1 diff.
> Update every user-facing surface to the B1' model. **i18n gotcha:** `applyTranslations()`
> replaces the full text of any `data-i18n` element — keep dynamic Jinja values in sibling
> `<span>`s, never inside the translated element.
>
> **1. `web/templates/partials/results.html`:**
>    - Promote the "Monthly Drawdown Capacity" panel to the primary cash-flow story:
>      "Your WR budget" = `result.wr_budget_annual_jpy` (show /mo and /yr; before-pension
>      net of `annual_nhi_gap_jpy`, after-pension adding pension net of `annual_nhi_jpy`).
>      It must read from the new result fields, not recompute portfolio×WR in Jinja.
>    - Rework the "Retirement Cash Flow" card to show: WR budget (funded lifestyle) →
>      pension offset → NHI (gap/steady) → net portfolio draw/yr (= what MC simulates),
>      then a comparison block: stated expenses (variant-labeled, existing
>      `active_annual_expenses_jpy`) vs budget → surplus ¥/mo or shortfall + deemed WR
>      (`deemed_wr_gap_pct` / `deemed_wr_steady_pct`). Reuse the existing warning styling.
>    - MC card: add one line under the success badge: "Simulates drawing
>      ¥{wr_budget}/yr (your {WR}% of ¥{portfolio}) — not your stated expenses." Update
>      the `chart.mc.*` info-panel copy to the new semantics (success = sustainability of
>      the WR policy; the deemed-WR check tells you whether that budget covers your life).
>    - Year-by-year table + CSV: header "Expenses" → "WR Budget" (`lifestyle_budget_jpy`).
>
> **2. `web/templates/compare.html` (+ `routes/compare.py` `/api` payload):**
>    - Cash-flow group: rows for "WR Budget /yr", "Net Portfolio Draw /yr" (new fields),
>      keep stated-expenses row (variant-labeled), add "Deemed WR (from actual spending)"
>      row vs the "Withdrawal Rate" assumption row so the two are adjacent and comparable.
>
> **3. `engine/report_generator.py`:** Monthly Drawdown Capacity + FIRE Number Breakdown +
>    MC section: same reframing; the "concrete levers" list is now mechanically true
>    (lower WR ⇒ lower draw ⇒ higher success) — rewrite it to reference the actual
>    computed safe WR and deemed WR instead of generic rules of thumb.
>
> **4. `web/static/js/i18n.js`:** add/adjust all new keys in **both** EN and JA
>    (budget, deemed WR, draw, shortfall/headroom, MC subtitle). JA suggestions:
>    WR budget = 「取り崩し予算」, deemed WR = 「実質取り崩し率」, net draw =
>    「ポートフォリオからの実際の引き出し額」.
>
> **5. Dashboard summary (`routes/scenarios.py:_cache_summary`):** add
>    `wr_budget_annual_jpy` and `deemed_wr_gap_pct`; show deemed-WR chip on the card only
>    when it exceeds the chosen WR (danger color).
>
> **6. Browser verification (preview tools, both EN and JA):** scenario page (budget card,
>    MC subtitle, cash-flow table header, CSV), compare page with the two "Andrew"
>    scenarios (WR 5%/6% vs 3.5%/4%): MC success must now *differ in the intuitive
>    direction*, deemed-WR row equal across columns, FIRE numbers differing as before.
>    Screenshot proof. Full pytest.
>
> Acceptance: a user dragging WR sees budget, MC success, and warnings all move together
> coherently; no surface still claims MC simulates stated expenses.

---

### Phase 3 — Docs, regression sweep, ship

> **Prompt for Sonnet 5:**
>
> 1. Update `CLAUDE.md` (Japan Tax Notes / key principles) and `README.md`: WR now defines
>    the simulated portfolio draw (Model B1', see `PLAN_wr_model_redesign.md` §2); stated
>    expenses size the FIRE target and the deemed-WR check. Soften any remaining
>    "3–3.5% is safe" absolutes to reference the computed per-scenario safe WR.
> 2. Append a "SUPERSEDED by PLAN_wr_model_redesign.md Phases 0–2" note to the relevant
>    items in `HANDOFF_monte_carlo_fixes.md`.
> 3. Regression sweep: full pytest; browser pass over dashboard, one regular scenario,
>    one lean scenario, one pre-FIRE scenario (e.g. "Fixed Test" — verify D1 copy makes
>    the high-success/low-budget combination non-misleading), compare page, report.md
>    download, cashflow.csv download.
> 4. Commit per phase if not already done; then (only when Andrew confirms) push to
>    origin main.

---

### Phase 4 — Backlog (do not start without Andrew's explicit go)

- **Lifecycle MC (D3 upgrade):** stochastic accumulation years, per-path draw =
  (per-path portfolio at target age) × WR. Makes pre-FIRE MC success meaningful.
- **`mc_seed` assumption + "re-roll" button** (D6 extension).
- **Log-scale for the compare-page MC median chart** (same crushing issue as the
  trajectory chart fixed 2026-07-05; `renderCompareMC` in `charts.js`).
- **Hero-card i18n bug:** variant-aware `hero_label` is wiped by `applyTranslations()`
  (`results.html` — documented in `HANDOFF_monte_carlo_fixes.md` Item #3).
- **Sanity-check the ¥5.7bn 48-year trajectories** in the "Andrew" scenarios (likely
  legitimate compounding of pension-surplus years at 5.9%: ~¥480M × 1.059⁴⁷ ≈ ¥7bn —
  verify, and consider a chart annotation for "pension exceeds draw from age N").
- **Barista end-age modeling** (income ceasing at pension age raises the draw — D4 note).

---

## 6. Verification protocol (Andrew's own repro, must pass after Phase 2)

Duplicate a scenario, change **only** WR (e.g. 3.5% → 5.0%), compare:

| Row | Expected |
|---|---|
| FIRE Number | differs (unchanged behavior) |
| WR Budget /yr | higher for higher WR |
| Net Portfolio Draw /yr | higher for higher WR |
| **MC Success** | **lower for higher WR — strictly, no noise (fixed seed)** |
| Deemed WR | identical across both columns |
| Stated expenses | identical across both columns |
