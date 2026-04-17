// ══════════════════════════════════════════
// PORTFOLIO ROADMAP
// ══════════════════════════════════════════

// ── State ──
let portfolioData = [];          // raw data from API
let selectedPrograms = new Set(); // program codes to display
let expandedPrograms = new Set(); // program codes expanded to show projects
let expandMode = 'collapsed';    // 'collapsed' or 'expanded'
let showTodayLine = true;
let showFiscalQuarters = false;

// ── Init ──
document.addEventListener('DOMContentLoaded', async function() {
    loadSettings();
    await fetchPortfolioData();
    renderProgramFilterItems();
    renderPortfolioChart();

    document.addEventListener('click', function(e) {
        const dropdown = document.getElementById('programFilterDropdown');
        if (!dropdown.contains(e.target)) closeProgramFilter();
    });
});

// ══════════════════════════════════════════
// DATA FETCH
// ══════════════════════════════════════════

async function fetchPortfolioData() {
    try {
        const response = await fetch('/api/portfolio/roadmap-data');
        if (!response.ok) throw new Error('Failed to fetch');
        portfolioData = await response.json();

        // Default: select all programs
        if (selectedPrograms.size === 0) {
            selectedPrograms = new Set(portfolioData.map(p => p.programCode));
        }

        document.getElementById('loadingState').style.display = 'none';
    } catch (err) {
        console.error('Failed to load portfolio data:', err);
        document.getElementById('loadingState').innerHTML =
            '<span style="color:#ef4444;">Failed to load portfolio data. Please refresh.</span>';
    }
}

// ══════════════════════════════════════════
// EXPAND MODE
// ══════════════════════════════════════════

function setExpandMode(mode) {
    expandMode = mode;
    document.getElementById('btnCollapsed').classList.toggle('active', mode === 'collapsed');
    document.getElementById('btnExpanded').classList.toggle('active', mode === 'expanded');

    if (mode === 'collapsed') {
        expandedPrograms.clear();
    } else {
        // Expand all
        expandedPrograms = new Set(portfolioData.map(p => p.programCode));
    }
    saveSettings();
    renderPortfolioChart();
}

// ══════════════════════════════════════════
// PROGRAM FILTER
// ══════════════════════════════════════════

function toggleProgramFilter() {
    const toggle = document.querySelector('#programFilterDropdown .dropdown-toggle');
    const menu = document.getElementById('programFilterMenu');
    toggle.classList.toggle('open');
    menu.classList.toggle('show');
}

function closeProgramFilter() {
    const toggle = document.querySelector('#programFilterDropdown .dropdown-toggle');
    const menu = document.getElementById('programFilterMenu');
    if (toggle) toggle.classList.remove('open');
    if (menu) menu.classList.remove('show');
}

