// Data from backend
const _ganttBridge = document.getElementById("gantt-data-bridge");
const projectCode = _ganttBridge.dataset.projectCode;
const projectName = _ganttBridge.dataset.projectName;

function exportXml() {
    window.location.href = `/api/export/xml/${encodeURIComponent(projectCode)}`;
}

const ganttData = JSON.parse(_ganttBridge.dataset.ganttData);

// ── State ──
let viewMode = 'project';  // 'project' or 'level'
let roadmapDetailMode = 'expanded';  // 'summary' or 'expanded'
let availableLevels = [];
let selectedLevel = null;
let levelItems = [];
let selectedItems = new Set();

// Project Roadmap state
let projectGroups = [];        // unique Resource values
let selectedGroups = new Set(); // selected group names

// ── Initialize ──
document.addEventListener('DOMContentLoaded', async function() {
    detectAvailableLevels();
    detectProjectGroups();
    await loadSavedSettings();
    populateLevelDropdown();
    applyViewMode();
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        const dropdown = document.getElementById('projectDropdown');
        const groupDropdown = document.getElementById('groupFilterDropdown');
        if (!dropdown.contains(e.target)) closeDropdown();
        if (!groupDropdown.contains(e.target)) closeGroupFilter();
    });
});

// ══════════════════════════════════════════
// VIEW MODE TOGGLE
// ══════════════════════════════════════════

function setViewMode(mode) {
    viewMode = mode;
    applyViewMode();
    saveSettings();
}

function applyViewMode() {
    const btnProject = document.getElementById('btnProjectRoadmap');
    const btnLevel = document.getElementById('btnLevelDetail');
    const levelControls = document.getElementById('levelDetailControls');
    const projectControls = document.getElementById('projectRoadmapControls');

    if (viewMode === 'project') {
        btnProject.classList.add('active');
        btnLevel.classList.remove('active');
        levelControls.style.display = 'none';
        projectControls.style.display = '';
        renderGroupFilterItems();
        renderProjectRoadmap();
    } else {
        btnLevel.classList.add('active');
        btnProject.classList.remove('active');
        levelControls.style.display = '';
        projectControls.style.display = 'none';
        
        if (selectedLevel) {
            buildLevelItems(selectedLevel);
            renderDropdownItems();
            renderRoadmap();
        } else {
            renderDropdownItems();
            updateStatus();
        }
    }
}

// ══════════════════════════════════════════
// PROJECT ROADMAP VIEW
// ══════════════════════════════════════════

function setRoadmapDetail(mode) {
    roadmapDetailMode = mode;
    document.getElementById('btnSummary').classList.toggle('active', mode === 'summary');
    document.getElementById('btnExpanded').classList.toggle('active', mode === 'expanded');
    saveSettings();
    renderProjectRoadmap();
}

function detectProjectGroups() {
    const groupSet = new Set();
    ganttData.forEach(task => {
        if (task.Resource) {
            groupSet.add(task.Resource);
        }
    });
    projectGroups = Array.from(groupSet).sort();
    
    // Default: all selected
    if (selectedGroups.size === 0) {
        selectedGroups = new Set(projectGroups);
    }
}

function toggleGroupFilter() {
    const toggle = document.querySelector('#groupFilterDropdown .dropdown-toggle');
    const menu = document.getElementById('groupFilterMenu');
    toggle.classList.toggle('open');
    menu.classList.toggle('show');
}

function closeGroupFilter() {
    const toggle = document.querySelector('#groupFilterDropdown .dropdown-toggle');
    const menu = document.getElementById('groupFilterMenu');
    if (toggle) toggle.classList.remove('open');
    if (menu) menu.classList.remove('show');
}

