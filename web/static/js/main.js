// JPFIRECalc — main.js

// Format a number as Japanese yen
function formatYen(amount) {
  if (amount >= 100_000_000) {
    return `¥${(amount / 100_000_000).toFixed(1)}億`;
  }
  if (amount >= 10_000) {
    return `¥${(amount / 10_000).toFixed(0)}万`;
  }
  return `¥${amount.toLocaleString()}`;
}

// Format years with one decimal place
function formatYears(years) {
  return `${years.toFixed(1)} yrs`;
}

// Debounce utility for live recalc inputs
function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

document.addEventListener("DOMContentLoaded", () => {

  // ── Auto-dismiss flash messages after 6s ────────────────────────────────
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 6000);
  });

  // ── Client-side form validation for .fire-form ───────────────────────────
  document.querySelectorAll(".fire-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const t = (key, fallback) =>
        typeof I18n !== "undefined" ? I18n.t(key) : fallback;
      const errors = [];

      const age = parseInt(form.querySelector('[name="current_age"]')?.value);
      const retireAge = parseInt(form.querySelector('[name="target_retirement_age"]')?.value);
      if (!isNaN(age) && !isNaN(retireAge) && retireAge <= age) {
        errors.push(t("validation.age_order", "Target retirement age must be greater than current age."));
      }

      const nisa = parseInt(form.querySelector('[name="monthly_nisa_contribution_jpy"]')?.value || "0");
      if (nisa > 100_000) {
        errors.push(t("validation.nisa_limit", "Monthly NISA contribution cannot exceed ¥100,000 (tsumitate frame limit)."));
      }

      const wr = parseFloat(form.querySelector('[name="withdrawal_rate_pct"]')?.value || "0");
      if (wr > 0 && (wr < 0.5 || wr > 10)) {
        errors.push(t("validation.wr_range", "Withdrawal rate must be between 0.5% and 10%."));
      }

      const sims = parseInt(form.querySelector('[name="monte_carlo_simulations"]')?.value || "0");
      if (sims > 0 && sims > 50_000) {
        const el = form.querySelector('[name="monte_carlo_simulations"]');
        if (el) el.value = 10_000;
        // just clamp, don't block submission
      }

      if (errors.length > 0) {
        e.preventDefault();
        form.querySelectorAll(".form-inline-error").forEach(el => el.remove());
        const banner = document.createElement("div");
        banner.className = "form-inline-error";
        banner.innerHTML = errors.map(err => `<div>${err}</div>`).join("");
        form.prepend(banner);
        banner.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // ── Mobile nav toggle ────────────────────────────────────────────────────
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");
  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      const open = navMenu.dataset.open === "true";
      navMenu.dataset.open = open ? "false" : "true";
      navToggle.setAttribute("aria-expanded", !open);
    });
  }

  // ── Tooltip hover (all pages with .tooltip-trigger) ─────────────────────
  // Uses data-tip-key="help.{name}" for i18n; falls back to data-tip (English).
  document.querySelectorAll(".tooltip-trigger").forEach(el => {
    el.addEventListener("mouseenter", () => {
      const key = el.dataset.tipKey;
      let text = el.dataset.tip; // English fallback
      if (key && typeof I18n !== "undefined") {
        const translated = I18n.t(key);
        if (translated && translated !== key) text = translated;
      }
      const tip = document.createElement("div");
      tip.className = "tooltip-popup";
      tip.textContent = text;
      el.appendChild(tip);
    });
    el.addEventListener("mouseleave", () => {
      el.querySelectorAll(".tooltip-popup").forEach(t => t.remove());
    });
  });

});

// ── Mortgages list editor ─────────────────────────────────────────────────
// Renders one row per mortgage loan in profile.mortgages. Users can add
// and remove rows; field names are re-indexed on each change so the form
// posts `mortgages_0_*`, `mortgages_1_*`, etc. — server parses into
// list[MortgageEntry].

// Fields exposed per row (prefix is "mortgages_{idx}_"):
const MORTGAGE_FIELDS = [
  "label", "is_foreign", "balance_jpy", "interest_rate_pct",
  "monthly_payment_jpy", "remaining_years", "loan_type", "prepayment_fee_jpy",
  "tax_credit_remaining_years", "tax_credit_rate_pct", "tax_credit_principal_cap_jpy",
];