function renderProgramFilterItems() {
    const container = document.getElementById('programFilterItems');
    if (portfolioData.length === 0) {
        container.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No programs found</div>';
        updateProgramStatus();
        return;
    }
    container.innerHTML = portfolioData.map(prog => {
        const checked = selectedPrograms.has(prog.programCode) ? 'checked' : '';
        const code = prog.programCode.replace(/'/g, "\\'");
        return `
            <label class="dropdown-item">
                <input type="checkbox" ${checked} onchange="toggleProgram('${code}', this.checked)">
                <span class="item-name">${escapeHtml(prog.programName)}</span>
                <span class="item-count">${prog.milestoneCount || 0} ms</span>
            </label>`;
    }).join('');
    updateProgramStatus();
}

function toggleProgram(code, checked) {
    if (checked) selectedPrograms.add(code);
    else selectedPrograms.delete(code);
    updateProgramStatus();
}

function selectAllPrograms() {
    selectedPrograms = new Set(portfolioData.map(p => p.programCode));
    renderProgramFilterItems();
}

function selectNonePrograms() {
    selectedPrograms.clear();
    renderProgramFilterItems();
}

function applyProgramFilter() {
    closeProgramFilter();
    saveSettings();
    renderPortfolioChart();
}

function updateProgramStatus() {
    const label = document.getElementById('programFilterLabel');
    const status = document.getElementById('programStatus');
    const count = selectedPrograms.size;
    const total = portfolioData.length;
    if (count === 0) {
        label.textContent = 'Select programs...';
        status.textContent = 'No programs selected';
    } else if (count === total) {
        label.textContent = `All programs (${total})`;
        status.textContent = `Showing all ${total} programs`;
    } else {
        label.textContent = `${count} of ${total} programs`;
        status.textContent = `Showing ${count} of ${total} programs`;
    }
}

// ══════════════════════════════════════════
// MARKER TOGGLES
// ══════════════════════════════════════════

function toggleTodayLine() {
    showTodayLine = !showTodayLine;
    document.getElementById('btnTodayLine').classList.toggle('active', showTodayLine);
    saveSettings();
    renderPortfolioChart();
}

function toggleFiscalQuarters() {
    showFiscalQuarters = !showFiscalQuarters;
    document.getElementById('btnFiscalQ').classList.toggle('active', showFiscalQuarters);
    saveSettings();
    renderPortfolioChart();
}

// ══════════════════════════════════════════
// SETTINGS (localStorage)
// ══════════════════════════════════════════

function loadSettings() {
    try {
        const raw = localStorage.getItem('portfolio-roadmap-settings');
        if (!raw) return;
        const s = JSON.parse(raw);
        if (s.expandMode) expandMode = s.expandMode;
        if (Array.isArray(s.selectedPrograms)) selectedPrograms = new Set(s.selectedPrograms);
        if (Array.isArray(s.expandedPrograms)) expandedPrograms = new Set(s.expandedPrograms);
        if (typeof s.showTodayLine === 'boolean') showTodayLine = s.showTodayLine;
        if (typeof s.showFiscalQuarters === 'boolean') showFiscalQuarters = s.showFiscalQuarters;

        // Reflect state in UI
        document.getElementById('btnCollapsed').classList.toggle('active', expandMode === 'collapsed');
        document.getElementById('btnExpanded').classList.toggle('active', expandMode === 'expanded');
        document.getElementById('btnTodayLine').classList.toggle('active', showTodayLine);
        document.getElementById('btnFiscalQ').classList.toggle('active', showFiscalQuarters);
    } catch (e) {
        console.log('No saved portfolio settings');
    }
}

function saveSettings() {
    try {
        localStorage.setItem('portfolio-roadmap-settings', JSON.stringify({
            expandMode,
            selectedPrograms: Array.from(selectedPrograms),
            expandedPrograms: Array.from(expandedPrograms),
            showTodayLine,
            showFiscalQuarters
        }));
    } catch (e) {
        console.error('Failed to save settings:', e);
    }
}

// ══════════════════════════════════════════
// RENDERING
// ══════════════════════════════════════════

function renderPortfolioChart() {
    const chartDiv = document.getElementById('portfolioChart');
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');
    if (loadingState) loadingState.style.display = 'none';

    const visiblePrograms = portfolioData.filter(p => selectedPrograms.has(p.programCode));

    if (visiblePrograms.length === 0) {
        emptyState.style.display = 'block';
        Plotly.purge(chartDiv);
        return;
    }
    emptyState.style.display = 'none';

    const yCategories = [];
    const traces = [];
    const annotations = [];
    const shapes = [];
    const traceMeta = [];

    // Build from bottom-up (Plotly reverses Y)
    const reversed = [...visiblePrograms].reverse();

    reversed.forEach(prog => {
        if (!prog.startDate || !prog.endDate) return;

        const isExpanded = expandedPrograms.has(prog.programCode);
        const label = isExpanded ? `▾ ${prog.programName}` : `▸ ${prog.programName}`;
        yCategories.push(label);

        // Color based on status/completion
        let barColor = '#3b82f6';
        if (prog.status === 'COMPLETED') barColor = '#22c55e';
        else if (prog.status === 'IN_PROGRESS') barColor = '#eab308';

        const progStart = new Date(prog.startDate);
        const progEnd = new Date(prog.endDate);

        // Program summary bar
        traces.push({
            x: [prog.startDate, prog.endDate],
            y: [label, label],
            mode: 'lines',
            line: { width: 32, color: barColor },
            opacity: 0.85,
            showlegend: false,
            hovertemplate:
                `<b>${escapeHtml(prog.programName)}</b><br>` +
                `${prog.milestoneCount || 0} milestones<br>` +
                `Completed: ${prog.completedCount || 0}/${prog.milestoneCount || 0}<br>` +
                `${progStart.toLocaleDateString()} – ${progEnd.toLocaleDateString()}<br>` +
                `Progress: ${prog.completionPct}%<extra></extra>`
        });

        traceMeta.push({
            taskName: label,
            startDate: prog.startDate,
            endDate: prog.endDate,
            programCode: prog.programCode,
            programName: prog.programName,
            isProgram: true,
            isProject: false,
            barWidth: 32,
            status: prog.status,
            completionPct: prog.completionPct
        });

        // Progress overlay
        if (prog.completionPct > 0 && prog.completionPct < 100) {
            const range = progEnd.getTime() - progStart.getTime();
            const progressEnd = new Date(progStart.getTime() + range * (prog.completionPct / 100));
            traces.push({
                x: [prog.startDate, progressEnd.toISOString().split('T')[0]],
                y: [label, label],
                mode: 'lines',
                line: { width: 32, color: barColor },
                opacity: 1.0,
                showlegend: false,
                hoverinfo: 'skip'
            });
        }

        // Annotation
        annotations.push({
            x: prog.endDate,
            y: label,
            text: `${prog.completionPct}% (${prog.completedCount || 0}/${prog.milestoneCount || 0})`,
            showarrow: false,
            font: { size: 11, color: '#374151' },
            xanchor: 'left',
            xshift: 10
        });

        // ── Expanded: show project bars under this program ──
        if (isExpanded && prog.projects && prog.projects.length > 0) {
            const sortedProjects = [...prog.projects].sort((a, b) =>
                new Date(a.startDate) - new Date(b.startDate)
            );
            sortedProjects.forEach(proj => {
                if (!proj.startDate || !proj.endDate) return;
                const projLabel = `    ${proj.projectName}`;
                yCategories.push(projLabel);

                let projColor = '#9ca3af';
                if (proj.status === 'COMPLETED') projColor = '#22c55e';
                else if (proj.status === 'IN_PROGRESS') projColor = '#eab308';

                traces.push({
                    x: [proj.startDate, proj.endDate],
                    y: [projLabel, projLabel],
                    mode: 'lines',
                    line: { width: 20, color: projColor },
                    opacity: 0.85,
                    showlegend: false,
                    hovertemplate:
                        `<b>${escapeHtml(proj.projectName)}</b><br>` +
                        `Program: ${escapeHtml(prog.programName)}<br>` +
                        `${proj.milestoneCount} milestones<br>` +
                        `Completed: ${proj.completedCount}/${proj.milestoneCount}<br>` +
                        `${new Date(proj.startDate).toLocaleDateString()} – ${new Date(proj.endDate).toLocaleDateString()}<br>` +
                        `Progress: ${proj.completionPct}%<extra></extra>`
                });

                traceMeta.push({
                    taskName: projLabel,
                    startDate: proj.startDate,
                    endDate: proj.endDate,
                    programCode: prog.programCode,
                    programName: prog.programName,
                    projectName: proj.projectName,
                    parentStart: prog.startDate,
                    parentEnd: prog.endDate,
                    isProgram: false,
                    isProject: true,
                    barWidth: 20,
                    status: proj.status,
                    completionPct: proj.completionPct
                });

                annotations.push({
                    x: proj.endDate,
                    y: projLabel,
                    text: `${proj.completionPct}% (${proj.completedCount}/${proj.milestoneCount})`,
                    showarrow: false,
                    font: { size: 10, color: '#6b7280' },
                    xanchor: 'left',
                    xshift: 8
                });
            });
        }
    });

    // ── Today line ──
    if (showTodayLine) {
        const todayStr = new Date().toISOString().split('T')[0];
        shapes.push({
            type: 'line',
            x0: todayStr, x1: todayStr,
            y0: 0, y1: 1,
            yref: 'paper',
            line: { color: '#ef4444', width: 2, dash: 'dash' }
        });
        annotations.push({
            x: todayStr,
            y: 1.02,
            yref: 'paper',
            text: 'Today',
            showarrow: false,
            font: { size: 10, color: '#ef4444', weight: 'bold' },
            xanchor: 'center'
        });
    }

    // ── Fiscal quarter boundaries ──
    if (showFiscalQuarters) {
        // Determine date range from data
        let minDate = Infinity, maxDate = -Infinity;
        visiblePrograms.forEach(p => {
            if (p.startDate) { const d = new Date(p.startDate).getTime(); if (d < minDate) minDate = d; }
            if (p.endDate) { const d = new Date(p.endDate).getTime(); if (d > maxDate) maxDate = d; }
        });
        if (minDate !== Infinity && maxDate !== -Infinity) {
            const startYear = new Date(minDate).getFullYear();
            const endYear = new Date(maxDate).getFullYear() + 1;
            const qDates = ['-01-01', '-04-01', '-07-01', '-10-01'];
            const qLabels = ['Q1', 'Q2', 'Q3', 'Q4'];
            for (let yr = startYear; yr <= endYear; yr++) {
                qDates.forEach((qd, qi) => {
                    const dateStr = `${yr}${qd}`;
                    const dateMs = new Date(dateStr).getTime();
                    if (dateMs >= minDate && dateMs <= maxDate) {
                        shapes.push({
                            type: 'line',
                            x0: dateStr, x1: dateStr,
                            y0: 0, y1: 1,
                            yref: 'paper',
                            line: { color: '#a855f7', width: 1, dash: 'dot' }
                        });
                        annotations.push({
                            x: dateStr,
                            y: -0.03,
                            yref: 'paper',
                            text: `${qLabels[qi]} ${yr}`,
                            showarrow: false,
                            font: { size: 9, color: '#a855f7' },
                            xanchor: 'center'
                        });
                    }
                });
            }
        }
    }

    // Chart sizing
    const rowCount = yCategories.length;
    const hasExpanded = expandedPrograms.size > 0;
    const barHeight = hasExpanded
        ? (rowCount <= 10 ? 36 : rowCount <= 30 ? 28 : 22)
        : (rowCount <= 3 ? 60 : rowCount <= 8 ? 50 : 40);
    const chartHeight = Math.max(300, (barHeight * rowCount) + 140);

    const layout = {
        title: null,
        xaxis: {
            title: { text: 'Timeline', font: { size: 12 } },
            type: 'date',
            tickformat: '%b %Y',
            showgrid: true,
            gridcolor: '#e5e7eb'
        },
        yaxis: {
            automargin: true,
            type: 'category',
            categoryorder: 'array',
            categoryarray: yCategories,
            showgrid: false,
            tickfont: { size: hasExpanded ? 10 : 12 }
        },
        height: chartHeight,
        margin: { l: hasExpanded ? 320 : 300, r: 100, t: 30, b: 60 },
        hovermode: 'closest',
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        annotations: annotations,
        shapes: shapes
    };

    Plotly.newPlot(chartDiv, traces, layout, {
        responsive: true,
        displayModeBar: false
    }).then(() => {
        setupDragHandles(chartDiv, traceMeta);
        setupClickToExpand(chartDiv, traceMeta);
    });

    chartDiv.on('plotly_relayout', () => {
        setupDragHandles(chartDiv, traceMeta);
    });
}

// ══════════════════════════════════════════
// CLICK-TO-EXPAND
// ══════════════════════════════════════════

function setupClickToExpand(chartDiv, traceMeta) {
    chartDiv.removeAllListeners('plotly_click');
    chartDiv.on('plotly_click', function(data) {
        if (!data.points || !data.points[0]) return;
        const yVal = data.points[0].y;
        // Find the program meta for this click
        const meta = traceMeta.find(m => m.taskName === yVal && m.isProgram);
        if (!meta) return;

        if (expandedPrograms.has(meta.programCode)) {
            expandedPrograms.delete(meta.programCode);
        } else {
            expandedPrograms.add(meta.programCode);
        }

        // Update expand mode button state
        const allExpanded = portfolioData.every(p =>
            !selectedPrograms.has(p.programCode) || expandedPrograms.has(p.programCode)
        );
        const noneExpanded = expandedPrograms.size === 0;
        document.getElementById('btnCollapsed').classList.toggle('active', noneExpanded);
        document.getElementById('btnExpanded').classList.toggle('active', allExpanded);

        saveSettings();
        renderPortfolioChart();
    });
}

// ══════════════════════════════════════════
// DRAG SYSTEM
// ══════════════════════════════════════════

let dragState = null;
let dragOverlays = [];

function removeDragOverlays() {
    dragOverlays.forEach(el => el.remove());
    dragOverlays = [];
}

function setupDragHandles(chartDiv, traceMeta) {
    removeDragOverlays();

    const plotArea = chartDiv.querySelector('.plot');
    if (!plotArea) return;

    const xa = chartDiv._fullLayout.xaxis;
    const ya = chartDiv._fullLayout.yaxis;

    traceMeta.forEach(meta => {
        const yPos = ya.d2p(meta.taskName);
        const xStart = xa.d2p(new Date(meta.startDate).getTime());
        const xEnd = xa.d2p(new Date(meta.endDate).getTime());

        if (isNaN(yPos) || isNaN(xStart) || isNaN(xEnd)) return;

        const barWidth = meta.barWidth || 20;
        const handleWidth = 8;
        const barLeft = Math.min(xStart, xEnd);
        const barRight = Math.max(xStart, xEnd);
        const barTop = yPos - barWidth / 2;

        // Center body (move)
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'drag-handle drag-body';
        bodyDiv.style.cssText = `position:absolute; left:${barLeft + handleWidth}px; top:${barTop}px; width:${Math.max(barRight - barLeft - 2 * handleWidth, 4)}px; height:${barWidth}px; cursor:grab; z-index:10;`;
        bodyDiv.title = `Drag to move: ${meta.taskName.replace(/^[▸▾\s]+/, '')}`;
        bodyDiv.addEventListener('mousedown', e => startDrag(e, meta, 'move', chartDiv));
        bodyDiv.addEventListener('touchstart', e => startDrag(e, meta, 'move', chartDiv), {passive: false});
        plotArea.appendChild(bodyDiv);
        dragOverlays.push(bodyDiv);

        // Left edge (resize start)
        const leftDiv = document.createElement('div');
        leftDiv.className = 'drag-handle drag-edge-left';
        leftDiv.style.cssText = `position:absolute; left:${barLeft}px; top:${barTop}px; width:${handleWidth}px; height:${barWidth}px; cursor:ew-resize; z-index:11;`;
        leftDiv.title = 'Drag to change start date';
        leftDiv.addEventListener('mousedown', e => startDrag(e, meta, 'resize-left', chartDiv));
        leftDiv.addEventListener('touchstart', e => startDrag(e, meta, 'resize-left', chartDiv), {passive: false});
        plotArea.appendChild(leftDiv);
        dragOverlays.push(leftDiv);

        // Right edge (resize end)
        const rightDiv = document.createElement('div');
        rightDiv.className = 'drag-handle drag-edge-right';
        rightDiv.style.cssText = `position:absolute; left:${barRight - handleWidth}px; top:${barTop}px; width:${handleWidth}px; height:${barWidth}px; cursor:ew-resize; z-index:11;`;
        rightDiv.title = 'Drag to change end date';
        rightDiv.addEventListener('mousedown', e => startDrag(e, meta, 'resize-right', chartDiv));
        rightDiv.addEventListener('touchstart', e => startDrag(e, meta, 'resize-right', chartDiv), {passive: false});
        plotArea.appendChild(rightDiv);
        dragOverlays.push(rightDiv);
    });
}

function startDrag(e, meta, dragType, chartDiv) {
    e.preventDefault();
    e.stopPropagation();

    const clientX = e.touches ? e.touches[0].clientX : e.clientX;

    dragState = {
        meta,
        dragType,
        startClientX: clientX,
        origStart: meta.startDate,
        origEnd: meta.endDate,
        chartDiv,
        newStart: meta.startDate,
        newEnd: meta.endDate,
        constraintViolation: false
    };

    showDragTooltip(clientX, e.touches ? e.touches[0].clientY : e.clientY, meta.startDate, meta.endDate);

    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd);
    document.addEventListener('touchmove', onDragMove, {passive: false});
    document.addEventListener('touchend', onDragEnd);
}

