/**
 * FraudGuard – Online Payment Fraud Detection System
 * Main Frontend Application Script
 */

// Global State & Chart Instances
const state = {
  charts: {},
  currentPage: 'dashboard',
  filters: {
    search: '',
    status: 'all',
    sort: 'date_desc',
    offset: 0,
    limit: 20
  }
};

// Utilities: Currency and Number formatting
const formatCurrency = (val) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2
  }).format(val || 0);
};

const formatPercent = (val) => {
  return `${(Number(val) * 100).toFixed(2)}%`;
};

// Toast Notification Manager
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconSvg = '';
  if (type === 'success') {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  } else if (type === 'error') {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
  } else {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
  }

  toast.innerHTML = `${iconSvg} <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Chart.js Theme Defaults (Dark Navy Cyber Theme)
if (window.Chart) {
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.plugins.tooltip.backgroundColor = '#0f182a';
  Chart.defaults.plugins.tooltip.titleColor = '#f1f5f9';
  Chart.defaults.plugins.tooltip.bodyColor = '#94a3b8';
  Chart.defaults.plugins.tooltip.borderColor = '#1e2e4a';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

// ==============================================================================
// 1. DASHBOARD CONTROLLER
// ==============================================================================
async function initDashboard() {
  const container = document.getElementById('dashboard-view');
  if (!container) return;

  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    if (data.status !== 'success') {
      showToast(data.message || 'Error loading dashboard telemetry', 'error');
      return;
    }

    const { stats, recent_transactions, type_breakdown, model_summary } = data;

    // 1. Update Stat Numbers
    document.getElementById('stat-total-txns').textContent = Number(stats.total_transactions).toLocaleString();
    document.getElementById('stat-legit-txns').textContent = Number(stats.legitimate_transactions).toLocaleString();
    document.getElementById('stat-fraud-txns').textContent = Number(stats.fraudulent_transactions).toLocaleString();
    document.getElementById('stat-fraud-rate').textContent = `${stats.fraud_rate}%`;

    // 2. Render Charts
    renderDashboardCharts(stats, type_breakdown);

    // 3. Render Recent Transactions Table
    renderRecentTable(recent_transactions);

    // 4. Update Model Snapshot Card
    if (model_summary && document.getElementById('dash-model-acc')) {
      document.getElementById('dash-model-name').textContent = model_summary.name;
      document.getElementById('dash-model-acc').textContent = formatPercent(model_summary.accuracy);
      document.getElementById('dash-model-prec').textContent = formatPercent(model_summary.precision);
      document.getElementById('dash-model-rec').textContent = formatPercent(model_summary.recall);
      document.getElementById('dash-model-f1').textContent = formatPercent(model_summary.f1_score);
    }

  } catch (err) {
    console.error('Dashboard init error:', err);
    showToast('Failed to connect to backend API', 'error');
  }
}

function renderDashboardCharts(stats, type_breakdown) {
  // Chart 1: Ratio Doughnut Chart
  const ratioCtx = document.getElementById('chart-fraud-ratio');
  if (ratioCtx) {
    if (state.charts.ratio) state.charts.ratio.destroy();

    const legit = stats.legitimate_transactions;
    const fraud = stats.fraudulent_transactions;
    const hasData = (legit + fraud) > 0;

    state.charts.ratio = new Chart(ratioCtx, {
      type: 'doughnut',
      data: {
        labels: hasData ? ['Legitimate', 'Fraudulent'] : ['No Transactions Yet'],
        datasets: [{
          data: hasData ? [legit, fraud] : [1],
          backgroundColor: hasData ? ['#10b981', '#f43f5e'] : ['#1e2e4a'],
          borderWidth: 2,
          borderColor: '#0f182a',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 16 } }
        },
        cutout: '72%'
      }
    });
  }

  // Chart 2: Activity by Transaction Type Bar Chart
  const activityCtx = document.getElementById('chart-activity');
  if (activityCtx) {
    if (state.charts.activity) state.charts.activity.destroy();

    const labels = Object.keys(type_breakdown || {});
    const totals = labels.map(k => type_breakdown[k].total);
    const frauds = labels.map(k => type_breakdown[k].fraud);

    state.charts.activity = new Chart(activityCtx, {
      type: 'bar',
      data: {
        labels: labels.length ? labels : ['PAYMENT', 'TRANSFER', 'CASH_OUT', 'CASH_IN', 'DEBIT'],
        datasets: [
          {
            label: 'Total Volume',
            data: totals.length ? totals : [0, 0, 0, 0, 0],
            backgroundColor: 'rgba(56, 189, 248, 0.4)',
            borderColor: '#38bdf8',
            borderWidth: 1,
            borderRadius: 6
          },
          {
            label: 'Fraud Flagged',
            data: frauds.length ? frauds : [0, 0, 0, 0, 0],
            backgroundColor: 'rgba(244, 63, 94, 0.75)',
            borderColor: '#f43f5e',
            borderWidth: 1,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, padding: 12 } }
        },
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.04)' } },
          y: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, beginAtZero: true }
        }
      }
    });
  }
}

function renderRecentTable(transactions) {
  const tbody = document.getElementById('recent-txns-tbody');
  const emptyState = document.getElementById('recent-txns-empty');
  if (!tbody) return;

  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.style.display = 'flex';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  tbody.innerHTML = transactions.map(txn => {
    const isFraud = txn.is_fraud === 1;
    const badgeClass = isFraud ? 'badge-fraud' : 'badge-legit';
    const riskBadgeClass = `badge-risk-${txn.risk_level.toLowerCase()}`;

    return `
      <tr>
        <td><span class="mono-tag">${txn.trans_uuid}</span></td>
        <td><strong>${txn.trans_type}</strong></td>
        <td><strong>${formatCurrency(txn.amount)}</strong></td>
        <td>
          <span class="badge ${badgeClass}">
            ${isFraud ? '● FRAUDULENT' : '✓ LEGITIMATE'}
          </span>
        </td>
        <td>
          <span class="badge ${riskBadgeClass}">
            ${txn.risk_level} (${txn.fraud_probability_pct})
          </span>
        </td>
        <td style="color: var(--text-dim); font-size: 0.8rem;">
          ${txn.created_at}
        </td>
      </tr>
    `;
  }).join('');
}

// ==============================================================================
// 2. TRANSACTION FRAUD DETECTION (LIVE PREDICTION)
// ==============================================================================
function initDetection() {
  const form = document.getElementById('detection-form');
  if (!form) return;

  // Load sample presets
  loadPresets();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById('btn-analyze');
    const loadingBox = document.getElementById('detection-loading');
    const resultBox = document.getElementById('detection-result-container');

    // Gather & validate inputs
    const payload = {
      type: document.getElementById('input-type').value,
      amount: parseFloat(document.getElementById('input-amount').value),
      oldbalanceOrg: parseFloat(document.getElementById('input-oldbalanceOrg').value),
      newbalanceOrig: parseFloat(document.getElementById('input-newbalanceOrig').value),
      oldbalanceDest: parseFloat(document.getElementById('input-oldbalanceDest').value),
      newbalanceDest: parseFloat(document.getElementById('input-newbalanceDest').value),
      hour_of_day: parseInt(document.getElementById('input-hour').value || new Date().getHours()),
      sender_account: document.getElementById('input-sender').value.trim(),
      recipient_account: document.getElementById('input-recipient').value.trim()
    };

    if (isNaN(payload.amount) || payload.amount <= 0) {
      showToast('Please enter a valid transaction amount greater than $0.00', 'error');
      return;
    }

    if ([payload.oldbalanceOrg, payload.newbalanceOrig, payload.oldbalanceDest, payload.newbalanceDest].some(v => isNaN(v) || v < 0)) {
      showToast('Account balances cannot be negative or invalid numbers', 'error');
      return;
    }

    // UI State: Loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <div class="radar-spinner" style="width: 18px; height: 18px; border-width: 2px;"></div>
      <span>Analyzing Transaction...</span>
    `;
    if (loadingBox) loadingBox.style.display = 'flex';
    if (resultBox) resultBox.style.display = 'none';

    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const responseData = await res.json();

      if (!res.ok || responseData.status !== 'success') {
        throw new Error(responseData.message || 'Prediction failed');
      }

      // Display result
      displayPredictionResult(responseData.data);
      showToast('Analysis completed successfully', 'success');

    } catch (err) {
      console.error('Prediction submission error:', err);
      showToast(err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <span>Analyze Transaction with ML Engine</span>
      `;
      if (loadingBox) loadingBox.style.display = 'none';
    }
  });
}

function displayPredictionResult(data) {
  const resultBox = document.getElementById('detection-result-container');
  if (!resultBox) return;

  const isFraud = data.is_fraud === 1;
  const isLegit = !isFraud;
  const boxClass = isFraud ? 'fraudulent' : 'legitimate';

  const probPct = `${(data.fraud_probability * 100).toFixed(2)}%`;
  const riskClass = `badge-risk-${data.risk_level.toLowerCase()}`;

  // Audit factors
  const factorsHtml = (data.risk_reasons || []).map(r => `
    <div class="factor-card">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${isFraud ? '#f43f5e' : '#10b981'}" stroke-width="2">
        ${isFraud 
          ? '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>' 
          : '<polyline points="20 6 9 17 4 12"/>'}
      </svg>
      <div>${r}</div>
    </div>
  `).join('');

  resultBox.innerHTML = `
    <div class="prediction-box ${boxClass}">
      <div class="prediction-header">
        <div class="pred-badge-group">
          <div class="pred-icon-large">
            ${isFraud ? `
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            ` : `
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <polyline points="9 12 11 14 15 10"/>
              </svg>
            `}
          </div>
          <div class="pred-title-text">
            <h2>${data.prediction} TRANSACTION</h2>
            <p>Risk Classification: <span class="badge ${riskClass}">${data.risk_level} RISK</span> · ID: <span class="mono-tag">${data.trans_uuid}</span></p>
          </div>
        </div>

        <div class="probability-meter-card">
          <span>Fraud Probability</span>
          <strong>${probPct}</strong>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: ${Math.max(data.fraud_probability * 100, 4)}%;"></div>
          </div>
        </div>
      </div>

      <!-- Transaction details snapshot -->
      <div style="margin-bottom: 1.5rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; background: rgba(0,0,0,0.25); padding: 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        <div>
          <span style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;">Amount</span>
          <div style="font-size: 1.1rem; font-weight: 700;">${formatCurrency(data.amount)}</div>
        </div>
        <div>
          <span style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;">Type</span>
          <div style="font-size: 1.1rem; font-weight: 600;">${data.trans_type}</div>
        </div>
        <div>
          <span style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;">Sender Orig Balance</span>
          <div style="font-size: 1.1rem; font-weight: 600;">${formatCurrency(data.oldbalance_org)}</div>
        </div>
        <div>
          <span style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;">Sender New Balance</span>
          <div style="font-size: 1.1rem; font-weight: 600;">${formatCurrency(data.newbalance_orig)}</div>
        </div>
      </div>

      <!-- Audit factors -->
      <div>
        <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">
          Explainable ML Risk Factors & Audit Trail:
        </h4>
        <div class="audit-factors-grid">
          ${factorsHtml}
        </div>
      </div>

      <div style="margin-top: 1.5rem; display: flex; gap: 1rem; justify-content: flex-end;">
        <a href="/history" class="btn btn-secondary btn-sm">
          <span>View in Transaction History</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
  `;

  resultBox.style.display = 'block';
  resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function loadPresets() {
  const container = document.getElementById('preset-buttons-container');
  if (!container) return;

  try {
    const res = await fetch('/api/sample-transactions');
    const data = await res.json();
    if (data.status === 'success' && data.samples) {
      container.innerHTML = data.samples.map((s, idx) => `
        <button type="button" class="btn-preset" data-idx="${idx}">
          ${s.expected === 'FRAUDULENT' ? '🚨' : '🟢'} ${s.name}
        </button>
      `).join('');

      // Attach click events
      container.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', () => {
          const sample = data.samples[parseInt(btn.getAttribute('data-idx'))];
          fillFormWithPreset(sample);
        });
      });
    }
  } catch (e) {
    console.error('Error loading presets:', e);
  }
}

function fillFormWithPreset(sample) {
  document.getElementById('input-type').value = sample.type;
  document.getElementById('input-amount').value = sample.amount;
  document.getElementById('input-oldbalanceOrg').value = sample.oldbalanceOrg;
  document.getElementById('input-newbalanceOrig').value = sample.newbalanceOrig;
  document.getElementById('input-oldbalanceDest').value = sample.oldbalanceDest;
  document.getElementById('input-newbalanceDest').value = sample.newbalanceDest;
  document.getElementById('input-hour').value = sample.hour_of_day;

  showToast(`Loaded preset: "${sample.name}"`, 'info');
}

// ==============================================================================
// 3. TRANSACTION HISTORY CONTROLLER
// ==============================================================================
async function initHistory() {
  const container = document.getElementById('history-view');
  if (!container) return;

  // Search input handler
  const searchInput = document.getElementById('history-search');
  if (searchInput) {
    searchInput.addEventListener('input', debounce((e) => {
      state.filters.search = e.target.value;
      state.filters.offset = 0;
      fetchHistory();
    }, 300));
  }

  // Filter status handler
  const statusFilter = document.getElementById('history-status');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      state.filters.status = e.target.value;
      state.filters.offset = 0;
      fetchHistory();
    });
  }

  // Sort handler
  const sortSelect = document.getElementById('history-sort');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      state.filters.sort = e.target.value;
      state.filters.offset = 0;
      fetchHistory();
    });
  }

  // Initial fetch
  fetchHistory();
}

async function fetchHistory() {
  const tbody = document.getElementById('history-tbody');
  const emptyState = document.getElementById('history-empty');
  const totalCountEl = document.getElementById('history-total-count');
  if (!tbody) return;

  try {
    const params = new URLSearchParams({
      search: state.filters.search,
      status: state.filters.status,
      sort: state.filters.sort,
      offset: state.filters.offset,
      limit: state.filters.limit
    });

    const res = await fetch(`/api/transactions?${params.toString()}`);
    const data = await res.json();

    if (data.status !== 'success') {
      showToast(data.message, 'error');
      return;
    }

    if (totalCountEl) totalCountEl.textContent = `${data.total} records found`;

    if (!data.transactions || data.transactions.length === 0) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    tbody.innerHTML = data.transactions.map(txn => {
      const isFraud = txn.is_fraud === 1;
      const badgeClass = isFraud ? 'badge-fraud' : 'badge-legit';
      const riskClass = `badge-risk-${txn.risk_level.toLowerCase()}`;

      return `
        <tr>
          <td><span class="mono-tag">${txn.trans_uuid}</span></td>
          <td><strong>${txn.trans_type}</strong></td>
          <td><strong style="font-size: 0.95rem;">${formatCurrency(txn.amount)}</strong></td>
          <td>
            <div style="font-size: 0.78rem; color: var(--text-dim);">${txn.sender_account}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">${formatCurrency(txn.oldbalance_org)} → ${formatCurrency(txn.newbalance_orig)}</div>
          </td>
          <td>
            <div style="font-size: 0.78rem; color: var(--text-dim);">${txn.recipient_account}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">${formatCurrency(txn.oldbalance_dest)} → ${formatCurrency(txn.newbalance_dest)}</div>
          </td>
          <td>
            <span class="badge ${badgeClass}">
              ${isFraud ? '● FRAUDULENT' : '✓ LEGITIMATE'}
            </span>
          </td>
          <td>
            <span class="badge ${riskClass}">
              ${txn.risk_level} (${txn.fraud_probability_pct})
            </span>
          </td>
          <td style="color: var(--text-dim); font-size: 0.78rem;">
            ${txn.created_at}
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="deleteTransaction(${txn.id})" title="Delete record">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('History fetch error:', err);
    showToast('Failed to fetch transaction history', 'error');
  }
}

