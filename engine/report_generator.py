"""
Markdown report generator for FIRE scenario results.

Produces a self-contained .md file that the user can download, share,
open in Obsidian/Notion, or convert to PDF via pandoc.

The report includes:
  - Executive summary (FIRE number, years, MC success)
  - Current situation snapshot
  - Retirement cash flow breakdown
  - Account balances projected to retirement
  - Monte Carlo percentile table
  - Sensitivity analysis table
  - Net worth trajectory milestones
  - Warnings and action items
  - Foreigners mode notes (if applicable)
  - Full assumptions used
  - Disclaimer
"""
from __future__ import annotations
from datetime import date
from models.profile import FinancialProfile
from models.scenario import Scenario, ScenarioResult


def _yen(value: int) -> str:
    return f"¥{value:,}"


def _pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def _yrs(value: float) -> str:
    if value >= 99:
        return "Never (increase savings or reduce expenses)"
    return f"{value:.1f} years"


def generate_markdown_report(
    profile: FinancialProfile,
    scenario: Scenario,
    result: ScenarioResult,
) -> str:
    """
    Generate a full Markdown report from a scenario result.

    Returns the report as a UTF-8 string ready to be served as a file download.
    """
    today = date.today().strftime("%Y-%m-%d")
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        lines.append(f"\n{'#' * level} {text}\n")

    def p(text: str) -> None:
        lines.append(text)
        lines.append("")

    def rule() -> None:
        lines.append("---")
        lines.append("")

    def table(headers: list[str], rows: list[list[str]]) -> None:
        widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
                  for i, h in enumerate(headers)]
        sep = "| " + " | ".join("-" * w for w in widths) + " |"
        header_row = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
        lines.append(header_row)
        lines.append(sep)
        for row in rows:
            lines.append("| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |")
        lines.append("")

    def kv(label: str, value: str) -> None:
        lines.append(f"- **{label}:** {value}")

    def warn_block(items: list[str], title: str = "⚠️ Warnings") -> None:
        if not items:
            return
        lines.append(f"### {title}")
        lines.append("")
        for item in items:
            lines.append(f"> ⚠️ {item}")
            lines.append(">")
        lines.append("")

    # ── Title block ──────────────────────────────────────────────────────────
    lines.append(f"# FIRE Report — {result.scenario_name}")
    lines.append("")
    lines.append(f"> **Generated:** {today}  ")
    lines.append(f"> **Scenario:** {result.scenario_name}  ")
    lines.append(f"> **Region:** {scenario.region.replace('_', ' ').title()}  ")
    lines.append(f"> **FIRE variant:** {scenario.assumptions.fire_variant.replace('_', ' ').title()}  ")
    lines.append(f"> **Withdrawal rate:** {_pct(scenario.assumptions.withdrawal_rate_pct)}")
    lines.append("")
    rule()

    # ── Executive summary ─────────────────────────────────────────────────────
    h(2, "Executive Summary")

    mc_status = ""
    if result.monte_carlo:
        sr = result.monte_carlo.success_rate_pct
        if sr >= 90:
            mc_status = f"{_pct(sr)} ✅ (on track)"
        elif sr >= 75:
            mc_status = f"{_pct(sr)} ⚠️ (borderline)"
        else:
            mc_status = f"{_pct(sr)} ❌ (below target)"

    fire_age_str = f"{result.fire_age:.0f}" if result.years_to_fire < 99 else "—"

    # ── Divergence callout: FIRE number reached but MC sub-90% ───────────────
    if (result.monte_carlo
            and result.years_to_fire < 1
            and result.monte_carlo.success_rate_pct < 90):
        p(f"> ℹ️ **Your current portfolio exceeds your FIRE number, so years-to-FIRE is 0.** "
          f"However, your Monte Carlo survival rate of "
          f"{_pct(result.monte_carlo.success_rate_pct)} tells a different story — and both "
          f"can be true at the same time.")
        p(f"> The **FIRE number** answers: *\"Have I accumulated enough to never run out, "
          f"if returns are exactly average every year?\"*")
        p(f"> The **Monte Carlo** answers: *\"What happens if I get unlucky with returns early "
          f"in retirement — the period that matters most?\"*")
        p(f"> A sub-90% survival rate means there is meaningful risk that a bad-luck sequence "
          f"early in retirement permanently impairs your portfolio. See the Monte Carlo section "
          f"below for details and concrete ways to improve the rate.")
        lines.append("")

    table(
        ["Metric", "Value", "Notes"],
        [
            ["FIRE Number", _yen(result.fire_number_jpy),
             f"Portfolio needed at {_pct(scenario.assumptions.withdrawal_rate_pct)} WR"],
            ["Current Portfolio", _yen(result.current_portfolio_jpy),
             f"{result.progress_pct:.1f}% of FIRE number"],
            ["Years to FIRE", _yrs(result.years_to_fire), f"Projected FIRE age: {fire_age_str}"],
            ["Coast FIRE Number", _yen(result.coast_fire_number_jpy),
             "Reached ✅" if result.coast_fire_reached else "Not yet reached"],
            ["MC Portfolio Survival", mc_status if mc_status else "—",
             f"{result.monte_carlo.n_simulations:,} simulations" if result.monte_carlo else ""],
        ],
    )

    # ── Warnings ──────────────────────────────────────────────────────────────
    if result.warnings:
        warn_block(result.warnings)

    rule()

    # ── Current situation ─────────────────────────────────────────────────────
    h(2, "Current Situation")

    h(3, "Personal")
    kv("Current age", str(profile.current_age))
    kv("Target retirement age", str(profile.target_retirement_age))
    kv("Years to retirement", str(profile.years_to_retirement))
    kv("Employment type", profile.employment_type.replace("_", " ").title())
    lines.append("")

    h(3, "Income")
    kv("Annual gross income", _yen(profile.annual_gross_income_jpy))
    kv("Social insurance paid", _yen(profile.social_insurance_annual_jpy))
    if profile.has_spouse and profile.spouse_income_jpy > 0:
        kv("Spouse income", _yen(profile.spouse_income_jpy))
    kv("Dependents", str(profile.num_dependents))
    lines.append("")

    h(3, "Current Portfolio")
    portfolio_rows = [
        ["新NISA", _yen(profile.nisa_balance_jpy), "Tax-free, fully liquid"],
        ["iDeCo", _yen(profile.ideco_balance_jpy), "Locked until age 60"],
        ["Taxable brokerage", _yen(profile.taxable_brokerage_jpy), "Gains taxed at 20.315%"],
        ["Cash savings", _yen(profile.cash_savings_jpy), ""],
    ]
    if profile.foreign_assets_usd > 0:
        portfolio_rows.append([
            "Foreign assets",
            f"${profile.foreign_assets_usd:,.0f} USD = {_yen(int(profile.foreign_assets_usd * profile.usd_jpy_rate))}",
            f"@ ¥{profile.usd_jpy_rate:.0f}/USD",
        ])
    for field, label in [
        ("gold_silver_value_jpy", "Gold / precious metals"),
        ("crypto_value_jpy", "Cryptocurrency"),
        ("rsu_unvested_value_jpy", "Unvested RSUs"),
        ("other_assets_jpy", "Other assets"),
    ]:
        val = getattr(profile, field, 0)
        if val > 0:
            portfolio_rows.append([label, _yen(val), ""])
    portfolio_rows.append([
        "**Total accessible**", f"**{_yen(result.current_portfolio_jpy)}**",
        f"iDeCo {'included' if profile.target_retirement_age >= 60 else 'excluded (locked)'}",
    ])
    table(["Account", "Balance", "Notes"], portfolio_rows)

    h(3, "Monthly Cash Flow")
    monthly_savings = (
        profile.monthly_nisa_contribution_jpy
        + profile.ideco_monthly_contribution_jpy
        + profile.nisa_growth_frame_annual_jpy // 12
    )
    kv("Monthly expenses", _yen(profile.monthly_expenses_jpy))
    kv("Monthly NISA contribution (tsumitate)", _yen(profile.monthly_nisa_contribution_jpy))
    if profile.nisa_growth_frame_annual_jpy > 0:
        kv("NISA growth frame (monthly equiv.)", _yen(profile.nisa_growth_frame_annual_jpy // 12))
    kv("iDeCo monthly contribution", _yen(profile.ideco_monthly_contribution_jpy))
    kv("Total monthly savings", _yen(monthly_savings))
    lines.append("")

    # Real estate
    if profile.owns_property or getattr(profile, "owns_foreign_property", False):
        h(3, "Real Estate")
        if profile.owns_property:
            kv("Japan property value", _yen(profile.property_value_jpy))
            kv("Mortgage balance", _yen(profile.mortgage_balance_jpy))
            kv("Monthly mortgage payment", _yen(profile.monthly_mortgage_payment_jpy))
            if profile.rental_income_monthly_jpy > 0:
                kv("Monthly rental income", _yen(profile.rental_income_monthly_jpy))
            sale_age = getattr(profile, "property_planned_sale_age", None)
            if sale_age:
                appr = getattr(profile, "property_appreciation_pct", 0.0)
                kv("Planned sale age", f"{sale_age} (at {_pct(appr)} annual appreciation)")
        if getattr(profile, "owns_foreign_property", False):
            kv("Foreign property value", _yen(getattr(profile, "foreign_property_value_jpy", 0)))
            kv("Foreign mortgage balance", _yen(getattr(profile, "foreign_property_mortgage_jpy", 0)))
            if getattr(profile, "foreign_property_rental_monthly_jpy", 0) > 0:
                kv("Foreign monthly rental income", _yen(getattr(profile, "foreign_property_rental_monthly_jpy", 0)))
            fp_sale_age = getattr(profile, "foreign_property_planned_sale_age", None)
            if fp_sale_age:
                fp_appr = getattr(profile, "foreign_property_appreciation_pct", 0.0)
                kv("Foreign property planned sale age", f"{fp_sale_age} (at {_pct(fp_appr)} annual appreciation)")
        lines.append("")

    rule()

    # ── FIRE projections ──────────────────────────────────────────────────────
    h(2, "FIRE Projections")

    h(3, "FIRE Number Breakdown")
    table(
        ["Component", "Annual (JPY)", "Notes"],
        [
            ["Retirement expenses", _yen(result.annual_expenses_jpy),
             f"{_yen(result.annual_expenses_jpy // 12)}/month"],
            ["Less: pension income", f"−{_yen(result.annual_pension_net_jpy)}",
             f"Claim age {profile.nenkin_claim_age}"],
            ["Plus: NHI premium", _yen(result.annual_nhi_jpy), "Solved iteratively"],
            ["= Net portfolio need", _yen(result.annual_withdrawal_needed_jpy),
             f"÷ {_pct(scenario.assumptions.withdrawal_rate_pct)} WR"],
            ["**FIRE number**", f"**{_yen(result.fire_number_jpy)}**", ""],
        ],
    )

    if result.year1_residence_tax_shock_jpy > 0:
        p(f"> ⚠️ **Year-1 residence tax shock:** {_yen(result.year1_residence_tax_shock_jpy)} "
          f"— this extra cost is due in your first retirement year on top of regular expenses.")

    h(3, "Projected Account Balances at Retirement")
    balance_rows = [
        ["新NISA", _yen(result.nisa_at_retirement_jpy), "Tax-free, fully accessible"],
        ["iDeCo", _yen(result.ideco_at_retirement_jpy),
         "Accessible at FIRE" if result.ideco_accessible_at_fire else f"Locked until 60 (bridge needed: {_yen(result.ideco_bridge_needed_jpy)})"],
        ["Taxable / Cash", _yen(result.taxable_at_retirement_jpy), "Gains taxed at 20.315%"],
    ]
    table(["Account", "Balance", "Notes"], balance_rows)

    h(3, "FIRE Variants")
    table(
        ["Variant", "Target", "Status"],
        [
            ["Full FIRE", _yen(result.fire_number_jpy),
             "Reached ✅" if result.current_portfolio_jpy >= result.fire_number_jpy else f"{result.progress_pct:.1f}% — {_yrs(result.years_to_fire)}"],
            ["Coast FIRE", _yen(result.coast_fire_number_jpy),
             "Reached ✅" if result.coast_fire_reached else "Not yet reached"],
            ["Barista FIRE", _yen(result.barista_fire_number_jpy),
             "Smaller target if supplemented by part-time income"],
        ],
    )

    rule()

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    if result.monte_carlo:
        h(2, "Monte Carlo Simulation")
        mc = result.monte_carlo
        kv("Simulations run", f"{mc.n_simulations:,}")
        kv("Portfolio survival rate", f"{_pct(mc.success_rate_pct)}")
        kv("Mean return assumption", _pct(scenario.assumptions.retirement_return_pct))
        kv("Volatility assumption", _pct(scenario.assumptions.return_volatility_pct))
        kv("Simulation horizon", f"{scenario.assumptions.simulation_years} years")
        lines.append("")

        p("**What the success rate means:**")
        p(f"In {mc.n_simulations:,} simulated market paths, "
          f"{_pct(mc.success_rate_pct)} kept the portfolio above ¥0 for the full "
          f"{scenario.assumptions.simulation_years}-year retirement horizon. "
          "A simulation *fails* when a bad sequence of returns early in retirement "
          "(the 'sequence-of-returns risk' window — amplified 1.5× in the first 5 years) "
          "permanently shrinks the portfolio so that ongoing withdrawals eventually exhaust it.")
        p("Each individual path represents one possible future. The spread between p10 and p90 "
          "shows the range from worst-case to optimistic outcomes across all simulations.")
        lines.append("")

        p("**Why this differs from your years-to-FIRE:**")
        p("The FIRE number and years-to-FIRE use a *single fixed return* every year — "
          "exactly the expected average, no volatility, no bad years. That is the right model "
          "for a savings roadmap: it tells you whether your current trajectory gets you there. "
          "The Monte Carlo tests a different question: what if returns are *not* average? "
          "The worst time to get unlucky is early in retirement, because losses then have "
          "40 years to compound negatively against ongoing withdrawals. "
          "A portfolio can be 'at the FIRE number' deterministically but still fail in "
          "30% of simulated paths because a 15% volatility environment produces "
          "meaningful probability of exactly that bad-early scenario.")
        lines.append("")

        if mc.success_rate_pct < 90:
            p("**Concrete levers to improve your survival rate:**")
            # Estimate rough WR impact: dropping 0.5% WR typically adds 5-8% survival
            # This is directionally accurate without running additional MCs
            current_wr = scenario.assumptions.withdrawal_rate_pct
            p(f"  1. **Lower withdrawal rate:** At {current_wr}% WR, your survival rate is "
              f"{_pct(mc.success_rate_pct)}. Reducing to {current_wr - 0.5:.1f}% WR "
              f"(e.g. by spending ¥{int(result.fire_number_jpy * 0.005 / 12):,} less/month "
              f"or targeting ¥{int(result.fire_number_jpy * 0.005):,} more in assets) "
              f"typically adds 5–8 percentage points to survival.")
            p(f"  2. **Delay pension claiming:** Every year you defer nenkin past 65 "
              f"(up to 75) reduces the annual draw from the portfolio and meaningfully "
              f"improves survival — especially powerful if deferring to 70+, which adds "
              f"~42% to the annual benefit.")
            if result.monte_carlo.ruin_year_median:
                p(f"  3. **Ruin timing:** In failed paths, the portfolio typically hits "
                  f"¥0 around retirement year {result.monte_carlo.ruin_year_median} "
                  f"(age {profile.target_retirement_age + result.monte_carlo.ruin_year_median}). "
                  f"This is concentrated in the first 10 years — exactly the SOR window.")
            if scenario.assumptions.sequence_of_returns_risk:
                p(f"  4. **Sequence-of-returns risk:** Currently enabled — volatility is "
                  f"amplified 1.5× for the first 5 years of retirement, which reduces the "
                  f"success rate compared to a constant-volatility model. This is "
                  f"conservative and consistent with Japan-focused research (Kitces/ERN).")
            lines.append("")
        elif mc.success_rate_pct >= 90:
            p("**Your survival rate is solid.** At ≥90%, the probability that your "
              "portfolio outlasts a 40-year retirement under realistic volatility is high. "
              "The main remaining risk is inflation — consider maintaining a small cash buffer "
              "in early retirement to avoid selling equities at a bad time.")

        # Percentile table — sample at years 0, 5, 10, 15, 20, 25, 30 (if available)
        sample_years = [0, 5, 10, 15, 20, 25, 30]
        available = len(mc.p50)
        sample_years = [y for y in sample_years if y < available]

        h(3, "Portfolio Percentiles at Key Retirement Years")
        p("**p10 (stress):** 10% of simulations are at or below this value. "
          "**Median (p50):** Half of simulations exceed this. "
          "**p90 (optimistic):** Only 10% exceed this — a good year.")
        table(
            ["Year", "Age", "p10 (stress)", "p25", "Median (p50)", "p75", "p90 (optimistic)"],
            [
                [
                    str(y),
                    str(profile.target_retirement_age + y),
                    _yen(mc.p10[y]),
                    _yen(mc.p25[y]),
                    _yen(mc.p50[y]),
                    _yen(mc.p75[y]),
                    _yen(mc.p90[y]),
                ]
                for y in sample_years
            ],
        )

        rule()

    # ── Sensitivity analysis ──────────────────────────────────────────────────
    if result.sensitivity:
        h(2, "Sensitivity Analysis")
        surplus_mode = result.sensitivity[0].surplus_mode if result.sensitivity else False
        if surplus_mode:
            p("Each variable was shifted ±20% from the base value. Because you have already "
              "reached FIRE, the table shows the impact on your **FIRE surplus %** "
              "(how far above your FIRE number your portfolio sits). "
              "Variables are ranked by total impact — focus on the top rows.")
        else:
            p("Each variable was shifted ±20% from the base value. The table shows how many "
              "years earlier (optimistic) or later (pessimistic) FIRE would be reached. "
              "Variables are ranked by total impact — focus on the top rows.")

        sens_rows = []
        for item in result.sensitivity:
            direction = "↑ more impact" if (abs(item.delta_pessimistic) + abs(item.delta_optimistic)) > 4 else ""
            if surplus_mode:
                sens_rows.append([
                    item.label,
                    f"{item.base_years:.1f}%",
                    f"−{item.delta_pessimistic:.1f}%",
                    f"+{item.delta_optimistic:.1f}%",
                    direction,
                ])
            else:
                sens_rows.append([
                    item.label,
                    f"{item.base_years:.1f} yrs",
                    f"+{item.delta_pessimistic:.1f} yrs",
                    f"−{item.delta_optimistic:.1f} yrs",
                    direction,
                ])

        if surplus_mode:
            table(
                ["Variable", "Base surplus", "Pessimistic (−%)", "Optimistic (+%)", ""],
                sens_rows,
            )
        else:
            table(
                ["Variable", "Base", "Pessimistic (+yrs)", "Optimistic (−yrs)", ""],
                sens_rows,
            )
        rule()

    # ── Net worth trajectory ───────────────────────────────────────────────────
    if result.trajectory:
        h(2, "Net Worth Trajectory (Key Milestones)")
        p("Fixed-return deterministic projection. Hover the chart in the app for "
          "year-by-year details.")

        # Pick milestone ages: every 5 years, retirement age, pension start, and last year
        milestone_ages = set()
        for age in range(profile.current_age, profile.current_age + len(result.trajectory), 5):
            milestone_ages.add(age)
        milestone_ages.add(profile.target_retirement_age)
        milestone_ages.add(profile.nenkin_claim_age)
        milestone_ages.add(min(profile.current_age + len(result.trajectory) - 1,
                               profile.current_age + 50))

        traj_map = {yr.age: yr for yr in result.trajectory}
        traj_rows = []
        for age in sorted(milestone_ages):
            yr = traj_map.get(age)
            if not yr:
                continue
            phase_label = "Accumulation" if yr.phase == "accumulation" else "Retirement"
            annotation = ""
            if age == profile.target_retirement_age:
                annotation = "← FIRE target"
            elif age == profile.nenkin_claim_age:
                annotation = "← Pension starts"
            traj_rows.append([
                str(age),
                phase_label,
                _yen(yr.portfolio_value_jpy),
                annotation,
            ])
        table(["Age", "Phase", "Portfolio Value", "Notes"], traj_rows)
        rule()

    # ── Current tax summary ───────────────────────────────────────────────────
    h(2, "Current Tax Summary")
    kv("Income tax (所得税)", _yen(result.current_income_tax_jpy))
    kv("Residence tax (住民税)", _yen(result.current_residence_tax_jpy))
    kv("Social insurance (社会保険)", _yen(profile.social_insurance_annual_jpy))
    kv("**Total tax + social insurance**",
       f"**{_yen(result.current_income_tax_jpy + result.current_residence_tax_jpy + profile.social_insurance_annual_jpy)}**")
    kv("Effective rate (income tax + residence tax + social insurance ÷ gross)",
       _pct(result.current_effective_tax_rate_pct))
    lines.append("")
    rule()

    # ── Foreigners mode ────────────────────────────────────────────────────────
    if result.foreigners_warnings or result.foreigners_notes:
        h(2, "Foreigners Mode Analysis")
        if result.foreigners_dta_country:
            kv("DTA country", result.foreigners_dta_country)
        if result.foreigners_totalization:
            kv("Totalization eligible", "Yes ✅")
        if result.foreigners_non_pr:
            kv("Non-permanent resident rules", "Applicable ⚠️")
        if result.foreigners_exit_tax_risk:
            kv("Exit tax risk", "Yes — assets may exceed ¥100M threshold ⚠️")
        lines.append("")

        if result.foreigners_warnings:
            warn_block(result.foreigners_warnings, "⚠️ Action Required")
        if result.foreigners_notes:
            lines.append("### ℹ️ Information")
            lines.append("")
            for note in result.foreigners_notes:
                lines.append(f"> {note}")
                lines.append(">")
            lines.append("")
        rule()

    # ── Assumptions ───────────────────────────────────────────────────────────
    h(2, "Assumptions Used")
    a = scenario.assumptions
    table(
        ["Assumption", "Value"],
        [
            ["Accumulation return", _pct(a.investment_return_pct)],
            ["Retirement return", _pct(a.retirement_return_pct)],
            ["Withdrawal rate", _pct(a.withdrawal_rate_pct)],
            ["Japan inflation", _pct(a.japan_inflation_pct)],
            ["Return volatility (MC)", _pct(a.return_volatility_pct)],
            ["Monte Carlo simulations", f"{a.monte_carlo_simulations:,}"],
            ["Simulation horizon", f"{a.simulation_years} years"],
            ["Sequence-of-returns risk", "Enabled" if a.sequence_of_returns_risk else "Disabled"],
            ["NHI household members", str(a.nhi_household_members)],
            ["NHI municipality key", a.nhi_municipality_key],
            ["USD/JPY rate", f"¥{a.usd_jpy_rate:.0f}"],
        ],
    )
    rule()

    # ── Pension details ────────────────────────────────────────────────────────
    h(2, "Pension Details")
    kv("Nenkin contribution months (current)", str(profile.nenkin_contribution_months))
    kv("Pension claim age", str(profile.nenkin_claim_age))
    kv("Net pension at claim age", _yen(result.annual_pension_net_jpy))
    if profile.nenkin_net_kosei_annual_jpy:
        kv("Kosei nenkin (NenkinNet override)", _yen(profile.nenkin_net_kosei_annual_jpy))
    if profile.avg_standard_monthly_remuneration_jpy > 0:
        kv("Avg standard monthly remuneration", _yen(profile.avg_standard_monthly_remuneration_jpy))
    if profile.foreign_pension_annual_jpy > 0:
        kv("Foreign pension income", f"{_yen(profile.foreign_pension_annual_jpy)}/yr (starts age {profile.foreign_pension_start_age})")
    lines.append("")
    rule()

    # ── Methodology ──────────────────────────────────────────────────────────
    h(2, "Methodology")

    h(3, "FIRE Number")
    p("The FIRE number is the minimum investment portfolio required to fund retirement "
      "indefinitely. It is calculated as:")
    p("`FIRE Number = (Annual Expenses − Net Pension Income + NHI Premium) ÷ Withdrawal Rate`")
    p("**Annual expenses** are derived from a region-specific template (e.g. Tokyo cost of living) "
      "plus any ongoing mortgage payments. **Net pension** is the after-tax combined kokumin nenkin "
      "and kosei nenkin income at the chosen claim age. **NHI premium** is solved iteratively because "
      "it depends on the withdrawal amount, which itself depends on the NHI premium — the solver "
      "converges in 5–10 iterations. The **withdrawal rate** (default 3.5%) determines what fraction "
      "of the portfolio is drawn down each year.")

    h(3, "Years to FIRE")
    p("Calculated analytically using the future-value annuity formula:")
    p("`FV = PV × (1+r)^n + PMT × ((1+r)^n − 1) / r`")
    p("where PV = current accessible portfolio, PMT = annual savings, r = pre-retirement return, "
      "and FV = FIRE number. Solving for n gives the years remaining. If PV already exceeds the "
      "FIRE number, years-to-FIRE is 0 (already FIRE'd).")
    p("**Important — this is a deterministic estimate, not a survival analysis.** "
      "It assumes the portfolio grows at exactly the configured return every year with no volatility. "
      "The Monte Carlo simulation (below) tests a different question: how does the portfolio "
      "fare under realistic return volatility over a multi-decade retirement? "
      "A scenario can show years_to_FIRE = 0 (accumulation complete by the deterministic model) "
      "while the Monte Carlo success rate is below 90% — both are correct because they "
      "answer different questions. The deterministic model asks 'can I get there?' "
      "The Monte Carlo asks 'will I stay there under bad-luck sequences?'")

    h(3, "Accessible Portfolio")
    p("The accessible portfolio includes NISA, taxable brokerage, cash savings, foreign assets, "
      "gold/crypto/RSU/other assets. **iDeCo is excluded if FIRE age < 60** (locked until age 60). "
      "If 'Mortgage paid off by retirement' is selected, the remaining mortgage balance — amortised "
      "to the retirement date at 1.5% annual interest — is deducted from the portfolio.")

    h(3, "Monte Carlo Simulation")
    p("Portfolio survival is tested by running N independent simulations (default 10,000). "
      "Each year's real return is drawn from a **log-normal distribution** calibrated to the "
      "configured mean return and volatility. Inflation erodes expenses annually at the Japan "
      "inflation rate. When sequence-of-returns risk is enabled, volatility is amplified by 1.5× "
      "during the first 5 years of retirement (the most vulnerable period).")
    p("A simulation **succeeds** if the portfolio never reaches ¥0 over the configured horizon "
      "(default 40 years). The **success rate** is the percentage of simulations that survive. "
      "Japan-focused research recommends targeting 90%+ success at a 3–3.5% withdrawal rate — "
      "more conservative than the US 4% rule due to historically lower Japanese equity returns.")

    h(3, "Pension Estimation")
    p("**Kokumin nenkin (国民年金):** Base amount ≈ ¥795,000/year × (contribution months ÷ 480). "
      "**Kosei nenkin (厚生年金):** Estimated from the average standard monthly remuneration "
      "(標準報酬月額) × multiplier × contribution years, or from a NenkinNet override if provided. "
      "Early/late claim age adjustments: −0.4%/month before 65, +0.7%/month after 65.")

    h(3, "Tax Calculations")
    p("**Income tax (所得税):** Progressive brackets from 5% to 45%, plus 2.1% reconstruction "
      "surtax. Standard employment income deduction applied for company employees. "
      "**Residence tax (住民税):** Flat 10% of taxable income + per capita levy (¥5,000). "
      "**Effective tax rate** = (income tax + residence tax + social insurance) ÷ gross income. "
      "**Capital gains:** 20.315% flat rate (income tax 15.315% + residence tax 5%) on investment "
      "gains in taxable accounts. NISA gains are tax-free.")

    h(3, "NHI (National Health Insurance)")
    p("Calculated per municipality schedule with income-proportional (所得割), per-capita (均等割), "
      "and per-household (平等割) components across medical, support, and care (age 40–64) categories. "
      "Subject to annual caps. The iterative solver accounts for the circular dependency between "
      "withdrawal amount and NHI premium.")

    rule()

    # ── Disclaimer ────────────────────────────────────────────────────────────
    h(2, "Disclaimer")
    p("This report is generated by **JPFIRECalc** for informational purposes only. "
      "It does not constitute financial, investment, tax, or legal advice. "
      "FIRE projections are estimates based on assumed returns and may differ "
      "significantly from actual outcomes. Past market performance does not "
      "guarantee future results.")
    p("Japan-specific calculations (NHI, nenkin, residence tax, iDeCo) are "
      "approximations based on publicly available rules as of the report date. "
      "Tax laws change — verify current rules with a qualified Japan-registered "
      "tax accountant (税理士) before making financial decisions.")
    p("**JPFIRECalc is open source.** Contributions and bug reports welcome at "
      "https://github.com/thinknzombie/JPFIRECalc")

    return "\n".join(lines)