function onDragMove(e) {
    if (!dragState) return;
    e.preventDefault();

    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const dx = clientX - dragState.startClientX;

    const xa = dragState.chartDiv._fullLayout.xaxis;
    const origStartMs = new Date(dragState.origStart).getTime();
    const origEndMs = new Date(dragState.origEnd).getTime();
    const pxStart = xa.d2p(origStartMs);
    const pxEnd = xa.d2p(origEndMs);

    let newStartMs, newEndMs;

    if (dragState.dragType === 'move') {
        const dateAtNewPx = xa.p2d(pxStart + dx);
        const deltaMs = dateAtNewPx - origStartMs;
        newStartMs = origStartMs + deltaMs;
        newEndMs = origEndMs + deltaMs;
    } else if (dragState.dragType === 'resize-left') {
        newStartMs = xa.p2d(pxStart + dx);
        newEndMs = origEndMs;
        if (newStartMs >= newEndMs) newStartMs = newEndMs - 86400000;
    } else if (dragState.dragType === 'resize-right') {
        newStartMs = origStartMs;
        newEndMs = xa.p2d(pxEnd + dx);
        if (newEndMs <= newStartMs) newEndMs = newStartMs + 86400000;
    }

    // ── Constraint check: project bars constrained by parent program ──
    let constraintViolation = false;
    if (dragState.meta.isProject && dragState.meta.parentStart && dragState.meta.parentEnd) {
        const parentStartMs = new Date(dragState.meta.parentStart).getTime();
        const parentEndMs = new Date(dragState.meta.parentEnd).getTime();
        if (newStartMs < parentStartMs || newEndMs > parentEndMs) {
            constraintViolation = true;
        }
    }

    dragState.newStart = msToDateStr(newStartMs);
    dragState.newEnd = msToDateStr(newEndMs);
    dragState.constraintViolation = constraintViolation;

    showDragTooltip(clientX, clientY, dragState.newStart, dragState.newEnd, constraintViolation);
}