async function deleteTransaction(id) {
  if (!confirm('Are you sure you want to delete this transaction record?')) return;
  try {
    const res = await fetch(`/api/transactions/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('Record deleted', 'success');
      fetchHistory();
    } else {
      showToast(data.message, 'error');
    }
  } catch (e) {
    showToast('Delete operation failed', 'error');
  }
}

// ==============================================================================
// 4. ANALYTICS CONTROLLER
// ==============================================================================
async function initAnalytics() {
  const container = document.getElementById('analytics-view');
  if (!container) return;

  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    if (data.status !== 'success') return;

    const { database_metrics, offline_evaluation } = data;

    // Stat cards
    document.getElementById('analytics-total').textContent = Number(database_metrics.total).toLocaleString();
    document.getElementById('analytics-fraud-rate').textContent = `${database_metrics.fraud_rate}%`;
    document.getElementById('analytics-avg-legit').textContent = formatCurrency(database_metrics.avg_legit_amount);
    document.getElementById('analytics-avg-fraud').textContent = formatCurrency(database_metrics.avg_fraud_amount);

    // Chart 1: Ratio
    const ratioCtx = document.getElementById('analytics-ratio-chart');
    if (ratioCtx) {
      if (state.charts.analyticsRatio) state.charts.analyticsRatio.destroy();
      state.charts.analyticsRatio = new Chart(ratioCtx, {
        type: 'pie',
        data: {
          labels: ['Legitimate', 'Fraudulent'],
          datasets: [{
            data: [database_metrics.legitimate, database_metrics.fraud],
            backgroundColor: ['#10b981', '#f43f5e'],
            borderColor: '#0f182a',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }

    // Chart 2: Type breakdown
    const typeCtx = document.getElementById('analytics-type-chart');
    if (typeCtx) {
      if (state.charts.analyticsType) state.charts.analyticsType.destroy();
      const stats = database_metrics.type_stats || [];
      state.charts.analyticsType = new Chart(typeCtx, {
        type: 'bar',
        data: {
          labels: stats.map(s => s.type),
          datasets: [
            {
              label: 'Legitimate',
              data: stats.map(s => s.legitimate),
              backgroundColor: 'rgba(16, 185, 129, 0.65)',
              borderRadius: 4
            },
            {
              label: 'Fraudulent',
              data: stats.map(s => s.fraud),
              backgroundColor: 'rgba(244, 63, 94, 0.85)',
              borderRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { stacked: true, grid: { color: 'rgba(255,255,255,0.04)' } },
            y: { stacked: true, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
          }
        }
      });
    }

    // Chart 3: Risk Level Distribution
    const riskCtx = document.getElementById('analytics-risk-chart');
    if (riskCtx) {
      if (state.charts.analyticsRisk) state.charts.analyticsRisk.destroy();
      const dist = database_metrics.risk_distribution || {};
      state.charts.analyticsRisk = new Chart(riskCtx, {
        type: 'doughnut',
        data: {
          labels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
          datasets: [{
            data: [dist.LOW || 0, dist.MEDIUM || 0, dist.HIGH || 0, dist.CRITICAL || 0],
            backgroundColor: ['#10b981', '#f59e0b', '#f97316', '#f43f5e'],
            borderWidth: 2,
            borderColor: '#0f182a'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }

    // Render Confusion Matrix from Offline Evaluation
    if (offline_evaluation && offline_evaluation.champion_metrics) {
      const cm = offline_evaluation.champion_metrics.confusion_matrix;
      document.getElementById('cm-tn').textContent = Number(cm.tn).toLocaleString();
      document.getElementById('cm-fp').textContent = Number(cm.fp).toLocaleString();
      document.getElementById('cm-fn').textContent = Number(cm.fn).toLocaleString();
      document.getElementById('cm-tp').textContent = Number(cm.tp).toLocaleString();
    }

  } catch (err) {
    console.error('Analytics error:', err);
  }
}

// ==============================================================================
// 5. MODEL INFORMATION CONTROLLER
// ==============================================================================
async function initModelInfo() {
  const container = document.getElementById('model-info-view');
  if (!container) return;

  try {
    const res = await fetch('/api/model-info');
    const data = await res.json();
    if (data.status !== 'success' || !data.data) return;

    const info = data.data;
    const champ = info.champion_metrics || {};

    // Populate Overview
    document.getElementById('info-algo').textContent = info.algorithm || 'RandomForestClassifier';
    document.getElementById('info-total-samples').textContent = Number(info.total_dataset_samples).toLocaleString();
    document.getElementById('info-train-samples').textContent = Number(info.training_samples).toLocaleString();
    document.getElementById('info-test-samples').textContent = Number(info.testing_samples).toLocaleString();
    document.getElementById('info-fraud-rate').textContent = `${info.fraud_rate_pct}%`;

    // Champion Metrics
    document.getElementById('info-accuracy').textContent = formatPercent(champ.accuracy);
    document.getElementById('info-precision').textContent = formatPercent(champ.precision);
    document.getElementById('info-recall').textContent = formatPercent(champ.recall);
    document.getElementById('info-f1').textContent = formatPercent(champ.f1_score);
    document.getElementById('info-auc').textContent = champ.roc_auc || '0.9999';

    // Model Comparison Table
    const comparisonTbody = document.getElementById('model-comparison-tbody');
    if (comparisonTbody && info.models_comparison) {
      comparisonTbody.innerHTML = Object.keys(info.models_comparison).map(name => {
        const m = info.models_comparison[name];
        const isBest = name === info.best_model;
        return `
          <tr ${isBest ? 'style="background: rgba(14, 165, 233, 0.08); font-weight: 600;"' : ''}>
            <td>
              ${isBest ? '🏆 <strong>' + name + '</strong> (Selected)' : name}
            </td>
            <td>${formatPercent(m.accuracy)}</td>
            <td>${formatPercent(m.precision)}</td>
            <td>${formatPercent(m.recall)}</td>
            <td><strong style="color: var(--cyan);">${formatPercent(m.f1_score)}</strong></td>
            <td>${m.roc_auc}</td>
          </tr>
        `;
      }).join('');
    }

    // Feature Importances
    const featureContainer = document.getElementById('feature-importance-bars');
    if (featureContainer && info.feature_importances) {
      featureContainer.innerHTML = info.feature_importances.map(f => `
        <div style="margin-bottom: 0.85rem;">
          <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.25rem;">
            <span style="font-family: var(--font-mono); color: var(--text-main);">${f.feature}</span>
            <span style="color: var(--cyan); font-weight: 600;">${(f.importance * 100).toFixed(1)}%</span>
          </div>
          <div class="progress-bar-bg" style="height: 6px;">
            <div class="progress-bar-fill" style="width: ${f.importance * 100}%; background: linear-gradient(90deg, #0ea5e9, #38bdf8);"></div>
          </div>
        </div>
      `).join('');
    }

  } catch (err) {
    console.error('Model info fetch error:', err);
  }
}

// ==============================================================================
// 6. GLOBAL ACTIONS: SEEDING & RESET
// ==============================================================================
async function handleSeedDemoData() {
  if (!confirm('Seed 13 benchmark test transactions evaluated through the ML model into the database?')) return;
  try {
    const res = await fetch('/api/seed-samples', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, data.status === 'success' ? 'success' : 'info');
    setTimeout(() => window.location.reload(), 800);
  } catch (e) {
    showToast('Failed to seed demo data', 'error');
  }
}

async function handleResetDatabase() {
  if (!confirm('Are you sure you want to reset all transaction history? The dashboard will show an empty zero-state.')) return;
  try {
    const res = await fetch('/api/reset-database', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'info');
    setTimeout(() => window.location.reload(), 800);
  } catch (e) {
    showToast('Failed to reset database', 'error');
  }
}

// Mobile sidebar toggle
function initSidebarToggle() {
  const toggleBtn = document.getElementById('menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }
}

// Debounce helper
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initSidebarToggle();
  initDashboard();
  initDetection();
  initHistory();
  initAnalytics();
  initModelInfo();

  // Attach global seed/reset buttons if present
  const seedBtn = document.getElementById('btn-seed-data');
  if (seedBtn) seedBtn.addEventListener('click', handleSeedDemoData);

  const resetBtn = document.getElementById('btn-reset-db');
  if (resetBtn) resetBtn.addEventListener('click', handleResetDatabase);
});

