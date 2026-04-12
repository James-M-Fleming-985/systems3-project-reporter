/**
 * Financial Dashboard — Client-side rendering for Financial Governance & Strategic Intelligence.
 * Handles data fetching, GridStack KPI cards, Plotly charts, drill-down navigation,
 * and cross-program comparison.
 */

// ======================================================================
// State
// ======================================================================
const FinancialDashboard = {
    currentLevel: 'portfolio',   // portfolio | program | project
    currentProgramId: null,
    breadcrumb: [],
    gridStack: null,
    data: {},
    layoutKey: 'fgsi_dashboard_layout',
};

// ======================================================================
// Initialization
// ======================================================================

function initFinancialDashboard() {
    fetchFinancialSummary().then(() => {
        renderKPICards();
        renderCharts();
        renderLevers();
    });
}

// ======================================================================
// Data Fetching
// ======================================================================

async function fetchFinancialSummary(programId) {
    // Build query params with rolling 12-month date range
    const now = new Date();
    const startDate = new Date(now.getFullYear(), now.getMonth(), 1);
    const endDate = new Date(now.getFullYear(), now.getMonth() + 12, 0);
    const periodStart = startDate.toISOString().slice(0, 10);
    const periodEnd = endDate.toISOString().slice(0, 10);

    const qp = new URLSearchParams({ period_start: periodStart, period_end: periodEnd });
    if (programId) qp.set('program_id', programId);
    const qs = '?' + qp.toString();

    try {
        const [summaryRes, forecastRes, riskRes, leverRes] = await Promise.all([
            fetch(`/api/financial/summary${qs}`),
            fetch(`/api/financial/forecast${qs}`),
            fetch(`/api/financial/risks${qs}`),
            fetch(`/api/financial/levers${qs}`),
        ]);

        const summary = await summaryRes.json();
        const forecasts = await forecastRes.json();
        const risks = await riskRes.json();
        const levers = await leverRes.json();

        FinancialDashboard.data = {
            summary: summary.data || {},
            forecasts: forecasts.data || [],
            risks: risks.data || [],
            levers: levers.data || [],
        };
    } catch (err) {
        console.error('Failed to fetch financial data:', err);
        FinancialDashboard.data = { summary: {}, forecasts: [], risks: [], levers: [] };
    }
}

async function fetchTargetsAndActuals(programId) {
    const params = programId ? `?program_id=${encodeURIComponent(programId)}` : '';
    try {
        const [targetsRes, actualsRes] = await Promise.all([
            fetch(`/api/financial/targets${params}`),
            fetch(`/api/financial/actuals${params}`),
        ]);
        const targets = await targetsRes.json();
        const actuals = await actualsRes.json();
        return {
            targets: targets.data || [],
            actuals: actuals.data || [],
        };
    } catch (err) {
        console.error('Failed to fetch targets/actuals:', err);
        return { targets: [], actuals: [] };
    }
}

// ======================================================================
// KPI Cards
// ======================================================================