function renderGroupFilterItems() {
    const container = document.getElementById('groupFilterItems');
    
    if (projectGroups.length === 0) {
        container.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No project groups found</div>';
        updateGroupStatus();
        return;
    }
    
    container.innerHTML = projectGroups.map(group => {
        const checked = selectedGroups.has(group) ? 'checked' : '';
        const escapedName = group.replace(/'/g, "\\'");
        const count = ganttData.filter(t => t.Resource === group).length;
        return `
            <label class="dropdown-item">
                <input type="checkbox" ${checked} onchange="toggleGroup('${escapedName}', this.checked)">
                <span class="item-name">${escapeHtml(group)}</span>
                <span class="item-count">${count}</span>
            </label>
        `;
    }).join('');
    
    updateGroupStatus();
}

function toggleGroup(name, checked) {
    if (checked) selectedGroups.add(name);
    else selectedGroups.delete(name);
    updateGroupStatus();
}

function selectAllGroups() {
    selectedGroups = new Set(projectGroups);
    renderGroupFilterItems();
}

function selectNoneGroups() {
    selectedGroups.clear();
    renderGroupFilterItems();
}

function applyGroupFilter() {
    closeGroupFilter();
    saveSettings();
    renderProjectRoadmap();
}

function updateGroupStatus() {
    const label = document.getElementById('groupFilterLabel');
    const status = document.getElementById('groupStatus');
    const count = selectedGroups.size;
    const total = projectGroups.length;
    
    if (count === 0) {
        label.textContent = 'Select project groups...';
        status.textContent = 'No groups selected';
    } else if (count === total) {
        label.textContent = `All project groups (${total})`;
        status.textContent = `Showing all ${total} project groups`;
    } else {
        label.textContent = `${count} of ${total} groups`;
        status.textContent = `Showing ${count} of ${total} project groups`;
    }
}

function renderProjectRoadmap() {
    const chartDiv = document.getElementById('roadmapChart');
    const emptyState = document.getElementById('emptyState');
    
    if (selectedGroups.size === 0 || projectGroups.length === 0) {
        emptyState.style.display = 'block';
        if (projectGroups.length === 0) {
            emptyState.querySelector('h3').textContent = 'No Project Groups Found';
            emptyState.querySelector('p').textContent = 'This program has no milestones with project group data';
        } else {
            emptyState.querySelector('h3').textContent = 'Select Project Groups';
            emptyState.querySelector('p').textContent = 'Choose which project groups to display on the roadmap';
        }
        Plotly.purge(chartDiv);
        return;
    }
    
    emptyState.style.display = 'none';
    
    // Group tasks by Resource (parent_project), filter to selected groups
    const groupedTasks = {};
    ganttData.forEach(task => {
        if (task.Resource && selectedGroups.has(task.Resource)) {
            if (!groupedTasks[task.Resource]) groupedTasks[task.Resource] = [];
            groupedTasks[task.Resource].push(task);
        }
    });
    
    // Sort groups alphabetically
    const sortedGroupNames = Object.keys(groupedTasks).sort();
    
    const yCategories = [];
    const traces = [];
    const annotations = [];
    const shapes = [];
    const traceMeta = [];  // metadata for drag handles
    
    // Build from bottom-up (Plotly reverses Y)
    const reversedGroups = [...sortedGroupNames].reverse();
    
    const isExpanded = roadmapDetailMode === 'expanded';
    
    reversedGroups.forEach((groupName, groupIdx) => {
        const tasks = groupedTasks[groupName];
        
        // Calculate group date range from all milestones
        const groupStart = tasks.reduce((min, t) => {
            const d = new Date(t.Start);
            return d < min ? d : min;
        }, new Date('9999-12-31'));
        const groupEnd = tasks.reduce((max, t) => {
            const d = new Date(t.Finish);
            return d > max ? d : max;
        }, new Date('1970-01-01'));
        
        // Calculate overall completion %
        const totalPct = tasks.reduce((sum, t) => sum + (t.CompletionPct || 0), 0);
        const avgPct = Math.round(totalPct / tasks.length);
        
        // Count statuses
        const completed = tasks.filter(t => t.Status === 'COMPLETED').length;
        const inProgress = tasks.filter(t => t.Status === 'IN_PROGRESS').length;
        const total = tasks.length;
        
        // Color based on overall progress
        let barColor = '#3b82f6'; // blue default
        if (avgPct >= 100 || completed === total) barColor = '#22c55e'; // green
        else if (avgPct > 0 || inProgress > 0) barColor = '#eab308'; // yellow
        
        const startStr = groupStart.toISOString().split('T')[0];
        const endStr = groupEnd.toISOString().split('T')[0];
        
        // Summary bar label (with bold marker for expanded mode)
        const summaryLabel = isExpanded ? `▸ ${groupName}` : groupName;
        yCategories.push(summaryLabel);
        
        // Summary bar per project
        traces.push({
            x: [startStr, endStr],
            y: [summaryLabel, summaryLabel],
            mode: 'lines',
            line: { width: 28, color: barColor },
            opacity: 0.85,
            showlegend: false,
            hovertemplate:
                `<b>${escapeHtml(groupName)}</b><br>` +
                `${total} milestones<br>` +
                `Completed: ${completed}/${total}<br>` +
                `${groupStart.toLocaleDateString()} – ${groupEnd.toLocaleDateString()}<br>` +
                `Progress: ${avgPct}%<extra></extra>`
        });
        
        // Summary bar drag metadata
        traceMeta.push({
            taskName: summaryLabel,
            startDate: startStr,
            endDate: endStr,
            projectCode: tasks[0].ProjectCode || projectCode,
            milestoneId: '',
            resource: groupName,
            isSummary: true,
            barWidth: 28,
            status: '',
            completionPct: avgPct
        });
        
        // Progress completion overlay
        if (avgPct > 0 && avgPct < 100) {
            const range = groupEnd.getTime() - groupStart.getTime();
            const progressEnd = new Date(groupStart.getTime() + range * (avgPct / 100));
            const progressEndStr = progressEnd.toISOString().split('T')[0];
            traces.push({
                x: [startStr, progressEndStr],
                y: [summaryLabel, summaryLabel],
                mode: 'lines',
                line: { width: 28, color: barColor },
                opacity: 1.0,
                showlegend: false,
                hoverinfo: 'skip'
            });
        }
        
        // Annotation with percentage and milestone count
        annotations.push({
            x: endStr,
            y: summaryLabel,
            text: `${avgPct}% (${completed}/${total})`,
            showarrow: false,
            font: { size: 11, color: '#374151' },
            xanchor: 'left',
            xshift: 10
        });
        
        // ── Expanded mode: add individual milestone bars under this group ──
        if (isExpanded) {
            const sortedTasks = [...tasks].sort((a, b) => new Date(a.Start) - new Date(b.Start));
            sortedTasks.forEach(task => {
                const msLabel = `    ${task.Task}`;
                yCategories.push(msLabel);
                
                let msStart = task.Start;
                let msFinish = task.Finish;
                const msStartDate = new Date(msStart);
                let msFinishDate = new Date(msFinish);
                if (msFinishDate <= msStartDate) {
                    msFinishDate = new Date(msStartDate);
                    msFinishDate.setDate(msFinishDate.getDate() + 7);
                    msFinish = msFinishDate.toISOString().split('T')[0];
                }
                
                const pct = task.CompletionPct || 0;
                let msColor = '#9ca3af';
                if (task.Status === 'COMPLETED') msColor = '#22c55e';
                else if (task.Status === 'IN_PROGRESS') msColor = '#eab308';
                
                traces.push({
                    x: [msStart, msFinish],
                    y: [msLabel, msLabel],
                    mode: 'lines',
                    line: { width: 16, color: msColor },
                    opacity: 0.85,
                    showlegend: false,
                    hovertemplate:
                        `<b>${escapeHtml(task.Task)}</b><br>` +
                        `Group: ${escapeHtml(groupName)}<br>` +
                        `Start: ${msStartDate.toLocaleDateString()}<br>` +
                        `End: ${msFinishDate.toLocaleDateString()}<br>` +
                        `Status: ${task.Status}<br>` +
                        `Progress: ${pct}%<extra></extra>`
                });
                
                // Milestone drag metadata
                traceMeta.push({
                    taskName: msLabel,
                    startDate: msStart,
                    endDate: msFinish,
                    projectCode: task.ProjectCode || projectCode,
                    milestoneId: task.MilestoneId || '',
                    resource: groupName,
                    isSummary: false,
                    parentStart: startStr,
                    parentEnd: endStr,
                    barWidth: 16,
                    status: task.Status,
                    completionPct: pct
                });
                
                annotations.push({
                    x: msFinish,
                    y: msLabel,
                    text: `${pct}%`,
                    showarrow: false,
                    font: { size: 10, color: '#6b7280' },
                    xanchor: 'left',
                    xshift: 8
                });
            });
        }
    });
    
    // Chart height
    const rowCount = yCategories.length;
    const barHeight = isExpanded
        ? (rowCount <= 10 ? 36 : rowCount <= 30 ? 28 : 22)
        : (rowCount <= 3 ? 60 : rowCount <= 8 ? 50 : 40);
    const chartHeight = Math.max(250, (barHeight * rowCount) + 120);
    
    const layout = {
        title: null,
        dragmode: false,
        xaxis: {
            title: { text: 'Timeline', font: { size: 12 } },
            type: 'date',
            tickformat: '%b %Y',
            showgrid: true,
            gridcolor: '#e5e7eb',
            fixedrange: true
        },
        yaxis: {
            automargin: true,
            type: 'category',
            categoryorder: 'array',
            categoryarray: yCategories,
            showgrid: false,
            tickfont: { size: isExpanded ? 10 : 11 },
            fixedrange: true
        },
        height: chartHeight,
        margin: { l: isExpanded ? 320 : 280, r: 80, t: 20, b: 60 },
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
    });
    
    // Reposition drag overlays on chart resize
    chartDiv.on('plotly_relayout', () => {
        setupDragHandles(chartDiv, traceMeta);
    });
}

