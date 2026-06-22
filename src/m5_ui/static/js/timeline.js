/**
 * timeline.js — Horizontal scroll timeline renderer
 *
 * Consumes TimelineResult from AnalysisResult:
 *   events: list[TimelineEvent]  (sorted asc by date)
 *   temporal_gaps: list[[date,date]]
 *   coherence_score: float
 *   total_sources_used: int
 *   date_range_covered: [date, date]
 *
 * TimelineEvent fields:
 *   event_id, date, date_precision, headline,
 *   description, publishers, confidence (HIGH/MEDIUM/LOW/UNVERIFIED)
 */

window.renderTimeline = function (timelineResult) {
  const skel  = document.getElementById('timeline-skeleton');
  const cont  = document.getElementById('timeline-container');
  const empty = document.getElementById('timeline-empty');
  const meta  = document.getElementById('timeline-meta');
  if (!cont) return;

  if (skel) skel.remove();

  if (!timelineResult || !timelineResult.events?.length) {
    empty?.classList.remove('hidden');
    return;
  }

  // Populate meta line
  if (meta) {
    const from = timelineResult.date_range_covered?.[0] || '';
    const to   = timelineResult.date_range_covered?.[1] || '';
    const coh  = timelineResult.coherence_score != null
      ? ` · Coherence ${Math.round(timelineResult.coherence_score * 100)}%` : '';
    meta.textContent =
      `${timelineResult.events.length} events · ${timelineResult.total_sources_used ?? 0} sources` +
      (from ? ` · ${from} → ${to}` : '') + coh;
  }

  cont.classList.remove('hidden');

  // Build gap lookup: map event index → gap after it
  const gapSet = new Set((timelineResult.temporal_gaps || []).map(g => g[0]));

  const inner = document.createElement('div');
  inner.className = 'timeline-inner';

  timelineResult.events.forEach((evt, idx) => {
    const confClass = (evt.confidence || 'UNVERIFIED').toLowerCase();

    // Event node
    const node = document.createElement('div');
    node.className = 'timeline-event anim-up';
    node.style.animationDelay = (idx * 50) + 'ms';
    node.setAttribute('title', evt.description || evt.headline);

    // Publisher list
    const pubs = (evt.publishers || []).join(', ') || 'Unknown source';
    const confBadgeClass = {
      high: 'badge-high', medium: 'badge-medium',
      low: 'badge-low', unverified: 'badge-unverified',
    }[confClass] || 'badge-unverified';

    node.innerHTML = `
      <div class="timeline-dot ${confClass}"></div>
      <div class="timeline-card">
        <div class="timeline-date">${evt.date || ''}
          <span style="font-size:0.65rem;color:var(--text-muted);">(${evt.date_precision || 'day'})</span>
        </div>
        <div class="timeline-headline">${sanitize(evt.headline || '')}</div>
        <div class="timeline-publishers">${sanitize(pubs)}</div>
        <div style="margin-top:0.375rem;">
          <span class="badge ${confBadgeClass}">${(evt.confidence || 'UNVERIFIED').toUpperCase()}</span>
        </div>
      </div>`;

    // Click to show description overlay
    node.addEventListener('click', () => showEventOverlay(evt));
    inner.appendChild(node);

    // Gap indicator after this event if needed
    if (gapSet.has(evt.date)) {
      const gap = document.createElement('div');
      gap.className = 'timeline-gap';
      gap.innerHTML = `
        <div class="timeline-dot" style="background:var(--accent-amber);"></div>
        <div class="timeline-gap-bar"></div>
        <div class="timeline-gap-label">GAP</div>`;
      inner.appendChild(gap);
    }
  });

  cont.appendChild(inner);
};

/* ── Event detail overlay ─────────────────────────────────── */
function showEventOverlay(evt) {
  let overlay = document.getElementById('event-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'event-overlay';
    overlay.style.cssText = `position:fixed;inset:0;z-index:800;display:flex;
      align-items:center;justify-content:center;
      background:rgba(8,11,20,0.85);backdrop-filter:blur(8px);`;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  const confBadgeClass = {
    HIGH: 'badge-high', MEDIUM: 'badge-medium',
    LOW: 'badge-low', UNVERIFIED: 'badge-unverified',
  }[evt.confidence] || 'badge-unverified';

  overlay.innerHTML = `
    <div class="glass" style="max-width:520px;width:90%;padding:2rem;position:relative;">
      <button onclick="document.getElementById('event-overlay').remove()"
        style="position:absolute;top:1rem;right:1rem;background:none;border:none;
               color:var(--text-muted);font-size:1.25rem;cursor:pointer;">✕</button>
      <div style="font-size:0.7rem;font-weight:700;color:var(--accent-cyan);
                  letter-spacing:0.08em;margin-bottom:0.5rem;">${evt.date || ''}</div>
      <h3 style="margin-bottom:0.75rem;">${sanitize(evt.headline || '')}</h3>
      <p style="font-size:0.875rem;color:var(--text-secondary);line-height:1.7;margin-bottom:1rem;">
        ${sanitize(evt.description || 'No description available.')}
      </p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center;">
        <span class="badge ${confBadgeClass}">${evt.confidence || 'UNVERIFIED'}</span>
        ${(evt.publishers||[]).map(p => `<span class="badge badge-ambiguous">${sanitize(p)}</span>`).join('')}
      </div>
    </div>`;
}

function sanitize(str) {
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}
