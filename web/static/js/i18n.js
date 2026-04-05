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
      "chart.mc.info": "Runs hundreds of simulations with randomised annual returns to show a range of outcomes. <strong>p50</strong> is the median — half of scenarios end above this line, half below. <strong>p10</strong> is the pessimistic 10th percentile; <strong>p90</strong> is optimistic. The shaded bands show the spread. The <em>success rate</em> is the percentage of simulations where the portfolio survives the full retirement period without hitting zero.",
      "chart.tornado.info": "Each bar shows how much your <em>Years to FIRE</em> changes when one variable is adjusted by ±20%. <strong>Red bars</strong> (right) show the pessimistic scenario — more years needed. <strong>Green bars</strong> (left) show the optimistic scenario — fewer years. The longest bars are the variables with the biggest impact on your plan; focus on those first.",
      "chart.trajectory.info": "The <strong>solid line</strong> shows your projected portfolio value during the accumulation phase — while you're working and saving. The <strong>dashed line</strong> shows the drawdown phase after retirement. The projection uses a fixed annual return (not randomised like Monte Carlo) and includes contributions, pension offsets, NHI, and inflation. Hover over the chart to see exact values at each age.",

      // ── Footer ────────────────────────────────────────────────────────────
      "footer.disclaimer": "JPFIRECalc — For informational purposes only. Not financial advice.",

      // ── Dashboard card ────────────────────────────────────────────────────
      "card.age_prefix": "Age",
      "dash.compare_n": "Compare {n} →",

      // ── Scenario detail ───────────────────────────────────────────────────
      "detail.delete_confirm": "Delete this scenario?",
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
      "chart.mc.info": "ランダムな年次リターンを用いた多数のシミュレーションを実行し、結果の分布を表示します。<strong>p50</strong>は中央値（シナリオの半分がこの線より上、半分が下）。<strong>p10</strong>は悲観的な下位10%、<strong>p90</strong>は楽観的な上位10%です。シェード帯はばらつきの幅を示します。<em>成功率</em>は、退職期間全体でポートフォリオがゼロにならずに生存したシミュレーションの割合です。",
      "chart.tornado.info": "各バーは、1つの変数を±20%変化させたときに<em>FIREまでの年数</em>がどれだけ変わるかを示します。<strong>赤いバー</strong>（右側）は悲観的シナリオ（年数が増える）、<strong>緑のバー</strong>（左側）は楽観的シナリオ（年数が減る）です。バーが長いほどプランへの影響が大きい変数です。まずそこに注目しましょう。",
      "chart.trajectory.info": "<strong>実線</strong>は就労・積立期間中のポートフォリオ推移を示します。<strong>破線</strong>は退職後の取り崩し期間を示します。この予測はモンテカルロと異なり固定リターンを使用し、積立・年金オフセット・国保・インフレを考慮しています。グラフにマウスを合わせると各年齢での資産額が確認できます。",

      // ── Footer ────────────────────────────────────────────────────────────
      "footer.disclaimer": "JPFIRECalc — 情報提供のみを目的としています。投資・税務アドバイスではありません。",

      // ── Dashboard card ────────────────────────────────────────────────────
      "card.age_prefix": "年齢",
      "dash.compare_n": "{n}件を比較 →",

      // ── Scenario detail ───────────────────────────────────────────────────
      "detail.delete_confirm": "このシナリオを削除しますか？",
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