// ══════════════════════════════════════════
// LEVEL DETAIL VIEW (original behavior)
// ══════════════════════════════════════════

function detectAvailableLevels() {
    const levelSet = new Set();
    ganttData.forEach(task => {
        const ol = task.OutlineLevel;
        if (ol && ol >= 2) levelSet.add(ol);
    });
    availableLevels = Array.from(levelSet).sort((a, b) => a - b);
}

function populateLevelDropdown() {
    const select = document.getElementById('levelSelect');
    
    if (availableLevels.length === 0) {
        select.innerHTML = '<option value="">No levels available</option>';
        select.disabled = true;
        return;
    }
    
    select.innerHTML = '<option value="">-- Select level --</option>' +
        availableLevels.map(lvl => {
            const selected = (selectedLevel === lvl) ? 'selected' : '';
            const count = ganttData.filter(t => t.OutlineLevel === lvl).length;
            return `<option value="${lvl}" ${selected}>Level ${lvl} (${count} items)</option>`;
        }).join('');
}

function onLevelChange() {
    const select = document.getElementById('levelSelect');
    const newLevel = select.value ? parseInt(select.value) : null;
    
    if (newLevel === selectedLevel) return;
    
    selectedLevel = newLevel;
    selectedItems.clear();
    
    if (selectedLevel) {
        buildLevelItems(selectedLevel);
        selectedItems = new Set(levelItems.map(t => t.Task));
    } else {
        levelItems = [];
    }
    
    renderDropdownItems();
    saveSettings();
    renderRoadmap();
    renderPills();
}

