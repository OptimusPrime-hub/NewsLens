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
  if (typeof renderSources === 'function') renderSources(result);
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
window.renderSources = function(result) {
  const skel = document.getElementById('sources-skeleton');
  const cont = document.getElementById('sources-container');
  if (!cont) return;
  if (skel) skel.remove();
  cont.innerHTML = '';
  cont.classList.remove('hidden');

  const meta = result.metadata || {};

  // Show metadata summary card
  const infoCard = document.createElement('div');
  infoCard.className = 'source-card';
  infoCard.style.gridColumn = '1 / -1';
  infoCard.innerHTML = `
    <div class="source-card-header">
      <span class="source-publisher">Retrieval Summary</span>
    </div>
    <p style="font-size:0.875rem;color:var(--text-secondary);margin:0;">
      ${meta.total_chunks_retrieved ?? 0} chunks retrieved via
      <strong>${meta.retrieval_tier_used ?? 'unknown'}</strong>,
      ${meta.total_chunks_used ?? 0} accepted after CRAG filtering.
    </p>`;
  cont.appendChild(infoCard);

  // Extract unique articles from timeline events
  const articlesMap = new Map();
  if (result.timeline_result?.events) {
    result.timeline_result.events.forEach(evt => {
      if (evt.source_articles) {
        evt.source_articles.forEach(ref => {
          if (ref.url) {
            articlesMap.set(ref.url, ref);
          }
        });
      }
    });
  }

  // Render article cards
  if (articlesMap.size > 0) {
    articlesMap.forEach(ref => {
      const card = document.createElement('div');
      card.className = 'source-card anim-up';
      card.innerHTML = `
        <div class="source-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
          <span class="source-publisher" style="font-weight:600; font-size:0.8rem; color:var(--accent-cyan);">${sanitizeHtml(ref.publisher)}</span>
          <span style="font-size:0.7rem; color:var(--text-muted);">${new Date(ref.publish_ts).toLocaleDateString()}</span>
        </div>
        <h4 style="margin:0 0 0.5rem 0; font-size:0.85rem; line-height:1.4; font-weight:600; color:var(--text-primary);">${sanitizeHtml(ref.title)}</h4>
        <a href="${ref.url}" target="_blank" style="font-size:0.75rem; color:var(--accent-cyan); text-decoration:none; display:inline-flex; align-items:center; gap:4px;">
          🔗 View Article
        </a>
      `;
      cont.appendChild(card);
    });
  } else {
    // If no articles found, look at summary / bias fallback to list publishers
    const uniquePublishers = new Set();
    if (result.summary_result?.summary_text) {
      // Very simple regex extraction of publishers from brackets: e.g. [247wallst.com]
      const matches = result.summary_result.summary_text.match(/\[[a-zA-Z0-9.\-_]+\]/g);
      if (matches) {
        matches.forEach(m => uniquePublishers.add(m.slice(1, -1)));
      }
    }
    
    if (uniquePublishers.size > 0) {
      uniquePublishers.forEach(pub => {
        const card = document.createElement('div');
        card.className = 'source-card anim-up';
        card.innerHTML = `
          <div class="source-card-header" style="margin-bottom:0.5rem;">
            <span class="source-publisher" style="font-weight:600; font-size:0.8rem; color:var(--accent-cyan);">${sanitizeHtml(pub)}</span>
          </div>
          <h4 style="margin:0; font-size:0.85rem; font-weight:600; color:var(--text-primary);">Publisher cited in summary</h4>
        `;
        cont.appendChild(card);
      });
    } else {
      const emptyCard = document.createElement('div');
      emptyCard.style.padding = '1.5rem';
      emptyCard.style.textAlign = 'center';
      emptyCard.style.color = 'var(--text-muted)';
      emptyCard.style.gridColumn = '1 / -1';
      emptyCard.textContent = 'No detailed source links available for this query.';
      cont.appendChild(emptyCard);
    }
  }
};

function sanitizeHtml(str) {
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

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
