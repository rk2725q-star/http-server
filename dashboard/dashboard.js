/**
 * NetServe Real-Time Dashboard Controller
 * Handles live polling, telemetry charts, table updates, and interactive traffic simulations.
 */

let pollingInterval = null;
let isPolling = true;
let timelineData = { labels: [], points: [] };
let recentRequestsCache = [];

// Chart Instances
let timelineChart = null;
let statusChart = null;
let methodChart = null;
let routesChart = null;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initControls();
    initTrafficGenerator();
    fetchDashboardData();
    startPolling();
});

/**
 * 1. Initialize Chart.js Instances
 */
function initCharts() {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded, skipping visual charts.');
        return;
    }

    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";

    // 1. Timeline Chart (Line)
    const ctxTimeline = document.getElementById('timelineChart')?.getContext('2d');
    if (ctxTimeline) {
        timelineChart = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Requests/min',
                    data: [],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointBackgroundColor: '#38bdf8'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' } }
                }
            }
        });
    }

    // 2. Status Distribution Chart (Doughnut)
    const ctxStatus = document.getElementById('statusChart')?.getContext('2d');
    if (ctxStatus) {
        statusChart = new Chart(ctxStatus, {
            type: 'doughnut',
            data: {
                labels: ['2xx OK', '3xx Redir', '4xx Client Err', '5xx Server Err'],
                datasets: [{
                    data: [1, 0, 0, 0],
                    backgroundColor: ['#10b981', '#06b6d4', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // 3. Method Distribution Chart (Doughnut)
    const ctxMethod = document.getElementById('methodChart')?.getContext('2d');
    if (ctxMethod) {
        methodChart = new Chart(ctxMethod, {
            type: 'doughnut',
            data: {
                labels: ['GET', 'HEAD'],
                datasets: [{
                    data: [1, 0],
                    backgroundColor: ['#3b82f6', '#a855f7'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // 4. Top Routes Chart (Horizontal Bar)
    const ctxRoutes = document.getElementById('routesChart')?.getContext('2d');
    if (ctxRoutes) {
        routesChart = new Chart(ctxRoutes, {
            type: 'bar',
            data: {
                labels: ['/', '/about', '/docs', '/dashboard', '/api/stats'],
                datasets: [{
                    label: 'Hits',
                    data: [0, 0, 0, 0, 0],
                    backgroundColor: 'rgba(56, 189, 248, 0.7)',
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    y: { grid: { display: false } }
                }
            }
        });
    }
}

/**
 * 2. Fetch Live Telemetry Data from JSON REST APIs
 */
async function fetchDashboardData() {
    try {
        const [statsRes, reqsRes] = await Promise.all([
            fetch('/api/stats'),
            fetch('/api/requests?limit=50')
        ]);

        if (!statsRes.ok || !reqsRes.ok) {
            throw new Error('API response failed');
        }

        const stats = await statsRes.json();
        const reqData = await reqsRes.json();

        updateHeaderStatus(true, stats);
        updateMetricCards(stats);
        updateCharts(stats);
        updateRequestsTable(reqData.requests || []);
    } catch (err) {
        updateHeaderStatus(false, null);
        console.warn('Telemetry polling error:', err.message);
    }
}

/**
 * 3. Update Status and Header
 */
function updateHeaderStatus(isOnline, stats) {
    const statusText = document.getElementById('serverStatusText');
    const hostPort = document.getElementById('serverHostPort');
    const uptimeEl = document.getElementById('uptimeDisplay');
    const livePulse = document.querySelector('.live-pulse');

    if (isOnline && stats) {
        if (statusText) statusText.textContent = 'Server Online';
        if (hostPort) hostPort.textContent = `${stats.server || 'NetServe'} • Port 8080`;
        if (uptimeEl) uptimeEl.textContent = stats.uptime || '00:00:00';
        if (livePulse) {
            livePulse.style.background = 'var(--accent-emerald)';
            livePulse.style.boxShadow = '0 0 10px var(--accent-emerald)';
        }
    } else {
        if (statusText) statusText.textContent = 'Reconnecting...';
        if (livePulse) {
            livePulse.style.background = 'var(--accent-rose)';
            livePulse.style.boxShadow = '0 0 10px var(--accent-rose)';
        }
    }
}

/**
 * 4. Update Metric Cards
 */
function updateMetricCards(stats) {
    setText('metricTotalRequests', stats.total_requests.toLocaleString());
    setText('metricUniqueClients', `${stats.unique_clients} Unique Client IP${stats.unique_clients === 1 ? '' : 's'}`);
    setText('metricActiveConn', stats.active_connections);
    setText('metricPeakConn', `Peak: ${stats.peak_connections} Sockets`);
    setText('metricReqPerMin', stats.requests_per_minute.toFixed(1));
    setText('metricAvgDuration', `${stats.average_response_time_ms.toFixed(1)} ms`);
    setText('metricTotalBytes', formatBytes(stats.total_bytes_served));
    setText('metricErrorRate', `${stats.error_rate_pct.toFixed(1)}%`);
    setText('metric404Count', `404 Count: ${stats.not_found_count}`);

    // System Telemetry Card
    setText('sysTopRoute', stats.most_requested_route || 'N/A');
}

/**
 * 5. Update Charts
 */
function updateCharts(stats) {
    const nowStr = new Date().toLocaleTimeString();

    // Timeline update
    if (timelineChart) {
        timelineData.labels.push(nowStr);
        timelineData.points.push(stats.requests_per_minute);

        if (timelineData.labels.length > 15) {
            timelineData.labels.shift();
            timelineData.points.shift();
        }

        timelineChart.data.labels = timelineData.labels;
        timelineChart.data.datasets[0].data = timelineData.points;
        timelineChart.update('none');
    }

    // Status Distribution
    if (statusChart && stats.status_distribution) {
        const d = stats.status_distribution;
        const vals = [d['2xx'] || 0, d['3xx'] || 0, d['4xx'] || 0, d['5xx'] || 0];
        const total = vals.reduce((a, b) => a + b, 0);
        statusChart.data.datasets[0].data = total > 0 ? vals : [1, 0, 0, 0];
        statusChart.update('none');
    }

    // Method Distribution
    if (methodChart && stats.method_distribution) {
        const m = stats.method_distribution;
        const vals = [m['GET'] || 0, m['HEAD'] || 0];
        const total = vals.reduce((a, b) => a + b, 0);
        methodChart.data.datasets[0].data = total > 0 ? vals : [1, 0];
        methodChart.update('none');
    }

    // Top Routes Chart
    if (routesChart && stats.top_routes) {
        const labels = stats.top_routes.map(r => r.route);
        const data = stats.top_routes.map(r => r.hits);
        if (labels.length > 0) {
            routesChart.data.labels = labels;
            routesChart.data.datasets[0].data = data;
            routesChart.update('none');
        }
    }
}

/**
 * 6. Update Real-Time Request Stream Table
 */
function updateRequestsTable(requests) {
    recentRequestsCache = requests;
    renderFilteredRequests();
}

function renderFilteredRequests() {
    const tbody = document.getElementById('requestTableBody');
    const filterInput = document.getElementById('filterInput');
    const query = filterInput ? filterInput.value.toLowerCase().trim() : '';

    if (!tbody) return;

    const filtered = recentRequestsCache.filter(r => {
        if (!query) return true;
        return (
            (r.path && r.path.toLowerCase().includes(query)) ||
            (r.client_ip && r.client_ip.toLowerCase().includes(query)) ||
            (r.method && r.method.toLowerCase().includes(query)) ||
            (String(r.status).includes(query))
        );
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No matching requests found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(r => {
        const statusClass = getStatusClass(r.status);
        const methodClass = r.method === 'HEAD' ? 'badge-method-head' : 'badge-method-get';

        return `
            <tr>
                <td>${r.timestamp}</td>
                <td>${r.client_ip}</td>
                <td><span class="badge-method ${methodClass}">${r.method}</span></td>
                <td><code>${escapeHtml(r.path)}</code></td>
                <td><span class="badge-status ${statusClass}">${r.status}</span></td>
                <td>${r.duration_ms} ms</td>
                <td>${formatBytes(r.size_bytes)}</td>
            </tr>
        `;
    }).join('');
}

/**
 * 7. Controls & Polling Setup
 */
function initControls() {
    const autoPoll = document.getElementById('autoPollCheckbox');
    const btnRefresh = document.getElementById('btnManualRefresh');
    const filterInput = document.getElementById('filterInput');

    if (autoPoll) {
        autoPoll.addEventListener('change', (e) => {
            isPolling = e.target.checked;
            if (isPolling) {
                startPolling();
            } else {
                stopPolling();
            }
        });
    }

    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            fetchDashboardData();
        });
    }

    if (filterInput) {
        filterInput.addEventListener('input', renderFilteredRequests);
    }
}

function startPolling() {
    stopPolling();
    pollingInterval = setInterval(() => {
        if (isPolling) {
            fetchDashboardData();
        }
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

/**
 * 8. Interactive Traffic Generator
 */
function initTrafficGenerator() {
    const buttons = document.querySelectorAll('.gen-btn[data-url]');
    const btnBurst = document.getElementById('btnBurstTraffic');
    const feedback = document.getElementById('genFeedback');

    buttons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const url = btn.getAttribute('data-url');
            if (feedback) feedback.textContent = `Dispatching GET ${url}...`;
            try {
                const t0 = performance.now();
                const res = await fetch(url);
                const lat = Math.round(performance.now() - t0);
                if (feedback) {
                    feedback.textContent = `[Success] ${res.status} ${res.statusText} for ${url} in ${lat}ms`;
                }
                fetchDashboardData();
            } catch (err) {
                if (feedback) feedback.textContent = `[Failed] ${err.message}`;
            }
        });
    });

    if (btnBurst) {
        btnBurst.addEventListener('click', async () => {
            if (feedback) feedback.textContent = 'Firing 10 concurrent requests to TCP socket pool...';
            const targets = ['/', '/about', '/docs', '/api/stats', '/api/status', '/api/network', '/css/style.css', '/js/app.js', '/api/requests', '/invalid-path'];
            try {
                const t0 = performance.now();
                await Promise.all(targets.map(t => fetch(t)));
                const lat = Math.round(performance.now() - t0);
                if (feedback) {
                    feedback.textContent = `[Burst Complete] 10 concurrent HTTP requests dispatched and fulfilled in ${lat}ms!`;
                }
                fetchDashboardData();
            } catch (err) {
                if (feedback) feedback.textContent = `[Burst Error] ${err.message}`;
            }
        });
    }
}

/**
 * Helpers
 */
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getStatusClass(status) {
    if (status >= 200 && status < 300) return 'badge-status-2xx';
    if (status >= 300 && status < 400) return 'badge-status-3xx';
    if (status >= 400 && status < 500) return 'badge-status-4xx';
    return 'badge-status-5xx';
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