function onDragEnd() {
    document.removeEventListener('mousemove', onDragMove);
    document.removeEventListener('mouseup', onDragEnd);
    document.removeEventListener('touchmove', onDragMove);
    document.removeEventListener('touchend', onDragEnd);
    hideDragTooltip();

    if (!dragState) return;

    const { origStart, origEnd, newStart, newEnd, constraintViolation, meta } = dragState;
    dragState = null;

    if ((origStart === newStart && origEnd === newEnd) || constraintViolation) {
        return;
    }

    showDateChangeModal(meta, origStart, origEnd, newStart, newEnd);
}

function msToDateStr(ms) {
    return new Date(ms).toISOString().split('T')[0];
}

// ── Drag Tooltip ──
function showDragTooltip(x, y, startDate, endDate, violation) {
    let tooltip = document.getElementById('dragTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'dragTooltip';
        tooltip.className = 'drag-tooltip';
        document.body.appendChild(tooltip);
    }
    const startFmt = new Date(startDate).toLocaleDateString();
    const endFmt = new Date(endDate).toLocaleDateString();
    tooltip.innerHTML = violation
        ? `<span style="color:#ef4444;">⚠ Exceeds program boundaries</span><br>${startFmt} – ${endFmt}`
        : `${startFmt} – ${endFmt}`;
    tooltip.style.left = (x + 12) + 'px';
    tooltip.style.top = (y - 40) + 'px';
    tooltip.style.display = 'block';
    tooltip.style.borderColor = violation ? '#ef4444' : '#3b82f6';
}

