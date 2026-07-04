# Hand-off: Monte Carlo fixes (2026-07-04)

## UPDATE (later same day): items #1 and #2 below are DONE, committed as `09c45e8`

Both the emergency-lump-sum pull-forward fix and the MC-derived safe-withdrawal-rate
messaging described in this note were implemented and merged — apparently by another
agent/session working against the same tree (commit `09c45e8 "fix: improve FIRE accuracy
and monte carlo modeling"`, authored by `thinknzombie`, contains a merge-conflict trailer
referencing `engine/fire_calculator.py`, `engine/monte_carlo.py`, `models/scenario.py`).
Verified present and working: `emergency_liquidation_pct` on `MonteCarloResult`,
`mc_safe_withdrawal_rate_pct`/`mc_safe_withdrawal_target_pct` on `ScenarioResult`, the
warning text in `fire_calculator.py`, and the corresponding UI in `results.html`
("MC推定の安全な取り崩し率" badge next to the MC chart). 391 tests passing (up from 354 —
`tests/test_monte_carlo.py` was added). The rest of this note (below the original status
section) is kept for historical reference / in case any of the documented edge cases
weren't covered.

**New item added below this update**: a third, unrelated Monte Carlo reporting bug —
variant-blind expense display — found via an external bug report and fixed in this
session. See "Item #3" at the bottom of this note.

## Status of this session's work (original, still accurate for context)

**Already implemented, tests passing, verified in browser:**
- 2025 tax reform data + calc logic fixes (basic deduction net-income base, residence-tax
  base, income-based NHI, iDeCo lump-sum tax, pension-gap discount rate, etc.)
- Dashboard headline stats, year-by-year cash-flow table + CSV export, report additions
- See `tests/test_accuracy_fixes.py` for the regression suite covering all of it.

**This note is about a *separate* piece of work**: an adversarial pass on
the Monte Carlo engine, triggered by the user reporting that MC portfolio charts "bottom out
to zero in the first 5 years after retirement, then jump up and work as expected." Two root
causes were found and diagnosed with reproductions. The user picked a fix approach for
each — both are now implemented (see update above).

---

## Root cause #1 (real bug): ruined paths get resurrected by later lump sums

**File:** `engine/monte_carlo.py`, `run_simulation()`, lines ~255-268 (the main per-year loop).

Once a simulated path's portfolio is floored to ¥0 it is supposed to be *permanently* ruined
— that's what `success_rate_pct` assumes (`min_portfolio > 0` check a few lines below the
loop). But a later **deterministic lump sum** (e.g. a scheduled property sale, passed in via
the `lump_sums` param as `(year_into_retirement, amount)` tuples) is added to **every** path
unconditionally at `portfolios[:, yr+1] += lump_sum_map[yr+1]`, including paths already
sitting at ¥0. That "revives" already-ruined paths.

### Reproduction (already run, don't need to re-derive)

Scenario `scenarios/44384a85-e1d5-4364-a20b-9ab042da1fc8.json` ("Full Test": FIRE age 52,
property sale scheduled at age 58 → retirement year 6, net proceeds ¥67.6M):

```
year  p10          p25          p50
3     0            0            1,778,494
4     0            0            0
5     0            0            0
6     62,404,836   62,404,836   62,404,836   ← percentiles collapse to one value
```

`success_rate_pct` for this scenario is **3.3%** — i.e. the model is telling you 96.7% of
paths went broke — yet the percentile chart *looks* like a healthy recovery to ¥60M+ after
year 6. That mismatch is the "weird zero reading."

When the property sale is removed from the same profile, the scenario just flatlines at ¥0
from year 4 onward forever (0% success, no jump) — confirming the lump sum is what's
producing the jump.

### Chosen fix: pull the lump sum forward to the ruin year (per-path)

User's decision: rather than just making ruin permanent (simplest fix), simulate an
**emergency/forced sale** — if a path's portfolio would go to ¥0 *before* its scheduled lump
sum(s), inject the lump sum(s) immediately at the ruin year for that path instead of waiting
for the originally-planned age. This is more realistic (someone actually going broke would
sell early, not sit at ¥0 for years) and keeps the model's optimism about "you have an asset
to fall back on" while removing the incoherent flat-then-vertical-jump artifact.

### Implementation plan

This needs **per-path state** (currently the loop is fully vectorized/shared across paths
with no per-path bookkeeping beyond the `portfolios` array itself). Plan:

1. **Precompute a "remaining lump sum after year t" array**, since lump sum amounts/timing
   are deterministic and shared across paths (same schedule for everyone until they diverge
   due to early-ruin pull-forwards):
   ```python
   remaining_lump_by_year = np.zeros(simulation_years + 1)
   cum = 0
   for yr in range(simulation_years, -1, -1):
       remaining_lump_by_year[yr] = cum      # sum of lump sums scheduled at year > yr
       if yr in lump_sum_map:
           cum += lump_sum_map[yr]
   ```

2. **Track a per-path `emergency_triggered` boolean mask** (`np.zeros(n_simulations, dtype=bool)`),
   set once a path has had its lump sum(s) pulled forward. This does double duty:
   - Prevents re-applying the *originally scheduled* lump sum a second time to a path that
     already had it pulled forward early (must gate the normal scheduled-injection line with
     `~emergency_triggered`).
   - Prevents re-triggering the emergency logic twice for the same path.

3. **Rewrite the loop body** (replace lines ~255-268) along these lines:
   ```python
   emergency_triggered = np.zeros(n_simulations, dtype=bool)
   emergency_year = np.full(n_simulations, -1)   # optional, for diagnostics/reporting

   for yr in range(simulation_years):
       base_net = net_withdrawal[yr]
       effective_withdrawal = base_net + (mortgage_delta[:, yr] if mortgage_delta is not None and yr < mortgage_delta.shape[1] else 0)
       raw = portfolios[:, yr] * gross_returns[:, yr] - effective_withdrawal

       # Normal scheduled lump sum — only for paths that haven't already had an
       # emergency pull-forward (they already consumed this money early).
       if yr + 1 in lump_sum_map:
           raw = raw + np.where(~emergency_triggered, lump_sum_map[yr + 1], 0.0)

       # Emergency pull-forward: paths newly going broke this year, that still have
       # some future scheduled lump sum, get it injected right now instead.
       newly_ruined = (raw <= 0) & (~emergency_triggered)
       if newly_ruined.any() and remaining_lump_by_year[yr + 1] > 0:
           raw = raw + np.where(newly_ruined, remaining_lump_by_year[yr + 1], 0.0)
           emergency_triggered = emergency_triggered | newly_ruined
           emergency_year = np.where(newly_ruined, yr + 1, emergency_year)

       portfolios[:, yr + 1] = np.maximum(raw, 0)
   ```

4. **Known, documented simplification (do not silently expand scope):** withdrawal
   reductions (e.g. mortgage payments stopping, rental income ceasing after a sale) are
   currently a single deterministic 1D schedule (`net_withdrawal`, shape `(simulation_years,)`
   shared across all paths) — they are **not** pulled forward alongside the emergency lump
   sum. So an emergency-sale path still "pays" mortgage/loses rental income on the
   originally-scheduled timeline even though it sold the property early. Fully fixing this
   would require making `net_withdrawal` per-path (2D), which is a bigger lift. Add a code
   comment noting this as a known limitation, not a silent bug.

5. **Surface this in reporting** (small, valuable addition, consistent with the reporting
   work already done this session): return `emergency_liquidation_pct` from `run_simulation`
   (`float(emergency_triggered.mean() * 100)`), thread it through `run_monte_carlo()` into a
   new `MonteCarloResult.emergency_liquidation_pct` field, and in `fire_calculator.py` after
   the MC call, append a warning when it's non-trivial (e.g. > 5%):
   ```python
   if mc_result.emergency_liquidation_pct > 5:
       warnings.append(
           f"In {mc_result.emergency_liquidation_pct:.0f}% of Monte Carlo simulations, your "
           f"portfolio would be depleted before your planned property sale at age "
           f"{profile.property_planned_sale_age} — forcing an earlier, unplanned sale to "
           "avoid running out of money entirely."
       )
   ```
   (Only wire this up if there's an actual scheduled sale in the scenario — check
   `property_lump_sums` is non-empty before adding the warning, and word it generically if
   there could be multiple lump sums.)

6. **Tests to add** (`tests/test_accuracy_fixes.py` or a new `test_monte_carlo_lumpsum.py`):
   - A path forced to ruin before a scheduled lump sum should show portfolio > 0 in the year
     it goes broke (not stay at 0 until the originally-scheduled year) — reproduce with a
     tiny deterministic case (few sims, fixed seed, or `volatility=0` + a manually-forced bad
     first-year return) so it's a clean deterministic assertion, not a statistical one.
   - `success_rate_pct` semantics unchanged (still counts any zero-touch as failure) —
     the emergency-pull-forward changes *when* the lump sum lands, not whether the path
     counts as ruined.
   - Removing the lump sum entirely should still flatline correctly (regression guard against
     re-breaking the "no lump sum" path).
   - `emergency_liquidation_pct` is 0 when no path ever gets forced to sell early, and > 0 for
     the reproduction scenario above.