function renderKPICards() {
    const s = FinancialDashboard.data.summary || {};
    const container = document.getElementById('financialKPIGrid');
    if (!container) return;

    const cards = [
        {
            id: 'kpi-revenue',
            title: 'Total Revenue',
            value: formatCurrency(s.total_revenue_actual),
            detail: `Target: ${formatCurrency(s.total_revenue_target)}`,
            variance: s.revenue_variance_pct,
            gs: { x: 0, y: 0, w: 4, h: 2 },
        },
        {
            id: 'kpi-cost',
            title: 'Total Cost',
            value: formatCurrency(s.total_cost_actual),
            detail: `Budget: ${formatCurrency(s.total_cost_budget)}`,
            variance: s.cost_variance_pct,
            invertColor: true,
            gs: { x: 4, y: 0, w: 4, h: 2 },
        },
        {
            id: 'kpi-margin',
            title: 'Margin',
            value: s.actual_margin != null ? s.actual_margin.toFixed(1) + '%' : '—',
            detail: s.target_margin != null ? `Target: ${s.target_margin.toFixed(1)}%` : '',
            variance: s.actual_margin != null && s.target_margin != null
                ? parseFloat((s.actual_margin - s.target_margin).toFixed(1)) : null,
            gs: { x: 8, y: 0, w: 4, h: 2 },
        },
        {
            id: 'kpi-profit',
            title: 'Net Profit',
            value: formatCurrency(s.net_profit),
            detail: s.profit_margin != null ? `Margin: ${s.profit_margin.toFixed(1)}%` : '',
            variance: s.profit_variance_pct,
            gs: { x: 0, y: 2, w: 4, h: 2 },
        },
        {
            id: 'kpi-forecast',
            title: 'Forecast Accuracy',
            value: s.forecast_accuracy != null ? s.forecast_accuracy.toFixed(0) + '%' : '—',
            detail: 'Model confidence',
            variance: null,
            gs: { x: 0, y: 4, w: 4, h: 2 },
        },
        {
            id: 'kpi-resource',
            title: 'Resource Utilisation',
            value: s.resource_utilisation != null ? s.resource_utilisation.toFixed(1) + '%' : '—',
            detail: 'Cost / Revenue ratio',
            variance: null,
            gs: { x: 4, y: 4, w: 4, h: 2 },
        },
        {
            id: 'kpi-risk',
            title: 'Financial Risk Score',
            value: s.financial_risk_score != null ? s.financial_risk_score.toString() : '0',
            detail: `${(FinancialDashboard.data.risks || []).length} open risk(s)`,
            variance: null,
            gs: { x: 8, y: 4, w: 4, h: 2 },
        },
    ];

    // Build GridStack items
    container.innerHTML = '';
    const savedLayout = loadLayout();

    cards.forEach(card => {
        const pos = savedLayout?.[card.id] || card.gs;
        const el = document.createElement('div');
        el.className = 'grid-stack-item';
        el.setAttribute('gs-x', pos.x);
        el.setAttribute('gs-y', pos.y);
        el.setAttribute('gs-w', pos.w);
        el.setAttribute('gs-h', pos.h);
        el.setAttribute('gs-id', card.id);

        const varBadge = card.variance != null ? varianceBadge(card.variance, card.invertColor) : '';

        el.innerHTML = `
            <div class="grid-stack-item-content">
                <div class="gs-widget-header">
                    <span class="widget-title">${card.title}</span>
                </div>
                <div class="gs-widget-body" style="flex-direction: column;">
                    <div class="kpi-value">${card.value}</div>
                    <div class="kpi-detail">${card.detail} ${varBadge}</div>
                </div>
            </div>
        `;
        container.appendChild(el);
    });

    // Init GridStack
    if (FinancialDashboard.gridStack) {
        FinancialDashboard.gridStack.destroy(false);
    }
    FinancialDashboard.gridStack = GridStack.init({
        column: 12,
        cellHeight: 80,
        animate: true,
        float: false,
        draggable: { handle: '.gs-widget-header' },
    }, container);

    FinancialDashboard.gridStack.on('change', saveLayout);
}

// ======================================================================
// Charts (Plotly.js)
// ======================================================================

function renderCharts() {
    renderRevenueTrajectoryChart();
    renderCostBreakdownChart();
    renderContributionChart();
    renderLeverChart();
}