function hideDragTooltip() {
    const tooltip = document.getElementById('dragTooltip');
    if (tooltip) tooltip.style.display = 'none';
}

// ══════════════════════════════════════════
// CONFIRMATION MODAL
// ══════════════════════════════════════════

function showDateChangeModal(meta, oldStart, oldEnd, newStart, newEnd) {
    let modal = document.getElementById('dateChangeModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dateChangeModal';
        modal.className = 'date-change-modal-overlay';
        document.body.appendChild(modal);
    }

    const displayName = meta.taskName.replace(/^[▸▾\s]+/, '').trim();
    const typeLabel = meta.isProgram ? 'Program' : 'Project';
    const oldStartFmt = new Date(oldStart).toLocaleDateString();
    const oldEndFmt = new Date(oldEnd).toLocaleDateString();
    const newStartFmt = new Date(newStart).toLocaleDateString();
    const newEndFmt = new Date(newEnd).toLocaleDateString();

    const startDaysDiff = Math.round((new Date(newStart) - new Date(oldStart)) / 86400000);
    const endDaysDiff = Math.round((new Date(newEnd) - new Date(oldEnd)) / 86400000);

    let changeDesc = '';
    if (oldStart !== newStart && oldEnd !== newEnd) {
        changeDesc = `Moved by ${Math.abs(startDaysDiff)} day(s) ${startDaysDiff > 0 ? 'later' : 'earlier'}`;
    } else if (oldStart !== newStart) {
        changeDesc = `Start ${startDaysDiff > 0 ? 'delayed' : 'advanced'} by ${Math.abs(startDaysDiff)} day(s)`;
    } else {
        changeDesc = `End ${endDaysDiff > 0 ? 'extended' : 'shortened'} by ${Math.abs(endDaysDiff)} day(s)`;
    }

    modal.innerHTML = `
        <div class="date-change-modal">
            <h3>Confirm ${typeLabel} Schedule Change</h3>
            <div class="modal-milestone-name">${escapeHtml(displayName)}</div>
            <div class="modal-dates">
                <div><strong>Start:</strong> ${oldStartFmt} → ${newStartFmt} ${oldStart !== newStart ? '(' + (startDaysDiff > 0 ? '+' : '') + startDaysDiff + 'd)' : ''}</div>
                <div><strong>End:</strong> ${oldEndFmt} → ${newEndFmt} ${oldEnd !== newEnd ? '(' + (endDaysDiff > 0 ? '+' : '') + endDaysDiff + 'd)' : ''}</div>
            </div>
            <div class="modal-summary">${changeDesc}</div>
            <label class="modal-checkbox">
                <input type="checkbox" id="modalRecordChange" checked>
                Record in Change Log
            </label>
            <textarea id="modalChangeReason" class="modal-reason" placeholder="Reason for change (optional)"></textarea>
            <div class="modal-actions">
                <button class="modal-btn modal-btn-cancel" onclick="closeDateChangeModal()">Cancel</button>
                <button class="modal-btn modal-btn-save" id="modalSaveBtn" onclick="confirmDateChange()">Save</button>
            </div>
        </div>
    `;

    modal._changeData = { meta, oldStart, oldEnd, newStart, newEnd };
    modal.style.display = 'flex';
}