function nextMortgageIdx() {
  const list = document.getElementById("mortgages-list");
  if (!list) return 0;
  return list.querySelectorAll(".mortgage-row").length;
}

function buildEmptyMortgageRowHTML(idx) {
  // Mirror of the Jinja mortgage_row macro. Keep field names and
  // default values in sync with components/form_field.html.
  const fields = MORTGAGE_FIELDS.map((name) => {
    let defaultVal = "";
    let type = "text";
    let step = "";
    let min = "";
    let prefix = "";
    let suffix = "";
    let cls = "form-input";
    let isCheckbox = false;
    let checked = "";

    if (name === "label") {
      type = "text";
      suffix = `placeholder="e.g. 柿ノ木坂 土地"`;
    } else if (name === "is_foreign") {
      type = "checkbox";
      isCheckbox = true;
      cls = "form-checkbox";
    } else if (["balance_jpy", "monthly_payment_jpy", "prepayment_fee_jpy",
                 "tax_credit_principal_cap_jpy"].includes(name)) {
      type = "number";
      min = 'min="0"';
      step = name === "monthly_payment_jpy" || name === "prepayment_fee_jpy"
               ? 'step="10000"'
               : name === "balance_jpy"
                 ? 'step="100000"'
                 : 'step="1000000"';
      prefix = '<div class="input-prefix-wrapper"><span class="input-prefix">¥</span>';
      suffix = `${step} ${min} class="form-input has-prefix"></div>`;
    } else if (name === "interest_rate_pct") {
      type = "number"; min = 'min="0" max="20"'; step = 'step="0.05"';
      suffix = `${min} ${step} class="form-input">`;
    } else if (name === "remaining_years" || name === "tax_credit_remaining_years") {
      type = "number";
      const max = name === "tax_credit_remaining_years" ? 'max="13"' : 'max="50"';
      min = 'min="0"';
      step = 'step="1"';
      suffix = `${min} ${max} ${step} class="form-input">`;
    } else if (name === "tax_credit_rate_pct") {
      type = "number"; min = 'min="0" max="1"'; step = 'step="0.05"';
      suffix = `${min} ${step} class="form-input">`;
    } else if (name === "loan_type") {
      // special: select with options
      return null;
    } else {
      suffix = `class="form-input">`;
    }

    if (isCheckbox) {
      return `
        <div class="form-field form-field--checkbox">
          <label class="checkbox-label">
            <input type="checkbox" id="mortgages_${idx}_${name}"
                   name="mortgages_${idx}_${name}" ${checked} class="${cls}">
            <span class="checkbox-text">Foreign loan (no 住宅ローン控除)</span>
          </label>
        </div>`;
    } else {
      const id = `mortgages_${idx}_${name}`;
      const nameAttr = `mortgages_${idx}_${name}`;
      return `
        <div class="form-field">
          <label for="${id}" class="form-label">${labelFor(name)}</label>
          ${prefix}
            <input type="${type}" id="${id}" name="${nameAttr}" value="${defaultVal}" ${suffix.trim()}>
        </div>`;
    }
  }).filter(Boolean);

  // Build grid layout (2-col first row, then 3-col, then 3-col)
  // Simpler: render flat list — let CSS flex-wrap handle layout.
  // But for cleaner layout, we'll structure by rows.
  // For now: emit a flat 3-col grid (we'll style with grid-template-columns:
  // repeat(auto-fit, minmax(220px, 1fr))).
  const gridItems = [];
  // Row 1: label, is_foreign (checkbox, no label)
  gridItems.push(`<div class="form-grid form-grid--2">${fields.slice(0, 2).join("")}</div>`);
  // Row 2: balance, rate, payment
  gridItems.push(`<div class="form-grid form-grid--3">${fields.slice(2, 5).join("")}</div>`);
  // Row 3: remaining, loan_type (select), prepay fee
  const loanTypeSelect = `
    <div class="form-field">
      <label for="mortgages_${idx}_loan_type" class="form-label">Type</label>
      <select id="mortgages_${idx}_loan_type" name="mortgages_${idx}_loan_type" class="form-select">
        <option value="variable">Variable</option>
        <option value="fixed">Fixed</option>
      </select>
    </div>`;
  gridItems.push(`<div class="form-grid form-grid--3">${[fields[5], loanTypeSelect, fields[7]].join("")}</div>`);
  // Row 4: tax credit fields
  const taxCreditFields = fields.slice(8);
  gridItems.push(`<div class="mortgage-tax-credit-fields">
    <div class="form-subsection-divider mortgage-credit-divider"></div>
    <p class="form-help-inline">Housing loan tax credit (住宅ローン控除) — Japanese mortgages only</p>
    <div class="form-grid form-grid--3">${taxCreditFields.join("")}</div>
  </div>`);

  return `
    <div class="mortgage-row-inner">
      <input type="hidden" name="mortgages_${idx}_id" value="">
      <div class="mortgage-row-header">
        <span class="mortgage-row-title">Loan #${idx + 1}</span>
        <button type="button" class="mortgage-remove-btn" data-action="remove-mortgage"
                aria-label="Remove mortgage row">×</button>
      </div>
      ${gridItems.join("\n")}
    </div>`;
}

