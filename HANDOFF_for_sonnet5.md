# Hand-off to Sonnet 5 — WR Model Redesign + loose ends

**From:** Fable 5 (strategic architect) — 2026-07-05
**To:** Sonnet 5 (implementer)
**Repo:** `E:\Programming\JPFIRECalc` (GitHub: thinknzombie/JPFIRECalc, deployed on Railway)

---

## Your mission

Implement the Withdrawal-Rate model redesign specified in **`PLAN_wr_model_redesign.md`**
(repo root). That document is the source of truth: it contains the full problem statement,
the target model spec with exact formulas (§2), six locked design decisions with rationale
(§3, D1–D6), a verified file/line anchor map (§4), and **one self-contained prompt per
phase** (§5). Work phases strictly in order: **0 → 1 → 2 → 3**. Phase 4 is backlog — do
not start it without Andrew's explicit go.

Read the plan in full before writing any code. If anything in the current code contradicts
the plan's anchor map, trust the code and re-verify — line numbers drift.

## One-paragraph context (why this exists)

Andrew discovered the WR slider never moved Monte Carlo success. Root cause: MC simulates
*stated expenses* (`monthly_expenses_jpy`); WR only sizes the FIRE Number and never reaches
the simulation — while parts of the UI (Monthly Drawdown Capacity panel) already present
`portfolio × WR` as "max monthly spend." Andrew chose Model **B1′**: WR defines the actual
simulated draw (a lifestyle budget `portfolio × WR`, inflated yearly, pension offsetting the
draw when it starts), and stated expenses survive only to size the FIRE target and drive a
new **deemed-WR warning** ("your stated spending implies a ~W% actual withdrawal rate").
Two confirmed bugs ride along: `find_safe_withdrawal_rate()` ignores its
`annual_expenses_jpy` parameter entirely (verified: identical output for ¥1M–¥500M
expenses), and `seed=None` on the main MC call makes every render a fresh random draw
(±0.5pp), which Andrew repeatedly misread as real WR effects when comparing scenarios.

## State of the tree right now

- **Committed & pushed** (through `294262d` on `origin/main`): everything up to and
  including the compare-page accuracy fix and variant-aware expense display. 391 tests
  passing at last full run.
- **Uncommitted, working tree:**
  - `web/static/js/charts.js` — **finished, verified, not yet committed**: log-scale
    y-axis for the compare-page Net Worth Projection chart (scenarios spanning ¥116k to
    ¥5.7bn were being crushed flat on a shared linear axis; all lines confirmed visible
    in-browser after the change; ¥0/ruin values floored just under the smallest real value
    with "Depleted (¥0)" hover). **Commit this first as its own commit** before starting
    Phase 0 — suggested message: `fix: log-scale compare trajectory chart so all scenarios
    stay visible`. Note the matching MC-median compare chart (`renderCompareMC`) still has
    the same linear-axis problem — that's Phase-4 backlog, don't fix it now unless asked.
  - `PLAN_wr_model_redesign.md` — the plan; commit it alongside or with Phase 0.
- **Do not push** anything without Andrew's explicit instruction. Commit per phase with
  the established style; end commit messages with
  `Co-Authored-By: Claude <your model> <noreply@anthropic.com>`.

## Working agreements (learned this session — will save you time)

1. **Tests:** run `python -m pytest tests/ -q` from the repo root. Suite is fast (~1s).
   Every phase's prompt lists required new tests; update Model-A assertions rather than
   deleting them.
2. **Browser verification is expected, not optional.** Use the preview tools
   (`.claude/launch.json` → server name `jpfirecalc`). If port 5000 is stuck, `app.py`
   now honors a `PORT` env var and launch.json has `autoPort: true`. The screenshot tool
   sometimes times out — `preview_eval` + `preview_snapshot` inspections are acceptable
   proof when it does.
3. **i18n gotcha (bit us twice):** `applyTranslations()` in `web/static/js/i18n.js`
   overwrites the **entire** textContent of any element carrying `data-i18n`. Never put
   dynamic Jinja output inside a translated element — use a sibling `<span>`. Add every
   new key to **both** the EN and JA dictionaries.
4. **Scenario JSON files** in `scenarios/` are gitignored user data. The two "Andrew"
   scenarios (`deffe6da-…`, `3aede6d6-…`) are Andrew's real inputs — read them for
   verification, never edit them (if you must mutate one for a test, copy to `.bak` and
   restore, and clean up any stray `.json.lock` files afterwards).
5. **Multiple agents have worked this tree concurrently** (a `09c45e8` commit landed
   mid-session from elsewhere). Before large edits: `git status` + `git log --oneline -3`
   and re-read any file you haven't touched in the current phase.
6. **Windows shell quirks:** cp1252 console — pipe engine output containing `¥`/`−` to a
   UTF-8 file instead of printing; write scratch files inside the repo, not `/tmp`.

## Verification protocol for the finished redesign (from the plan, §6)

Duplicate a scenario, change **only** WR (3.5% → 5.0%), open `/compare`:
- FIRE Number differs (as today); WR Budget and Net Portfolio Draw higher for higher WR;
- **MC Success strictly lower for the higher WR — identical on re-render (fixed seed)**;
- Deemed WR and stated expenses identical across both columns.

That table passing is the definition of done for Phases 0–2.

## Context documents, in priority order

1. `PLAN_wr_model_redesign.md` — the spec you're implementing (read fully, first).
2. `HANDOFF_monte_carlo_fixes.md` — history of this session's MC fixes (emergency
   lump-sum pull-forward, safe-WR messaging, variant-blind display bug). Items marked
   done there are in `origin/main`. Phase 3 has you mark the superseded parts.
3. `CLAUDE.md` — project conventions (engine never imports Flask; data files updated
   annually; all money in int JPY).

Good luck — the engine change is smaller than it looks (`run_simulation` already has the
right mechanics; you're changing what flows into it), and the surface/copy work is where
the care goes. D1 in the plan is the one decision to keep in your head the whole time:
MC success now answers "is this WR sustainable," and the deemed-WR check answers "can I
actually live on it" — every screen must keep that pairing intact.
