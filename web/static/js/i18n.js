/**
 * JPFIRECalc i18n — Japanese / English language toggle
 *
 * Default language: Japanese (ja)
 * Preference stored in localStorage under 'jpfirecalc_lang'
 *
 * Usage: elements with data-i18n="key.path" are swapped on toggle.
 * Keys that contain HTML use innerHTML; plain strings use textContent.
 */

const I18n = (() => {

  const TRANSLATIONS = {
    en: {
      // Nav
      "nav.dashboard": "Dashboard",
      "nav.new": "+ New",
      "nav.lang": "日本語",

      // Hero
      "hero.badge": "Built for Japan",
      "hero.title": "Your FIRE number,<br>the Japan way.",
      "hero.subtitle": "Model iDeCo, 新NISA, nenkin, NHI premiums, residence tax, and regional cost of living — all the variables that generic calculators miss.",
      "hero.cta_primary": "Get Started",
      "hero.cta_secondary": "How it works",

      // Features
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

      // Rules
      "rules.title": "Japan FIRE — Rules of Thumb",
      "rules.swr": "Safe withdrawal rate for Japan<br><small>Lower than the US 4% rule due to Japan's lower expected equity returns and higher bond allocation norms</small>",
      "rules.shock": "Residence tax shock<br><small>You'll pay full residence tax on your last salary in year 1 of retirement. Budget for it.</small>",
      "rules.ideco": "iDeCo unlock age<br><small>iDeCo is completely illiquid before 60. Pre-60 FIRE means NISA + taxable must cover the gap.</small>",
      "rules.nisa": "新NISA lifetime cap<br><small>1.2M/yr tsumitate + 2.4M/yr growth frame. Tax-free growth and withdrawal, fully liquid.</small>",

      // CTA
      "cta.title": "Ready to run your numbers?",
      "cta.body": "Create a profile, build scenarios, and compare them side by side.",
      "cta.button": "Start Calculating",

      // Dashboard
      "dash.title": "Dashboard",
      "dash.new": "+ New Scenario",
      "dash.hint": "Select scenarios to compare side-by-side.",
      "dash.compare": "Compare Selected →",
      "dash.empty.title": "No scenarios yet",
      "dash.empty.body": "Create your first scenario to model your Japan FIRE path — including Monte Carlo simulation, NHI projections, and pension offset.",
      "dash.empty.cta": "Create First Scenario →",
      "dash.storage": "Scenarios are saved on the server. On the free Railway plan the filesystem resets on redeploy — export important scenarios before updating.",

      // Scenario card
      "card.view": "View Results →",
      "card.return": "Return",
      "card.withdrawal": "Withdrawal",
      "card.inflation": "Inflation",
      "card.sims": "Simulations",

      // Scenario detail
      "detail.edit_profile": "Edit Profile",
      "detail.edit_assumptions": "Edit Assumptions",
      "detail.delete": "Delete",

      // Results
      "result.fire_number": "FIRE Number",
      "result.years": "Years to FIRE",
      "result.progress": "Progress",
      "result.mc_success": "MC Success",
      "result.already_fired": "Already FIRE'd!",
      "result.never": "Never reached",
      "result.never_sub": "Increase savings or reduce expenses",
      "result.coast": "Coast FIRE",
      "result.cashflow": "Retirement Cash Flow",
      "result.expenses": "Annual Expenses",
      "result.pension": "Pension (net)",
      "result.nhi": "NHI Premium",
      "result.net_portfolio": "Net from Portfolio / yr",
      "result.year1_shock": "Year-1 Residence Tax Shock",
      "result.balances": "Projected Balances at Retirement",
      "result.nisa_label": "新NISA",
      "result.ideco_label": "iDeCo",
      "result.taxable_label": "Taxable / Cash",
      "result.mc_chart": "Portfolio Survival — Monte Carlo",
      "result.sensitivity": "Sensitivity Analysis",
      "result.trajectory": "Net Worth Projection",
      "result.tax_summary": "Current Tax Summary",
      "result.income_tax": "Income Tax",
      "result.residence_tax": "Residence Tax",
      "result.effective_rate": "Effective Tax Rate",
      "result.foreigners": "Foreigners Mode",

      // Errors
      "error.back": "Go to Dashboard",
      "error.home": "Home",
    },

    ja: {
      // Nav
      "nav.dashboard": "ダッシュボード",
      "nav.new": "+ 新規",
      "nav.lang": "English",

      // Hero
      "hero.badge": "日本のFIREに特化",
      "hero.title": "あなたのFIRE目標額を、<br>日本仕様で計算。",
      "hero.subtitle": "iDeCo・新NISA・年金・国民健康保険料・住民税・地域別生活費など、一般的な計算ツールでは対応していない日本特有の変数をすべてモデル化します。",
      "hero.cta_primary": "はじめる",
      "hero.cta_secondary": "使い方を見る",

      // Features
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

      // Rules
      "rules.title": "日本のFIRE — 基本的な目安",
      "rules.swr": "日本における安全な取り崩し率<br><small>日本株の期待リターンの低さと債券比率の高さから、米国の4%ルールより低い水準が推奨されています</small>",
      "rules.shock": "退職1年目の住民税ショック<br><small>退職翌年も前年の給与をもとに住民税が課税されます。退職初年度の予算確保が必要です。</small>",
      "rules.ideco": "iDeCoの解禁年齢<br><small>iDeCoは60歳まで引き出し不可。60歳前にFIREする場合は、新NISA＋特定口座でブリッジ期間をカバーする必要があります。</small>",
      "rules.nisa": "新NISAの生涯投資枠<br><small>つみたて投資枠120万円/年＋成長投資枠240万円/年。売却しても翌年に枠が復活。利益・配当はすべて非課税。</small>",

      // CTA
      "cta.title": "あなたの数字を計算してみましょう",
      "cta.body": "プロフィールを作成し、複数のシナリオを構築・比較できます。",
      "cta.button": "無料で計算を始める",

      // Dashboard
      "dash.title": "ダッシュボード",
      "dash.new": "+ 新規シナリオ",
      "dash.hint": "シナリオを選択して比較できます。",
      "dash.compare": "選択したシナリオを比較 →",
      "dash.empty.title": "シナリオがまだありません",
      "dash.empty.body": "最初のシナリオを作成して、モンテカルロ・シミュレーション、国民健康保険料の試算、年金オフセットを含む日本のFIREプランを構築しましょう。",
      "dash.empty.cta": "最初のシナリオを作成 →",
      "dash.storage": "シナリオはサーバーに保存されます。Railwayの無料プランではデプロイのたびにファイルシステムがリセットされます。重要なシナリオは事前にエクスポートしてください。",

      // Scenario card
      "card.view": "結果を見る →",
      "card.return": "リターン",
      "card.withdrawal": "取り崩し率",
      "card.inflation": "インフレ率",
      "card.sims": "シミュレーション数",

      // Scenario detail
      "detail.edit_profile": "プロフィール編集",
      "detail.edit_assumptions": "前提条件を編集",
      "detail.delete": "削除",

      // Results
      "result.fire_number": "FIRE目標額",
      "result.years": "FIREまでの年数",
      "result.progress": "達成率",
      "result.mc_success": "MC成功率",
      "result.already_fired": "すでにFIRE達成！",
      "result.never": "達成不可",
      "result.never_sub": "貯蓄を増やすか支出を減らしてください",
      "result.coast": "コーストFIRE",
      "result.cashflow": "退職後のキャッシュフロー",
      "result.expenses": "年間支出",
      "result.pension": "年金収入（税引後）",
      "result.nhi": "国民健康保険料",
      "result.net_portfolio": "ポートフォリオからの純引き出し額/年",
      "result.year1_shock": "1年目の住民税ショック",
      "result.balances": "退職時の口座残高予測",
      "result.nisa_label": "新NISA",
      "result.ideco_label": "iDeCo",
      "result.taxable_label": "特定口座／現金",
      "result.mc_chart": "ポートフォリオ生存率 — モンテカルロ",
      "result.sensitivity": "感度分析",
      "result.trajectory": "資産推移グラフ",
      "result.tax_summary": "現在の税負担",
      "result.income_tax": "所得税",
      "result.residence_tax": "住民税",
      "result.effective_rate": "実効税率",
      "result.foreigners": "外国人居住者向け分析",

      // Errors
      "error.back": "ダッシュボードへ戻る",
      "error.home": "ホーム",
    }
  };

  const STORAGE_KEY = 'jpfirecalc_lang';
  let currentLang = localStorage.getItem(STORAGE_KEY) || 'ja';

  function t(key) {
    const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.ja;
    return dict[key] || TRANSLATIONS.en[key] || key;
  }

  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const text = t(key);
      if (!text) return;
      // Use innerHTML for strings that contain tags (<br>, <small>, etc.)
      if (text.includes('<')) {
        el.innerHTML = text;
      } else {
        el.textContent = text;
      }
    });

    // Update lang toggle button label (shows the OTHER language)
    const toggleBtn = document.getElementById('langToggle');
    if (toggleBtn) {
      toggleBtn.textContent = t('nav.lang');
      toggleBtn.setAttribute('lang', currentLang === 'ja' ? 'en' : 'ja');
    }

    // Update html lang attribute
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