function labelFor(name) {
  return {
    label: "Label",
    balance_jpy: "Balance",
    interest_rate_pct: "Interest Rate (%)",
    monthly_payment_jpy: "Monthly Payment",
    remaining_years: "Remaining (years)",
    prepayment_fee_jpy: "Prepay Fee",
    tax_credit_remaining_years: "Credit Years Left",
    tax_credit_rate_pct: "Credit Rate (%)",
    tax_credit_principal_cap_jpy: "Credit Cap",
  }[name] || name;
}

function addMortgageRow() {
  const list = document.getElementById("mortgages-list");
  if (!list) return;
  const idx = nextMortgageIdx();
  const wrap = document.createElement("div");
  wrap.className = "mortgage-row";
  wrap.dataset.idx = String(idx);
  wrap.innerHTML = buildEmptyMortgageRowHTML(idx);
  list.appendChild(wrap);
  // Wire up the foreign toggle and remove button on the new row
  wireMortgageRow(wrap);
}

function removeMortgageRow(rowEl) {
  rowEl.remove();
  reindexMortgageRows();
}

function reindexMortgageRows() {
  const list = document.getElementById("mortgages-list");
  if (!list) return;
  const rows = list.querySelectorAll(".mortgage-row");
  rows.forEach((row, newIdx) => {
    row.dataset.idx = String(newIdx);
    // Update field name + id attributes that start with "mortgages_<n>_"
    row.querySelectorAll("[name^='mortgages_'], [id^='mortgages_']").forEach((el) => {
      const attr = el.hasAttribute("name") ? "name" : "id";
      el.setAttribute(attr, el.getAttribute(attr).replace(/^mortgages_\d+_/, `mortgages_${newIdx}_`));
    });
    // Update the row title
    const titleEl = row.querySelector(".mortgage-row-title");
    if (titleEl) titleEl.textContent = `Loan #${newIdx + 1}`;
  });
}

function wireMortgageRow(rowEl) {
  const foreignCheckbox = rowEl.querySelector("input[type='checkbox'][id$='_is_foreign']");
  const taxCreditBlock = rowEl.querySelector(".mortgage-tax-credit-fields");
  const updateVisibility = () => {
    if (!foreignCheckbox || !taxCreditBlock) return;
    taxCreditBlock.style.display = foreignCheckbox.checked ? "none" : "";
  };
  if (foreignCheckbox) {
    foreignCheckbox.addEventListener("change", updateVisibility);
    updateVisibility();
  }
}

function initMortgagesList() {
  const list = document.getElementById("mortgages-list");
  const addBtn = document.getElementById("mortgages-add-btn");
  if (!list || !addBtn) return;

  // Wire up existing rows (server-rendered)
  list.querySelectorAll(".mortgage-row").forEach((row) => wireMortgageRow(row));

  // Add button
  addBtn.addEventListener("click", () => {
    addMortgageRow();
  });

  // Remove buttons — delegated (also catches dynamically added rows
  // even though wireMortgageRow only handles the new row's foreign toggle)
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action='remove-mortgage']");
    if (!btn) return;
    const row = btn.closest(".mortgage-row");
    if (row) removeMortgageRow(row);
  });

  // If user has zero rows on initial load, add one empty row so the
  // form is functional (the server renders at least one row already,
  // but guard against edge cases where the list starts empty).
  if (list.children.length === 0) {
    addMortgageRow();
  }
}