---

## Root cause #2 (calibration/messaging, not a code bug): default assumptions make the "3.0–3.5% is safe" claim false

**Not a math bug** — independently cross-checked the log-normal moment matching against a
from-scratch numpy simulation; they agree. The problem is that the app's own defaults
(`retirement_return_pct=4.5%`, `return_volatility_pct=15%`) pair a bond-like return with
equity-like volatility, and under *that* combination the withdrawal rate the app calls "safe
for Japan" isn't actually safe by the app's own Monte Carlo:

- A portfolio funded at **exactly 100%** of its own computed FIRE number, 3.5% WR, defaults:
  **32.6% MC success** (not ~90%).
- `find_safe_withdrawal_rate()` (already exists, `engine/monte_carlo.py`) says the WR that
  actually clears 90% success under the defaults is **~1.4%**, not 3.0–3.5%.
- To make 3.5% WR hit ~90% success at 15% vol, you'd need more like a 9–10% nominal return:
  ```
  mean_return=4.5%  vol=15%  WR=3.5% → success=46%
  mean_return=8.0%  vol=15%  WR=3.5% → success=83%
  mean_return=10.0% vol=15%  WR=3.5% → success=94%
  ```

This means most scenarios drive a large fraction of paths to the ¥0 floor — which is exactly
the setup that makes root cause #1 visible whenever there's a scheduled lump sum.

### Chosen fix: leave the defaults alone, fix the messaging

User's decision: don't touch `retirement_return_pct` / `return_volatility_pct` defaults (that's
a capital-market-assumption judgment call, explicitly deferred). Instead, **stop asserting a
blanket "3.0–3.5% is safe for Japan"** and **surface the actual MC-derived safe withdrawal
rate for each scenario**, computed from that scenario's own return/volatility/expense/pension
inputs, so the guidance is always internally consistent with what the simulation shows.

### Implementation plan