function buildLevelItems(level) {
    levelItems = ganttData.filter(task => task.OutlineLevel === level);
    levelItems.sort((a, b) => new Date(a.Start) - new Date(b.Start));
}

async function loadSavedSettings() {
    try {
        const response = await fetch(`/dashboard/api/roadmap/${encodeURIComponent(projectCode)}/settings`);
        const settings = await response.json();
        
        // Load view mode
        if (settings.view_mode && (settings.view_mode === 'project' || settings.view_mode === 'level')) {
            viewMode = settings.view_mode;
        }
        
        // Load saved level (for level detail view)
        if (settings.selected_level && availableLevels.includes(settings.selected_level)) {
            selectedLevel = settings.selected_level;
            buildLevelItems(selectedLevel);
        }
        
        // Load saved level selections
        if (selectedLevel && settings.selected_groups && settings.selected_groups.length > 0 && !settings.show_all) {
            const validNames = new Set(levelItems.map(t => t.Task));
            selectedItems = new Set(settings.selected_groups.filter(g => validNames.has(g)));
        } else if (selectedLevel) {
            selectedItems = new Set(levelItems.map(t => t.Task));
        }
        
        // Load saved project group selections (for project roadmap view)
        if (settings.selected_project_groups && settings.selected_project_groups.length > 0) {
            const validGroups = new Set(projectGroups);
            selectedGroups = new Set(settings.selected_project_groups.filter(g => validGroups.has(g)));
        } else {
            selectedGroups = new Set(projectGroups);
        }
        
        // Load roadmap detail mode
        if (settings.roadmap_detail_mode === 'summary' || settings.roadmap_detail_mode === 'expanded') {
            roadmapDetailMode = settings.roadmap_detail_mode;
            document.getElementById('btnSummary').classList.toggle('active', roadmapDetailMode === 'summary');
            document.getElementById('btnExpanded').classList.toggle('active', roadmapDetailMode === 'expanded');
        }
    } catch (error) {
        console.log('No saved settings');
    }
}

