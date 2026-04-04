/**
 * JPFIRECalc chart rendering — wraps Plotly.js
 *
 * Reads data from <script type="application/json"> blocks and
 * renders into designated div containers.
 *
 * Called on DOMContentLoaded and after every HTMX swap.
 */

const JPFIRECharts = (() => {
  // ── Shared Plotly layout defaults ─────────────────────────────────────────
  const BASE_LAYOUT = {
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'transparent',
    font: { family: 'Inter, -apple-system, sans-serif', color: '#e8eaf2', size: 12 },
    margin: { t: 24, r: 24, b: 48, l: 80 },
    xaxis: { gridcolor: '#2a2f45', zerolinecolor: '#2a2f45', tickfont: { color: '#8a90a8' } },
    yaxis: { gridcolor: '#2a2f45', zerolinecolor: '#2a2f45', tickfont: { color: '#8a90a8' } },
    legend: { bgcolor: 'transparent', font: { color: '#8a90a8' } },
    hovermode: 'x unified',
    hoverlabel: { bgcolor: '#1e2235', bordercolor: '#2a2f45', font: { color: '#e8eaf2' } },
  };

  const CONFIG = { responsive: true, displayModeBar: false };

  // Palette
  const C = {
    primary:  '#5b6af0',
    accent:   '#e8b84b',
    success:  '#34c77b',
    danger:   '#e05252',
    muted:    '#8a90a8',
    band_p25_p75: 'rgba(91,106,240,0.20)',
    band_p10_p90: 'rgba(91,106,240,0.10)',
  };

  function formatYen(v) {
    if (Math.abs(v) >= 1e8) return '¥' + (v / 1e8).toFixed(1) + '億';
    if (Math.abs(v) >= 1e4) return '¥' + Math.round(v / 1e4) + '万';
    return '¥' + v.toLocaleString();
  }

  // ── Monte Carlo fan chart ─────────────────────────────────────────────────
  function renderMonteCarlo() {
    const el = document.getElementById('mcChart');
    if (!el) return;

    const p10 = JSON.parse(el.dataset.p10 || '[]');
    const p25 = JSON.parse(el.dataset.p25 || '[]');
    const p50 = JSON.parse(el.dataset.p50 || '[]');
    const p75 = JSON.parse(el.dataset.p75 || '[]');
    const p90 = JSON.parse(el.dataset.p90 || '[]');
    const years = Array.from({ length: p50.length }, (_, i) => i);

    const traces = [
      // p10–p90 outer band (fill between p10 and p90)
      {
        x: [...years, ...years.slice().reverse()],
        y: [...p90, ...p10.slice().reverse()],
        fill: 'toself', fillcolor: C.band_p10_p90,
        line: { width: 0 }, name: 'p10–p90', showlegend: true,
        hoverinfo: 'skip',
      },
      // p25–p75 inner band
      {
        x: [...years, ...years.slice().reverse()],
        y: [...p75, ...p25.slice().reverse()],
        fill: 'toself', fillcolor: C.band_p25_p75,
        line: { width: 0 }, name: 'p25–p75', showlegend: true,
        hoverinfo: 'skip',
      },
      // p10 line
      {
        x: years, y: p10, mode: 'lines',
        line: { color: C.danger, width: 1, dash: 'dot' },
        name: 'p10', hovertemplate: 'p10: %{text}<extra></extra>',
        text: p10.map(formatYen),
      },
      // p50 median — most prominent
      {
        x: years, y: p50, mode: 'lines',
        line: { color: C.primary, width: 2.5 },
        name: 'Median (p50)', hovertemplate: 'Median: %{text}<extra></extra>',
        text: p50.map(formatYen),
      },
      // p90 line
      {
        x: years, y: p90, mode: 'lines',
        line: { color: C.success, width: 1, dash: 'dot' },
        name: 'p90', hovertemplate: 'p90: %{text}<extra></extra>',
        text: p90.map(formatYen),
      },
    ];

    const layout = {
      ...BASE_LAYOUT,
      xaxis: { ...BASE_LAYOUT.xaxis, title: 'Years into Retirement' },
      yaxis: {
        ...BASE_LAYOUT.yaxis,
        title: 'Portfolio Value',
        tickformat: ',.0f',
        tickprefix: '¥',
      },
    };

    Plotly.newPlot(el, traces, layout, CONFIG);
  }

  // ── Tornado / sensitivity chart ───────────────────────────────────────────
  function renderTornado() {
    const dataEl = document.getElementById('tornadoData');
    const chartEl = document.getElementById('tornadoChart');
    if (!dataEl || !chartEl) return;

    let items;
    try { items = JSON.parse(dataEl.textContent); } catch (e) { return; }
    if (!items || items.length === 0) return;

    // Sort largest swing at top (already sorted server-side, but ensure)
    items.sort((a, b) =>
      (Math.abs(b.delta_pessimistic) + Math.abs(b.delta_optimistic)) -
      (Math.abs(a.delta_pessimistic) + Math.abs(a.delta_optimistic))
    );

    const labels = items.map(d => d.label);
    // Pessimistic bars go right (positive delta = more years = bad)
    const pessValues = items.map(d => Math.max(0, d.delta_pessimistic));
    // Optimistic bars go left (negative delta = fewer years = good)
    const optValues  = items.map(d => -Math.max(0, d.delta_optimistic));

    const traces = [
      {
        type: 'bar', orientation: 'h',
        y: labels, x: pessValues,
        name: 'Pessimistic (+yrs)',
        marker: { color: C.danger },
        hovertemplate: '+%{x:.1f} years<extra>Pessimistic</extra>',
      },
      {
        type: 'bar', orientation: 'h',
        y: labels, x: optValues,
        name: 'Optimistic (−yrs)',
        marker: { color: C.success },
        hovertemplate: '%{x:.1f} years<extra>Optimistic</extra>',
      },
    ];

    const layout = {
      ...BASE_LAYOUT,
      barmode: 'overlay',
      xaxis: { ...BASE_LAYOUT.xaxis, title: 'Change in Years to FIRE', zeroline: true, zerolinewidth: 2, zerolinecolor: '#353b55' },
      yaxis: { ...BASE_LAYOUT.yaxis, automargin: true },
      margin: { ...BASE_LAYOUT.margin, l: 180 },
      legend: { ...BASE_LAYOUT.legend, orientation: 'h', y: -0.15 },
    };

    Plotly.newPlot(chartEl, traces, layout, CONFIG);
  }

  // ── Net worth trajectory ──────────────────────────────────────────────────
  function renderTrajectory() {
    const dataEl = document.getElementById('trajectoryData');
    const chartEl = document.getElementById('trajectoryChart');
    if (!dataEl || !chartEl) return;

    let data;
    try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
    if (!data || data.length === 0) return;

    const accum = data.filter(d => d.phase === 'accumulation');
    const retire = data.filter(d => d.phase === 'retirement');

    const traces = [];
    if (accum.length > 0) {
      traces.push({
        x: accum.map(d => d.age), y: accum.map(d => d.portfolio_value_jpy),
        mode: 'lines', name: 'Accumulation',
        line: { color: C.primary, width: 2.5 },
        hovertemplate: 'Age %{x}: %{text}<extra>Accumulation</extra>',
        text: accum.map(d => formatYen(d.portfolio_value_jpy)),
      });
    }
    if (retire.length > 0) {
      traces.push({
        x: retire.map(d => d.age), y: retire.map(d => d.portfolio_value_jpy),
        mode: 'lines', name: 'Retirement',
        line: { color: C.accent, width: 2.5, dash: 'dash' },
        hovertemplate: 'Age %{x}: %{text}<extra>Retirement</extra>',
        text: retire.map(d => formatYen(d.portfolio_value_jpy)),
      });
    }

    const layout = {
      ...BASE_LAYOUT,
      xaxis: { ...BASE_LAYOUT.xaxis, title: 'Age' },
      yaxis: {
        ...BASE_LAYOUT.yaxis,
        title: 'Portfolio Value',
        tickformat: ',.0f',
        tickprefix: '¥',
      },
    };

    Plotly.newPlot(chartEl, traces, layout, CONFIG);
  }

  // ── Public: render everything present on the page ─────────────────────────
  function renderAll() {
    if (typeof Plotly === 'undefined') return;
    renderMonteCarlo();
    renderTornado();
    renderTrajectory();
  }

  return { renderAll, renderMonteCarlo, renderTornado, renderTrajectory };
})();
