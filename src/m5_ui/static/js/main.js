/**
 * main.js — NewsLens app bootstrap
 * Exposes renderResult() called by results.html after SSE or sessionStorage load.
 */

/* ── Tier badge helper ────────────────────────────────────── */
function tierBadgeHTML(tier) {
  const map = {
    pathway: ['badge-live',    '● LIVE INDEX'],
    bing:    ['badge-bing',    '⚡ BING FALLBACK'],
    scraper: ['badge-scraper', '🔧 SCRAPER FALLBACK'],
  };
  const [cls, label] = map[tier] || ['badge-ambiguous', tier?.toUpperCase() || 'UNKNOWN'];
  return `<span class="badge ${cls}">${label}</span>`;
}

/* ── Confidence colour ────────────────────────────────────── */
function confColor(score) {
  if (score >= 0.75) return 'var(--conf-high)';
  if (score >= 0.5)  return 'var(--conf-medium)';
  if (score >= 0.25) return 'var(--conf-low)';
  return 'var(--conf-unverified)';
}

/* ── Top-level renderer — consumes AnalysisResult directly ── */
window.renderResult = function(result) {
  // Header / meta
  const qEl = document.getElementById('result-query');
  if (qEl) qEl.textContent = result.raw_query || '';

  // Tier badge
  const tierEl = document.getElementById('tier-badge');
  if (tierEl) tierEl.outerHTML = tierBadgeHTML(result.metadata?.retrieval_tier_used);

  // Confidence bar
  const pct = Math.round((result.overall_confidence || 0) * 100);
  const fill = document.getElementById('confidence-fill');
  const pctEl = document.getElementById('confidence-pct');
  if (fill) { fill.style.width = pct + '%'; fill.style.background = confColor(result.overall_confidence); }
  if (pctEl) pctEl.textContent = pct + '%';

  // Metadata card
  const m = result.metadata || {};
  setText('meta-latency',   m.total_latency_ms ? m.total_latency_ms + ' ms' : '—');
  setText('meta-retrieved', m.total_chunks_retrieved ?? '—');
  setText('meta-used',      m.total_chunks_used ?? '—');
  setText('meta-model',     m.model_versions?.primary || '—');

  // Warnings
  if (result.warnings?.length) {
    const sec = document.getElementById('warnings-section');
    const list = document.getElementById('warnings-list');
    if (sec) sec.classList.remove('hidden');
    if (list) result.warnings.forEach(w => {
      const li = document.createElement('li');
      li.style.cssText = 'font-size:0.75rem;color:var(--accent-amber);';
      li.textContent = w;
      list.appendChild(li);
    });
  }

  // Delegate to sub-renderers
  if (typeof renderTrace   === 'function') renderTrace(result.agent_trace || []);
  if (typeof renderTimeline=== 'function') renderTimeline(result.timeline_result);
  if (typeof renderSummary === 'function') renderSummary(result.summary_result);
  if (typeof renderBias    === 'function') renderBias(result.bias_result);
  if (typeof renderSources === 'function') renderSources(result.agent_trace, result.metadata);
};

/* ── Summary renderer ─────────────────────────────────────── */
window.renderSummary = function(summary) {
  const skel = document.getElementById('summary-skeleton');
  const cont = document.getElementById('summary-container');
  const empty = document.getElementById('summary-empty');
  if (!cont) return;

  if (skel) skel.remove();

  if (!summary) { empty?.classList.remove('hidden'); return; }

  cont.classList.remove('hidden');

  if (summary.summary_text) {
    const p = document.createElement('p');
    p.style.cssText = 'font-size:0.95rem;line-height:1.75;margin-bottom:1.5rem;color:var(--text-secondary);';
    p.textContent = summary.summary_text;
    cont.appendChild(p);
  }

  if (summary.key_takeaways?.length) {
    const h = el('h3', { marginBottom: '0.75rem' }, '✨ Key Takeaways');
    cont.appendChild(h);
    summary.key_takeaways.forEach(t => {
      const card = makeCard(t, '0.875rem');
      cont.appendChild(card);
    });
  }

  if (summary.consensus_points?.length) {
    const h = el('h3', { margin: '1.25rem 0 0.75rem' }, '✅ Consensus Points');
    cont.appendChild(h);
    summary.consensus_points.forEach(c => {
      const card = makeCard(c, '0.875rem');
      cont.appendChild(card);
    });
  }
};

/* ── Sources renderer (uses retrieved chunk metadata) ─────── */
window.renderSources = function(_trace, meta) {
  const skel = document.getElementById('sources-skeleton');
  const cont = document.getElementById('sources-container');
  if (!cont) return;
  if (skel) skel.remove();
  cont.classList.remove('hidden');

  // Show metadata summary card if no actual chunk data
  const infoCard = document.createElement('div');
  infoCard.className = 'source-card';
  infoCard.style.gridColumn = '1 / -1';
  infoCard.innerHTML = `
    <div class="source-card-header">
      <span class="source-publisher">Retrieval Summary</span>
    </div>
    <p style="font-size:0.875rem;color:var(--text-secondary);">
      ${meta?.total_chunks_retrieved ?? 0} chunks retrieved via
      <strong>${meta?.retrieval_tier_used ?? 'unknown'}</strong>,
      ${meta?.total_chunks_used ?? 0} accepted after CRAG filtering.
    </p>`;
  cont.appendChild(infoCard);
};

/* ── DOM helpers ──────────────────────────────────────────── */
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(val);
}

function el(tag, styles, text) {
  const e = document.createElement(tag);
  Object.assign(e.style, styles || {});
  if (text) e.textContent = text;
  return e;
}

function makeCard(text, fontSize) {
  const d = document.createElement('div');
  d.style.cssText = `background:var(--bg-elevated);border:1px solid var(--border-subtle);
    border-radius:var(--radius-md);padding:0.75rem 1rem;margin-bottom:0.5rem;
    font-size:${fontSize};color:var(--text-secondary);line-height:1.6;`;
  d.textContent = text;
  return d;
}
