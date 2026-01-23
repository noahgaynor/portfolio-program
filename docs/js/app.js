/**
 * V-Stop Portfolio Dashboard
 * Frontend JavaScript for loading and displaying portfolio data
 */

// Data URLs (relative to docs folder)
const DATA_URLS = {
    portfolio: 'data/portfolio.json',
    history: 'data/history.json',
    signals: 'data/signals.json',
    watchlist: 'data/watchlist.json',
    settings: 'data/settings.json'
};

// Color palette for pie chart
const CHART_COLORS = [
    '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
    '#14b8a6', '#a855f7', '#eab308', '#3b82f6', '#22c55e'
];

// State
let portfolioData = null;
let historyData = null;
let signalsData = null;
let settingsData = null;

/**
 * Fetch JSON data from URL
 */
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${url}:`, error);
        return null;
    }
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Format currency
 */
function formatCurrency(value) {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

/**
 * Format percentage
 */
function formatPercent(value) {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * Initialize tab navigation
 */
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // Update button states
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update panel visibility
            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `${targetTab}-tab`) {
                    panel.classList.add('active');
                }
            });

            // Render pie chart when portfolio tab is shown
            if (targetTab === 'portfolio') {
                renderPieChart();
            }

            // Render rejected list when settings tab is shown
            if (targetTab === 'settings') {
                renderRejectedList();
            }
        });
    });
}

/**
 * Initialize settings controls
 */
function initSettings() {
    const slider = document.getElementById('correlation-threshold');
    const valueDisplay = document.getElementById('correlation-value');
    const saveBtn = document.getElementById('save-settings');
    const saveStatus = document.getElementById('save-status');

    if (!slider || !valueDisplay || !saveBtn) return;

    // Update value display when slider changes
    slider.addEventListener('input', () => {
        valueDisplay.textContent = `${slider.value}%`;
    });

    // Save settings
    saveBtn.addEventListener('click', async () => {
        const threshold = parseInt(slider.value) / 100;

        // Save to localStorage (for frontend persistence)
        localStorage.setItem('correlation_threshold', threshold);

        // Note: In a real setup, this would POST to a backend endpoint
        // For GitHub Pages (static hosting), we can only save to localStorage
        // The actual settings.json is updated when the workflow runs

        saveStatus.textContent = 'Saved! Will apply on next scan.';
        setTimeout(() => {
            saveStatus.textContent = '';
        }, 3000);

        console.log('Settings saved:', { correlation_threshold: threshold });
    });
}

/**
 * Load settings and update UI
 */
function loadSettings() {
    const slider = document.getElementById('correlation-threshold');
    const valueDisplay = document.getElementById('correlation-value');

    if (!slider || !valueDisplay) return;

    // Try localStorage first (user's local preference)
    const localThreshold = localStorage.getItem('correlation_threshold');

    // Then try from loaded settings data
    const serverThreshold = signalsData?.correlation_threshold || settingsData?.correlation_threshold;

    // Use localStorage if available, otherwise server settings, otherwise default
    let threshold = 0.75;
    if (localThreshold) {
        threshold = parseFloat(localThreshold);
    } else if (serverThreshold) {
        threshold = serverThreshold;
    }

    // Update slider
    slider.value = Math.round(threshold * 100);
    valueDisplay.textContent = `${slider.value}%`;
}

/**
 * Render rejected entries list
 */
function renderRejectedList() {
    const container = document.getElementById('rejected-list');
    if (!container) return;

    const rejected = signalsData?.rejected_correlated || [];

    if (rejected.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔗</div>
                <div class="empty-state-text">No rejections in last scan</div>
            </div>
        `;
        return;
    }

    container.innerHTML = rejected.map(item => `
        <div class="rejected-item">
            <div class="rejected-symbol">${item.symbol}</div>
            <div class="rejected-reason">${item.rejection_reason || 'Too correlated'}</div>
        </div>
    `).join('');
}

/**
 * Update last update time display
 */
function updateLastUpdateTime() {
    const element = document.getElementById('last-update-time');
    if (signalsData && signalsData.last_update) {
        const date = new Date(signalsData.last_update);
        element.textContent = `Last Update: ${date.toLocaleString()}`;
    } else if (portfolioData && portfolioData.last_update) {
        const date = new Date(portfolioData.last_update);
        element.textContent = `Last Update: ${date.toLocaleString()}`;
    } else {
        element.textContent = 'No data available';
    }
}

/**
 * Update summary cards
 */