function toggleDropdown() {
    const toggle = document.querySelector('#projectDropdown .dropdown-toggle');
    const menu = document.getElementById('dropdownMenu');
    toggle.classList.toggle('open');
    menu.classList.toggle('show');
}

function closeDropdown() {
    const toggle = document.querySelector('#projectDropdown .dropdown-toggle');
    const menu = document.getElementById('dropdownMenu');
    if (toggle) toggle.classList.remove('open');
    if (menu) menu.classList.remove('show');
}

function renderDropdownItems() {
    const container = document.getElementById('dropdownItems');
    
    if (!selectedLevel) {
        container.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">Select a project level first</div>';
        updateStatus();
        return;
    }
    
    if (levelItems.length === 0) {
        container.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No items at this level</div>';
        updateStatus();
        return;
    }
    
    container.innerHTML = levelItems.map(task => {
        const checked = selectedItems.has(task.Task) ? 'checked' : '';
        const escapedName = task.Task.replace(/'/g, "\\'");
        const statusIcon = task.Status === 'COMPLETED' ? '🟢' : task.Status === 'IN_PROGRESS' ? '🟡' : '⚪';
        
        return `
            <label class="dropdown-item">
                <input type="checkbox" ${checked} onchange="toggleProject('${escapedName}', this.checked)">
                <span class="item-name">${statusIcon} ${escapeHtml(task.Task)}</span>
            </label>
        `;
    }).join('');
    
    updateStatus();
}

function updateStatus() {
    const label = document.getElementById('dropdownLabel');
    const status = document.getElementById('selectionStatus');
    
    if (!selectedLevel) {
        label.textContent = 'Select items...';
        status.textContent = 'Select a project level first';
        return;
    }
    
    const count = selectedItems.size;
    const total = levelItems.length;
    
    if (count === 0) {
        label.textContent = 'Select items...';
        status.textContent = `Level ${selectedLevel}: No items selected`;
    } else if (count === total) {
        label.textContent = `All items (${total})`;
        status.textContent = `Level ${selectedLevel}: Showing all ${total} items`;
    } else {
        label.textContent = `${count} of ${total} selected`;
        status.textContent = `Level ${selectedLevel}: Showing ${count} of ${total} items`;
    }
}

function toggleProject(name, checked) {
    if (checked) selectedItems.add(name);
    else selectedItems.delete(name);
    updateStatus();
}

function selectAllProjects() {
    selectedItems = new Set(levelItems.map(t => t.Task));
    renderDropdownItems();
}

function selectNoneProjects() {
    selectedItems.clear();
    renderDropdownItems();
}

function applyAndClose() {
    closeDropdown();
    saveSettings();
    renderRoadmap();
    renderPills();
}

function renderPills() {
    const container = document.getElementById('selectionPills');
    container.innerHTML = '';
}

function removePill(name) {
    selectedItems.delete(name);
    renderDropdownItems();
    saveSettings();
    renderRoadmap();
    renderPills();
}

async function saveSettings() {
    try {
        await fetch(`/dashboard/api/roadmap/${encodeURIComponent(projectCode)}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                view_mode: viewMode,
                selected_level: selectedLevel,
                selected_groups: Array.from(selectedItems),
                show_all: selectedItems.size === levelItems.length,
                selected_project_groups: Array.from(selectedGroups),
                roadmap_detail_mode: roadmapDetailMode
            })
        });
    } catch (error) {
        console.error('Failed to save settings:', error);
    }
}

function renderRoadmap() {
    const chartDiv = document.getElementById('roadmapChart');
    const emptyState = document.getElementById('emptyState');
    
    if (!selectedLevel || selectedItems.size === 0) {
        emptyState.style.display = 'block';
        emptyState.querySelector('h3').textContent = 'Select Project Level and Projects';
        emptyState.querySelector('p').textContent = 'Choose a project level to see available projects, then select which ones to display';
        Plotly.purge(chartDiv);
        return;
    }
    
    emptyState.style.display = 'none';
    
    const selected = levelItems
        .filter(t => selectedItems.has(t.Task))
        .sort((a, b) => new Date(a.Start) - new Date(b.Start));
    
    const traces = [];
    const annotations = [];
    const taskNames = selected.map(t => t.Task).reverse();
    const traceMeta = [];

    selected.forEach(task => {
        let startStr = task.Start;
        let finishStr = task.Finish;
        
        const taskStart = new Date(startStr);
        let taskFinish = new Date(finishStr);
        
        if (taskFinish <= taskStart) {
            taskFinish = new Date(taskStart);
            taskFinish.setDate(taskFinish.getDate() + 7);
            finishStr = taskFinish.toISOString().split('T')[0];
        }
        
        const pct = task.CompletionPct || 0;
        
        let barColor = '#9ca3af';
        if (task.Status === 'COMPLETED') barColor = '#22c55e';
        else if (task.Status === 'IN_PROGRESS') barColor = '#eab308';
        
        traces.push({
            x: [startStr, finishStr],
            y: [task.Task, task.Task],
            mode: 'lines',
            line: { width: 20, color: barColor },
            opacity: 0.85,
            name: task.Task,
            showlegend: false,
            hovertemplate:
                `<b>${escapeHtml(task.Task)}</b><br>` +
                `Start: ${taskStart.toLocaleDateString()}<br>` +
                `End: ${taskFinish.toLocaleDateString()}<br>` +
                `Status: ${task.Status}<br>` +
                `Progress: ${pct}%<extra></extra>`
        });
        
        traceMeta.push({
            taskName: task.Task,
            startDate: startStr,
            endDate: finishStr,
            projectCode: task.ProjectCode || projectCode,
            milestoneId: task.MilestoneId || '',
            resource: task.Resource || '',
            isSummary: false,
            barWidth: 20,
            status: task.Status,
            completionPct: pct
        });
        
        annotations.push({
            x: finishStr,
            y: task.Task,
            text: `${pct}%`,
            showarrow: false,
            font: { size: 11, color: '#374151' },
            xanchor: 'left',
            xshift: 8
        });
    });
    
    const rowCount = selected.length;
    const barHeight = rowCount <= 3 ? 60 : rowCount <= 8 ? 45 : 35;
    const chartHeight = Math.max(250, (barHeight * rowCount) + 120);
    
    const layout = {
        title: null,
        dragmode: false,
        xaxis: {
            title: { text: 'Timeline', font: { size: 12 } },
            type: 'date',
            tickformat: '%b %Y',
            showgrid: true,
            gridcolor: '#e5e7eb',
            fixedrange: true
        },
        yaxis: {
            automargin: true,
            type: 'category',
            categoryorder: 'array',
            categoryarray: taskNames,
            showgrid: false,
            tickfont: { size: 11 },
            fixedrange: true
        },
        height: chartHeight,
        margin: { l: 250, r: 80, t: 20, b: 60 },
        hovermode: 'closest',
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        annotations: annotations
    };
    
    Plotly.newPlot(chartDiv, traces, layout, {
        responsive: true,
        displayModeBar: false
    }).then(() => {
        setupDragHandles(chartDiv, traceMeta);
    });
    
    chartDiv.on('plotly_relayout', () => {
        setupDragHandles(chartDiv, traceMeta);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ══════════════════════════════════════════
// INTERACTIVE DRAG SYSTEM
// ══════════════════════════════════════════

let dragState = null;  // active drag info
let dragOverlays = []; // DOM elements for drag handles

function removeDragOverlays() {
    dragOverlays.forEach(el => el.remove());
    dragOverlays = [];
}

/**
 * Build drag handle overlays for each milestone bar on the chart.
 * @param {HTMLElement} chartDiv - the Plotly chart div
 * @param {Array} traceMeta - array of {taskName, startDate, endDate, projectCode, milestoneId, resource, isSummary}
 */
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
        
        const barWidth = meta.isSummary ? 28 : (meta.barWidth || 16);
        const handleWidth = 8;
        const barLeft = Math.min(xStart, xEnd);
        const barRight = Math.max(xStart, xEnd);
        const barTop = yPos - barWidth / 2;
        
        // Center body (move handle)
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'drag-handle drag-body';
        bodyDiv.style.cssText = `position:absolute; left:${barLeft + handleWidth}px; top:${barTop}px; width:${Math.max(barRight - barLeft - 2 * handleWidth, 4)}px; height:${barWidth}px; cursor:grab; z-index:10;`;
        bodyDiv.title = `Drag to move: ${meta.taskName}`;
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
        meta: meta,
        dragType: dragType,
        startClientX: clientX,
        origStart: meta.startDate,
        origEnd: meta.endDate,
        chartDiv: chartDiv,
        newStart: meta.startDate,
        newEnd: meta.endDate
    };
    
    // Show tooltip
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
    
    // Convert pixel delta to date delta
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
        const dateAtNewPx = xa.p2d(pxStart + dx);
        newStartMs = dateAtNewPx;
        newEndMs = origEndMs;
        // Minimum 1 day
        if (newStartMs >= newEndMs) {
            newStartMs = newEndMs - 86400000;
        }
    } else if (dragState.dragType === 'resize-right') {
        const dateAtNewPx = xa.p2d(pxEnd + dx);
        newStartMs = origStartMs;
        newEndMs = dateAtNewPx;
        // Minimum 1 day
        if (newEndMs <= newStartMs) {
            newEndMs = newStartMs + 86400000;
        }
    }
    
    // ── Parent-child constraint: children can't exceed parent boundaries ──
    // Uses pre-computed parentStart/parentEnd from the summary bar at render time
    let constraintViolation = false;
    if (!dragState.meta.isSummary && dragState.meta.parentStart && dragState.meta.parentEnd) {
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

function onDragEnd(e) {
    document.removeEventListener('mousemove', onDragMove);
    document.removeEventListener('mouseup', onDragEnd);
    document.removeEventListener('touchmove', onDragMove);
    document.removeEventListener('touchend', onDragEnd);
    hideDragTooltip();
    
    if (!dragState) return;
    
    const { origStart, origEnd, newStart, newEnd, constraintViolation, meta } = dragState;
    dragState = null;
    
    // If no change or constraint violation, cancel
    if ((origStart === newStart && origEnd === newEnd) || constraintViolation) {
        return;
    }
    
    // Show confirmation modal
    showDateChangeModal(meta, origStart, origEnd, newStart, newEnd);
}

function msToDateStr(ms) {
    const d = new Date(ms);
    return d.toISOString().split('T')[0];
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
        ? `<span style="color:#ef4444;">⚠ Adjust parent dates first</span><br>${startFmt} – ${endFmt}`
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
    
    const displayName = meta.taskName.replace(/^[▸\s]+/, '').trim();
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
            <h3>Confirm Schedule Change</h3>
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
    
    // Store change data on the modal
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
    
    const { meta, oldStart, oldEnd, newStart, newEnd } = modal._changeData;
    const recordChange = document.getElementById('modalRecordChange').checked;
    const reason = document.getElementById('modalChangeReason').value.trim();
    
    const saveBtn = document.getElementById('modalSaveBtn');
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;
    
    try {
        // Strip display prefixes from task name for API matching
        const cleanName = meta.taskName.replace(/^[▸\s]+/, '').trim();
        
        // Build milestone update payload for the existing /milestones/update endpoint
        const response = await fetch('/milestones/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_code: meta.projectCode,
                milestone: {
                    id: meta.milestoneId || '',
                    name: cleanName,
                    target_date: newEnd,
                    start_date: newStart,
                    status: meta.status || 'NOT_STARTED',
                    completion_percentage: meta.completionPct || 0,
                    parent_project: meta.resource || ''
                },
                confirmed_date_change: recordChange
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Update ganttData in-memory
            const task = ganttData.find(t =>
                t.Task === cleanName && t.Resource === meta.resource
            );
            if (task) {
                task.Start = newStart;
                task.Finish = newEnd;
            }
            
            closeDateChangeModal();
            showToast('Schedule updated successfully', 'success');
            
            // Re-render current view
            if (viewMode === 'project') {
                renderProjectRoadmap();
            } else {
                renderRoadmap();
            }
        } else {
            showToast(result.detail || 'Failed to save change', 'error');
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

// ── Toast notification ──
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
