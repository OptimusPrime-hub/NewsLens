/**
 * query.js — SSE streaming query handler for index.html
 *
 * Intercepts the search form submit, opens a SSE stream to POST /api/analyze/stream,
 * animates live progress steps, stores AnalysisResult in sessionStorage,
 * then navigates to /results.
 */

(function () {
  'use strict';

  /* ── Step definitions ─────────────────────────────────────── */
  const STEPS = [
    { id: 1, label: 'Classifying intent',     icon: '🧠' },
    { id: 2, label: 'Retrieving articles',    icon: '📡' },
    { id: 3, label: 'CRAG relevance filter',  icon: '🔬' },
    { id: 4, label: 'Running analysis agent', icon: '⚙️'  },
  ];

  /* ── DOM refs ─────────────────────────────────────────────── */
  const form    = document.getElementById('search-form');
  const overlay = document.getElementById('progress-overlay');
  const stepsEl = document.getElementById('progress-steps');
  const searchBtn = document.getElementById('search-btn');

  if (!form) return; // Not on index page

  /* ── Render progress steps ────────────────────────────────── */
  function buildSteps() {
    stepsEl.innerHTML = '';
    STEPS.forEach(s => {
      const div = document.createElement('div');
      div.id = 'step-' + s.id;
      div.className = 'trace-step';
      div.innerHTML = `
        <div class="trace-icon pending" id="step-icon-${s.id}">${s.icon}</div>
        <div class="trace-body">
          <div class="trace-title">${s.label}</div>
          <div class="trace-desc" id="step-desc-${s.id}" style="color:var(--text-muted);">Waiting…</div>
        </div>`;
      stepsEl.appendChild(div);
    });
  }

  function markStep(id, status, message) {
    const step = document.getElementById('step-' + id);
    const icon = document.getElementById('step-icon-' + id);
    const desc = document.getElementById('step-desc-' + id);
    if (!step) return;
    step.classList.remove('done', 'running', 'error');
    icon.classList.remove('done', 'running', 'pending', 'error');
    step.classList.add(status);
    icon.classList.add(status);
    if (desc && message) desc.textContent = message;
  }

  /* ── Form submit handler ──────────────────────────────────── */
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = document.getElementById('query-input').value.trim();
    if (!query) return;

    sessionStorage.setItem('nl_query', query);

    // Show overlay
    buildSteps();
    overlay.classList.remove('hidden');
    overlay.style.display = 'flex';
    searchBtn.disabled = true;

    // Mark all as running initially
    markStep(1, 'running', 'Classifying…');

    try {
      const resp = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let result = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        let eventType = null;
        for (const line of lines) {
          if (line.startsWith('event: ')) { eventType = line.slice(7).trim(); continue; }
          if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventType === 'progress') {
                const status = data.done ? 'done' : 'running';
                markStep(data.step, status, data.message);
                // Mark next step as running if this one is done
                if (data.done && data.step < 4) markStep(data.step + 1, 'running', 'Running…');
              } else if (eventType === 'result') {
                result = data;
                // Mark remaining steps as done
                STEPS.forEach(s => markStep(s.id, 'done', ''));
              } else if (eventType === 'error') {
                throw new Error(data.message);
              }
            } catch (parseErr) { /* ignore parse errors */ }
            eventType = null;
          }
        }
      }

      if (result) {
        sessionStorage.setItem('nl_result', JSON.stringify(result));
        window.location.href = '/results';
      } else {
        throw new Error('No result received from server');
      }

    } catch (err) {
      STEPS.forEach(s => markStep(s.id, 'error', ''));
      // Show error in overlay
      const errDiv = document.createElement('div');
      errDiv.style.cssText = 'color:var(--accent-red);font-size:0.875rem;text-align:center;margin-top:1rem;';
      errDiv.textContent = '⚠ ' + err.message;
      stepsEl.appendChild(errDiv);

      // Re-enable after 3s
      setTimeout(() => {
        overlay.style.display = 'none';
        searchBtn.disabled = false;
      }, 3000);
    }
  });

  /* ── Pre-fill from sessionStorage if returning to home ─────── */
  window.addEventListener('DOMContentLoaded', () => {
    const q = sessionStorage.getItem('nl_query');
    const input = document.getElementById('query-input');
    if (q && input) input.value = q;
  });

})();
