// Data from backend
const _ganttBridge = document.getElementById("gantt-data-bridge");
const projectCode = _ganttBridge.dataset.projectCode;
const projectName = _ganttBridge.dataset.projectName;

function exportXml() {
    window.location.href = `/api/export/xml/${encodeURIComponent(projectCode)}`;
}

const ganttData = JSON.parse(_ganttBridge.dataset.ganttData);

// ── State ──
let roadmapDetailMode = 'summary';  // 'summary' or 'expanded'

// Project Roadmap state
let projectGroups = [];        // unique project group names
let selectedGroups = new Set(); // selected group names

/**
 * Get the project group for a task.
 * Uses the backend-computed ProjectGroup field which is set by Python using
 * document-order sequence tracking — guaranteed correct regardless of
 * what is stored in parent_levels or parent_project.
 */
function getProjectGroup(task) {
    return task.ProjectGroup || task.Resource || task.ProjectName || 'Unknown';
}

// ── Initialize ──
document.addEventListener('DOMContentLoaded', async function() {
    detectProjectGroups();
    await loadSavedSettings();
    renderGroupFilterItems();
    renderProjectRoadmap();
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        const groupDropdown = document.getElementById('groupFilterDropdown');
        if (!groupDropdown.contains(e.target)) closeGroupFilter();
    });
});

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
        const group = getProjectGroup(task);
        if (group) {
            groupSet.add(group);
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
        const count = ganttData.filter(t => getProjectGroup(t) === group).length;
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
    
    // Group tasks by L2 project ancestor, filter to selected groups
    const groupedTasks = {};
    ganttData.forEach((task, idx) => {
        const group = getProjectGroup(task);
        if (group && selectedGroups.has(group)) {
            if (!groupedTasks[group]) groupedTasks[group] = [];
            groupedTasks[group].push(task);
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
        
        // Summary bar label (with expand/collapse marker for expanded mode)
        const summaryLabel = isExpanded ? `▾ ${groupName}` : `▸ ${groupName}`;
        
        // ── Expanded mode: collect direct-child tasks ─────────────────────
        // Push children into yCategories BEFORE the summary bar so that in
        // Plotly's bottom-up Y axis the summary header appears at the TOP of
        // the group with task bars below it.
        let childTasksForGroup = [];
        if (isExpanded) {
            childTasksForGroup = [...tasks]
                .filter(t => t.IsDirectChild)
                .sort((a, b) => new Date(a.Start) - new Date(b.Start));
            
            // Reverse before pushing → earliest task ends up highest in yCategories
            // (last-pushed = top of Plotly's bottom-up stack) → renders below header
            [...childTasksForGroup].reverse().forEach(task => {
                const msLabel = `  ${task.Task}`;
                yCategories.push(msLabel);
            });
        }
        
        // Summary bar goes LAST → highest index → visually at the TOP of this group
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
            groupName: groupName,
            groupSize: tasks.length,
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
        
        // ── Expanded mode: add individual milestone traces ─────────────────
        // (yCategories entries were already pushed above, before the summary bar)
        if (isExpanded) {
            childTasksForGroup.forEach(task => {
                const msLabel = `  ${task.Task}`;
                
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
        
        // Load saved project group selections (for project roadmap view)
        // Only restore if ALL currently-valid groups were present in the saved list
        // (guards against stale names from a previous data shape restoring a partial view)
        if (settings.selected_project_groups && settings.selected_project_groups.length > 0) {
            const validGroups = new Set(projectGroups);
            const validSaved = settings.selected_project_groups.filter(g => validGroups.has(g));
            const allCurrentGroupsSaved = projectGroups.every(g => settings.selected_project_groups.includes(g));
            if (allCurrentGroupsSaved) {
                // Saved list covered every current group → honor any deliberate deselection
                selectedGroups = new Set(validSaved);
            } else {
                // Stale or partial saved groups → default to showing everything
                selectedGroups = new Set(projectGroups);
            }
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
    removeDragGhost();
}

function removeDragGhost() {
    const g = document.getElementById('dragGhost');
    if (g) g.remove();
}

function createDragGhost(chartDiv, meta) {
    removeDragGhost();
    const svgContainer = chartDiv.querySelector('.svg-container');
    if (!svgContainer) return null;
    const xa = chartDiv._fullLayout.xaxis;
    const ya = chartDiv._fullLayout.yaxis;
    const yPos = ya.d2p(meta.taskName);
    const xStart = xa.d2p(new Date(meta.startDate).getTime());
    const xEnd = xa.d2p(new Date(meta.endDate).getTime());
    if (isNaN(yPos) || isNaN(xStart) || isNaN(xEnd)) return null;
    const barWidth = meta.isSummary ? 28 : (meta.barWidth || 16);
    const plotLeft = xa._offset || 0;
    const plotTop = ya._offset || 0;
    const ghost = document.createElement('div');
    ghost.id = 'dragGhost';
    ghost.className = 'drag-ghost';
    const left = plotLeft + Math.min(xStart, xEnd);
    const width = Math.max(Math.abs(xEnd - xStart), 4);
    ghost.style.left = left + 'px';
    ghost.style.top = (plotTop + yPos - barWidth / 2) + 'px';
    ghost.style.width = width + 'px';
    ghost.style.height = barWidth + 'px';
    svgContainer.appendChild(ghost);
    return ghost;
}

function updateDragGhost(chartDiv, meta, newStart, newEnd, violation) {
    const ghost = document.getElementById('dragGhost');
    if (!ghost) return;
    const xa = chartDiv._fullLayout.xaxis;
    const xStart = xa.d2p(new Date(newStart).getTime());
    const xEnd = xa.d2p(new Date(newEnd).getTime());
    if (isNaN(xStart) || isNaN(xEnd)) return;
    const plotLeft = xa._offset || 0;
    ghost.style.left = (plotLeft + Math.min(xStart, xEnd)) + 'px';
    ghost.style.width = Math.max(Math.abs(xEnd - xStart), 4) + 'px';
    ghost.classList.toggle('violation', !!violation);
}

/**
 * Build drag handle overlays for each milestone bar on the chart.
 * @param {HTMLElement} chartDiv - the Plotly chart div
 * @param {Array} traceMeta - array of {taskName, startDate, endDate, projectCode, milestoneId, resource, isSummary}
 */
function setupDragHandles(chartDiv, traceMeta) {
    removeDragOverlays();
    
    // In Plotly 2.x, '.plot' is an SVG <g> element — HTML divs cannot be appended there.
    // Instead, append to the plot container div and position relative to it.
    const svgContainer = chartDiv.querySelector('.svg-container');
    if (!svgContainer) return;
    // Ensure relative positioning so absolute children are placed correctly
    svgContainer.style.position = 'relative';
    
    const xa = chartDiv._fullLayout.xaxis;
    const ya = chartDiv._fullLayout.yaxis;
    
    traceMeta.forEach(meta => {
        const yPos = ya.d2p(meta.taskName);
        const xStart = xa.d2p(new Date(meta.startDate).getTime());
        const xEnd = xa.d2p(new Date(meta.endDate).getTime());
        
        if (isNaN(yPos) || isNaN(xStart) || isNaN(xEnd)) return;
        
        const barWidth = meta.isSummary ? 28 : (meta.barWidth || 16);
        const handleWidth = 10;
        const barLeft = Math.min(xStart, xEnd);
        const barRight = Math.max(xStart, xEnd);
        const barTop = yPos - barWidth / 2;
        
        // Offset: Plotly's d2p returns coords relative to the plot area origin,
        // but we need coords relative to the svg-container div (which includes margins).
        const plotLeft = xa._offset || 0;
        const plotTop = ya._offset || 0;
        
        // Body (move handle) — covers FULL bar width so the user can grab anywhere.
        // Edges sit on top with higher z-index so the resize cursor still wins on the ends.
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'drag-handle drag-body';
        bodyDiv.style.cssText = `position:absolute; left:${plotLeft + barLeft}px; top:${plotTop + barTop}px; width:${Math.max(barRight - barLeft, 4)}px; height:${barWidth}px; cursor:move; z-index:10;`;
        const cleanLabel = meta.taskName.replace(/^[▸▾\s]+/, '');
        bodyDiv.title = meta.isSummary
            ? `Drag to reschedule entire group (${meta.groupSize || '?'} milestones): ${cleanLabel}`
            : `Drag to move: ${cleanLabel}`;
        bodyDiv.addEventListener('mousedown', e => startDrag(e, meta, 'move', chartDiv));
        bodyDiv.addEventListener('touchstart', e => startDrag(e, meta, 'move', chartDiv), {passive: false});
        svgContainer.appendChild(bodyDiv);
        dragOverlays.push(bodyDiv);
        
        // Edge resize handles — milestones only (summary bars auto-span their children;
        // resizing a summary edge would visually revert on next render).
        if (!meta.isSummary) {
            const leftDiv = document.createElement('div');
            leftDiv.className = 'drag-handle drag-edge-left';
            leftDiv.style.cssText = `position:absolute; left:${plotLeft + barLeft}px; top:${plotTop + barTop}px; width:${handleWidth}px; height:${barWidth}px; cursor:ew-resize; z-index:12;`;
            leftDiv.title = 'Drag to change start date';
            leftDiv.addEventListener('mousedown', e => startDrag(e, meta, 'resize-left', chartDiv));
            leftDiv.addEventListener('touchstart', e => startDrag(e, meta, 'resize-left', chartDiv), {passive: false});
            svgContainer.appendChild(leftDiv);
            dragOverlays.push(leftDiv);
            
            const rightDiv = document.createElement('div');
            rightDiv.className = 'drag-handle drag-edge-right';
            rightDiv.style.cssText = `position:absolute; left:${plotLeft + barRight - handleWidth}px; top:${plotTop + barTop}px; width:${handleWidth}px; height:${barWidth}px; cursor:ew-resize; z-index:12;`;
            rightDiv.title = 'Drag to change end date';
            rightDiv.addEventListener('mousedown', e => startDrag(e, meta, 'resize-right', chartDiv));
            rightDiv.addEventListener('touchstart', e => startDrag(e, meta, 'resize-right', chartDiv), {passive: false});
            svgContainer.appendChild(rightDiv);
            dragOverlays.push(rightDiv);
        }
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
    
    // Create live ghost preview overlay
    createDragGhost(chartDiv, meta);
    
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
    updateDragGhost(dragState.chartDiv, dragState.meta, dragState.newStart, dragState.newEnd, constraintViolation);
}

function onDragEnd(e) {
    document.removeEventListener('mousemove', onDragMove);
    document.removeEventListener('mouseup', onDragEnd);
    document.removeEventListener('touchmove', onDragMove);
    document.removeEventListener('touchend', onDragEnd);
    hideDragTooltip();
    removeDragGhost();
    
    if (!dragState) return;
    
    const { origStart, origEnd, newStart, newEnd, constraintViolation, meta } = dragState;
    dragState = null;
    
    // No change → silent cancel
    if (origStart === newStart && origEnd === newEnd) return;
    
    // Constraint violation → silent cancel (tooltip already warned the user)
    if (constraintViolation) {
        showSavedToast({ message: '⚠ Move blocked: child would exceed parent dates', undoable: false });
        return;
    }
    
    // Day-snap threshold: ignore drags <1 day to avoid accidental edits
    const dayDelta = Math.abs(Math.round((new Date(newStart) - new Date(origStart)) / 86400000));
    const endDelta = Math.abs(Math.round((new Date(newEnd) - new Date(origEnd)) / 86400000));
    if (dayDelta === 0 && endDelta === 0) return;
    
    // Branch by drag target type
    if (meta.isSummary) {
        // Summary body drag → shift entire group by delta_days.
        // (Edge handles aren't created on summaries, so dragType will always be 'move' here.)
        const deltaDays = Math.round((new Date(newStart) - new Date(origStart)) / 86400000);
        const groupSize = meta.groupSize || 0;
        
        // Cascade-confirmation modal only when >5 children would shift
        if (groupSize > 5) {
            if (!window.confirm(
                `Reschedule "${meta.groupName}"?\n\n` +
                `This will shift ${groupSize} milestones by ${deltaDays > 0 ? '+' : ''}${deltaDays} day(s).\n\n` +
                `Click OK to apply (a backup will be saved automatically).`
            )) return;
        }
        
        saveGroupShift(meta, deltaDays, origStart, origEnd, newStart, newEnd);
    } else {
        saveMilestoneChange(meta, origStart, origEnd, newStart, newEnd);
    }
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
    
    const displayName = meta.taskName.replace(/^[▸▾\s]+/, '').trim();
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
        const cleanName = meta.taskName.replace(/^[▸▾\s]+/, '').trim();
        
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
            const task = ganttData.find((t, idx) => {
                if (meta.milestoneId && t.MilestoneId) {
                    return t.MilestoneId === meta.milestoneId;
                }
                return t.Task === cleanName && getProjectGroup(t) === meta.resource;
            });
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

// ══════════════════════════════════════════
// OPTIMISTIC SAVE + UNDO TOAST (Asana/Monday-style)
// ══════════════════════════════════════════

let _savedToastTimer = null;

/**
 * Bottom-right toast with optional Undo button.
 * @param {object} opts {message, undoable, onUndo, durationMs}
 */
function showSavedToast(opts) {
    const { message, undoable = false, onUndo = null, durationMs = 10000 } = opts || {};
    let toast = document.getElementById('savedToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'savedToast';
        toast.className = 'toast-saved';
        document.body.appendChild(toast);
    }
    if (_savedToastTimer) { clearTimeout(_savedToastTimer); _savedToastTimer = null; }
    
    const undoBtnHtml = undoable
        ? `<button class="toast-undo" id="savedToastUndoBtn">Undo</button>`
        : '';
    toast.innerHTML = `<span class="toast-msg">${escapeHtml(message)}</span>${undoBtnHtml}`;
    toast.classList.add('show');
    
    if (undoable) {
        const btn = document.getElementById('savedToastUndoBtn');
        if (btn) {
            btn.onclick = async () => {
                btn.disabled = true;
                btn.textContent = 'Undoing…';
                try {
                    if (typeof onUndo === 'function') await onUndo();
                    toast.classList.remove('show');
                } catch (err) {
                    console.error('Undo failed:', err);
                    btn.textContent = 'Undo failed';
                }
            };
        }
    }
    
    _savedToastTimer = setTimeout(() => { toast.classList.remove('show'); }, durationMs);
}

/**
 * Optimistic save for a milestone move/resize.
 * Updates ganttData immediately, calls /milestones/update, shows Undo toast.
 */
async function saveMilestoneChange(meta, oldStart, oldEnd, newStart, newEnd) {
    const cleanName = meta.taskName.replace(/^[▸▾\s]+/, '').trim();
    
    // Optimistic update of in-memory data
    const task = ganttData.find(t => {
        if (meta.milestoneId && t.MilestoneId) return t.MilestoneId === meta.milestoneId;
        return t.Task === cleanName && getProjectGroup(t) === meta.resource;
    });
    if (!task) {
        console.warn('[gantt] saveMilestoneChange: no matching task in ganttData', {meta, cleanName});
        showSavedToast({ message: '⚠ Could not locate task in chart data — change not saved', undoable: false });
        return;
    }
    task.Start = newStart;
    task.Finish = newEnd;
    rerenderCurrentView();
    
    try {
        const res = await fetch('/milestones/update', {
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
                confirmed_date_change: true
            })
        });
        const result = await res.json();
        if (!res.ok || !result.success) throw new Error(result.detail || 'Save failed');
        
        const days = Math.round((new Date(newStart) - new Date(oldStart)) / 86400000);
        showSavedToast({
            message: `Saved · "${cleanName}" moved ${days > 0 ? '+' : ''}${days} day(s)`,
            undoable: true,
            onUndo: async () => {
                if (task) { task.Start = oldStart; task.Finish = oldEnd; }
                rerenderCurrentView();
                await fetch('/milestones/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_code: meta.projectCode,
                        milestone: {
                            id: meta.milestoneId || '',
                            name: cleanName,
                            target_date: oldEnd,
                            start_date: oldStart,
                            status: meta.status || 'NOT_STARTED',
                            completion_percentage: meta.completionPct || 0,
                            parent_project: meta.resource || ''
                        },
                        confirmed_date_change: false
                    })
                });
            }
        });
    } catch (err) {
        // Rollback optimistic change
        if (task) { task.Start = oldStart; task.Finish = oldEnd; }
        rerenderCurrentView();
        showSavedToast({ message: '❌ Save failed: ' + (err.message || err), undoable: false });
    }
}

/**
 * Optimistic save for a summary-bar group shift.
 * Shifts every milestone in ganttData for that group by deltaDays, calls
 * POST /dashboard/api/roadmap/{code}/group/shift, shows Undo toast.
 */
async function saveGroupShift(meta, deltaDays, oldStart, oldEnd, newStart, newEnd) {
    const groupName = meta.groupName || meta.resource;
    const projectCode = meta.projectCode;
    
    // Optimistic in-memory shift of every task in this group
    const shiftDate = (s, days) => {
        const d = new Date(s);
        d.setDate(d.getDate() + days);
        return d.toISOString().split('T')[0];
    };
    const tasksInGroup = ganttData.filter(t => getProjectGroup(t) === groupName);
    tasksInGroup.forEach(t => {
        if (t.Start) t.Start = shiftDate(t.Start, deltaDays);
        if (t.Finish) t.Finish = shiftDate(t.Finish, deltaDays);
    });
    rerenderCurrentView();
    
    try {
        const res = await fetch(`/dashboard/api/roadmap/${encodeURIComponent(projectCode)}/group/shift`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                group_name: groupName,
                delta_days: deltaDays,
                confirm: true
            })
        });
        const result = await res.json();
        if (!res.ok || !result.success) throw new Error(result.error || 'Save failed');
        
        showSavedToast({
            message: `Saved · "${groupName}" shifted ${deltaDays > 0 ? '+' : ''}${deltaDays} day(s) (${result.n_milestones_shifted} milestones)`,
            undoable: true,
            onUndo: async () => {
                tasksInGroup.forEach(t => {
                    if (t.Start) t.Start = shiftDate(t.Start, -deltaDays);
                    if (t.Finish) t.Finish = shiftDate(t.Finish, -deltaDays);
                });
                rerenderCurrentView();
                await fetch(`/dashboard/api/roadmap/${encodeURIComponent(projectCode)}/group/shift`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        group_name: groupName,
                        delta_days: -deltaDays,
                        confirm: true
                    })
                });
            }
        });
    } catch (err) {
        // Rollback optimistic shift
        tasksInGroup.forEach(t => {
            if (t.Start) t.Start = shiftDate(t.Start, -deltaDays);
            if (t.Finish) t.Finish = shiftDate(t.Finish, -deltaDays);
        });
        rerenderCurrentView();
        showSavedToast({ message: '❌ Group shift failed: ' + (err.message || err), undoable: false });
    }
}

function rerenderCurrentView() {
    // gantt.html is the Program Roadmap page → always renderProjectRoadmap.
    // (The portfolio renderRoadmap() relies on selectedLevel/selectedItems,
    //  which don't exist here, so calling it would silently throw and the
    //  chart would never reflect the in-memory ganttData mutation.)
    if (typeof renderProjectRoadmap === 'function') {
        renderProjectRoadmap();
    } else if (typeof renderRoadmap === 'function') {
        renderRoadmap();
    }
}
