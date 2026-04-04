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

// Auto-dismiss flash messages after 6s
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 6000);
  });

  // Client-side form validation for .fire-form
  document.querySelectorAll(".fire-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const errors = [];

      const age = parseInt(form.querySelector('[name="current_age"]')?.value);
      const retireAge = parseInt(form.querySelector('[name="target_retirement_age"]')?.value);
      if (!isNaN(age) && !isNaN(retireAge) && retireAge <= age) {
        errors.push("Target retirement age must be greater than current age.");
      }

      const nisa = parseInt(form.querySelector('[name="monthly_nisa_contribution_jpy"]')?.value || "0");
      if (nisa > 100_000) {
        errors.push("Monthly NISA contribution cannot exceed ¥100,000 (tsumitate frame limit).");
      }

      const wr = parseFloat(form.querySelector('[name="withdrawal_rate_pct"]')?.value || "0");
      if (wr > 0 && (wr < 0.5 || wr > 10)) {
        errors.push("Withdrawal rate must be between 0.5% and 10%.");
      }

      const sims = parseInt(form.querySelector('[name="monte_carlo_simulations"]')?.value || "0");
      if (sims > 0 && sims > 50_000) {
        errors.push("Simulations capped at 50,000.");
        const el = form.querySelector('[name="monte_carlo_simulations"]');
        if (el) el.value = 10_000;
        errors.pop(); // just clamp, don't block
      }

      if (errors.length > 0) {
        e.preventDefault();
        // Remove old inline errors
        form.querySelectorAll(".form-inline-error").forEach(el => el.remove());
        // Show at top of form
        const banner = document.createElement("div");
        banner.className = "form-inline-error";
        banner.innerHTML = errors.map(err => `<div>${err}</div>`).join("");
        form.prepend(banner);
        banner.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // Mobile nav toggle
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");
  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      const open = navMenu.dataset.open === "true";
      navMenu.dataset.open = open ? "false" : "true";
      navToggle.setAttribute("aria-expanded", !open);
    });
  }
});