function closeDateChangeModal() {
    const modal = document.getElementById('dateChangeModal');
    if (modal) modal.style.display = 'none';
}

async function confirmDateChange() {
    const modal = document.getElementById('dateChangeModal');
    if (!modal || !modal._changeData) return;

    const { meta, newStart, newEnd } = modal._changeData;
    const saveBtn = document.getElementById('modalSaveBtn');
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        let response;

        if (meta.isProgram) {
            // Update program dates
            response = await fetch(`/api/programs/${encodeURIComponent(meta.programCode)}/dates`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_date: newStart,
                    target_completion: newEnd
                })
            });
        } else if (meta.isProject) {
            // Update project (parent_project group) boundary milestones
            response = await fetch(`/api/programs/${encodeURIComponent(meta.programCode)}/project-dates`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    parent_project: meta.projectName,
                    start_date: newStart,
                    end_date: newEnd
                })
            });
        }

        const result = await response.json();

        if (response.ok && result.success) {
            // Update in-memory data
            const prog = portfolioData.find(p => p.programCode === meta.programCode);
            if (prog) {
                if (meta.isProgram) {
                    prog.startDate = newStart;
                    prog.endDate = newEnd;
                } else if (meta.isProject && prog.projects) {
                    const proj = prog.projects.find(p => p.projectName === meta.projectName);
                    if (proj) {
                        proj.startDate = newStart;
                        proj.endDate = newEnd;
                    }
                }
            }

            closeDateChangeModal();
            showToast('Schedule updated successfully', 'success');
            renderPortfolioChart();
        } else {
            showToast(result.error || result.detail || 'Failed to save change', 'error');
            saveBtn.textContent = 'Save';
            saveBtn.disabled = false;
        }
    } catch (err) {
        console.error('Save failed:', err);
        showToast('Network error — please try again', 'error');
        saveBtn.textContent = 'Save';
        saveBtn.disabled = false;
    }
}

// ══════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type) {
    let toast = document.getElementById('ganttToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'ganttToast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = 'gantt-toast ' + (type === 'error' ? 'toast-error' : 'toast-success');
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, 3000);
}
