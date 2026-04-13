/**
 * JPFIRECalc i18n — Japanese / English language toggle
 *
 * Default language: Japanese (ja)
 * Preference stored in localStorage under 'jpfirecalc_lang'
 *
 * Usage:
 *   Elements with data-i18n="key.path" are translated on toggle.
 *   Form field labels are auto-translated by input name → field.{name} key.
 *   Keys containing HTML tags use innerHTML; plain strings use textContent.
 */

const I18n = (() => {

  const TRANSLATIONS = {
    en: {
      // ── Nav ────────────────────────────────────────────────────────────────
      "nav.dashboard": "Dashboard",
      "nav.new": "+ New",
      "nav.lang": "日本語",

      // ── Landing hero ───────────────────────────────────────────────────────
      "hero.badge": "Built for Japan",
      "hero.title": "Your FIRE number,<br>the Japan way.",
      "hero.subtitle": "Model iDeCo, 新NISA, nenkin, NHI premiums, residence tax, and regional cost of living — all the variables that generic calculators miss.",
      "hero.cta_primary": "Get Started",
      "hero.cta_secondary": "How it works",

      // ── Features ───────────────────────────────────────────────────────────
      "features.title": "What makes this different",
      "features.tax.title": "Japan Tax System",
      "features.tax.body": "Income tax, residence tax (including the year-1 retirement shock), and NHI premiums that vary with your withdrawal amount.",
      "features.nenkin.title": "Nenkin Integration",
      "features.nenkin.body": "Model kokumin and kosei nenkin benefits. See how deferring to 70 or 75 changes your FIRE number and break-even age.",
      "features.nisa.title": "iDeCo & 新NISA",
      "features.nisa.body": "Track NISA lifetime caps, model the iDeCo lock-up before 60, and compare tax-advantaged vs taxable withdrawal strategies.",
      "features.region.title": "Regional Cost of Living",
      "features.region.body": "Tokyo, Osaka, Fukuoka, rural Japan — cost-of-living templates built in. Inaka FIRE is a real strategy worth modeling.",
      "features.mc.title": "Monte Carlo Simulation",
      "features.mc.body": "10,000-path simulations with sequence-of-returns risk. See your p10/p50/p90 outcomes, not just a single projection line.",
      "features.foreign.title": "Foreign Residents",
      "features.foreign.body": "Non-permanent resident tax rules, totalization agreements, USD/JPY scenario bands, and exit tax warnings for large portfolios.",

      // ── Rules ──────────────────────────────────────────────────────────────
      "rules.title": "Japan FIRE — Rules of Thumb",
      "rules.swr": "Safe withdrawal rate for Japan<br><small>Lower than the US 4% rule due to Japan's lower expected equity returns and higher bond allocation norms</small>",
      "rules.shock": "Residence tax shock<br><small>You'll pay full residence tax on your last salary in year 1 of retirement. Budget for it.</small>",
      "rules.ideco": "iDeCo unlock age<br><small>iDeCo is completely illiquid before 60. Pre-60 FIRE means NISA + taxable must cover the gap.</small>",
      "rules.nisa": "新NISA lifetime cap<br><small>1.2M/yr tsumitate + 2.4M/yr growth frame. Tax-free growth and withdrawal, fully liquid.</small>",

      // ── CTA ────────────────────────────────────────────────────────────────
      "cta.title": "Ready to run your numbers?",
      "cta.body": "Create a profile, build scenarios, and compare them side by side.",
      "cta.button": "Start Calculating",

      // ── Dashboard ──────────────────────────────────────────────────────────
      "dash.title": "Dashboard",
      "dash.new": "+ New Scenario",
      "dash.hint": "Select scenarios to compare side-by-side.",
      "dash.compare": "Compare Selected →",
      "dash.empty.title": "No scenarios yet",
      "dash.empty.body": "Create your first scenario to model your Japan FIRE path — including Monte Carlo simulation, NHI projections, and pension offset.",
      "dash.empty.cta": "Create First Scenario →",
      "dash.storage": "Scenarios are saved on the server. On the free Railway plan the filesystem resets on redeploy — export important scenarios before updating.",

      // ── Scenario card (dashboard) ──────────────────────────────────────────
      "card.view": "View Results →",
      "card.return": "Return",
      "card.withdrawal": "Withdrawal",
      "card.inflation": "Inflation",
      "card.sims": "Simulations",

      // ── Profile page ───────────────────────────────────────────────────────
      "profile.subtitle": "Enter your financial details to run Japan-specific FIRE projections.",

      // ── Import / Export ────────────────────────────────────────────────────
      "import.title":         "Import from File",
      "import.subtitle":      "Download a template, fill it in with your numbers, then upload to pre-populate this form.",
      "import.download_json": "JSON Template",
      "import.download_csv":  "CSV Template",
      "import.upload_hint":   "Drop .json or .csv here, or click to browse",
      "import.upload_sub":    "Accepted: .json, .csv — max 256 KB",
      "import.upload_btn":    "Upload & Pre-fill",

      // ── Scenario form page ─────────────────────────────────────────────────
      "scenario_form.subtitle": "Adjust market assumptions to stress-test your FIRE plan.",

      // ── Form section headings ──────────────────────────────────────────────
      "section.scenario": "Scenario",
      "section.scenario.sub": "Give this scenario a name so you can compare it later.",
      "section.personal": "Personal Details",
      "section.income": "Income",
      "section.income.sub": "Gross figures — we calculate deductions automatically.",
      "section.assets": "Current Assets",
      "section.assets.sub": "Enter current market values for each account.",
      "section.cashflow": "Monthly Cash Flows",
      "section.cashflow.sub": "What you spend and invest each month.",
      "section.pension": "Japan Pension (年金)",
      "section.pension.sub": "Used to calculate your pension offset on the FIRE number.",
      "section.fx": "Foreign Exchange",
      "section.foreigners": "Foreigners Mode",
      "section.foreigners.sub": "Enables DTA treaty notes, exit tax warnings, and non-permanent resident analysis.",
      "section.realestate": "Real Estate (Optional)",
      "section.realestate.japan":   "Japan Property",
      "section.realestate.foreign": "Foreign / Overseas Property",
      "field.property_planned_sale_age":    "Planned Sale Age (blank = keep forever)",
      "field.property_appreciation_pct":    "Expected Annual Appreciation (%)",
      "field.fp_planned_sale_age":          "Planned Sale Age (blank = keep forever)",
      "field.fp_appreciation_pct":          "Expected Annual Appreciation (%)",
      "section.otherassets":        "Other Assets (Optional)",
      "section.otherassets.sub":    "Gold, crypto, RSUs, and other holdings that don't fit the standard account types.",
      "section.scenario_details": "Scenario Details",
      "section.returns": "Investment Returns",
      "section.returns.sub": "Global equity blend. Nominal, yen-denominated.",
      "section.withdrawal": "Withdrawal & Inflation",
      "section.fire_variant": "FIRE Variant",
      "section.nhi": "NHI (National Health Insurance)",
      "section.nhi.sub": "NHI premium is a function of your withdrawal — we solve for this iteratively.",
      "section.monte_carlo": "Monte Carlo Simulation",

      // ── Form field labels (auto-translated by input name) ──────────────────
      "field.scenario_name": "Scenario Name",
      "field.region": "Cost-of-Living Region",
      "field.current_age": "Current Age",
      "field.target_retirement_age": "Target Retirement Age",
      "field.employment_type": "Employment Type",
      "field.annual_gross_income_jpy": "Annual Gross Income",
      "field.social_insurance_annual_jpy": "Social Insurance Paid (Annual)",
      "field.has_spouse": "Has Spouse / Partner",
      "field.spouse_income_jpy": "Spouse Annual Income",
      "field.num_dependents": "Number of Dependents",
      "field.nisa_balance_jpy": "新NISA Balance",
      "field.nisa_lifetime_used_jpy": "新NISA Lifetime Cap Used (Acquisition Cost)",
      "field.ideco_balance_jpy": "iDeCo Balance",
      "field.taxable_brokerage_jpy": "Taxable Brokerage",
      "field.cash_savings_jpy": "Cash Savings",
      "field.foreign_assets_usd": "Foreign Assets (USD)",
      "field.monthly_expenses_jpy": "Monthly Expenses",
      "field.monthly_nisa_contribution_jpy": "Monthly NISA Contribution",
      "field.nisa_growth_frame_annual_jpy": "NISA Growth Frame (Annual Lump Sum)",
      "field.ideco_monthly_contribution_jpy": "iDeCo Monthly Contribution",
      "field.nenkin_contribution_months": "Nenkin Contribution Months",
      "field.nenkin_claim_age": "Pension Claim Age",
      "field.nenkin_net_kosei_annual_jpy": "Kosei Nenkin Estimate (Annual, Optional)",
      "field.avg_standard_monthly_remuneration_jpy": "Avg Standard Monthly Remuneration",
      "field.foreign_pension_annual_jpy": "Foreign Pension Income (Annual JPY)",
      "field.foreign_pension_start_age": "Foreign Pension Start Age",
      "field.usd_jpy_rate": "USD/JPY Rate",
      "field.nationality": "Nationality (ISO 3166-1 alpha-2)",
      "field.residency_status": "Japan Residency Status",
      "field.treaty_country": "Home Country (for DTA notes)",
      "field.years_in_japan": "Years Resident in Japan",
      "field.owns_property": "I own property in Japan",
      "field.property_value_jpy": "Property Value",
      "field.mortgage_balance_jpy": "Mortgage Balance",
      "field.monthly_mortgage_payment_jpy": "Monthly Mortgage Payment",
      "field.rental_income_monthly_jpy": "Monthly Rental Income",
      "field.property_paid_off_at_retirement": "Mortgage paid off by retirement",
      "field.owns_foreign_property":               "I own property outside Japan",
      "field.foreign_property_value_jpy":          "Foreign Property Value (JPY equivalent)",
      "field.foreign_property_mortgage_jpy":       "Foreign Property Mortgage (JPY equivalent)",
      "field.foreign_property_rental_monthly_jpy": "Foreign Monthly Rental Income (JPY equivalent)",
      "field.gold_silver_value_jpy":               "Gold / Precious Metals",
      "field.crypto_value_jpy":                    "Cryptocurrency",
      "field.rsu_unvested_value_jpy":              "Unvested RSUs (current FMV)",
      "field.rsu_vesting_annual_jpy":              "Annual RSU Vest (while employed)",
      "field.other_assets_jpy":                    "Other Assets",
      "field.description": "Description (optional)",
      "field.investment_return_pct": "Pre-Retirement Return (%)",
      "field.retirement_return_pct": "Post-Retirement Return (%)",
      "field.return_volatility_pct": "Annual Volatility (%)",
      "field.withdrawal_rate_pct": "Safe Withdrawal Rate (%)",
      "field.japan_inflation_pct": "Japan Inflation (%)",
      "field.retirement_expense_growth_pct": "Retirement Expense Growth (%)",
      "field.fire_variant": "FIRE Strategy",
      "field.coast_target_retirement_age": "Coast: Full Retirement Age",
      "field.barista_income_monthly_jpy": "Barista: Monthly Part-Time Income",
      "field.nhi_municipality_key": "Municipality",
      "field.nhi_household_members": "Household Members on NHI",
      "field.monte_carlo_simulations": "Number of Simulations",
      "field.simulation_years": "Simulation Years",
      "field.sequence_of_returns_risk": "Model Sequence-of-Returns Risk",

      // ── Buttons ────────────────────────────────────────────────────────────
      "btn.cancel": "Cancel",
      "btn.save_profile": "Save & Configure Assumptions →",
      "btn.edit_profile": "← Edit Profile",
      "btn.save_run": "Save & Run →",

      // ── Scenario detail ────────────────────────────────────────────────────
      "detail.edit_profile": "Edit Profile",
      "detail.edit_assumptions": "Edit Assumptions",
      "detail.delete": "Delete",

      // ── Results ────────────────────────────────────────────────────────────
      "result.fire_number": "FIRE Number",
      "result.years": "Years to FIRE",
      "result.progress": "Progress",
      "result.mc_success": "Monte Carlo Success",
      "result.already_fired": "Already FIRE'd!",
      "result.never": "Never reached",
      "result.never_sub": "Increase savings or reduce expenses",
      "result.coast": "Coast FIRE",
      "result.coast_number": "Coast Number (today)",
      "result.coast_reached": "Coast FIRE Reached?",
      "result.cashflow": "Retirement Cash Flow",
      "result.expenses": "Annual Expenses",
      "result.pension": "Pension Income (net)",
      "result.nhi": "NHI Premium",
      "result.net_portfolio": "Net from Portfolio / yr",
      "result.year1_shock": "Year-1 Residence Tax Shock",
      "result.balances": "Projected Balances at Retirement",
      "result.nisa_label": "新NISA",
      "result.nisa_note": "Tax-free, fully liquid",
      "result.ideco_label": "iDeCo",
      "result.ideco_accessible": "Accessible at FIRE age",
      "result.ideco_locked": "Locked until 60 — bridge needed",
      "result.taxable_label": "Taxable / Cash",
      "result.taxable_note": "Gains taxed at 20.315%",
      "result.mc_chart": "Portfolio Survival — Monte Carlo",
      "result.sensitivity": "Sensitivity Analysis",
      "result.sensitivity_sub": "Impact on Years to FIRE",
      "result.trajectory": "Net Worth Projection",
      "result.tax_summary": "Current Tax Summary",
      "result.income_tax": "Income Tax",
      "result.residence_tax": "Residence Tax",
      "result.effective_rate": "Effective Tax Rate",
      "result.foreigners": "Foreigners Mode",
      "result.totalization": "Totalization ✓",
      "result.non_pr": "Non-PR Rule",
      "result.exit_tax": "Exit Tax Risk",
      "result.action_required": "Action Required",
      "result.information": "Information",
      "result.disclaimer": "These notes are informational only and not legal or tax advice. Consult a Japan-registered tax accountant (税理士) for your specific situation.",
      "result.variants_title": "FIRE Variants Comparison",
      "result.show_budget": "Show monthly budget",
      "result.max_spend_before": "💰 Max monthly spend (before pension)",
      "result.social_insurance": "Social Insurance (社会保険)",
      "nav.settings": "Settings",
      "nav.edit_assumptions": "Edit Assumptions",
      "detail.clone": "Clone",
      "card.variant": "Strategy",
      "card.target_age": "Target Age",

      // ── Scenario comparison ────────────────────────────────────────────────
      "compare.title": "Scenario Comparison",
      "compare.dashboard": "← Dashboard",
      "compare.add": "+ Add scenario…",
      "compare.key_metrics": "Key Metrics",
      "compare.metric": "Metric",
      "compare.fire_number": "FIRE Number",
      "compare.years_to_fire": "Years to FIRE",
      "compare.fire_age": "FIRE Age",
      "compare.progress": "Progress to FIRE",
      "compare.mc_success": "MC Success Rate",
      "compare.cashflow": "Retirement Cash Flow",
      "compare.annual_expenses": "Annual Expenses",
      "compare.pension": "Pension (net)",
      "compare.nhi": "NHI Premium",
      "compare.net_portfolio": "Net from Portfolio / yr",
      "compare.balances": "Balances at Retirement",
      "compare.nisa": "新NISA",
      "compare.ideco": "iDeCo",
      "compare.coast": "Coast FIRE",
      "compare.coast_number": "Coast Number",
      "compare.coast_reached": "Coast Reached?",
      "compare.assumptions": "Assumptions",
      "compare.investment_return": "Investment Return",
      "compare.withdrawal_rate": "Withdrawal Rate",
      "compare.inflation": "Inflation",
      "compare.net_worth": "Net Worth Projection",
      "compare.mc_median": "Monte Carlo — Median Portfolio (p50)",
      "compare.already_fired": "Already FIRE'd",

      // ── Chart info panels ─────────────────────────────────────────────────
      "chart.note_label": "Japan note:",

      "chart.mc.intro":   "Runs 10,000 retirement scenarios with randomised annual returns — each one models a different possible future. The lines and shaded bands below show how your portfolio value spreads across all those outcomes.",
      "chart.mc.l.p50":   "<strong>Median (p50)</strong> — your expected middle outcome; half of all simulations finish above this line",
      "chart.mc.l.inner": "<strong>p25–p75 band</strong> — the middle 50% of outcomes; a realistic planning range",
      "chart.mc.l.outer": "<strong>p10–p90 band</strong> — 80% of all scenarios fall inside this range",
      "chart.mc.l.p90":   "<strong>p90 (green dotted)</strong> — optimistic ceiling: only 10% of runs end higher than this",
      "chart.mc.l.p10":   "<strong>p10 (red dotted)</strong> — stress-test floor: only 10% of runs end lower; plan so this stays above ¥0",
      "chart.mc.note":    "The <em>success rate</em> above is the % of simulations where the portfolio never hits ¥0. Japan research recommends targeting 90%+ success at a 3–3.5% withdrawal rate — lower than the US 4% rule, because Japanese equity returns have historically been lower and inflation has been more variable.",

      "chart.tornado.intro":   "Each variable in your plan is shifted ±20% from your input value. The bar shows how many years earlier or later you would reach FIRE as a result. Bars at the top have the biggest impact — those are the levers most worth pulling.",
      "chart.tornado.l.pess":  "<strong>Red bars (right →)</strong> — pessimistic: this variable getting 20% worse adds years to FIRE",
      "chart.tornado.l.opt":   "<strong>Green bars (← left)</strong> — optimistic: this variable improving by 20% removes years from FIRE",
      "chart.tornado.l.base":  "<strong>Centre line</strong> — your current base case; bars extend left and right from here",
      "chart.tornado.note":    "In Japan, <em>monthly expenses</em> and <em>withdrawal rate</em> typically show the longest bars — they matter more than investment return assumptions. Reducing living costs or lowering your withdrawal rate often shortens your FIRE timeline more than chasing higher returns in Japan's lower-yield environment.",

      "chart.traj.intro":      "A deterministic year-by-year projection using your fixed return assumptions — not randomised like Monte Carlo. Shows the single expected path: how your portfolio grows while working, and how it draws down in retirement. Hover any point to see the exact portfolio value at that age.",
      "chart.traj.l.accum":    "<strong>Blue solid line</strong> — accumulation phase: your portfolio growing through monthly contributions and investment returns",
      "chart.traj.l.retire":   "<strong>Amber dashed line</strong> — drawdown phase: portfolio being spent in retirement; slope flattens once pension income begins",
      "chart.traj.note":       "The drawdown slope accounts for nenkin (年金) income starting at your claim age — offsetting withdrawals and slowing the decline. The first retirement year may show a sharper drop due to the <em>year-1 residence tax shock</em> (住民税), which is billed on the prior year's working income.",

      // ── Footer ────────────────────────────────────────────────────────────
      "footer.disclaimer": "JPFIRECalc — For informational purposes only. Not financial advice.",

      // ── Dashboard card ────────────────────────────────────────────────────
      "card.age_prefix": "Age",
      "dash.compare_n": "Compare {n} →",

      // ── Scenario detail ───────────────────────────────────────────────────
      "detail.delete_confirm": "Delete this scenario?",
      "detail.download_report": "Download Report",
      "detail.running_simulations": "Running simulations…",

      // ── Compare page ──────────────────────────────────────────────────────
      "compare.scenarios_selected": "scenarios selected",

      // ── Result labels ─────────────────────────────────────────────────────
      "result.fire_number_sub": "Target portfolio at",
      "result.fire_age_label": "FIRE age:",
      "result.mc_simulations": "simulations",
      "result.coast_yes": "Yes ✓",
      "result.coast_not_yet": "Not yet",

      // ── Form validation messages ───────────────────────────────────────────
      "validation.age_order": "Target retirement age must be greater than current age.",
      "validation.nisa_limit": "Monthly NISA contribution cannot exceed ¥100,000 (tsumitate frame limit).",
      "validation.wr_range": "Withdrawal rate must be between 0.5% and 10%.",

      // ── Tooltip help text ─────────────────────────────────────────────────
      "help.investment_return_pct": "Expected annual return during accumulation. 5–7% is typical for a global equity portfolio.",
      "help.retirement_return_pct": "More conservative after FIRE — usually 0.5–1% below pre-retirement return.",
      "help.return_volatility_pct": "Standard deviation of returns. 15% is typical for a global equity fund.",
      "help.withdrawal_rate_pct": "Japan research suggests 3–3.5% is safer than the US 4% rule due to lower historical returns.",
      "help.japan_inflation_pct": "Recent Japan CPI has been ~2–3%. Your expenses grow at this rate in retirement.",
      "help.retirement_expense_growth_pct": "Typically below general inflation — retirees often spend less over time.",
      "help.fire_variant": "Changes which FIRE metric is highlighted in the results.",
      "help.coast_target_retirement_age": "Used for Coast FIRE — the age you stop working entirely.",
      "help.barista_income_monthly_jpy": "Income from part-time work during semi-retirement. Reduces required portfolio size.",
      "help.nhi_municipality_key": "NHI rates vary significantly by municipality — up to 2× between cheapest and most expensive.",
      "help.nhi_household_members": "Each additional member adds a per-head levy.",
      "help.monte_carlo_simulations": "1,000 is fast; 10,000 gives stable statistics. More = slower but more accurate.",
      "help.simulation_years": "How many years of retirement to simulate. FIRE at 45 → model to 95 = 50 years.",
      "help.sequence_of_returns_risk": "Amplifies volatility in early retirement years — the most dangerous period for early retirees.",

      // ── Profile field help text ───────────────────────────────────────────
      "help.scenario_name": "Name this scenario so you can compare it with others — e.g. 'Base Case' vs 'Pessimistic Returns'. Each scenario stores its own assumptions.",
      "help.region": "Sets your cost-of-living baseline. Regional monthly expense estimates are built in. Override with your actual figure in Monthly Expenses.",
      "help.current_age": "Your age today. Used to calculate years to FIRE and project account balances at retirement.",
      "help.target_retirement_age": "The age you plan to stop working. Earlier = fewer accumulation years and a longer drawdown, which requires a larger FIRE number.",
      "help.employment_type": "Determines which income deduction applies. Company employees receive a large employment income deduction (給与所得控除) that significantly lowers taxable income. Self-employed enter net business income directly.",
      "help.annual_gross_income_jpy": "Total salary before any deductions (税込み年収). Used to calculate income tax, residence tax, and social insurance. Check your withholding statement (源泉徴収票).",
      "help.social_insurance_annual_jpy": "健康保険 + 厚生年金 + 雇用保険. Typically ~14% of gross for company employees (e.g. ¥1.1M on ¥8M gross). Check your payslip or withholding statement (源泉徴収票). Enter 0 if unsure — tax estimate will be slightly high.",
      "help.has_spouse": "A qualifying spouse entitles you to the spouse deduction (配偶者控除) of ¥380,000, reducing your taxable income.",
      "help.spouse_income_jpy": "If your spouse earns ≤ ¥1,030,000/year you qualify for the full ¥380,000 spouse deduction (配偶者控除). Enter 0 if they have no income.",
      "help.num_dependents": "Each qualifying dependent reduces your taxable income by ¥380,000 (扶養控除). Include children under 16 and adult dependents you financially support.",
      "help.nisa_balance_jpy": "Current market value of your 新NISA account. Growth and withdrawals are completely tax-free — no capital gains or dividend tax.",
      "help.nisa_lifetime_used_jpy": "Total acquisition cost (purchase price, not current market value) of assets ever bought in your NISA. The ¥18M lifetime cap is tracked on purchase cost, not market value.",
      "help.ideco_balance_jpy": "Current iDeCo account value. Contributions are tax-deductible, but the account is locked until age 60. Pre-60 FIRE requires other accounts to bridge the gap.",
      "help.taxable_brokerage_jpy": "Investments in a regular brokerage (特定口座). Fully liquid, but realised gains are taxed at 20.315%. No lock-up period.",
      "help.cash_savings_jpy": "Bank deposits and liquid savings. No lock-up and immediately accessible, but earns near-zero interest in Japan.",
      "help.foreign_assets_usd": "Investments or savings held outside Japan (e.g. US brokerage, UK ISA). Converted to JPY using the USD/JPY rate you set.",
      "help.monthly_expenses_jpy": "Your total monthly living expenses — or your planned retirement budget. The single most important FIRE number input. Include rent, food, transport, utilities, insurance, travel, and hobbies.",
      "help.monthly_nisa_contribution_jpy": "Monthly investment into the tsumitate (積立) frame of 新NISA. Cap: ¥100,000/month (¥1.2M/year). Tax-free growth and withdrawal.",
      "help.nisa_growth_frame_annual_jpy": "Annual lump-sum contribution to the growth frame (成長投資枠) of 新NISA. Cap: ¥2.4M/year. Leave at 0 if you only use the monthly tsumitate frame.",
      "help.ideco_monthly_contribution_jpy": "Monthly iDeCo contribution — fully tax-deductible. Company employee cap: ¥23,000/month. Self-employed cap: ¥68,000/month. Funds are locked until age 60.",
      "help.nenkin_contribution_months": "Total months paid into the Japanese pension system (国民年金 + 厚生年金). Full kokumin nenkin requires 480 months (40 years). Check your statement at ねんきんネット (nenkin.ne.jp).",
      "help.nenkin_claim_age": "When you start receiving nenkin. Standard is 65. Claiming early (60–64) reduces the benefit 0.4%/month. Deferring past 65 increases it 0.7%/month — maximum at age 75.",
      "help.nenkin_net_kosei_annual_jpy": "Your annual kosei nenkin (厚生年金) estimate in JPY, after tax. Leave at 0 to let the app estimate from your average remuneration. Best source: your latest nenkin statement from ねんきんネット.",
      "help.avg_standard_monthly_remuneration_jpy": "Your average standard monthly remuneration (標準報酬月額) used to estimate kosei nenkin. A rough guide: use your typical gross monthly salary.",
      "help.foreign_pension_annual_jpy": "Annual income from a foreign state pension (e.g. US Social Security, UK State Pension, Australian Age Pension) in JPY. Permanent residents in Japan pay income tax on this.",
      "help.foreign_pension_start_age": "Age when your foreign pension begins. US Social Security: 62–70; UK State Pension: 66; Australian Age Pension: 67.",
      "help.usd_jpy_rate": "Current USD/JPY exchange rate. Used to convert USD-denominated foreign assets to JPY for the total portfolio calculation.",
      "help.nationality": "Your nationality as a 2-letter ISO code (e.g. US, GB, AU). Used to identify relevant double taxation agreements and non-permanent resident tax rules.",
      "help.residency_status": "Your immigration status in Japan. Non-permanent residents who have lived here fewer than 5 of the last 10 years may pay tax only on Japan-sourced income and foreign income remitted to Japan.",
      "help.treaty_country": "Your home country for Double Taxation Agreement (DTA) analysis. Japan has treaties with most OECD countries covering how pensions and investments are taxed.",
      "help.years_in_japan": "Total years resident in Japan. Non-permanent residents with fewer than 5 years here in the last 10 may qualify for favourable tax treatment — foreign investment gains may not be taxable in Japan.",
      "help.property_value_jpy": "Current estimated market value of your Japan property. Not included in the investable portfolio unless you plan to sell.",
      "help.mortgage_balance_jpy": "Remaining mortgage principal. Subtracted from property value to show your net property equity.",
      "help.monthly_mortgage_payment_jpy": "Your monthly mortgage repayment. Added to expenses until paid off — tick the checkbox below if it will be paid off by retirement.",
      "help.rental_income_monthly_jpy": "Monthly rental income from this property. Reduces net monthly expenses and lowers your FIRE number.",
      "help.property_paid_off_at_retirement": "If ticked, the mortgage payment is removed from your retirement expenses — improving cash flow and lowering your FIRE number.",
      "help.property_planned_sale_age": "If you plan to sell, net proceeds (value minus remaining mortgage) are injected as a lump sum into your portfolio at that age in the Monte Carlo simulation.",
      "help.property_appreciation_pct": "Expected annual property value growth. Japan residential property has seen near-zero or negative real appreciation in many regions. Tokyo central is an exception.",
      "help.foreign_property_value_jpy": "Estimated current market value of your foreign property, converted to JPY.",
      "help.foreign_property_mortgage_jpy": "Remaining mortgage on the foreign property, converted to JPY.",
      "help.foreign_property_rental_monthly_jpy": "Monthly rental income from the foreign property, converted to JPY.",
      "help.foreign_property_planned_sale_age": "Age when you plan to sell the foreign property. Net proceeds are added as a lump sum to your portfolio in the simulation.",
      "help.foreign_property_appreciation_pct": "Expected annual appreciation for the foreign property.",
      "help.gold_silver_value_jpy": "Current market value of gold, silver, or other precious metals.",
      "help.crypto_value_jpy": "Current value of cryptocurrency. Note: crypto gains in Japan are taxed as miscellaneous income (雑所得) at progressive rates — not the flat 20.315% capital gains rate.",
      "help.rsu_unvested_value_jpy": "Fair market value of unvested Restricted Stock Units. RSUs are taxed as employment income when they vest, not when sold.",
      "help.rsu_vesting_annual_jpy": "Annual value of RSUs vesting while employed. Modelled as additional savings each year in the accumulation phase.",
      "help.other_assets_jpy": "Other assets not covered above — e.g. whole-life insurance (終身保険), business equity, unlisted stock, or collectibles.",

      // ── Settings help text ────────────────────────────────────────────────
      "help.default_region": "Pre-fills the region for new scenarios. Can be changed per-scenario.",
      "help.default_nhi_municipality_key": "Default NHI municipality for new scenarios. NHI rates can vary up to 2× between cheapest and most expensive municipalities.",
      "help.default_nhi_household_members": "Default number of people covered under NHI. Each additional member adds a per-head levy to the annual premium.",
      "help.default_usd_jpy_rate": "Default USD/JPY rate pre-filled for new scenarios. Update when the rate changes significantly.",
      "help.default_fire_variant": "Which FIRE strategy is highlighted by default in new scenario results. All variants are always calculated regardless of this setting.",
      "help.default_language": "Sets the default display language. Can be switched at any time using the language toggle in the navigation bar.",

      // ── Errors ────────────────────────────────────────────────────────────
      "error.back": "Go to Dashboard",
      "error.home": "Home",
    },

    ja: {
      // ── Nav ────────────────────────────────────────────────────────────────
      "nav.dashboard": "ダッシュボード",
      "nav.new": "+ 新規",
      "nav.lang": "English",

      // ── Landing hero ───────────────────────────────────────────────────────
      "hero.badge": "日本のFIREに特化",
      "hero.title": "あなたのFIRE目標額を、<br>日本仕様で計算。",
      "hero.subtitle": "iDeCo・新NISA・年金・国民健康保険料・住民税・地域別生活費など、一般的な計算ツールでは対応していない日本特有の変数をすべてモデル化します。",
      "hero.cta_primary": "はじめる",
      "hero.cta_secondary": "使い方を見る",

      // ── Features ───────────────────────────────────────────────────────────
      "features.title": "このツールの特長",
      "features.tax.title": "日本の税制に対応",
      "features.tax.body": "所得税・住民税（退職1年目の住民税ショックを含む）・引き出し額に連動する国民健康保険料を正確にモデル化します。",
      "features.nenkin.title": "年金シミュレーション",
      "features.nenkin.body": "国民年金・厚生年金の受給額を試算。70歳・75歳への繰下げ受給がFIRE目標額と損益分岐年齢にどう影響するかを可視化します。",
      "features.nisa.title": "iDeCo・新NISA対応",
      "features.nisa.body": "新NISAの生涯投資枠の管理、60歳まで引き出せないiDeCoのロックアップ期間、税制優遇口座と課税口座の出口戦略を比較できます。",
      "features.region.title": "地域別生活費テンプレート",
      "features.region.body": "東京・大阪・福岡・地方など、地域別の生活費テンプレートを搭載。「田舎FIRE」も現実的な選択肢として試算できます。",
      "features.mc.title": "モンテカルロ・シミュレーション",
      "features.mc.body": "1万通りのシナリオで「リターンの順序リスク」を考慮した試算を実施。p10/p50/p90の結果分布で資産の生存確率を確認できます。",
      "features.foreign.title": "外国人居住者向け機能",
      "features.foreign.body": "非永住者の課税規則・社会保障協定（トータリゼーション）・為替レート変動の影響分析・1億円超の資産に対する国外転出時課税の警告に対応。",

      // ── Rules ──────────────────────────────────────────────────────────────
      "rules.title": "日本のFIRE — 基本的な目安",
      "rules.swr": "日本における安全な取り崩し率<br><small>日本株の期待リターンの低さと債券比率の高さから、米国の4%ルールより低い水準が推奨されています</small>",
      "rules.shock": "退職1年目の住民税ショック<br><small>退職翌年も前年の給与をもとに住民税が課税されます。退職初年度の予算確保が必要です。</small>",
      "rules.ideco": "iDeCoの解禁年齢<br><small>iDeCoは60歳まで引き出し不可。60歳前にFIREする場合は、新NISA＋特定口座でブリッジ期間をカバーする必要があります。</small>",
      "rules.nisa": "新NISAの生涯投資枠<br><small>つみたて投資枠120万円/年＋成長投資枠240万円/年。売却しても翌年に枠が復活。利益・配当はすべて非課税。</small>",

      // ── CTA ────────────────────────────────────────────────────────────────
      "cta.title": "あなたの数字を計算してみましょう",
      "cta.body": "プロフィールを作成し、複数のシナリオを構築・比較できます。",
      "cta.button": "無料で計算を始める",

      // ── Dashboard ──────────────────────────────────────────────────────────
      "dash.title": "ダッシュボード",
      "dash.new": "+ 新規シナリオ",
      "dash.hint": "シナリオを選択して比較できます。",
      "dash.compare": "選択したシナリオを比較 →",
      "dash.empty.title": "シナリオがまだありません",
      "dash.empty.body": "最初のシナリオを作成して、モンテカルロ・シミュレーション、国民健康保険料の試算、年金オフセットを含む日本のFIREプランを構築しましょう。",
      "dash.empty.cta": "最初のシナリオを作成 →",
      "dash.storage": "シナリオはサーバーに保存されます。Railwayの無料プランではデプロイのたびにファイルシステムがリセットされます。重要なシナリオは事前にエクスポートしてください。",

      // ── Scenario card (dashboard) ──────────────────────────────────────────
      "card.view": "結果を見る →",
      "card.return": "リターン",
      "card.withdrawal": "取り崩し率",
      "card.inflation": "インフレ率",
      "card.sims": "シミュレーション数",

      // ── Profile page ───────────────────────────────────────────────────────
      "profile.subtitle": "日本のFIRE試算に必要な財務情報を入力してください。",

      // ── Import / Export ────────────────────────────────────────────────────
      "import.title":         "ファイルから読み込む",
      "import.subtitle":      "テンプレートをダウンロードして数値を入力し、アップロードするとフォームが自動で埋まります。",
      "import.download_json": "JSONテンプレート",
      "import.download_csv":  "CSVテンプレート",
      "import.upload_hint":   ".jsonまたは.csvをドロップ、またはクリックして選択",
      "import.upload_sub":    "対応形式: .json, .csv — 最大256KB",
      "import.upload_btn":    "アップロードして入力",

      // ── Scenario form page ─────────────────────────────────────────────────
      "scenario_form.subtitle": "市場の前提条件を調整してFIREプランをストレステストします。",

      // ── Form section headings ──────────────────────────────────────────────
      "section.scenario": "シナリオ",
      "section.scenario.sub": "後で比較できるようにシナリオ名をつけてください。",
      "section.personal": "個人情報",
      "section.income": "収入",
      "section.income.sub": "額面収入を入力してください。控除は自動計算されます。",
      "section.assets": "現在の資産",
      "section.assets.sub": "各口座の現在の時価評価額を入力してください。",
      "section.cashflow": "毎月のキャッシュフロー",
      "section.cashflow.sub": "毎月の支出と投資額を入力してください。",
      "section.pension": "年金（日本）",
      "section.pension.sub": "FIRE目標額の年金オフセット計算に使用します。",
      "section.fx": "外国為替",
      "section.foreigners": "外国人居住者モード",
      "section.foreigners.sub": "租税条約の注記、国外転出時課税の警告、非永住者分析を有効にします。",
      "section.realestate": "不動産（任意）",
      "section.realestate.japan":   "日本の不動産",
      "section.realestate.foreign": "海外不動産",
      "field.property_planned_sale_age":    "売却予定年齢（空白＝保有継続）",
      "field.property_appreciation_pct":    "年間予想値上がり率（%）",
      "field.fp_planned_sale_age":          "売却予定年齢（空白＝保有継続）",
      "field.fp_appreciation_pct":          "年間予想値上がり率（%）",
      "section.otherassets":        "その他の資産（任意）",
      "section.otherassets.sub":    "通常の口座区分に該当しない金・暗号資産・RSUなどの保有資産",
      "section.scenario_details": "シナリオ詳細",
      "section.returns": "投資リターン",
      "section.returns.sub": "グローバル株式ブレンド。名目リターン、円建て。",
      "section.withdrawal": "取り崩しとインフレ",
      "section.fire_variant": "FIREの種類",
      "section.nhi": "国民健康保険（NHI）",
      "section.nhi.sub": "国保保険料は引き出し額に連動するため、反復計算で算出します。",
      "section.monte_carlo": "モンテカルロ・シミュレーション",

      // ── Form field labels (auto-translated by input name) ──────────────────
      "field.scenario_name": "シナリオ名",
      "field.region": "生活費地域",
      "field.current_age": "現在の年齢",
      "field.target_retirement_age": "目標退職年齢",
      "field.employment_type": "雇用形態",
      "field.annual_gross_income_jpy": "年収（額面）",
      "field.social_insurance_annual_jpy": "社会保険料（年額）",
      "field.has_spouse": "配偶者あり",
      "field.spouse_income_jpy": "配偶者の年収",
      "field.num_dependents": "扶養家族数",
      "field.nisa_balance_jpy": "新NISA残高",
      "field.nisa_lifetime_used_jpy": "新NISA生涯投資枠使用額（取得価額）",
      "field.ideco_balance_jpy": "iDeCo残高",
      "field.taxable_brokerage_jpy": "特定口座残高",
      "field.cash_savings_jpy": "現金・預金",
      "field.foreign_assets_usd": "海外資産（USD）",
      "field.monthly_expenses_jpy": "月間支出",
      "field.monthly_nisa_contribution_jpy": "新NISA月額積立",
      "field.nisa_growth_frame_annual_jpy": "成長投資枠（年間一括投資）",
      "field.ideco_monthly_contribution_jpy": "iDeCo月額掛金",
      "field.nenkin_contribution_months": "年金納付月数",
      "field.nenkin_claim_age": "年金受給開始年齢",
      "field.nenkin_net_kosei_annual_jpy": "厚生年金見込み額（年額・任意）",
      "field.avg_standard_monthly_remuneration_jpy": "平均標準報酬月額",
      "field.foreign_pension_annual_jpy": "海外年金収入（年額・円）",
      "field.foreign_pension_start_age": "海外年金受給開始年齢",
      "field.usd_jpy_rate": "USD/JPY レート",
      "field.nationality": "国籍（ISO 3166-1 alpha-2）",
      "field.residency_status": "在留資格",
      "field.treaty_country": "母国（租税条約確認用）",
      "field.years_in_japan": "日本在住年数",
      "field.owns_property": "日本に不動産を所有しています",
      "field.property_value_jpy": "不動産評価額",
      "field.mortgage_balance_jpy": "住宅ローン残高",
      "field.monthly_mortgage_payment_jpy": "月々の住宅ローン支払い",
      "field.rental_income_monthly_jpy": "月間賃貸収入",
      "field.property_paid_off_at_retirement": "退職時にローン完済予定",
      "field.owns_foreign_property":               "日本国外に不動産を所有しています",
      "field.foreign_property_value_jpy":          "海外不動産評価額（円換算）",
      "field.foreign_property_mortgage_jpy":       "海外不動産ローン残高（円換算）",
      "field.foreign_property_rental_monthly_jpy": "海外不動産月間賃貸収入（円換算）",
      "field.gold_silver_value_jpy":               "金・貴金属",
      "field.crypto_value_jpy":                    "暗号資産",
      "field.rsu_unvested_value_jpy":              "未確定RSU（現在の公正市場価格）",
      "field.rsu_vesting_annual_jpy":              "年間RSU確定額（在職中）",
      "field.other_assets_jpy":                    "その他の資産",
      "field.description": "説明（任意）",
      "field.investment_return_pct": "退職前リターン（%）",
      "field.retirement_return_pct": "退職後リターン（%）",
      "field.return_volatility_pct": "年率ボラティリティ（%）",
      "field.withdrawal_rate_pct": "安全取り崩し率（%）",
      "field.japan_inflation_pct": "日本のインフレ率（%）",
      "field.retirement_expense_growth_pct": "退職後の支出増加率（%）",
      "field.fire_variant": "FIREの戦略",
      "field.coast_target_retirement_age": "コースト：完全退職年齢",
      "field.barista_income_monthly_jpy": "バリスタ：月間アルバイト収入",
      "field.nhi_municipality_key": "市区町村",
      "field.nhi_household_members": "国保加入世帯人数",
      "field.monte_carlo_simulations": "シミュレーション回数",
      "field.simulation_years": "シミュレーション期間（年）",
      "field.sequence_of_returns_risk": "リターンの順序リスクをモデル化",

      // ── Buttons ────────────────────────────────────────────────────────────
      "btn.cancel": "キャンセル",
      "btn.save_profile": "保存して前提条件へ →",
      "btn.edit_profile": "← プロフィール編集",
      "btn.save_run": "保存して計算 →",

      // ── Scenario detail ────────────────────────────────────────────────────
      "detail.edit_profile": "プロフィール編集",
      "detail.edit_assumptions": "前提条件を編集",
      "detail.delete": "削除",

      // ── Results ────────────────────────────────────────────────────────────
      "result.fire_number": "FIRE目標額",
      "result.years": "FIREまでの年数",
      "result.progress": "達成率",
      "result.mc_success": "MC成功率",
      "result.already_fired": "すでにFIRE達成！",
      "result.never": "達成不可",
      "result.never_sub": "貯蓄を増やすか支出を減らしてください",
      "result.coast": "コーストFIRE",
      "result.coast_number": "コースト目標額（現在値）",
      "result.coast_reached": "コーストFIRE達成？",
      "result.cashflow": "退職後のキャッシュフロー",
      "result.expenses": "年間支出",
      "result.pension": "年金収入（税引後）",
      "result.nhi": "国民健康保険料",
      "result.net_portfolio": "ポートフォリオからの純引き出し額/年",
      "result.year1_shock": "1年目の住民税ショック",
      "result.balances": "退職時の口座残高予測",
      "result.nisa_label": "新NISA",
      "result.nisa_note": "非課税・いつでも引き出し可能",
      "result.ideco_label": "iDeCo",
      "result.ideco_accessible": "FIRE時に引き出し可能",
      "result.ideco_locked": "60歳まで引き出し不可 — ブリッジ期間が必要",
      "result.taxable_label": "特定口座／現金",
      "result.taxable_note": "売却益に20.315%課税",
      "result.mc_chart": "ポートフォリオ生存率 — モンテカルロ",
      "result.sensitivity": "感度分析",
      "result.sensitivity_sub": "FIREまでの年数への影響",
      "result.trajectory": "資産推移グラフ",
      "result.tax_summary": "現在の税負担",
      "result.income_tax": "所得税",
      "result.residence_tax": "住民税",
      "result.effective_rate": "実効税率",
      "result.foreigners": "外国人居住者向け分析",
      "result.totalization": "社会保障協定 ✓",
      "result.non_pr": "非永住者ルール",
      "result.exit_tax": "国外転出時課税リスク",
      "result.action_required": "要対応",
      "result.information": "参考情報",
      "result.disclaimer": "これらの情報は参考目的のみであり、法的・税務的なアドバイスではありません。個別の状況については、日本の税理士にご相談ください。",
      "result.variants_title": "FIRE戦略の比較",
      "result.show_budget": "月額予算を表示",
      "result.max_spend_before": "💰 月額上限（年金前）",
      "result.social_insurance": "社会保険",
      "nav.settings": "Settings",
      "nav.edit_assumptions": "前提条件を編集",
      "detail.clone": "複製",
      "card.variant": "戦略",
      "card.target_age": "目標年齢",

      // ── Scenario comparison ────────────────────────────────────────────────
      "compare.title": "シナリオ比較",
      "compare.dashboard": "← ダッシュボード",
      "compare.add": "+ シナリオを追加…",
      "compare.key_metrics": "主要指標",
      "compare.metric": "指標",
      "compare.fire_number": "FIRE目標額",
      "compare.years_to_fire": "FIREまでの年数",
      "compare.fire_age": "FIRE達成年齢",
      "compare.progress": "FIRE達成率",
      "compare.mc_success": "MC成功率",
      "compare.cashflow": "退職後のキャッシュフロー",
      "compare.annual_expenses": "年間支出",
      "compare.pension": "年金（税引後）",
      "compare.nhi": "国民健康保険料",
      "compare.net_portfolio": "ポートフォリオからの純引き出し額/年",
      "compare.balances": "退職時の残高",
      "compare.nisa": "新NISA",
      "compare.ideco": "iDeCo",
      "compare.coast": "コーストFIRE",
      "compare.coast_number": "コースト目標額",
      "compare.coast_reached": "コースト達成？",
      "compare.assumptions": "前提条件",
      "compare.investment_return": "投資リターン",
      "compare.withdrawal_rate": "取り崩し率",
      "compare.inflation": "インフレ率",
      "compare.net_worth": "資産推移グラフ",
      "compare.mc_median": "モンテカルロ — 中央値ポートフォリオ (p50)",
      "compare.already_fired": "FIRE達成済み",

      // ── Chart info panels ─────────────────────────────────────────────────
      "chart.note_label": "日本補足：",

      "chart.mc.intro":   "ランダムな年次リターンを用いた1万通りの退職シミュレーション。各線とシェード帯は、すべての結果における資産額の分布を示します。",
      "chart.mc.l.p50":   "<strong>中央値 (p50)</strong> — 期待される標準的な結果。シミュレーションの半数がこの線より上で終了",
      "chart.mc.l.inner": "<strong>p25–p75帯</strong> — 中央50%の結果。現実的な計画の基準範囲",
      "chart.mc.l.outer": "<strong>p10–p90帯</strong> — 全シナリオの80%がこの範囲内に収まる",
      "chart.mc.l.p90":   "<strong>p90（緑の点線）</strong> — 楽観的上限：全体の10%のみがこれより高い結果",
      "chart.mc.l.p10":   "<strong>p10（赤の点線）</strong> — ストレステストの下限：ここがゼロを下回らないよう計画を立てる",
      "chart.mc.note":    "上の<em>成功率</em>は、ポートフォリオが一度も¥0にならずに生存したシミュレーションの割合です。日本では3〜3.5%の取り崩し率で成功率90%以上を目標とすることが推奨されています。これは日本株の期待リターンの低さとインフレの変動を考慮した結果、米国の4%ルールより低く設定されています。",

      "chart.tornado.intro":   "プランの各変数を現在値から±20%変化させ、FIREまでの年数への影響を測定します。上位のバーが影響力の大きい変数です。まずそこに注目して最適化しましょう。",
      "chart.tornado.l.pess":  "<strong>赤いバー（右→）</strong> — 悲観的：この変数が20%悪化すると、FIREまでの年数が増える",
      "chart.tornado.l.opt":   "<strong>緑のバー（←左）</strong> — 楽観的：この変数が20%改善すると、FIREまでの年数が減る",
      "chart.tornado.l.base":  "<strong>中央線</strong> — 現在のベースケース。バーはここから左右に伸びる",
      "chart.tornado.note":    "日本では<em>月間支出</em>と<em>取り崩し率</em>が最も長いバーになることが多く、投資リターンより影響が大きい傾向があります。低利回り環境の日本では、高リターンを追うより生活費を下げるか取り崩し率を低くする方が、FIREを早める効果が高い場合があります。",

      "chart.traj.intro":      "固定リターンを用いた年次シミュレーション（モンテカルロと異なり、乱数なし）。就労中の資産成長から退職後の取り崩しまで、期待される単一の軌跡を表示します。各点にマウスを合わせると、その年齢での資産額が確認できます。",
      "chart.traj.l.accum":    "<strong>青い実線</strong> — 積立フェーズ：毎月の積立と運用益によりポートフォリオが成長",
      "chart.traj.l.retire":   "<strong>琥珀色の破線</strong> — 取り崩しフェーズ：退職後に資産を取り崩す期間。年金受給開始後は傾きが緩やかになる",
      "chart.traj.note":       "取り崩しフェーズの傾きは、設定した受給開始年齢から始まる年金（国民年金・厚生年金）収入を反映しており、引き出しを相殺して減少を緩やかにします。退職初年度は、前年の給与に基づく<em>住民税ショック</em>により、より急な落ち込みが生じる場合があります。",

      // ── Footer ────────────────────────────────────────────────────────────
      "footer.disclaimer": "JPFIRECalc — 情報提供のみを目的としています。投資・税務アドバイスではありません。",

      // ── Dashboard card ────────────────────────────────────────────────────
      "card.age_prefix": "年齢",
      "dash.compare_n": "{n}件を比較 →",

      // ── Scenario detail ───────────────────────────────────────────────────
      "detail.delete_confirm": "このシナリオを削除しますか？",
      "detail.download_report": "レポートをダウンロード",
      "detail.running_simulations": "シミュレーション実行中…",

      // ── Compare page ──────────────────────────────────────────────────────
      "compare.scenarios_selected": "件を選択中",

      // ── Result labels ─────────────────────────────────────────────────────
      "result.fire_number_sub": "目標ポートフォリオ：",
      "result.fire_age_label": "FIRE達成年齢：",
      "result.mc_simulations": "回のシミュレーション",
      "result.coast_yes": "達成 ✓",
      "result.coast_not_yet": "未達成",

      // ── Form validation messages ───────────────────────────────────────────
      "validation.age_order": "目標退職年齢は現在の年齢より大きく設定してください。",
      "validation.nisa_limit": "新NISAのつみたて投資枠の月額上限は10万円です。",
      "validation.wr_range": "取り崩し率は0.5%〜10%の間で入力してください。",

      // ── Tooltip help text ─────────────────────────────────────────────────
      "help.investment_return_pct": "積立期間中の期待年率リターン。グローバル株式ポートフォリオでは5〜7%が目安です。",
      "help.retirement_return_pct": "FIRE後はより保守的な設定が一般的です。退職前リターンより0.5〜1%低い値が推奨されます。",
      "help.return_volatility_pct": "リターンの標準偏差。グローバル株式インデックスファンドでは15%程度が一般的です。",
      "help.withdrawal_rate_pct": "日本の研究では、歴史的リターンの低さから3〜3.5%が米国の4%ルールより安全とされています。",
      "help.japan_inflation_pct": "最近の日本のCPIは約2〜3%です。退職後の支出はこの率で増加します。",
      "help.retirement_expense_growth_pct": "一般インフレより低いのが通常です。退職者は時間とともに支出が減る傾向があります。",
      "help.fire_variant": "結果でハイライトされるFIRE指標が変わります。",
      "help.coast_target_retirement_age": "コーストFIREで使用します。完全に仕事をやめる年齢を入力してください。",
      "help.barista_income_monthly_jpy": "セミリタイア中のアルバイト等の収入。必要なポートフォリオ額が減少します。",
      "help.nhi_municipality_key": "国保の保険料は市区町村によって大きく異なります。最安値と最高値で最大2倍の差があります。",
      "help.nhi_household_members": "加入者が増えるごとに均等割が加算されます。",
      "help.monte_carlo_simulations": "1,000回は高速、10,000回は安定した統計が得られます。多いほど精度は上がりますが時間がかかります。",
      "help.simulation_years": "退職後のシミュレーション期間。45歳でFIRE→95歳まで = 50年が目安です。",
      "help.sequence_of_returns_risk": "退職初期のボラティリティを増幅します。早期リタイアにとって最も危険な期間です。",

      // ── Profile field help text ───────────────────────────────────────────
      "help.scenario_name": "シナリオに名前をつけると他と比較しやすくなります。例：「ベースケース」vs「悲観的リターン」。各シナリオには独自の前提条件が保存されます。",
      "help.region": "生活費の基準を設定します。各地域の月額目安が内蔵されています。実際の支出額は「月間生活費」で上書きできます。",
      "help.current_age": "現在の年齢。FIREまでの年数と退職時の資産残高の試算に使用します。",
      "help.target_retirement_age": "仕事をやめる予定の年齢。早いほど積立期間が短く取り崩し期間が長くなるため、より大きなFIRE数が必要になります。",
      "help.employment_type": "適用される所得控除の種類を決定します。会社員は給与所得控除により課税所得が大幅に下がります。自営業者は事業所得（純利益）を直接入力してください。",
      "help.annual_gross_income_jpy": "控除前の年収（税込み年収）。所得税・住民税・社会保険料の計算に使用します。源泉徴収票で確認してください。",
      "help.social_insurance_annual_jpy": "健康保険＋厚生年金＋雇用保険の年間合計額。会社員の場合、目安は年収の約14%（例：年収800万円なら約112万円）。給与明細または源泉徴収票で確認してください。不明な場合は0を入力（税額が若干高めに計算されます）。",
      "help.has_spouse": "配偶者が要件を満たす場合、配偶者控除38万円が適用され、課税所得が減少します。",
      "help.spouse_income_jpy": "配偶者の年収が103万円以下の場合、配偶者控除38万円が適用されます。収入がない場合は0を入力してください。",
      "help.num_dependents": "扶養親族1人につき38万円の扶養控除が適用されます。16歳未満の子どもや経済的に扶養している家族を含みます。",
      "help.nisa_balance_jpy": "新NISA口座の現在の時価評価額。運用益・配当・解約すべて非課税です。",
      "help.nisa_lifetime_used_jpy": "NISAで購入した資産の取得原価（時価ではなく購入価格）の累計。1,800万円の生涯上限は時価ではなく取得原価で管理されます。",
      "help.ideco_balance_jpy": "iDeCo口座の現在の評価額。掛金は全額所得控除されますが、60歳まで引き出し不可。60歳前にFIREする場合は他の口座でつなぐ必要があります。",
      "help.taxable_brokerage_jpy": "特定口座など課税口座の投資残高。いつでも引き出し可能ですが、売却益に20.315%の税金がかかります。",
      "help.cash_savings_jpy": "銀行預金などの流動性資産。拘束期間なしでいつでも引き出せますが、日本ではほぼ無利子です。",
      "help.foreign_assets_usd": "日本国外の投資・貯蓄（例：米国証券口座、英国ISA）。USD/JPYレートを使って円換算されます。",
      "help.monthly_expenses_jpy": "現在の月間生活費、または退職後の予算。FIREナンバーに最も影響する入力項目です。家賃・食費・交通費・光熱費・保険・旅行・趣味をすべて含めてください。",
      "help.monthly_nisa_contribution_jpy": "新NISAのつみたて投資枠への月間積立額。上限は月10万円（年120万円）。運用益・解約時ともに非課税。",
      "help.nisa_growth_frame_annual_jpy": "新NISAの成長投資枠への年間一括投資額。上限は年240万円。つみたて投資枠のみ使用する場合は0のままにしてください。",
      "help.ideco_monthly_contribution_jpy": "iDeCoの月間掛金。全額所得控除。会社員上限：月2万3千円。自営業者上限：月6万8千円。60歳まで引き出し不可。",
      "help.nenkin_contribution_months": "国民年金＋厚生年金への加入期間（月数）の合計。老齢基礎年金の満額受給には480ヶ月（40年）必要です。ねんきんネット（nenkin.ne.jp）で確認してください。",
      "help.nenkin_claim_age": "年金の受給開始年齢。標準は65歳。繰り上げ受給（60〜64歳）は月0.4%減額。繰り下げ受給（66〜75歳）は月0.7%増額されます。",
      "help.nenkin_net_kosei_annual_jpy": "税引き後の老齢厚生年金の年間受給見込額（円）。0のままにすると、標準報酬月額から自動試算します。ねんきんネットの最新の年金見込み額が最も正確です。",
      "help.avg_standard_monthly_remuneration_jpy": "厚生年金の試算に使用する標準報酬月額の平均。目安として平均的な月額総支給額を入力してください。老齢厚生年金の見込み額を直接入力する場合は不要です。",
      "help.foreign_pension_annual_jpy": "外国の公的年金（米国社会保障、英国国家年金、オーストラリア老齢年金など）の年間受給見込額（円換算）。永住者は日本で所得税がかかります。",
      "help.foreign_pension_start_age": "外国年金の受給開始年齢。米国社会保障：62〜70歳、英国国家年金：66歳、オーストラリア老齢年金：67歳。",
      "help.usd_jpy_rate": "現在のUSD/JPYレート。外貨建て資産を円換算するために使用します。",
      "help.nationality": "2文字のISO国籍コード（例：US、GB、AU）。租税条約の適用確認や非永住者課税ルールの判定に使用します。",
      "help.residency_status": "日本の在留資格。過去10年のうち5年未満の在留歴しかない非永住者は、国外源泉所得のうち国内への送金分のみ課税対象となる場合があります。",
      "help.treaty_country": "租税条約（DTA）の分析に使用する出身国。日本はOECD加盟国の多くと条約を締結しており、年金・投資所得の課税方法に影響します。",
      "help.years_in_japan": "日本への通算在留年数。過去10年のうち日本在留が5年未満の非永住者は、海外の投資収益が日本では課税されない場合があります。",
      "help.property_value_jpy": "日本の不動産の現在の推定時価。売却予定がない場合は運用可能資産には含まれません。",
      "help.mortgage_balance_jpy": "住宅ローンの残高。不動産評価額から差し引いて純資産を算出します。",
      "help.monthly_mortgage_payment_jpy": "毎月の住宅ローン返済額。完済まで月間支出に加算されます。退職時に完済予定の場合は下のチェックボックスをオンにしてください。",
      "help.rental_income_monthly_jpy": "この不動産からの月間賃料収入。月間純支出を減らし、FIREナンバーを下げる効果があります。",
      "help.property_paid_off_at_retirement": "チェックすると、退職後の支出からローン返済額が除かれ、キャッシュフローが改善しFIREナンバーが下がります。",
      "help.property_planned_sale_age": "売却予定がある場合、その年齢で売却益（評価額−残ローン）がモンテカルロシミュレーションの全パスに一括入金されます。",
      "help.property_appreciation_pct": "不動産の年間値上がり率の見込み。日本の住宅は多くの地域で実質ゼロか値下がりしている場合が多いです。東京都心は例外です。",
      "help.foreign_property_value_jpy": "海外不動産の現在の推定時価（円換算）。",
      "help.foreign_property_mortgage_jpy": "海外不動産のローン残高（円換算）。",
      "help.foreign_property_rental_monthly_jpy": "海外不動産からの月間賃料収入（円換算）。",
      "help.foreign_property_planned_sale_age": "海外不動産の売却予定年齢。売却益はシミュレーション内でその年齢にポートフォリオへ加算されます。",
      "help.foreign_property_appreciation_pct": "海外不動産の年間値上がり率の見込み。",
      "help.gold_silver_value_jpy": "金・銀などの貴金属の現在の時価。",
      "help.crypto_value_jpy": "仮想通貨の現在の評価額。注意：日本では暗号資産の利益は雑所得として総合課税（最高55%）され、株式の20.315%の申告分離課税とは異なります。",
      "help.rsu_unvested_value_jpy": "未確定RSU（制限付き株式ユニット）の現在の公正市場価値。RSUは付与（ベスト）時に給与所得として課税されます。",
      "help.rsu_vesting_annual_jpy": "在職中に年間ベストされるRSUの評価額。積立フェーズの年間貯蓄として試算に反映されます。",
      "help.other_assets_jpy": "上記に該当しないその他の資産（例：終身保険の解約返戻金、非上場株式、事業資産、コレクションなど）。",

      // ── Settings help text ────────────────────────────────────────────────
      "help.default_region": "新規シナリオのデフォルト地域。シナリオごとに変更できます。",
      "help.default_nhi_municipality_key": "新規シナリオのデフォルト国保市区町村。国保料は市区町村によって最大2倍の差があります。",
      "help.default_nhi_household_members": "新規シナリオのデフォルトNHI加入人数。加入者が増えるほど均等割が加算されます。",
      "help.default_usd_jpy_rate": "新規シナリオのデフォルトUSD/JPYレート。レートが大きく変動したときに更新してください。",
      "help.default_fire_variant": "新規シナリオの結果でデフォルトでハイライトされるFIRE戦略。この設定に関わらず、すべてのバリアントは常に計算されます。",
      "help.default_language": "デフォルトの表示言語。ナビゲーションバーの言語切り替えでいつでも変更できます。",

      // ── Errors ────────────────────────────────────────────────────────────
      "error.back": "ダッシュボードへ戻る",
      "error.home": "ホーム",
    }
  };

  const STORAGE_KEY = 'jpfirecalc_lang';
  let currentLang = localStorage.getItem(STORAGE_KEY) || 'ja';

  function t(key) {
    const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.ja;
    return dict[key] !== undefined ? dict[key] : (TRANSLATIONS.en[key] || key);
  }

  /**
   * Translate all [data-i18n] elements and auto-translate form field labels
   * by looking up field.{inputName} for each <label for="..."> element.
   */
  function applyTranslations() {
    // 1. Static data-i18n attributes
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const text = t(key);
      if (!text || text === key) return;
      if (text.includes('<')) {
        el.innerHTML = text;
      } else {
        el.textContent = text;
      }
    });

    // 2a. Auto-translate standard field labels by input name
    //     Macros wrap label text in <span>, so we target that span.
    //     e.g. <label for="current_age"> → look up field.current_age
    document.querySelectorAll('label[for]').forEach(label => {
      const inputName = label.getAttribute('for');
      const key = 'field.' + inputName;
      const text = t(key);
      if (!text || text === key) return;
      const span = label.querySelector('span:first-child');
      if (span) span.textContent = text;
    });

    // 2b. Auto-translate checkbox labels (label wraps input directly, no for= attr)
    //     Target .checkbox-text span inside .checkbox-label, keyed by input name.
    document.querySelectorAll('label.checkbox-label').forEach(label => {
      const input = label.querySelector('input[type="checkbox"]');
      if (!input || !input.name) return;
      const key = 'field.' + input.name;
      const text = t(key);
      if (!text || text === key) return;
      const span = label.querySelector('.checkbox-text');
      if (span) span.textContent = text;
    });

    // 2c. Auto-translate .form-help paragraphs via data-help-key attribute.
    //     These are the always-visible help texts below each field.
    document.querySelectorAll('[data-help-key]').forEach(el => {
      const key = el.dataset.helpKey;
      const text = t(key);
      if (!text || text === key) return;
      el.textContent = text;
    });

    // 3. Update lang toggle button label (shows the OTHER language)
    const toggleBtn = document.getElementById('langToggle');
    if (toggleBtn) {
      toggleBtn.textContent = t('nav.lang');
      toggleBtn.setAttribute('lang', currentLang === 'ja' ? 'en' : 'ja');
    }

    // 4. Update html lang attribute
    document.documentElement.lang = currentLang;
  }

  function toggle() {
    currentLang = currentLang === 'ja' ? 'en' : 'ja';
    localStorage.setItem(STORAGE_KEY, currentLang);
    applyTranslations();
  }

  function init() {
    applyTranslations();
    const btn = document.getElementById('langToggle');
    if (btn) btn.addEventListener('click', toggle);
  }

  return { init, toggle, t, currentLang: () => currentLang };
})();

document.addEventListener('DOMContentLoaded', I18n.init);
