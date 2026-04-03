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

// Auto-dismiss flash messages after 5s
document.addEventListener("DOMContentLoaded", () => {
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});
