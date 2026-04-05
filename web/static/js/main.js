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