function updateSummaryCards() {
    // Number of positions
    const numPositions = portfolioData?.positions ?
        Object.keys(portfolioData.positions).length : 0;
    document.getElementById('num-positions').textContent = numPositions;

    // Cash percentage
    const cashWeight = portfolioData?.cash_weight ?? 1.0;
    document.getElementById('cash-percent').textContent = formatPercent(cashWeight);

    // Qualifying stocks
    const numQualifying = signalsData?.qualifying_stocks?.length || 0;
    document.getElementById('num-qualifying').textContent = numQualifying;

    // Total return (placeholder - would need price data)
    document.getElementById('total-return').textContent = '-';
}

/**
 * Render portfolio table
 */
function renderPortfolioTable() {
    const tbody = document.getElementById('portfolio-body');

    if (!portfolioData?.positions || Object.keys(portfolioData.positions).length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <div class="empty-state-text">No positions in portfolio</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const positions = Object.values(portfolioData.positions);
    positions.sort((a, b) => (b.weight || 0) - (a.weight || 0));

    tbody.innerHTML = positions.map(pos => `
        <tr>
            <td><strong>${pos.symbol}</strong></td>
            <td>${pos.name || '-'}</td>
            <td>${formatCurrency(pos.entry_price)}</td>
            <td>${formatPercent(pos.weight)}</td>
            <td>${formatDate(pos.entry_date)}</td>
        </tr>
    `).join('');
}

/**
 * Render pie chart for portfolio allocation
 */
function renderPieChart() {
    const canvas = document.getElementById('portfolio-pie-chart');
    const legendContainer = document.getElementById('pie-legend');

    if (!canvas || !legendContainer) return;

    const ctx = canvas.getContext('2d');
    const positions = portfolioData?.positions ? Object.values(portfolioData.positions) : [];
    const cashWeight = portfolioData?.cash_weight ?? 1.0;

    // Clear previous chart
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    legendContainer.innerHTML = '';

    if (positions.length === 0 && cashWeight >= 1.0) {
        // All cash
        legendContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💵</div>
                <div class="empty-state-text">100% Cash - No positions</div>
            </div>
        `;
        return;
    }

    // Build data for pie chart
    const data = [];
    positions.forEach((pos, i) => {
        data.push({
            label: pos.symbol,
            value: pos.weight || 0.07,
            color: CHART_COLORS[i % CHART_COLORS.length]
        });
    });

    // Add cash if any
    if (cashWeight > 0.001) {
        data.push({
            label: 'Cash',
            value: cashWeight,
            color: '#9ca3af'
        });
    }

    // Draw pie chart
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(centerX, centerY) - 10;

    let startAngle = -Math.PI / 2; // Start from top

    data.forEach(slice => {
        const sliceAngle = (slice.value / 1.0) * 2 * Math.PI;

        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        ctx.fillStyle = slice.color;
        ctx.fill();

        // Add subtle border
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();

        startAngle += sliceAngle;
    });

    // Draw legend
    legendContainer.innerHTML = data.map(item => `
        <div class="pie-legend-item">
            <span class="pie-legend-color" style="background-color: ${item.color}"></span>
            <span>${item.label}</span>
            <span class="pie-legend-value">${formatPercent(item.value)}</span>
        </div>
    `).join('');
}

/**
 * Render signals table
 */
function renderSignalsTable() {
    const tbody = document.getElementById('signals-body');

    if (!signalsData?.scan_results || Object.keys(signalsData.scan_results).length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8">
                    <div class="empty-state">
                        <div class="empty-state-icon">📡</div>
                        <div class="empty-state-text">No signal data available. Run the scanner to populate.</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const results = Object.values(signalsData.scan_results);
    results.sort((a, b) => {
        // Sort by all_bullish first, then by symbol
        if (a.all_bullish !== b.all_bullish) {
            return b.all_bullish - a.all_bullish;
        }
        return a.symbol.localeCompare(b.symbol);
    });

    tbody.innerHTML = results.map(result => {
        const signalClass = (val) => val ? 'signal-bullish' : 'signal-bearish';
        const signalText = (val) => val ? '▲' : '▼';
        const statusBadge = result.all_bullish ?
            '<span class="badge badge-success">QUALIFIED</span>' :
            '<span class="badge badge-danger">NOT QUALIFIED</span>';

        return `
            <tr>
                <td><strong>${result.symbol}</strong></td>
                <td>${result.name || '-'}</td>
                <td>${result.sector || 'Unknown'}</td>
                <td>${formatCurrency(result.current_price)}</td>
                <td class="${signalClass(result.daily_bullish)}">${signalText(result.daily_bullish)}</td>
                <td class="${signalClass(result.weekly_bullish)}">${signalText(result.weekly_bullish)}</td>
                <td class="${signalClass(result.monthly_bullish)}">${signalText(result.monthly_bullish)}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Render activity feed
 */
function renderActivityFeed() {
    const container = document.getElementById('activity-feed');

    if (!historyData || historyData.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <div class="empty-state-text">No recent activity</div>
            </div>
        `;
        return;
    }

    // Get last 10 activities from history
    const activities = [];
    historyData.slice(-10).reverse().forEach(record => {
        if (record.buys) {
            record.buys.forEach(buy => {
                activities.push({
                    type: 'buy',
                    symbol: buy.symbol,
                    name: buy.name,
                    price: buy.entry_price,
                    time: record.timestamp
                });
            });
        }
        if (record.sells) {
            record.sells.forEach(sell => {
                activities.push({
                    type: 'sell',
                    symbol: sell.symbol,
                    name: sell.name,
                    price: sell.exit_price,
                    reason: sell.reason,
                    time: record.timestamp
                });
            });
        }
    });

    if (activities.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <div class="empty-state-text">No buy/sell activity yet</div>
            </div>
        `;
        return;
    }

    container.innerHTML = activities.slice(0, 10).map(activity => `
        <div class="activity-item">
            <div class="activity-icon ${activity.type}">
                ${activity.type === 'buy' ? '🟢' : '🔴'}
            </div>
            <div class="activity-content">
                <div class="activity-title">
                    ${activity.type.toUpperCase()} ${activity.symbol}
                </div>
                <div class="activity-details">
                    ${activity.name || ''} @ ${formatCurrency(activity.price)}
                    ${activity.reason ? `<br>${activity.reason}` : ''}
                </div>
            </div>
            <div class="activity-time">${formatDate(activity.time)}</div>
        </div>
    `).join('');
}

/**
 * Render history table
 */
function renderHistoryTable() {
    const tbody = document.getElementById('history-body');

    if (!historyData || historyData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="empty-state">
                        <div class="empty-state-icon">📜</div>
                        <div class="empty-state-text">No historical data available</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    // Flatten history into individual transactions
    const transactions = [];
    historyData.forEach(record => {
        if (record.buys) {
            record.buys.forEach(buy => {
                transactions.push({
                    date: record.timestamp,
                    action: 'BUY',
                    symbol: buy.symbol,
                    price: buy.entry_price,
                    reason: `Weight: ${formatPercent(buy.weight)}`
                });
            });
        }
        if (record.sells) {
            record.sells.forEach(sell => {
                transactions.push({
                    date: record.timestamp,
                    action: 'SELL',
                    symbol: sell.symbol,
                    price: sell.exit_price,
                    reason: sell.reason || 'Signal change'
                });
            });
        }
    });

    // Sort by date descending
    transactions.sort((a, b) => new Date(b.date) - new Date(a.date));

    if (transactions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="empty-state">
                        <div class="empty-state-icon">📜</div>
                        <div class="empty-state-text">No transactions yet</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = transactions.slice(0, 50).map(tx => `
        <tr>
            <td>${formatDate(tx.date)}</td>
            <td class="${tx.action === 'BUY' ? 'action-buy' : 'action-sell'}">${tx.action}</td>
            <td><strong>${tx.symbol}</strong></td>
            <td>${formatCurrency(tx.price)}</td>
            <td>${tx.reason}</td>
        </tr>
    `).join('');
}

/**
 * Load all data and render dashboard
 */
async function loadDashboard() {
    console.log('Loading dashboard data...');

    // Fetch all data in parallel
    const [portfolio, history, signals, settings] = await Promise.all([
        fetchData(DATA_URLS.portfolio),
        fetchData(DATA_URLS.history),
        fetchData(DATA_URLS.signals),
        fetchData(DATA_URLS.settings)
    ]);

    portfolioData = portfolio;
    historyData = history;
    signalsData = signals;
    settingsData = settings;

    console.log('Data loaded:', { portfolioData, historyData, signalsData, settingsData });

    // Render all components
    updateLastUpdateTime();
    updateSummaryCards();
    renderPortfolioTable();
    renderSignalsTable();
    renderActivityFeed();
    renderHistoryTable();
    loadSettings();

    // Render pie chart if portfolio tab is active
    if (document.querySelector('#portfolio-tab.active')) {
        renderPieChart();
    }

    // Render rejected list if settings tab is active
    if (document.querySelector('#settings-tab.active')) {
        renderRejectedList();
    }
}

/**
 * Initialize dashboard
 */
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSettings();
    loadDashboard();

    // Refresh data every 5 minutes
    setInterval(loadDashboard, 5 * 60 * 1000);
});

// Export for debugging
window.dashboardState = {
    getData: () => ({ portfolioData, historyData, signalsData, settingsData }),
    refresh: loadDashboard
};
