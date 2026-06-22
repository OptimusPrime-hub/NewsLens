/**
 * trace_panel.js — Agent trace step renderer for results.html
 *
 * Reads agent_trace (list[TraceEntry]) from AnalysisResult and renders
 * execution-focused step cards into #trace-steps.
 *
 * TraceEntry fields used:
 *   step_index, node_name, action, output_summary,
 *   latency_ms, fallback_triggered, fallback_tier
 */

window.renderTrace = function (traceEntries) {
  const container = document.getElementById('trace-steps');
  if (!container) return;
  container.innerHTML = '';

  if (!traceEntries?.length) {
    container.innerHTML = '<p style="font-size:0.75rem;color:var(--text-muted);">No trace data.</p>';
    return;
  }

  traceEntries.forEach((entry, idx) => {
    const isFallback = entry.fallback_triggered;
    const statusClass = isFallback ? 'error' : 'done';

    const div = document.createElement('div');
    div.className = `trace-step ${statusClass}`;
    div.style.animationDelay = (idx * 60) + 'ms';

    // Icon: checkmark or fallback warning
    const iconText = isFallback ? '⚡' : '✓';
    const iconClass = isFallback ? 'error' : 'done';

    // Fallback tier badge
    const fallbackBadge = isFallback && entry.fallback_tier != null
      ? ` <span class="badge badge-bing" style="margin-left:4px;">TIER ${entry.fallback_tier}</span>`
      : '';

    // Human-readable node labels
    const nodeLabels = {
      supervisor:     'Intent Routed',
      retrieve:       'Articles Retrieved',
      crag_evaluate:  'CRAG Filtered',
      bias_agent:     'Bias Engine',
      timeline_agent: 'Timeline Synthesizer',
      summary_agent:  'Summary Agent',
      validate:       'Output Validated',
      assembler:      'Result Assembled',
    };
    const title = nodeLabels[entry.node_name] || entry.action || entry.node_name;

    div.innerHTML = `
      <div class="trace-icon ${iconClass}">${iconText}</div>
      <div class="trace-body">
        <div class="trace-title">${title}${fallbackBadge}</div>
        <div class="trace-desc">${sanitize(entry.output_summary || '')}</div>
        <div class="trace-latency">${entry.latency_ms ?? 0} ms</div>
      </div>`;
    container.appendChild(div);
  });
};

function sanitize(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
