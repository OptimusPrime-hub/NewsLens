/**
 * bias_chart.js — Chart.js bias visualisations (no chartjs-chart-matrix required)
 *
 * Renders from BiasAnalysisResult:
 *   publisher_profiles: list[PublisherBiasProfile]
 *     publisher, sentiment{positive,neutral,negative,compound},
 *     framing{conflict,economic,human_interest,morality,responsibility},
 *     bias_score, supporting_quotes
 *   summary_explanation: str
 *
 * Chart 1: Stacked horizontal bar — positive/neutral/negative sentiment per publisher
 * Chart 2: Radar — framing dimensions averaged across publishers
 * Below:   Publisher bias profile cards with quotes
 */

window.renderBias = function (biasResult) {
  const skel  = document.getElementById('bias-skeleton');
  const cont  = document.getElementById('bias-container');
  const empty = document.getElementById('bias-empty');
  if (!cont) return;

  if (skel) skel.remove();

  if (!biasResult || !biasResult.publisher_profiles?.length) {
    empty?.classList.remove('hidden');
    return;
  }

  cont.classList.remove('hidden');

  const profiles = biasResult.publisher_profiles;

  /* ── Chart 1: Stacked sentiment bars ─────────────────────── */
  const sentCtx = document.getElementById('chart-sentiment');
  if (sentCtx) {
    const labels = profiles.map(p => p.publisher);
    new Chart(sentCtx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Positive',
            data: profiles.map(p => +(p.sentiment?.positive * 100).toFixed(1)),
            backgroundColor: 'rgba(34,197,94,0.75)',
          },
          {
            label: 'Neutral',
            data: profiles.map(p => +(p.sentiment?.neutral * 100).toFixed(1)),
            backgroundColor: 'rgba(99,102,241,0.55)',
          },
          {
            label: 'Negative',
            data: profiles.map(p => +(p.sentiment?.negative * 100).toFixed(1)),
            backgroundColor: 'rgba(239,68,68,0.7)',
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#8b949e', font: { size: 11 } } },
          tooltip: {
            callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%` },
          },
        },
        scales: {
          x: {
            stacked: true, max: 100,
            ticks: { color: '#8b949e', callback: v => v + '%' },
            grid:  { color: 'rgba(255,255,255,0.05)' },
          },
          y: {
            stacked: true,
            ticks: { color: '#f0f6fc', font: { weight: '600' } },
            grid:  { display: false },
          },
        },
      },
    });
  }

  /* ── Chart 2: Framing radar (averaged) ───────────────────── */
  const framingCtx = document.getElementById('chart-framing');
  if (framingCtx) {
    const dims = ['conflict', 'economic', 'human_interest', 'morality', 'responsibility'];
    const dimLabels = ['Conflict', 'Economic', 'Human Interest', 'Morality', 'Responsibility'];
    const COLORS = [
      'rgba(99,102,241,0.7)',  'rgba(6,182,212,0.7)',
      'rgba(34,197,94,0.7)',   'rgba(245,158,11,0.7)',
      'rgba(239,68,68,0.7)',
    ];

    const datasets = profiles.map((p, i) => ({
      label: p.publisher,
      data: dims.map(d => +((p.framing?.[d] || 0) * 100).toFixed(1)),
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: COLORS[i % COLORS.length].replace('0.7', '0.1'),
      borderWidth: 2,
      pointBackgroundColor: COLORS[i % COLORS.length],
    }));

    new Chart(framingCtx, {
      type: 'radar',
      data: { labels: dimLabels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#8b949e', font: { size: 11 } } },
        },
        scales: {
          r: {
            min: 0, max: 100,
            ticks: { color: '#484f58', stepSize: 25, backdropColor: 'transparent' },
            pointLabels: { color: '#8b949e', font: { size: 11 } },
            grid:  { color: 'rgba(255,255,255,0.07)' },
            angleLines: { color: 'rgba(255,255,255,0.06)' },
          },
        },
      },
    });
  }

  /* ── Publisher profile cards ──────────────────────────────── */
  const profilesEl = document.getElementById('bias-profiles');
  if (!profilesEl) return;

  // Summary explanation banner
  if (biasResult.summary_explanation) {
    const banner = document.createElement('div');
    banner.style.cssText = `grid-column:1/-1;background:var(--bg-elevated);
      border:1px solid var(--border-subtle);border-radius:var(--radius-md);
      padding:1rem 1.25rem;font-size:0.875rem;color:var(--text-secondary);
      line-height:1.7;margin-bottom:0.25rem;`;
    banner.textContent = biasResult.summary_explanation;
    profilesEl.appendChild(banner);
  }

  profiles.forEach((p, i) => {
    const biasAbs = Math.abs(p.bias_score || 0);
    const biasLabel = biasAbs > 0.6 ? 'High' : biasAbs > 0.3 ? 'Medium' : 'Low';
    const biasClass = biasAbs > 0.6 ? 'badge-low' : biasAbs > 0.3 ? 'badge-medium' : 'badge-relevant';
    const compound = p.sentiment?.compound || 0;
    const sentLabel = compound > 0.05 ? '▲ Positive' : compound < -0.05 ? '▼ Negative' : '● Neutral';
    const sentColor = compound > 0.05 ? 'var(--conf-high)' : compound < -0.05 ? 'var(--accent-red)' : 'var(--text-muted)';

    const card = document.createElement('div');
    card.className = 'glass';
    card.style.cssText = 'padding:1.25rem;animation:slideUp 0.4s ease both;';
    card.style.animationDelay = (i * 80) + 'ms';

    const quotes = (p.supporting_quotes || []).slice(0, 2).map(q =>
      `<blockquote style="border-left:2px solid var(--border-glow);padding-left:0.75rem;
         margin-top:0.5rem;font-size:0.75rem;color:var(--text-secondary);
         font-style:italic;line-height:1.6;">"${sanitize(q)}"</blockquote>`
    ).join('');

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
        <span style="font-size:0.8rem;font-weight:700;color:var(--accent-cyan);
                     letter-spacing:0.06em;text-transform:uppercase;">${sanitize(p.publisher)}</span>
        <span class="badge ${biasClass}">BIAS ${biasLabel}</span>
      </div>
      <div style="font-size:0.8rem;font-weight:600;color:${sentColor};margin-bottom:0.5rem;">${sentLabel}</div>
      <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.25rem;">
        Bias score: ${(p.bias_score || 0).toFixed(3)}
      </div>
      ${quotes}`;
    profilesEl.appendChild(card);
  });
};

function sanitize(str) {
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}