1. **Compute a per-scenario safe withdrawal rate** in `run_fire_scenario()`
   (`engine/fire_calculator.py`), after the main `mc_result` is computed. Reuse
   `find_safe_withdrawal_rate()` (already exists, does a ~20-step binary search), called with:
   - `initial_portfolio_jpy=current_portfolio`
   - `annual_expenses_jpy=active_mc_expenses + nhi_steady` (approximate — `find_safe_withdrawal_rate`
     doesn't currently accept an `extra_expense_schedule`/lump sums like `run_monte_carlo` does;
     baking in a flat average NHI estimate is a reasonable, documented approximation rather than
     extending that function's signature to match `run_monte_carlo` exactly)
   - `net_pension_annual_jpy=japan_pension_for_mc`, `pension_start_year=pension_start_year`
   - `simulation_years=assumptions.simulation_years`
   - `n_simulations=min(assumptions.monte_carlo_simulations, 2000)` — cap for perf, matches
     the existing pattern in `mortgage_rate_scenarios` (`mc_simulations_override=1_000`)
   - `mean_return=assumptions.retirement_return_pct/100`, `volatility=assumptions.return_volatility_pct/100`
   - `target_success_rate=90.0`
   - **Caveat to document in a code comment and in the UI**: this ignores one-off events like
     scheduled property sales (since it doesn't take `lump_sums`), so it understates the true
     safe rate for scenarios with a rescue event queued up. Label it accordingly in the UI
     rather than silently presenting it as exact.

2. **Add fields to `ScenarioResult`** (`models/scenario.py`):
   - `mc_safe_withdrawal_rate_pct: float = 0.0`
   - `mc_safe_withdrawal_target_pct: float = 90.0` (so the UI can say "at a 90% target" even if
     this becomes configurable later)

3. **Replace the blanket warnings.** Three spots currently hard-code "3.0–3.5%":
   - `engine/fire_calculator.py` `calculate_fire_number()` (~line 129) — this is a low-level
     utility called from places with no MC context (e.g. `sensitivity.py`), so don't remove its
     self-contained warning, but soften the specific numeric claim to something like: *"above 4%
     is aggressive by conventional FIRE standards — check your Monte Carlo success rate for this
     scenario."* Don't assert a specific "safe" number here since this function doesn't know it.
   - `engine/fire_calculator.py` `run_fire_scenario()` warnings list (~line 1239) — this one
     *does* have MC context by the time it runs. Replace with a dynamic comparison against the
     newly-computed `mc_safe_withdrawal_rate_pct`, e.g.:
     ```python
     if assumptions.withdrawal_rate_pct > mc_safe_wr_pct + 0.25:  # small margin to avoid noise
         warnings.append(
             f"Your chosen withdrawal rate of {assumptions.withdrawal_rate_pct:.1f}% is above "
             f"the ~{mc_safe_wr_pct:.1f}% rate that clears 90% Monte Carlo success under your "
             "own return/volatility assumptions (excluding one-off events like a property sale)."
         )
     else:
         # still worth surfacing even when the user IS being conservative
         warnings.append(
             f"Your Monte Carlo-implied safe withdrawal rate is ~{mc_safe_wr_pct:.1f}% "
             "(90% target success) under your current return/volatility assumptions."
         )
     ```
   - `engine/pension_calculator.py` `calculate_pension_offset_on_fire_number()` docstring
     (~line 407-408) — just a comment/docstring, update wording to stop stating "3–3.5%" as a
     universal fact; note it depends on the return/volatility assumptions used.

4. **UI copy** — these currently assert the blanket "3–3.5%" claim and need the same softening:
   - `web/static/js/i18n.js` — `"rules.swr"` (~line 46), `"chart.mc.note"` (~line 302),
     `"help.withdrawal_rate_pct"` (~line 346). Update both English and Japanese variants (search
     for the JA equivalents near those keys — they weren't all in the earlier grep since it was
     English-anchored; check the JA half of the dict too).
   - `web/templates/partials/results.html` (~line 340) — same `chart.mc.note` text is also
     hardcoded inline in one spot as a fallback/duplicate; check whether it should just defer to
     the i18n key or needs the same edit directly.
   - Add a new line near the Monte Carlo chart (in `partials/results.html`, in the MC card,
     alongside the existing success-rate badge) showing the computed
     `result.mc_safe_withdrawal_rate_pct` next to the user's chosen `withdrawal_rate_pct`, so
     it's visible without digging into warnings text.

5. **`engine/report_generator.py`** (~line 722-723) has the same "3–3.5%" claim in the Monte
   Carlo section of the markdown report — update to reference `result.mc_safe_withdrawal_rate_pct`
   the same way.

6. **`README.md`** (~line 133) and `CLAUDE.md` also assert "Safe withdrawal rate: 3–3.5%" as
   project-level documentation/rationale (not live warning text) — lower priority, but worth a
   pass to soften into "3–3.5% is a common starting point, but the app now computes and shows a
   scenario-specific MC-derived safe rate" so the docs don't contradict the app's own behavior.

7. **Also noticed in passing (unrelated but should probably be fixed while touching this
   area):** `web/static/js/i18n.js` `"help.spouse_income_jpy"` (~line 367) still says the
   spouse income threshold is ¥1,030,000 — that's the *pre-2025-reform* number. The engine
   itself was already corrected earlier this session (`spouse_income_limit_full` is now
   1,230,000 in `data/tax_brackets.json`), but this help-text string was missed. Quick fix,
   unrelated to MC — just flagging so it doesn't get lost.

### Tests to add

- A test that `mc_safe_withdrawal_rate_pct` moves in the expected direction with
  `retirement_return_pct` and `return_volatility_pct` (higher return → higher safe rate; higher
  vol → lower safe rate) — sanity/monotonicity check, not an exact-value assertion (MC has
  sampling noise).
- A test that the warning text no longer contains a hardcoded "3.0–3.5%" / "3–3.5%" literal
  (grep-style test against the warnings list, or just check the new dynamic phrasing appears).
- Existing `test_fire_calculator.py::TestFireNumber` tests that assert on the exact old warning
  string (search for `"Japan research suggests 3.0"` in `tests/`) will need their expected
  strings updated to match new copy.

---

## Suggested order of operations for whoever picks this up

1. Implement the emergency-pull-forward MC fix first (self-contained, `engine/monte_carlo.py`
   + threading `emergency_liquidation_pct` through `MonteCarloResult`) — get tests green.
2. Re-run the reproduction from Root Cause #1 above (`scenarios/44384a85-...json`) to confirm
   the flat-zero-then-vertical-jump artifact is gone and the chart now shows a gradual
   emergency-sale recovery spread across the years paths actually go broke, not a single
   collapsed spike.
3. Then implement the safe-withdrawal-rate computation + messaging changes (Root Cause #2) —
   this is more spread out across templates/i18n so budget more time for the UI sweep.
4. Full `pytest` run, then a browser pass (preview tools) on at least one scenario with a
   property sale and one without, checking the MC chart and the new safe-rate line/warning
   text render sensibly in both English and Japanese.
5. Commit the earlier (already-implemented) accuracy/reporting work and this MC work as
   separate commits — they're logically distinct even though they landed in the same session.

---

## Item #3 (found via external bug report, fixed 2026-07-04, same day): variant-blind expense display

A bug report (filed by "Hermes" on behalf of the user, referencing a separate working tree
at `~/.openclaw/workspace/tmp/JPFIRECalc/`) observed MC survival dropping 94.8% → 86.1%
between a "Lean FIRE 3.0% WR" run and a "Regular FIRE 2.7% WR" run of the same profile, and
concluded (incorrectly) that the withdrawal rate itself was destabilizing MC.

**Verified independently in this tree:** WR alone, variant held constant, moves only the
deterministic FIRE number — MC success is unchanged (noise-level difference, matching the
reporter's own local finding). The real driver was the *variant* switch (Lean vs Regular),
which legitimately simulates a lower expense burn for Lean (`active_mc_expenses` in
`fire_calculator.py`, e.g. `lean_annual` = 70% of the user's own `monthly_expenses_jpy`).
That's correct behavior. **The bug**: `ScenarioResult.annual_expenses_jpy` (and
`annual_nhi_jpy`, `annual_withdrawal_needed_jpy`) always held the base/"Regular" figures
regardless of `fire_variant` — so the report's "FIRE Number Breakdown" table and the web
"Retirement Cash Flow" card displayed the *same* expense number for every variant, even
though Monte Carlo was actually simulating a different one for lean/fat/barista. This made
it look like "same inputs, different survival rate" when the inputs had in fact differed —
exactly what confused the reporter.

**Fix implemented:**
- Added `active_annual_expenses_jpy`, `active_annual_nhi_jpy`, `active_annual_withdrawal_jpy`
  to `ScenarioResult` (`models/scenario.py`), computed once in `run_fire_scenario()`
  (`engine/fire_calculator.py`, right where `active_fire_number`/`active_mc_expenses` are
  already branched per variant) rather than re-deriving variant logic per display surface.
- `report_generator.py`'s "FIRE Number Breakdown" table now uses these, labels the row with
  the variant name, and adds an explanatory callout when the active figure differs from the
  base one (i.e. whenever `fire_variant != 'regular'`).
- `partials/results.html`'s "Retirement Cash Flow" card does the same, plus a matching
  inline note.
- **Gotcha hit while doing this**: `i18n.js`'s `applyTranslations()` runs on every page load
  (default locale is Japanese) and does `el.textContent = translated_string` for any element
  with `data-i18n`, which **wipes out any dynamic Jinja content rendered inside that same
  element** — including "(Lean)" appended straight into the `<h3 data-i18n="...">` title.
  Fix: split into `<span data-i18n="...">static label</span> <span>({{ v|title }})</span>`
  so translation only touches the static part. **This same pattern already silently breaks
  the hero card's variant-aware label** (`hero_label`, e.g. "Lean FIRE Number" gets wiped
  back down to generic "FIRE Number" on load) — confirmed via browser (`heroLabel` returned
  `"FIRE目標額"` not a lean-specific string, while the *value* and *sub-label* below it, which
  have no `data-i18n`, correctly show lean-specific numbers). **Not fixed in this session**
  (out of scope for this specific bug) — worth a small follow-up pass over `results.html` for
  any other `data-i18n` element carrying dynamic Jinja content.
- Tests: 391 passing (no new tests added for this specific display fix — it's a template/
  display-layer change; consider adding one if this recurs).
- Verified in browser: reproduced the exact report shape (Lean vs Regular numbers), applied
  the fix, confirmed the "Retirement Cash Flow" card now shows the correct per-variant
  expense figure and the h3 suffix survives i18n translation.

**Not yet done / worth a follow-up:** the "before pension" NHI row in both the report and the
web card still shows the base `annual_nhi_gap_jpy`, not a variant-aware equivalent — this
only matters for the `barista` variant (extra income raises NHI), and is a much smaller
effect than the expense mismatch. Left as-is to keep this fix contained; flag if barista
users report anything similar.

**Incidental fix while unblocking local verification:** `app.py`'s `app.run()` hardcoded
`port=5000`; changed to `int(os.environ.get("PORT", 5000))` so a stuck/orphaned local dev
socket doesn't require killing processes to work around — zero effect on the Railway
deployment, which already runs via `gunicorn --bind 0.0.0.0:${PORT:-5000}` per
`railway.toml`/`Procfile`, not `app.py`'s `__main__` block.