async function renderRevenueTrajectoryChart() {
    const chartEl = document.getElementById('revenueTrajectoryChart');
    if (!chartEl) return;

    const { targets, actuals } = await fetchTargetsAndActuals(FinancialDashboard.currentProgramId);
    const forecasts = FinancialDashboard.data.forecasts || [];

    // --- Aggregate by period with per-program breakdown ---
    function aggregateByPeriod(records, revenueField, costField) {
        const byDate = {};
        records.forEach(r => {
            const d = r.period_start;
            if (!byDate[d]) byDate[d] = { total_revenue: 0, total_cost: 0, programs: {} };
            const pid = r.program_id || 'portfolio';
            if (!byDate[d].programs[pid]) byDate[d].programs[pid] = { revenue: 0, cost: 0 };
            byDate[d].programs[pid].revenue += r[revenueField] || 0;
            byDate[d].programs[pid].cost += r[costField] || 0;
            byDate[d].total_revenue += r[revenueField] || 0;
            byDate[d].total_cost += r[costField] || 0;
        });
        return Object.entries(byDate).sort((a, b) => a[0].localeCompare(b[0]))
            .map(([date, v]) => ({ date, ...v }));
    }

    const aggTargets = aggregateByPeriod(targets, 'revenue_target', 'cost_budget');
    const aggActuals = aggregateByPeriod(actuals, 'actual_revenue', 'actual_cost');

    function buildHoverText(agg, label) {
        return agg.map(a => {
            const lines = [`<b>${label}: ${formatCurrency(a.total_revenue)}</b>`];
            Object.entries(a.programs).forEach(([pid, v]) => {
                lines.push(`  ${pid}: ${formatCurrency(v.revenue)}`);
            });
            if (a.total_cost > 0) {
                const profit = a.total_revenue - a.total_cost;
                lines.push(`Cost: ${formatCurrency(a.total_cost)}`);
                lines.push(`Profit: ${formatCurrency(profit)}`);
            }
            return lines.join('<br>');
        });
    }

    // Build traces
    const targetTrace = {
        x: aggTargets.map(a => a.date),
        y: aggTargets.map(a => a.total_revenue),
        name: 'Target',
        mode: 'lines+markers',
        line: { color: '#9CA3AF', dash: 'dash', width: 2 },
        marker: { size: 6 },
        text: buildHoverText(aggTargets, 'Target Revenue'),
        hoverinfo: 'text',
    };

    const actualTrace = {
        x: aggActuals.map(a => a.date),
        y: aggActuals.map(a => a.total_revenue),
        name: 'Actual Revenue',
        mode: 'lines+markers',
        line: { color: '#3B82F6', width: 3 },
        marker: { size: 8 },
        text: buildHoverText(aggActuals, 'Actual Revenue'),
        hoverinfo: 'text',
    };

    // Profit trace (actuals revenue minus costs)
    const profitTrace = {
        x: aggActuals.map(a => a.date),
        y: aggActuals.map(a => a.total_revenue - a.total_cost),
        name: 'Profit',
        mode: 'lines+markers',
        line: { color: '#10B981', width: 2 },
        marker: { size: 5, symbol: 'diamond' },
        text: aggActuals.map(a => {
            const profit = a.total_revenue - a.total_cost;
            const margin = a.total_revenue > 0 ? ((profit / a.total_revenue) * 100).toFixed(1) : 0;
            return `<b>Profit: ${formatCurrency(profit)}</b><br>Margin: ${margin}%`;
        }),
        hoverinfo: 'text',
    };

    // Target profit trace (target revenue minus cost budget)
    const targetProfitTrace = {
        x: aggTargets.map(a => a.date),
        y: aggTargets.map(a => a.total_revenue - a.total_cost),
        name: 'Target Profit',
        mode: 'lines',
        line: { color: '#6EE7B7', dash: 'dash', width: 1.5 },
        hoverinfo: 'skip',
    };

    const traces = [targetTrace, actualTrace, targetProfitTrace, profitTrace];

    // Add forecast with confidence band
    const revForecasts = forecasts.filter(f => f.metric === 'revenue' && f.forecast_points?.length > 0);
    if (revForecasts.length > 0) {
        // Use longest horizon
        const forecast = revForecasts.reduce((a, b) =>
            (a.horizon_months || 0) > (b.horizon_months || 0) ? a : b
        );
        const pts = forecast.forecast_points || [];

        traces.push({
            x: pts.map(p => p.date),
            y: pts.map(p => p.value),
            name: 'Forecast',
            mode: 'lines',
            line: { color: '#10B981', width: 2, dash: 'dot' },
        });

        // Confidence band (95%)
        if (pts[0]?.lower_95 != null) {
            traces.push({
                x: pts.map(p => p.date).concat(pts.map(p => p.date).reverse()),
                y: pts.map(p => p.upper_95).concat(pts.map(p => p.lower_95).reverse()),
                fill: 'toself',
                fillcolor: 'rgba(16,185,129,0.1)',
                line: { color: 'transparent' },
                name: '95% Confidence',
                showlegend: true,
                type: 'scatter',
            });
        }
    }

    Plotly.newPlot(chartEl, traces, {
        xaxis: { title: 'Period' },
        yaxis: { title: 'Amount (£)', tickformat: ',.0f' },
        legend: { orientation: 'h', y: -0.2 },
        margin: { t: 10, b: 60, l: 80, r: 20 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        hovermode: 'x unified',
    }, { responsive: true, displayModeBar: false });

    // Drill-down on click
    chartEl.on('plotly_click', function (data) {
        if (data.points && data.points.length > 0) {
            const pt = data.points[0];
            if (FinancialDashboard.currentLevel === 'portfolio' && pt.customdata) {
                drillDown('program', pt.customdata);
            }
        }
    });
}

function renderCostBreakdownChart() {
    const chartEl = document.getElementById('costBreakdownChart');
    if (!chartEl) return;

    const summaries = FinancialDashboard.data.summary?.program_summaries || [];
    if (summaries.length === 0) {
        chartEl.innerHTML = '<p class="text-gray-400 text-sm text-center p-4">No program cost data available</p>';
        return;
    }

    const trace = {
        x: summaries.map(s => s.program_id),
        y: summaries.map(s => s.cost_actual || 0),
        type: 'bar',
        marker: {
            color: summaries.map(s => {
                const var_pct = s.cost_budget > 0
                    ? ((s.cost_actual - s.cost_budget) / s.cost_budget * 100) : 0;
                return var_pct > 10 ? '#EF4444' : var_pct > 5 ? '#F59E0B' : '#10B981';
            }),
        },
        text: summaries.map(s => `£${(s.cost_actual || 0).toLocaleString()}`),
        textposition: 'outside',
    };

    const budgetTrace = {
        x: summaries.map(s => s.program_id),
        y: summaries.map(s => s.cost_budget || 0),
        type: 'scatter',
        mode: 'markers',
        name: 'Budget',
        marker: { color: '#6B7280', size: 10, symbol: 'line-ew-open', line: { width: 2 } },
    };

    Plotly.newPlot(chartEl, [trace, budgetTrace], {
        xaxis: { title: 'Program' },
        yaxis: { title: 'Cost (£)', tickformat: ',.0f' },
        showlegend: false,
        margin: { t: 10, b: 80, l: 80, r: 20 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
    }, { responsive: true, displayModeBar: false });

    // Drill-down on bar click
    chartEl.on('plotly_click', function (data) {
        if (data.points?.[0]?.x) {
            drillDown('program', data.points[0].x);
        }
    });
}

function renderContributionChart() {
    const chartEl = document.getElementById('contributionChart');
    if (!chartEl) return;

    const summaries = FinancialDashboard.data.summary?.program_summaries || [];
    if (summaries.length === 0) {
        chartEl.innerHTML = '<p class="text-gray-400 text-sm text-center p-4">No program data available yet. Record monthly financials to see contributions.</p>';
        return;
    }

    // Use actuals if available, otherwise fall back to targets
    const hasActuals = summaries.some(s => (s.revenue_actual || 0) > 0 || (s.cost_actual || 0) > 0);
    const valueKey = hasActuals ? 'revenue_actual' : 'revenue_target';
    const suffix = hasActuals ? '' : ' (Target)';

    const direct = summaries.filter(s => s.contribution_type === 'direct_revenue');
    const indirect = summaries.filter(s => s.contribution_type === 'indirect_revenue_impact');

    const labels = [];
    const values = [];
    const colors = [];

    direct.forEach(s => {
        const val = s[valueKey] || 0;
        if (val > 0) {
            labels.push(s.program_id + ' (Direct)' + suffix);
            values.push(val);
            colors.push('#3B82F6');
        }
    });
    indirect.forEach(s => {
        const val = s[valueKey] || 0;
        if (val > 0) {
            labels.push(s.program_id + ' (Indirect)' + suffix);
            values.push(val);
            colors.push('#8B5CF6');
        }
    });

    if (values.length === 0) {
        chartEl.innerHTML = '<p class="text-gray-400 text-sm text-center p-4">No revenue data recorded yet. Record monthly financials to see contributions.</p>';
        return;
    }

    Plotly.newPlot(chartEl, [{
        labels: labels,
        values: values,
        type: 'pie',
        hole: 0.5,
        marker: { colors: colors },
        textinfo: 'label+percent',
        textposition: 'outside',
    }], {
        showlegend: false,
        margin: { t: 10, b: 20, l: 20, r: 20 },
        paper_bgcolor: 'transparent',
    }, { responsive: true, displayModeBar: false });
}

function renderLeverChart() {
    const chartEl = document.getElementById('leverChart');
    if (!chartEl) return;

    const levers = FinancialDashboard.data.levers || [];
    if (levers.length === 0) {
        chartEl.innerHTML = '<p class="text-gray-400 text-sm text-center p-4">No strategic lever recommendations — portfolio is on track</p>';
        return;
    }

    const colorMap = {
        cost_reduction: '#EF4444',
        revenue_acceleration: '#3B82F6',
        resource_reallocation: '#F59E0B',
        risk_mitigation: '#8B5CF6',
    };

    Plotly.newPlot(chartEl, [{
        type: 'bar',
        orientation: 'h',
        y: levers.map(l => l.title.substring(0, 40)),
        x: levers.map(l => l.estimated_impact),
        marker: { color: levers.map(l => colorMap[l.lever_type] || '#6B7280') },
        text: levers.map(l => `£${l.estimated_impact.toLocaleString()}`),
        textposition: 'outside',
    }], {
        xaxis: { title: 'Estimated Impact (£)', tickformat: ',.0f' },
        yaxis: { automargin: true },
        margin: { t: 10, b: 40, l: 200, r: 80 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
    }, { responsive: true, displayModeBar: false });
}

// ======================================================================
// Strategic Levers List
// ======================================================================

function renderLevers() {
    const container = document.getElementById('leversList');
    if (!container) return;

    const levers = FinancialDashboard.data.levers || [];
    if (levers.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No recommendations at this time.</p>';
        return;
    }

    const typeIcons = {
        cost_reduction: '💰',
        revenue_acceleration: '📈',
        resource_reallocation: '🔄',
        risk_mitigation: '🛡️',
    };

    const effortColors = {
        low: 'bg-green-100 text-green-800',
        medium: 'bg-yellow-100 text-yellow-800',
        high: 'bg-red-100 text-red-800',
    };

    container.innerHTML = levers.map(l => `
        <div class="bg-white border border-gray-200 rounded-lg p-4 mb-3">
            <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-2">
                    <span class="text-xl">${typeIcons[l.lever_type] || '📋'}</span>
                    <h4 class="font-semibold text-gray-800">${escapeHtml(l.title)}</h4>
                </div>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium ${effortColors[l.effort_level] || ''}">${l.effort_level}</span>
            </div>
            <p class="text-sm text-gray-600 mb-2">${escapeHtml(l.description)}</p>
            <div class="flex items-center gap-4 text-xs text-gray-500">
                <span title="Estimated financial impact">Impact: <strong class="text-gray-800">£${l.estimated_impact.toLocaleString()}</strong></span>
                <span title="Model confidence level">Confidence: <strong class="text-gray-800">${(l.confidence * 100).toFixed(0)}%</strong></span>
                <span title="Recommended implementation timeline">Timeline: <strong class="text-gray-800">${l.recommended_timeline || '—'}</strong></span>
            </div>
        </div>
    `).join('');
}

// ======================================================================
// Cross-Program Comparison
// ======================================================================

function renderComparisonTable() {
    const container = document.getElementById('comparisonTable');
    if (!container) return;

    const summaries = FinancialDashboard.data.summary?.program_summaries || [];
    if (summaries.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm text-center p-4">No program data available for comparison</p>';
        return;
    }

    let html = `
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-200 text-left text-gray-600">
                    <th class="py-2 px-3 cursor-pointer" onclick="sortComparison('program_id')" title="Sort by program name">Program</th>
                    <th class="py-2 px-3 cursor-pointer" onclick="sortComparison('contribution_type')" title="Sort by contribution type">Type</th>
                    <th class="py-2 px-3 text-right cursor-pointer" onclick="sortComparison('revenue_actual')" title="Sort by revenue">Revenue</th>
                    <th class="py-2 px-3 text-right cursor-pointer" onclick="sortComparison('cost_actual')" title="Sort by cost">Cost</th>
                    <th class="py-2 px-3 text-right cursor-pointer" onclick="sortComparison('variance_pct')" title="Sort by variance">Variance</th>
                </tr>
            </thead>
            <tbody>`;

    summaries.forEach(s => {
        const varBadge = varianceBadge(s.variance_pct || 0);
        html += `
            <tr class="border-b border-gray-100 hover:bg-gray-50 cursor-pointer" onclick="drillDown('program', '${escapeHtml(s.program_id)}')">
                <td class="py-2 px-3 font-medium">${escapeHtml(s.program_id)}</td>
                <td class="py-2 px-3"><span class="px-2 py-0.5 rounded-full text-xs ${s.contribution_type === 'direct_revenue' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'}">${s.contribution_type === 'direct_revenue' ? 'Direct' : 'Indirect'}</span></td>
                <td class="py-2 px-3 text-right">${formatCurrency(s.revenue_actual)}</td>
                <td class="py-2 px-3 text-right">${formatCurrency(s.cost_actual)}</td>
                <td class="py-2 px-3 text-right">${varBadge}</td>
            </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

let comparisonSortKey = 'program_id';
let comparisonSortAsc = true;

function sortComparison(key) {
    if (comparisonSortKey === key) {
        comparisonSortAsc = !comparisonSortAsc;
    } else {
        comparisonSortKey = key;
        comparisonSortAsc = true;
    }
    const summaries = FinancialDashboard.data.summary?.program_summaries || [];
    summaries.sort((a, b) => {
        const va = a[key] ?? '';
        const vb = b[key] ?? '';
        const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb));
        return comparisonSortAsc ? cmp : -cmp;
    });
    renderComparisonTable();
}

// ======================================================================
// Drill-Down Navigation
// ======================================================================

function drillDown(level, id) {
    FinancialDashboard.breadcrumb.push({
        level: FinancialDashboard.currentLevel,
        id: FinancialDashboard.currentProgramId,
    });
    FinancialDashboard.currentLevel = level;
    FinancialDashboard.currentProgramId = id;
    renderBreadcrumb();
    refreshDashboard();
}

function drillUp(index) {
    if (index < 0) {
        // Back to portfolio
        FinancialDashboard.currentLevel = 'portfolio';
        FinancialDashboard.currentProgramId = null;
        FinancialDashboard.breadcrumb = [];
    } else {
        const entry = FinancialDashboard.breadcrumb[index];
        FinancialDashboard.currentLevel = entry.level;
        FinancialDashboard.currentProgramId = entry.id;
        FinancialDashboard.breadcrumb = FinancialDashboard.breadcrumb.slice(0, index);
    }
    renderBreadcrumb();
    refreshDashboard();
}

function renderBreadcrumb() {
    const container = document.getElementById('financialBreadcrumb');
    if (!container) return;

    let html = '<nav class="flex items-center text-sm text-gray-500 mb-4"><ol class="flex items-center gap-1">';
    html += `<li><button onclick="drillUp(-1)" class="hover:text-blue-600 transition" title="Return to portfolio view">Portfolio</button></li>`;

    FinancialDashboard.breadcrumb.forEach((entry, i) => {
        html += '<li class="text-gray-300">/</li>';
        html += `<li><button onclick="drillUp(${i})" class="hover:text-blue-600 transition">${escapeHtml(entry.id || entry.level)}</button></li>`;
    });

    if (FinancialDashboard.currentProgramId) {
        html += '<li class="text-gray-300">/</li>';
        html += `<li class="font-medium text-gray-800">${escapeHtml(FinancialDashboard.currentProgramId)}</li>`;
    }

    html += '</ol></nav>';
    container.innerHTML = html;
}

async function refreshDashboard() {
    await fetchFinancialSummary(FinancialDashboard.currentProgramId);
    renderKPICards();
    renderCharts();
    renderLevers();
    renderComparisonTable();
}

// ======================================================================
// Layout Persistence
// ======================================================================

function saveLayout() {
    if (!FinancialDashboard.gridStack) return;
    const items = FinancialDashboard.gridStack.getGridItems();
    const layout = {};
    items.forEach(el => {
        const id = el.getAttribute('gs-id');
        if (id) {
            layout[id] = {
                x: parseInt(el.getAttribute('gs-x') || 0),
                y: parseInt(el.getAttribute('gs-y') || 0),
                w: parseInt(el.getAttribute('gs-w') || 4),
                h: parseInt(el.getAttribute('gs-h') || 2),
            };
        }
    });
    try {
        localStorage.setItem(FinancialDashboard.layoutKey, JSON.stringify(layout));
    } catch (e) { /* ignore quota errors */ }
}

function loadLayout() {
    try {
        const raw = localStorage.getItem(FinancialDashboard.layoutKey);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}

// ======================================================================
// Utility
// ======================================================================

function formatCurrency(val) {
    if (val == null || isNaN(val)) return '—';
    return '£' + Number(val).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function varianceBadge(pct, invertColor) {
    if (pct == null) return '';
    const abs = Math.abs(pct).toFixed(1);
    const sign = pct >= 0 ? '+' : '';
    let color;
    if (invertColor) {
        // For costs: positive = bad, negative = good
        color = pct > 5 ? 'bg-red-100 text-red-800' : pct < -5 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700';
    } else {
        // For revenue/margin: positive = good, negative = bad
        color = pct >= -5 ? 'bg-green-100 text-green-800' : pct >= -15 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
    }
    return `<span class="inline-block px-1.5 py-0.5 rounded text-xs font-medium ${color}">${sign}${pct.toFixed(1)}%</span>`;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ======================================================================
// Financial Data Entry Modal
// ======================================================================

async function openFinancialEntryModal() {
    const modal = document.getElementById('financialEntryModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Default period to current month
    const now = new Date();
    const monthStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    document.getElementById('entryPeriod').value = monthStr;

    // Reset
    document.getElementById('entryNotes').value = '';
    document.getElementById('entryFormResult').textContent = '';

    // Fetch all programs (active + archived) from portfolio manager
    await populateProgramRows();
}

function closeFinancialEntryModal() {
    const modal = document.getElementById('financialEntryModal');
    if (modal) modal.classList.add('hidden');
    document.body.style.overflow = '';
}

async function populateProgramRows() {
    const container = document.getElementById('entryProgramRows');
    container.innerHTML = '<div class="text-sm text-gray-400 py-4 text-center">Loading programs…</div>';

    try {
        const resp = await fetch('/dashboard/projects?include_archived=true');
        if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({}));
            const msg = resp.status === 401
                ? 'Session expired — please refresh the page and log in again.'
                : `Error loading programs (${resp.status}): ${errBody.detail || 'unknown'}`;
            container.innerHTML = `<div class="text-sm text-red-500 py-4 text-center">${escapeHtml(msg)}</div>`;
            return;
        }
        const programs = await resp.json();

        if (!Array.isArray(programs) || programs.length === 0) {
            container.innerHTML = '<div class="text-sm text-gray-500 py-4 text-center">No programs found. Create a program in the Portfolio dashboard first.</div>';
            return;
        }

        container.innerHTML = programs.map(p => {
            const pid = escapeHtml(p.code || p.id);
            const label = escapeHtml(p.name);
            const archivedBadge = p.archived ? ' <span class="text-xs text-gray-400">(archived)</span>' : '';
            return `
                <div class="grid grid-cols-12 gap-2 items-center bg-gray-50 rounded-lg px-3 py-2" data-program-id="${pid}">
                    <div class="col-span-4 text-sm font-medium text-gray-700 truncate" title="${label}">${label}${archivedBadge}</div>
                    <div class="col-span-3">
                        <div class="relative">
                            <span class="absolute left-2 top-1.5 text-gray-400 text-xs">£</span>
                            <input type="number" min="0" step="0.01" class="entry-revenue w-full border border-gray-300 rounded pl-5 pr-2 py-1.5 text-sm text-right focus:ring-2 focus:ring-blue-500" placeholder="0.00" oninput="updateEntryTotals()"/>
                        </div>
                    </div>
                    <div class="col-span-3">
                        <div class="relative">
                            <span class="absolute left-2 top-1.5 text-gray-400 text-xs">£</span>
                            <input type="number" min="0" step="0.01" class="entry-cost w-full border border-gray-300 rounded pl-5 pr-2 py-1.5 text-sm text-right focus:ring-2 focus:ring-blue-500" placeholder="0.00" oninput="updateEntryTotals()"/>
                        </div>
                    </div>
                    <div class="col-span-2 text-sm text-right font-medium entry-profit text-gray-400">£0</div>
                </div>`;
        }).join('');

        updateEntryTotals();
    } catch (err) {
        container.innerHTML = `<div class="text-sm text-red-500 py-4 text-center">Failed to load programs: ${escapeHtml(err.message)}</div>`;
    }
}

function updateEntryTotals() {
    const rows = document.querySelectorAll('#entryProgramRows [data-program-id]');
    let totalRev = 0, totalCost = 0;

    rows.forEach(row => {
        const rev = parseFloat(row.querySelector('.entry-revenue').value) || 0;
        const cost = parseFloat(row.querySelector('.entry-cost').value) || 0;
        const profit = rev - cost;
        totalRev += rev;
        totalCost += cost;

        const profitEl = row.querySelector('.entry-profit');
        profitEl.textContent = formatCurrency(profit);
        profitEl.className = `col-span-2 text-sm text-right font-medium entry-profit ${profit > 0 ? 'text-green-700' : profit < 0 ? 'text-red-700' : 'text-gray-400'}`;
    });

    const totalProfit = totalRev - totalCost;
    const margin = totalRev > 0 ? ((totalProfit / totalRev) * 100).toFixed(1) : '0';

    document.getElementById('entryTotalRevenue').textContent = formatCurrency(totalRev);
    document.getElementById('entryTotalCost').textContent = formatCurrency(totalCost);

    const totalProfitEl = document.getElementById('entryTotalProfit');
    totalProfitEl.textContent = formatCurrency(totalProfit);
    totalProfitEl.className = `col-span-2 text-right ${totalProfit >= 0 ? 'text-green-700' : 'text-red-700'}`;

    document.getElementById('entryTotalMargin').textContent = `Margin: ${margin}%`;
}

async function submitFinancialEntry() {
    const resultEl = document.getElementById('entryFormResult');
    const submitBtn = document.getElementById('entrySubmitBtn');
    const periodVal = document.getElementById('entryPeriod').value;
    const notes = document.getElementById('entryNotes').value.trim();

    if (!periodVal) {
        resultEl.textContent = '⚠️ Select a month';
        resultEl.className = 'text-sm text-red-600';
        return;
    }

    // Collect rows with any non-zero values
    const rows = document.querySelectorAll('#entryProgramRows [data-program-id]');
    const entries = [];
    rows.forEach(row => {
        const programId = row.dataset.programId;
        const rev = parseFloat(row.querySelector('.entry-revenue').value) || 0;
        const cost = parseFloat(row.querySelector('.entry-cost').value) || 0;
        if (rev > 0 || cost > 0) {
            entries.push({ programId, revenue: rev, cost });
        }
    });

    if (!entries.length) {
        resultEl.textContent = '⚠️ Enter income or costs for at least one program';
        resultEl.className = 'text-sm text-red-600';
        return;
    }

    const periodStart = periodVal + '-01';
    const csrfToken = document.getElementById('csrfToken')?.value || '';

    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    resultEl.textContent = '';

    let savedCount = 0;
    const errors = [];

    for (const entry of entries) {
        try {
            const resp = await fetch('/api/financial/actuals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
                body: JSON.stringify({
                    actual_revenue: entry.revenue,
                    actual_cost: entry.cost,
                    period: 'monthly',
                    period_start: periodStart,
                    program_id: entry.programId,
                    notes: notes || undefined,
                }),
            });
            const result = await resp.json();
            if (resp.ok && result.status === 'success') {
                savedCount++;
            } else {
                errors.push(`${entry.programId}: ${result.detail || 'failed'}`);
            }
        } catch (err) {
            errors.push(`${entry.programId}: ${err.message}`);
        }
    }

    if (errors.length === 0) {
        resultEl.textContent = `✅ Saved ${savedCount} program${savedCount > 1 ? 's' : ''} successfully`;
        resultEl.className = 'text-sm text-green-600';
        refreshDashboard();
        setTimeout(() => closeFinancialEntryModal(), 1200);
    } else {
        resultEl.textContent = `⚠️ ${savedCount} saved, ${errors.length} failed`;
        resultEl.className = 'text-sm text-red-600';
        if (savedCount > 0) refreshDashboard();
    }

    submitBtn.disabled = false;
    submitBtn.textContent = 'Save All';
}

// ======================================================================
// Financial Data Upload
// ======================================================================

async function uploadFinancialData() {
    const fileInput = document.getElementById('importFile');
    const dataType = document.getElementById('importDataType').value;
    const resultDiv = document.getElementById('importResult');

    if (!fileInput.files.length) {
        resultDiv.className = 'mt-3 p-3 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm';
        resultDiv.textContent = 'Please select a file first.';
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    resultDiv.className = 'mt-3 p-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-sm';
    resultDiv.textContent = 'Uploading...';

    try {
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const resp = await fetch(`/api/financial/import?data_type=${encodeURIComponent(dataType)}`, {
            method: 'POST',
            headers: { 'x-csrf-token': csrfToken },
            body: formData,
        });
        const result = await resp.json();

        if (resp.ok && result.status === 'success') {
            const d = result.data;
            resultDiv.className = 'mt-3 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm';
            resultDiv.innerHTML = `<strong>✅ Import complete:</strong> ${d.imported} of ${d.total_rows} rows imported.`
                + (d.errors?.length ? `<br><span class="text-red-600">${d.errors.length} error(s) — check console for details.</span>` : '');
            if (d.errors?.length) console.warn('Import errors:', d.errors);
            // Refresh dashboard
            refreshDashboard();
        } else {
            resultDiv.className = 'mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm';
            resultDiv.textContent = '❌ ' + (result.detail || result.message || 'Import failed');
        }
    } catch (err) {
        resultDiv.className = 'mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm';
        resultDiv.textContent = '❌ Network error: ' + err.message;
    }
}
