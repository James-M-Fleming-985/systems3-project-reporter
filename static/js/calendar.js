let calendarInstance = null;
let allEvents = [];
let filteredEvents = [];
let currentEventData = null; // Store current event for actions
let _calendarEventsHash = null; // For auto-refresh polling
let _calendarPollInterval = null;
let _serverListOrder = {}; // Server-synced list sort order

// ── One-time migration: move localStorage lists to server ────────────────────
function _migrateLocalStorageListOrder() {
    try {
        const raw = localStorage.getItem('calendarListOrder');
        if (!raw) return;
        const order = JSON.parse(raw);
        if (!order || typeof order !== 'object' || Object.keys(order).length === 0) return;
        fetch('/api/calendar/list-order', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order })
        }).catch(() => {});
        localStorage.removeItem('calendarListOrder');
        _serverListOrder = order;
        console.log(`📅 Migrated list order (${Object.keys(order).length} entries) to server`);
    } catch (e) { /* ignore */ }
}

function _migrateLocalStorageAcknowledged() {
    try {
        const raw = localStorage.getItem('calendarAcknowledged');
        if (!raw) return;
        const acked = JSON.parse(raw);
        if (!Array.isArray(acked) || acked.length === 0) return;
        // Send each to server in one batch-style fire-and-forget
        acked.forEach(eventId => {
            fetch('/api/calendar/acknowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ eventId })
            }).catch(() => {});
        });
        localStorage.removeItem('calendarAcknowledged');
        console.log(`📅 Migrated ${acked.length} acknowledged events to server`);
    } catch (e) { /* ignore */ }
}

// ── Auto-refresh: poll for server-side changes every 60s ────────────────────
function _startCalendarPolling() {
    if (_calendarPollInterval) return;
    _calendarPollInterval = setInterval(async () => {
        try {
            const resp = await fetch('/api/calendar/events-hash', { cache: 'no-store' });
            if (!resp.ok) return;
            const data = await resp.json();
            if (_calendarEventsHash !== null && data.hash !== _calendarEventsHash) {
                console.log('📅 Calendar data changed on server — refreshing');
                reloadCalendarEvents();
            }
            _calendarEventsHash = data.hash;
        } catch (e) { /* ignore polling errors */ }
    }, 60000);
}

function _stopCalendarPolling() {
    if (_calendarPollInterval) {
        clearInterval(_calendarPollInterval);
        _calendarPollInterval = null;
    }
}

window.addEventListener('beforeunload', _stopCalendarPolling);

// ── Priority gradient for draggable sub-item lists ──────────────────────────
// Pastel red (#F4A0A0) at top (high priority) → pastel green (#A0D8A0) at bottom (low priority)
function getPriorityColor(index, total) {
    if (total <= 1) return 'transparent';
    const t = index / (total - 1); // 0 → 1
    const r = Math.round(244 + (160 - 244) * t); // 244 → 160
    const g = Math.round(160 + (216 - 160) * t); // 160 → 216
    const b = Math.round(160 + (160 - 160) * t); // stays 160
    return `rgb(${r}, ${g}, ${b})`;
}

function applyPriorityColors(container) {
    const rows = container.querySelectorAll('.sibling-row');
    const total = rows.length;
    rows.forEach((row, i) => {
        row.style.background = getPriorityColor(i, total);
        const pl = row.querySelector('.priority-label');
        if (pl) pl.textContent = 'P' + (i + 1);
    });
}

// Inline-edit: double-click a sub-task label to rename it
function makeSubtaskEditable(labelEl, saveCallback) {
    labelEl.addEventListener('dblclick', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (labelEl.querySelector('input')) return; // already editing
        const origText = labelEl.textContent.trim();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = origText;
        input.className = 'flex-1 text-sm px-1 py-0.5 border border-indigo-300 rounded focus:ring-1 focus:ring-indigo-500 outline-none';
        input.style.minWidth = '0';
        labelEl.textContent = '';
        labelEl.appendChild(input);
        input.focus();
        input.select();

        function finish(save) {
            const newTitle = input.value.trim();
            if (save && newTitle && newTitle !== origText) {
                labelEl.textContent = newTitle;
                saveCallback(newTitle);
            } else {
                labelEl.textContent = origText;
            }
        }
        input.addEventListener('keydown', (ke) => {
            if (ke.key === 'Enter') { ke.preventDefault(); finish(true); }
            else if (ke.key === 'Escape') { ke.preventDefault(); finish(false); }
        });
        input.addEventListener('blur', () => finish(true));
    });
}

// Generic drag-reorder for .sibling-row items inside a container
// Uses an AbortController so re-init after innerHTML clear works correctly
function initSubtaskDrag(container, onReorderDone) {
    if (container._subtaskDragAbort) container._subtaskDragAbort.abort();
    const ac = new AbortController();
    container._subtaskDragAbort = ac;
    const opts = { signal: ac.signal };
    let dragEl = null;
    // Track mousedown target so dragstart can check if user grabbed the handle
    // (dragstart e.target is the draggable row, not the child element clicked)
    let _mousedownTarget = null;
    container.addEventListener('mousedown', e => { _mousedownTarget = e.target; }, opts);
    container.addEventListener('dragstart', e => {
        const row = e.target.closest('.sibling-row');
        if (!row || !_mousedownTarget || !_mousedownTarget.closest('.subtask-drag-handle')) { e.preventDefault(); e.stopPropagation(); return; }
        dragEl = row;
        row.classList.add('subtask-dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', '');
    }, opts);
    container.addEventListener('dragover', e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const row = e.target.closest('.sibling-row');
        if (row && row !== dragEl) {
            container.querySelectorAll('.sibling-row').forEach(r => r.classList.remove('subtask-drag-over'));
            row.classList.add('subtask-drag-over');
        }
    }, opts);
    container.addEventListener('dragleave', e => {
        const row = e.target.closest('.sibling-row');
        if (row) row.classList.remove('subtask-drag-over');
    }, opts);
    container.addEventListener('drop', e => {
        e.preventDefault();
        const targetRow = e.target.closest('.sibling-row');
        if (!targetRow || !dragEl || targetRow === dragEl) return;
        // Insert dragged element before or after target based on position
        const rect = targetRow.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
            container.insertBefore(dragEl, targetRow);
        } else {
            container.insertBefore(dragEl, targetRow.nextSibling);
        }
        container.querySelectorAll('.sibling-row').forEach(r => r.classList.remove('subtask-drag-over'));
        applyPriorityColors(container);
        if (onReorderDone) onReorderDone(container);
    }, opts);
    container.addEventListener('dragend', () => {
        if (dragEl) dragEl.classList.remove('subtask-dragging');
        container.querySelectorAll('.sibling-row').forEach(r => r.classList.remove('subtask-drag-over'));
        dragEl = null;
    }, opts);
}

document.addEventListener('DOMContentLoaded', async function() {
    console.log('📅 Calendar: Initializing...');
    
    try {
        // Fetch events from API (no-store prevents browser from returning stale cached data)
        const resp = await fetch('/api/calendar/events', { cache: 'no-store' });
        const data = await resp.json();
        allEvents = data.events || [];
        
        // Acknowledged events are now filtered server-side per user.
        // Migrate any legacy localStorage data to server (one-time).
        _migrateLocalStorageAcknowledged();
        _migrateLocalStorageListOrder();

        // Fetch server-synced list order (must complete before rendering)
        try {
            const orderResp = await fetch('/api/calendar/list-order', { cache: 'no-store' });
            const orderData = await orderResp.json();
            if (orderData.order && Object.keys(orderData.order).length) _serverListOrder = orderData.order;
        } catch (e) { /* use empty order */ }

        // Events hash for polling (fire-and-forget — not needed until later)
        fetch('/api/calendar/events-hash', { cache: 'no-store' })
            .then(r => r.json())
            .then(d => { _calendarEventsHash = d.hash; })
            .catch(() => {});
        
        console.log(`📅 Calendar: Loaded ${allEvents.length} events`);
        
        // Populate program filter
        const programs = [...new Set(allEvents.map(e => e.extendedProps?.program).filter(Boolean))];
        const programSelect = document.getElementById('programFilter');
        programs.sort().forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.textContent = p.length > 40 ? p.substring(0, 37) + '...' : p;
            programSelect.appendChild(opt);
        });
        
        // Apply initial filters
        applyFilters();
        
        // Initialize FullCalendar
        const calendarEl = document.getElementById('calendar');
        const isMobile = window.innerWidth < 640;
        const validViews = ['dayGridMonth', 'timeGridWeek', 'listMonth'];
        const storedView = localStorage.getItem('calendarView');
        const defaultView = isMobile ? 'listMonth' : 'dayGridMonth';
        const initialView = (storedView && validViews.includes(storedView)) ? storedView : defaultView;
        calendarInstance = new FullCalendar.Calendar(calendarEl, {
            initialView: initialView,
            headerToolbar: isMobile
                ? { left: 'prev,next', center: 'title', right: 'listMonth,timeGridWeek' }
                : { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,listMonth' },
            handleWindowResize: true,
            windowResize: function(arg) {
                const nowMobile = window.innerWidth < 640;
                calendarInstance.setOption('headerToolbar', nowMobile
                    ? { left: 'prev,next', center: 'title', right: 'listMonth,timeGridWeek' }
                    : { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,listMonth' });
            },
            events: function(fetchInfo, successCallback, failureCallback) {
                successCallback(filteredEvents);
            },
            eventClick: function(info) {
                console.log('Event clicked:', info.event);
                info.jsEvent.preventDefault();
                // Route standalone tasks to the edit modal
                if (info.event.extendedProps?.type === 'standalone') {
                    openEditStandaloneTaskModal(info.event.extendedProps.taskId);
                } else {
                    showEventModal(info.event);
                }
            },
            dateClick: function(info) {
                openNewStandaloneTaskModal(info.dateStr);
            },
            viewDidMount: function(arg) {
                const isListView = arg.view.type === 'listMonth';
                document.getElementById('customListView').classList.toggle('active', isListView);
                document.querySelector('.fc-view-harness').style.display = isListView ? 'none' : '';
                if (isListView) renderCustomListView();
                // Persist view selection so refresh restores the same view
                localStorage.setItem('calendarView', arg.view.type);
            },
            datesSet: function(arg) {
                // Re-render custom list when navigating months
                const clv = document.getElementById('customListView');
                if (clv && clv.classList.contains('active')) renderCustomListView();
            },
            // Drag-to-reschedule: disabled on touch devices
            editable: !window.matchMedia('(pointer: coarse)').matches,
            eventAllow: function(dropInfo, draggedEvent) {
                return ['schedule', 'milestone', 'risk_review', 'standalone'].includes(draggedEvent.extendedProps?.type);
            },
            eventDragStart: function(info) {
                const t = info.event.extendedProps?.type;
                if (!['schedule', 'milestone', 'risk_review', 'standalone'].includes(t)) {
                    showToast('Only schedule, milestone, risk items, and personal tasks can be rescheduled', 'info');
                }
            },
            eventDrop: async function(info) {
                const ep = info.event.extendedProps || {};
                const newDate = info.event.startStr.split('T')[0];

                // ── Optimistic: FullCalendar already moved the element visually ──
                // Update in-memory immediately so filters/stats reflect the move
                const memIdx = allEvents.findIndex(e => e.id === info.event.id);
                if (memIdx !== -1) allEvents[memIdx].start = newDate;

                // ── Schedule item drag ──
                if (ep.type === 'schedule') {
                    const { program: prog, tableId, rowId, dateColId } = ep;
                    if (!prog || !tableId || !rowId || !dateColId) { info.revert(); return; }
                    showToast('✓ Rescheduled', 'success');
                    _fcPersistDrop(info, () => fetch(
                        `/dashboard/api/schedule/${encodeURIComponent(prog)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/reschedule`,
                        {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' },
                            body: JSON.stringify({ date_col_id: dateColId, new_date: newDate })
                        }
                    ));
                    return;
                }

                // ── Milestone drag ──
                if (ep.type === 'milestone') {
                    const ms = ep.milestone || {};
                    const projectCode = ep.programCode || ms.project;
                    if (!projectCode || !ms.name) {
                        info.revert();
                        showToast('Missing project code or milestone name', 'error');
                        return;
                    }
                    showToast('✓ Milestone rescheduled', 'success');
                    _fcPersistDrop(info, () => fetch('/milestones/update', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            project_code: projectCode,
                            milestone: {
                                id: ms.id || ms.name, name: ms.name,
                                target_date: newDate,
                                start_date: ep.startDate || ms.start_date || '',
                                status: ep.status || ms.status || 'NOT_STARTED',
                                completion_percentage: ep.completionPct || 0,
                                notes: ep.notes || '',
                                resources: ep.resources || ms.resources || '',
                                parent_project: ep.parentProject || ms.parent_project || '',
                                is_true_milestone: ms.is_true_milestone,
                                outline_level: ms.outline_level,
                                parent_levels: ms.parent_levels
                            },
                            confirmed_date_change: false
                        })
                    }));
                    return;
                }

                // ── Risk review drag ──
                if (ep.type === 'risk_review') {
                    const riskId = ep.riskId;
                    const riskProgram = ep.program;
                    if (!riskId || !riskProgram) {
                        info.revert();
                        showToast('Missing risk details for reschedule', 'error');
                        return;
                    }
                    showToast('✓ Risk review rescheduled', 'success');
                    _fcPersistDrop(info, () => fetch(
                        `/risks/reschedule/${encodeURIComponent(riskProgram)}/${encodeURIComponent(riskId)}`,
                        {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ new_date: newDate })
                        }
                    ));
                    return;
                }

                // ── Standalone task drag ──
                if (ep.type === 'standalone') {
                    const taskId = ep.taskId;
                    if (!taskId) { info.revert(); return; }
                    const oldStart = info.oldEvent.startStr.split('T')[0];
                    const oldEnd = (info.oldEvent.endStr || info.oldEvent.startStr).split('T')[0];
                    const newStart = info.event.startStr.split('T')[0];
                    const dayDelta = Math.round((new Date(newStart) - new Date(oldStart)) / 86400000);
                    const newEnd = new Date(new Date(oldEnd).getTime() + dayDelta * 86400000).toISOString().split('T')[0];
                    showToast('✓ Task rescheduled', 'success');
                    _fcPersistDrop(info, () => fetch(
                        `/api/standalone-tasks/${encodeURIComponent(taskId)}/reschedule`,
                        {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' },
                            body: JSON.stringify({ new_due_date: newEnd, new_start_date: newStart })
                        }
                    ));
                    return;
                }

                info.revert();
            },
            eventContent: function(arg) {
                const ep = arg.event.extendedProps || {};
                const sourceLabel = ep.source_label || '';
                const statusCat = ep.status_category || 'not-started';
                const badgeAbbr = { 'Milestone': 'MIL', 'Change': 'CHG', 'Schedule': 'SCH', 'Metric': 'MET', 'Risk Review': 'RSK', 'My Task': 'TSK' };
                const abbr = badgeAbbr[sourceLabel] || sourceLabel.substring(0, 3).toUpperCase();
                return {
                    html: `<div class="cal-event-inner">`
                        + `<span class="source-badge">${abbr}</span>`
                        + `<span class="event-title">${arg.event.title}</span>`
                        + `<span class="status-dot status-dot-${statusCat}"></span>`
                        + `</div>`
                };
            },
            eventDidMount: function(info) {
                const ep = info.event.extendedProps || {};
                const parts = [
                    ep.source_label || '',
                    ep.description || info.event.title,
                    ep.due_date ? 'Due: ' + ep.due_date : '',
                    ep.status_label || '',
                    ep.program || ''
                ].filter(Boolean);
                info.el.title = parts.join(' | ');
            },
            height: 'auto',
            dayMaxEvents: 4,
            navLinks: true,
            nowIndicator: true,
            weekNumbers: false,
            fixedWeekCount: false,
            eventDisplay: 'block',
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                meridiem: 'short'
            }
        });
        
        calendarInstance.render();
        
        // Show calendar, hide loading
        // NOTE: Must show container BEFORE render for correct sizing,
        // but we render first then updateSize to handle the transition
        document.getElementById('calendarLoading').style.display = 'none';
        document.getElementById('calendarContainer').style.display = 'block';
        document.getElementById('calendarStats').style.display = 'grid';
        
        // Force recalculate after container is visible
        calendarInstance.updateSize();
        
        // Restore saved legend dot colors
        const savedColors = getTypeColors();
        document.querySelectorAll('.legend-dot[data-type]').forEach(dot => {
            const t = dot.getAttribute('data-type');
            if (savedColors[t]) dot.style.background = savedColors[t];
        });

        updateStats();

        // Start polling for server-side changes (auto-refresh every 60s)
        _startCalendarPolling();
        
    } catch (error) {
        console.error('📅 Calendar error:', error);
        document.getElementById('calendarLoading').innerHTML = `
            <div class="text-red-500">
                <p class="text-lg font-bold mb-2">Error loading calendar</p>
                <p class="text-sm">${error.message}</p>
            </div>
        `;
    }
    
    // Filter event listeners
    document.getElementById('filterMilestones').addEventListener('change', refreshCalendar);
    document.getElementById('filterChanges').addEventListener('change', refreshCalendar);
    document.getElementById('filterSchedule').addEventListener('change', refreshCalendar);
    document.getElementById('filterMetrics').addEventListener('change', refreshCalendar);
    document.getElementById('filterRiskReviews').addEventListener('change', refreshCalendar);
    document.getElementById('filterStandalone').addEventListener('change', refreshCalendar);
    document.getElementById('programFilter').addEventListener('change', refreshCalendar);
    
    // Modal close handlers
    document.getElementById('closeEventModal').addEventListener('click', closeEventModal);
    document.getElementById('eventModal').addEventListener('click', function(e) {
        if (e.target === this) closeEventModal();
    });
});

// ── Custom Type Colors ──
const DEFAULT_TYPE_COLORS = {
    milestone: '#3B82F6', change: '#F59E0B', schedule: '#6366F1',
    metric_target: '#8B5CF6', risk_review: '#EF4444', standalone: '#10B981'
};
const COLOR_PALETTE = [
    '#D50000','#E67C73','#F4511E','#F6BF26','#33B679','#0B8043',
    '#039BE5','#3F51B5','#7986CB','#8E24AA','#616161'
];
function getTypeColors() {
    try {
        const stored = localStorage.getItem('calendarTypeColors');
        return stored ? { ...DEFAULT_TYPE_COLORS, ...JSON.parse(stored) } : { ...DEFAULT_TYPE_COLORS };
    } catch { return { ...DEFAULT_TYPE_COLORS }; }
}
function saveTypeColors(overrides) {
    localStorage.setItem('calendarTypeColors', JSON.stringify(overrides));
}
function getContrastColor(hex) {
    const r = parseInt(hex.substr(1, 2), 16);
    const g = parseInt(hex.substr(3, 2), 16);
    const b = parseInt(hex.substr(5, 2), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 ? '#000000' : '#FFFFFF';
}
function showColorPicker(evt, type) {
    evt.stopPropagation();
    // Remove any existing popover
    document.querySelectorAll('.color-picker-popover').forEach(el => el.remove());
    const dot = evt.currentTarget;
    const rect = dot.getBoundingClientRect();
    const pop = document.createElement('div');
    pop.className = 'color-picker-popover';
    pop.style.left = rect.left + 'px';
    pop.style.top = (rect.bottom + 6) + 'px';
    pop.style.position = 'fixed';

    const currentColors = getTypeColors();
    const storedOverrides = (() => { try { return JSON.parse(localStorage.getItem('calendarTypeColors') || '{}'); } catch { return {}; } })();

    COLOR_PALETTE.forEach(c => {
        const sw = document.createElement('div');
        sw.className = 'color-swatch' + (storedOverrides[type] === c ? ' active' : '');
        sw.style.background = c;
        sw.onclick = (e) => { e.stopPropagation(); pickTypeColor(type, c, dot, pop); };
        pop.appendChild(sw);
    });
    // Reset swatch
    const rs = document.createElement('div');
    rs.className = 'color-swatch-reset' + (!storedOverrides[type] ? ' active' : '');
    rs.textContent = '↺';
    rs.title = 'Reset to default';
    rs.onclick = (e) => { e.stopPropagation(); pickTypeColor(type, null, dot, pop); };
    pop.appendChild(rs);

    document.body.appendChild(pop);
    // Close on outside click
    setTimeout(() => {
        const closer = (e) => { if (!pop.contains(e.target)) { pop.remove(); document.removeEventListener('click', closer); } };
        document.addEventListener('click', closer);
    }, 0);
}
function pickTypeColor(type, color, dot, pop) {
    const stored = (() => { try { return JSON.parse(localStorage.getItem('calendarTypeColors') || '{}'); } catch { return {}; } })();
    if (color) { stored[type] = color; } else { delete stored[type]; }
    saveTypeColors(stored);
    // Update legend dot
    const resolved = color || DEFAULT_TYPE_COLORS[type];
    dot.style.background = resolved;
    pop.remove();
    refreshCalendar();
}

/** Background persist for FullCalendar eventDrop; reverts on failure */
async function _fcPersistDrop(info, fetchFn) {
    try {
        const resp = await Promise.race([
            fetchFn(),
            new Promise((_, reject) => setTimeout(() => reject(Object.assign(new Error('timeout'), { name: 'AbortError' })), 15000))
        ]);
        if (!resp.ok) throw new Error(`Server ${resp.status}`);
        _scheduleDeferredSync();
    } catch (err) {
        console.error('eventDrop persist error:', err);
        // Revert the in-memory update
        const memIdx = allEvents.findIndex(e => e.id === info.event.id);
        if (memIdx !== -1) allEvents[memIdx].start = info.oldEvent.startStr.split('T')[0];
        info.revert();
        const msg = err.name === 'AbortError' ? 'Request timed out — server may be restarting' : 'Could not reschedule — please try again';
        showToast(msg, 'error');
    }
}

function applyFilters() {
    const showMilestones = document.getElementById('filterMilestones').checked;
    const showChanges = document.getElementById('filterChanges').checked;
    const showSchedule = document.getElementById('filterSchedule').checked;
    const showMetrics = document.getElementById('filterMetrics').checked;
    const showRiskReviews = document.getElementById('filterRiskReviews').checked;
    const showStandalone = document.getElementById('filterStandalone').checked;
    const programFilter = document.getElementById('programFilter').value;
    
    filteredEvents = allEvents.filter(e => {
        const type = e.extendedProps?.type;
        const program = e.extendedProps?.program;
        
        // Type filter
        if (type === 'milestone' && !showMilestones) return false;
        if (type === 'change' && !showChanges) return false;
        if (type === 'schedule' && !showSchedule) return false;
        if (type === 'metric_target' && !showMetrics) return false;
        if (type === 'risk_review' && !showRiskReviews) return false;
        if (type === 'standalone' && !showStandalone) return false;
        
        // Program filter — standalone tasks have no program, so skip this filter for them
        if (programFilter !== 'all' && type !== 'standalone' && program !== programFilter) return false;
        
        return true;
    });

    // Apply custom type colors (overridden by table-level color for schedule events)
    const typeColors = getTypeColors();
    filteredEvents.forEach(e => {
        const type = e.extendedProps?.type;
        const tableColor = e.extendedProps?.tableColor;
        // Table-level color takes precedence for schedule events
        if (tableColor) {
            e.backgroundColor = tableColor;
            e.borderColor = tableColor;
            e.textColor = getContrastColor(tableColor);
        } else if (type && typeColors[type]) {
            e.backgroundColor = typeColors[type];
            e.borderColor = typeColors[type];
            e.textColor = getContrastColor(typeColors[type]);
        }
    });
}

function refreshCalendar() {
    applyFilters();
    
    if (calendarInstance) {
        calendarInstance.refetchEvents();
    }
    
    // Update custom list view if active (but not during a drag)
    const clv = document.getElementById('customListView');
    if (clv && clv.classList.contains('active')) {
        if (_clvDragInProgress) {
            _clvRenderQueued = true;
        } else {
            renderCustomListView();
        }
    }
    
    updateStats();
}

async function reloadCalendarEvents() {
    try {
        const resp = await fetch('/api/calendar/events', { cache: 'no-store' });
        const data = await resp.json();
        allEvents = data.events || [];
        
        // Diagnostic: log milestone target dates to verify server returned fresh data
        const milestoneEvents = allEvents.filter(e => e.extendedProps?.type === 'milestone');
        console.log(`📅 Reload: ${allEvents.length} events (${milestoneEvents.length} milestones)`);
        milestoneEvents.slice(0, 5).forEach(e => {
            console.log(`  → ${e.title}: start=${e.start}, targetDate=${e.extendedProps?.targetDate}`);
        });
        
        // Acknowledged events are filtered server-side — no client-side filter needed
        refreshCalendar();
    } catch (err) {
        console.error('reloadCalendarEvents error:', err);
    }
}

/** Background sync: fetches fresh events but skips list re-render if data already correct locally */
function syncEventsQuietly() {
    fetch('/api/calendar/events', { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
            allEvents = data.events || [];
            applyFilters();
            if (calendarInstance) calendarInstance.refetchEvents();
            // Only re-render list if no drag in progress
            if (!_clvDragInProgress) {
                const clv = document.getElementById('customListView');
                if (clv && clv.classList.contains('active')) renderCustomListView();
            }
            updateStats();
        })
        .catch(err => console.error('syncEventsQuietly error:', err));
}

function updateStats() {
    // Deduplicate milestones — a milestone with both Start and Finish dates
    // creates two calendar events, but should count as one milestone.
    const milestoneKeys = new Set();
    filteredEvents.filter(e => e.extendedProps?.type === 'milestone').forEach(e => {
        const key = (e.extendedProps?.programCode || '') + '|' + (e.extendedProps?.description || e.title);
        milestoneKeys.add(key);
    });
    const milestones = milestoneKeys.size;
    const changes = filteredEvents.filter(e => e.extendedProps?.type === 'change').length;
    const schedule = filteredEvents.filter(e => e.extendedProps?.type === 'schedule').length;
    const overdue = filteredEvents.filter(e => e.extendedProps?.status_category === 'overdue').length;
    const riskReviews = filteredEvents.filter(e => e.extendedProps?.type === 'risk_review').length;
    const myTasks = filteredEvents.filter(e => e.extendedProps?.type === 'standalone').length;
    
    document.getElementById('statMilestones').textContent = milestones;
    document.getElementById('statChanges').textContent = changes;
    document.getElementById('statSchedule').textContent = schedule;
    document.getElementById('statOverdue').textContent = overdue;
    document.getElementById('statRiskReviews').textContent = riskReviews;
    const myTasksEl = document.getElementById('statMyTasks');
    if (myTasksEl) myTasksEl.textContent = myTasks;
}

function showEventModal(event) {
    try {
        console.log('showEventModal called with:', event);
        // Close any open FullCalendar popovers so the modal sits on top
        document.querySelectorAll('.fc-popover').forEach(el => el.remove());
        const modal = document.getElementById('eventModal');
        const ep = event.extendedProps || {};
        const type = ep.type || 'unknown';
        
        // Store event data for actions
        currentEventData = {
            type: ep.type,
            projectCode: ep.programCode,
            milestone: ep.milestone,
            eventId: event.id,
            // Schedule-specific
            scheduleProgram: ep.program,
            tableId: ep.tableId,
            rowId: ep.rowId,
            dateColId: ep.dateColId,
            _origDueDate: ep.due_date ? ep.due_date.split('T')[0] : '',
            allDataById: {},
            // Risk-specific
            riskId: ep.riskId,
            riskProgram: ep.program,
            // For acknowledge (change/metric) – just need the event id
        };
    
    // Source-based header colors (use custom type colors + table-level override)
    const headerColors = getTypeColors();
    let modalColor = headerColors[type] || '#3B82F6';
    if (ep.tableColor) modalColor = ep.tableColor;
    document.getElementById('eventModalHeader').style.backgroundColor = modalColor;
    document.getElementById('eventModalHeader').style.color = getContrastColor(modalColor);
    
    // Type label from uniform field
    document.getElementById('eventModalType').textContent = ep.source_label || type;
    document.getElementById('eventModalTitle').textContent = event.title;
    
    // Set "Go to Program" button URL
    const goBtn = document.getElementById('goToProgramBtn');
    const typeToTabNav = {
        'milestone': 'milestones',
        'change': 'changes',
        'schedule': 'schedule',
        'metric_target': 'metrics',
        'risk_review': 'risks'
    };
    const tabNav = typeToTabNav[type] || 'milestones';
    let goBtnUrl = ep.programCode
        ? `/dashboard/${tabNav}?project=${encodeURIComponent(ep.programCode)}`
        : `/dashboard/${tabNav}`;
    if (type === 'schedule' && ep.tableId) {
        goBtnUrl += (goBtnUrl.includes('?') ? '&' : '?') + `table=${encodeURIComponent(ep.tableId)}`;
    }
    goBtn.href = goBtnUrl;
    // Label: just the tab name, concise
    const tabLabels = { 'milestone': 'Milestones', 'change': 'Changes', 'schedule': 'Schedule', 'metric_target': 'Metrics', 'risk_review': 'Risks' };
    document.getElementById('goToProgramLabel').textContent = tabLabels[type] || 'View';

    // Show/hide footer action buttons based on event type
    const deleteBtn = document.getElementById('deleteEventBtn');
    const saveBtn = document.getElementById('saveEventBtn');
    const schedDoneBtn = document.getElementById('schedDoneBtn');
    const schedSaveBtn = document.getElementById('schedSaveBtn');
    const schedDeleteBtn = document.getElementById('schedDeleteBtn');
    const acknowledgeBtn = document.getElementById('acknowledgeBtn');

    const isMilestone = ep.type === 'milestone' && ep.milestone;
    deleteBtn.classList.toggle('hidden', !isMilestone);
    saveBtn.classList.toggle('hidden', !isMilestone);
    const showDone = ep.type === 'schedule' && !!ep.rowId;
    schedDoneBtn.classList.toggle('hidden', !showDone);
    schedSaveBtn.classList.toggle('hidden', !showDone);
    schedDeleteBtn.classList.toggle('hidden', !showDone);
    if (showDone) {
        // Always reset button state so a previous "Saving…" doesn't persist
        schedDoneBtn.disabled = false;
        schedDoneBtn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg> Done`;
        schedSaveBtn.disabled = false;
        schedSaveBtn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg> Save`;
    }
    acknowledgeBtn.classList.toggle('hidden', ep.type !== 'change' && ep.type !== 'metric_target');

    const markMitigatedBtn = document.getElementById('markMitigatedBtn');
    markMitigatedBtn.classList.toggle('hidden', ep.type !== 'risk_review');
    if (ep.type === 'risk_review') {
        markMitigatedBtn.disabled = false;
        markMitigatedBtn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Mark Mitigated`;
    }
    
    // --- Build navigation URL based on event type ---
    const typeToTab = {
        'milestone': 'milestones',
        'change': 'changes',
        'schedule': 'schedule',
        'metric_target': 'metrics',
        'risk_review': 'risks'
    };
    const tab = typeToTab[type] || 'milestones';
    let navUrl = ep.programCode
        ? `/dashboard/${tab}?project=${encodeURIComponent(ep.programCode)}`
        : `/dashboard/${tab}`;
    // For schedule events, append table ID so the page opens the right table tab
    if (type === 'schedule' && ep.tableId) {
        navUrl += (navUrl.includes('?') ? '&' : '?') + `table=${encodeURIComponent(ep.tableId)}`;
    }

    // --- UNIFORM TOP SECTION (same for ALL event types) ---
    const statusCat = ep.status_category || 'not-started';
    let bodyHtml = `
        <div class="uniform-info-grid">
            <div class="info-item">
                <span class="info-label">Type</span>
                <span class="info-value">
                    <a href="${navUrl}" class="source-type-badge source-type-${type} hover:brightness-110 hover:ring-2 hover:ring-offset-1 hover:ring-blue-300 transition cursor-pointer no-underline" style="background:${modalColor}; color:${getContrastColor(modalColor)}" title="Go to ${tab} tab for this program">
                        ${ep.source_label || type} ↗
                    </a>
                </span>
            </div>
            <div class="info-item">
                <span class="info-label">Status</span>
                <span class="info-value"><span class="status-badge status-${statusCat}">${ep.status_label || 'Unknown'}</span></span>
            </div>
            <div class="info-item" style="grid-column: 1 / -1">
                <span class="info-label">Description</span>
                <span class="info-value">${(ep.description && ep.description.trim()) || event.title || 'N/A'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Due Date</span>
                <span class="info-value">${ep.due_date ? formatDate(ep.due_date) : 'N/A'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Program</span>
                <span class="info-value">
                    <a href="/dashboard/?project=${encodeURIComponent(ep.programCode || '')}" class="text-blue-600 hover:text-blue-800 hover:underline transition" title="Go to program dashboard">
                        ${ep.programName && ep.programName !== ep.programCode ? ep.programName + ' (' + ep.programCode + ')' : (ep.programName || ep.program || 'N/A')} ↗
                    </a>
                </span>
            </div>
        </div>
    `;
    
    // --- TYPE-SPECIFIC DETAILS (below the uniform section) ---
    let detailsHtml = '';
    
    if (type === 'milestone') {
        const ms = ep.milestone || {};
        const _statusOpts = ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED'];
        const _statusLabels = { NOT_STARTED: 'Not Started', IN_PROGRESS: 'In Progress', COMPLETED: 'Completed' };
        detailsHtml = `
            <div>
                <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Name</label>
                <input type="text" id="calEditName" value="${(ms.name || event.title || '').replace(/"/g, '&quot;')}" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Start Date</label>
                    <input type="date" id="calEditStartDate" value="${ep.startDate || ''}" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Target Date</label>
                    <input type="date" id="calEditTargetDate" value="${ep.targetDate || ''}" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Status</label>
                    <select id="calEditStatus" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                        ${_statusOpts.map(s => `<option value="${s}" ${(ep.status || 'NOT_STARTED') === s ? 'selected' : ''}>${_statusLabels[s]}</option>`).join('')}
                    </select>
                </div>
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Progress (%)</label>
                    <input type="number" id="calEditCompletion" min="0" max="100" value="${ep.completionPct || 0}" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
            </div>
            ${ep.level3Parent ? `<div class="level3-parent-banner"><span style="opacity:0.6;font-size:0.7rem;">▸ LEVEL 3</span>${ep.level3Parent}</div>` : ''}
            ${ep.parentProject ? `<div class="p-3 bg-blue-50 rounded-lg"><p class="text-xs text-blue-600 uppercase font-semibold">Project Group</p><p class="text-sm font-medium text-blue-800">${ep.parentProject}</p></div>` : ''}
            <div>
                <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Resources</label>
                <input type="text" id="calEditResources" value="${(ep.resources || '').replace(/"/g, '&quot;')}" placeholder="e.g., Alice; Bob" class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Owner</label>
                <input type="text" id="calEditOwner" value="${(ep.owner || ms.owner || '').replace(/"/g, '&quot;')}" placeholder="e.g., Jane Smith" class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Notes</label>
                <textarea id="calEditNotes" rows="2" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">${(ms.notes || ep.notes || '').replace(/</g, '&lt;')}</textarea>
            </div>
        `;
    } else if (type === 'change') {
        detailsHtml = `
            <div class="p-3 bg-yellow-50 rounded-lg">
                <p class="text-xs text-yellow-700 uppercase font-semibold mb-2">Date Change</p>
                <div class="flex items-center gap-3">
                    <div class="text-center">
                        <p class="text-xs text-gray-500">From</p>
                        <p class="text-sm font-bold text-red-600 line-through">${formatDate(ep.oldDate)}</p>
                    </div>
                    <svg class="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
                    <div class="text-center">
                        <p class="text-xs text-gray-500">To</p>
                        <p class="text-sm font-bold text-green-600">${formatDate(ep.newDate)}</p>
                    </div>
                </div>
            </div>
            ${ep.reason ? `<div><p class="text-xs text-gray-500 uppercase font-semibold">Reason</p><p class="text-sm text-gray-700">${ep.reason}</p></div>` : ''}
            ${ep.impact ? `<div><p class="text-xs text-gray-500 uppercase font-semibold">Impact / Contingency</p><p class="text-sm text-gray-700">${ep.impact}</p></div>` : ''}
        `;
    } else if (type === 'schedule') {
        const _schedSubTasksRaw = ep.sub_tasks || [];
        // Sort: active first, completed last
        const _schedActive = _schedSubTasksRaw.filter(s => !s.completed);
        const _schedDone = _schedSubTasksRaw.filter(s => s.completed);
        const _schedSubTasks = [..._schedActive, ..._schedDone];
        detailsHtml = `
            ${ep.tableName ? `<div><p class="text-xs text-gray-500 uppercase font-semibold">Schedule Table</p><p class="text-sm font-medium">${ep.tableName}</p></div>` : ''}
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Due Date</label>
                    <input type="date" id="schedEditDueDate" value="${ep.due_date ? ep.due_date.split('T')[0] : ''}" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">${ep.dateField || 'Date Field'}</label>
                    <p class="text-sm font-medium mt-1.5">${formatDate(event.startStr)}</p>
                </div>
            </div>
            <div>
                <label class="text-xs text-gray-500 uppercase font-semibold block mb-1">Notes</label>
                <textarea id="schedEditNotes" rows="2" class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" placeholder="Add notes…">${(ep.notes || '').replace(/</g, '&lt;')}</textarea>
            </div>
            <div>
                <p class="text-xs text-gray-500 uppercase font-semibold mb-2">Sub-Tasks</p>
                <div id="schedSubTasksContainer" class="space-y-1 mb-2">
                    ${_schedSubTasks.length === 0 ? '<p class="text-sm text-gray-400 italic">No sub-tasks yet</p>' : (() => {
                        let _activeIdx = 0;
                        const _activeCount = _schedSubTasks.filter(s => !s.completed).length;
                        return _schedSubTasks.map((st) => {
                            const isActive = !st.completed;
                            const pIdx = isActive ? _activeIdx++ : -1;
                            return `
                        <div class="sibling-row group ${st.completed ? 'is-completed' : ''}" id="st-row-${st.id}" draggable="true" data-st-id="${st.id}" data-st-notes="${(st.notes || '').replace(/"/g, '&quot;')}" style="background:${isActive ? getPriorityColor(pIdx, _activeCount) : '#F9FAFB'}">
                            <span class="subtask-drag-handle" title="Drag to reorder">⠿</span>
                            <span class="priority-label">${isActive ? 'P' + (pIdx + 1) : ''}</span>
                            <input type="checkbox" class="sched-subtask-cb w-4 h-4 text-indigo-600 rounded flex-shrink-0"
                                   data-st-id="${st.id}" ${st.completed ? 'checked' : ''}
                                   onchange="toggleScheduleSubTask(this)">
                            <label class="flex-1 text-sm cursor-pointer select-none" ondblclick="openSchedSubTaskMini('${st.id}')" title="Double-click to edit details">${st.title.replace(/</g, '&lt;')}</label>
                            <button onclick="deleteScheduleSubTask('${st.id}')" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition p-0.5" title="Remove sub-task">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                        </div>
                    `}).join('');
                    })()}
                </div>
                <div class="flex gap-2">
                    <input type="text" id="schedNewSubTask" placeholder="Add a sub-task…"
                           class="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                           onkeydown="if(event.key==='Enter'){event.preventDefault();addScheduleSubTask();}">
                    <button onclick="addScheduleSubTask()"
                            class="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition">
                        + Add
                    </button>
                </div>
            </div>
            <div id="schedAllFieldsContainer" class="p-3 bg-indigo-50 rounded-lg">
                <p class="text-xs text-indigo-600 uppercase font-semibold mb-2">All Fields</p>
                <div id="schedAllFieldsContent" class="flex items-center justify-center py-3">
                    <svg class="animate-spin h-5 w-5 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span class="ml-2 text-sm text-gray-500">Loading fields…</span>
                </div>
            </div>
        `;
        // NOTE: _loadScheduleAllFields is called AFTER innerHTML injection below
    } else if (type === 'metric_target') {
        detailsHtml = `
            <div class="grid grid-cols-2 gap-4 p-4 bg-purple-50 rounded-lg">
                <div class="text-center">
                    <p class="text-xs text-purple-600 uppercase font-semibold">Current</p>
                    <p class="text-2xl font-bold text-gray-900">${ep.currentValue ?? 'N/A'}${ep.unit ? ' ' + ep.unit : ''}</p>
                </div>
                <div class="text-center">
                    <p class="text-xs text-purple-600 uppercase font-semibold">Target</p>
                    <p class="text-2xl font-bold text-purple-700">${ep.targetValue ?? 'N/A'}${ep.unit ? ' ' + ep.unit : ''}</p>
                </div>
            </div>
            ${(ep.currentValue != null && ep.targetValue) ? `
                <div>
                    <div class="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>${Math.min(100, Math.round((ep.currentValue / ep.targetValue) * 100))}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2.5">
                        <div class="bg-purple-600 h-2.5 rounded-full" style="width: ${Math.min(100, Math.round((ep.currentValue / ep.targetValue) * 100))}%"></div>
                    </div>
                </div>
            ` : ''}
        `;
    } else if (type === 'risk_review') {
        const severityColors = {
            'critical': 'bg-purple-100 text-purple-800',
            'high': 'bg-red-100 text-red-800',
            'medium': 'bg-yellow-100 text-yellow-800',
            'low': 'bg-green-100 text-green-800'
        };
        const sevColor = severityColors[ep.severity] || 'bg-gray-100 text-gray-800';
        detailsHtml = `
            <div class="p-4 bg-red-50 rounded-lg">
                <p class="text-xs text-red-600 uppercase font-semibold mb-3">Risk Review Details</p>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <p class="text-xs text-gray-500">Risk ID</p>
                        <p class="text-sm font-bold">${ep.riskId || 'N/A'}</p>
                    </div>
                    <div>
                        <p class="text-xs text-gray-500">Severity</p>
                        <span class="px-2 py-0.5 inline-flex text-xs font-semibold rounded-full ${sevColor}">${(ep.severity || 'unknown').toUpperCase()}</span>
                    </div>
                    <div>
                        <p class="text-xs text-gray-500">Owner</p>
                        <p class="text-sm font-medium">${ep.riskOwner || 'N/A'}</p>
                    </div>
                    <div>
                        <p class="text-xs text-gray-500">Status</p>
                        <p class="text-sm font-medium">${ep.riskStatus || 'N/A'}</p>
                    </div>
                    <div>
                        <p class="text-xs text-gray-500">Review Cadence</p>
                        <p class="text-sm font-medium">${ep.cadenceLabel || ep.cadence || 'N/A'}</p>
                    </div>
                    <div>
                        <p class="text-xs text-gray-500">Review #</p>
                        <p class="text-sm font-medium">${ep.occurrence || ''}</p>
                    </div>
                </div>
                ${ep.riskDescription ? `
                <div class="mt-3 pt-3 border-t border-red-200">
                    <p class="text-xs text-gray-500 mb-1">Description</p>
                    <p class="text-sm text-gray-700">${ep.riskDescription}</p>
                </div>` : ''}
                ${ep.riskMitigations ? `
                <div class="mt-3 pt-3 border-t border-red-200">
                    <p class="text-xs text-gray-500 mb-1">Mitigations</p>
                    <p class="text-sm text-gray-700">${ep.riskMitigations}</p>
                </div>` : ''}
                <div class="mt-3 pt-3 border-t border-red-200">
                    <p class="text-xs text-gray-500 mb-1">Reschedule Review</p>
                    <div class="flex gap-2 items-center">
                        <input type="date" id="riskRescheduleDate" value="${ep.due_date ? ep.due_date.split('T')[0] : ''}"
                               class="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500">
                        <button onclick="rescheduleRiskFromModal()" id="riskRescheduleBtn"
                                class="px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition whitespace-nowrap">
                            Move
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Combine uniform section + type-specific details
    if (detailsHtml.trim()) {
        bodyHtml += `
            <div class="mt-4 pt-4 border-t border-gray-200">
                <p class="text-xs uppercase font-bold text-gray-400 mb-3">Details</p>
                <div class="space-y-3">${detailsHtml}</div>
            </div>
        `;
    }
    
    // Add sibling tasks section for milestones
    if (type === 'milestone' && ep.milestone && ep.programCode) {
        bodyHtml += `
            <div class="mt-4 pt-4 border-t border-gray-200">
                <p class="text-xs uppercase font-semibold text-gray-500 mb-2">Related Tasks ${ep.level3Parent ? '<span class="font-normal text-gray-400 normal-case">under ' + ep.level3Parent + '</span>' : ''}</p>
                <div id="siblingTasksContainer" class="space-y-1">
                    <p class="text-sm text-gray-500">Loading...</p>
                </div>
            </div>
        `;
    }
    
    document.getElementById('eventModalBody').innerHTML = bodyHtml;
    modal.classList.remove('hidden');

    // Fetch all-fields data on demand (MUST be after innerHTML injection so DOM element exists)
    if (type === 'schedule') {
        _loadScheduleAllFields(ep.program || ep.programCode, ep.tableId, ep.rowId);
    }

    // Initialize drag-reorder for schedule sub-tasks
    if (type === 'schedule') {
        const schedContainer = document.getElementById('schedSubTasksContainer');
        if (schedContainer && schedContainer.querySelectorAll('.sibling-row').length > 1) {
            initSubtaskDrag(schedContainer, (cont) => {
                const ids = [...cont.querySelectorAll('.sibling-row[data-st-id]')].map(r => r.dataset.stId);
                fetch(`/dashboard/api/schedule/${encodeURIComponent(ep.program)}/tables/${ep.tableId}/rows/${ep.rowId}/sub-tasks/reorder`, {
                    method: 'PUT', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({ order: ids })
                }).catch(err => console.error('Sub-task reorder failed:', err));
            });
        }
        // Wire up double-click-to-edit on schedule sub-task labels
        if (schedContainer) {
            schedContainer.querySelectorAll('.sibling-row label').forEach(lbl => {
                const row = lbl.closest('.sibling-row');
                const stId = row?.dataset.stId;
                if (!stId) return;
                makeSubtaskEditable(lbl, (newTitle) => {
                    const csrf = document.getElementById('csrfToken')?.value || '';
                    fetch(`/dashboard/api/schedule/${encodeURIComponent(ep.program)}/tables/${encodeURIComponent(ep.tableId)}/rows/${encodeURIComponent(ep.rowId)}/sub-tasks/${encodeURIComponent(stId)}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrf },
                        body: JSON.stringify({ title: newTitle })
                    }).then(r => { if (!r.ok) throw new Error('Save failed'); showToast('Title updated', 'success', 2000); })
                      .catch(err => { console.error('Rename sub-task failed:', err); showToast('Could not rename', 'error'); });
                });
            });
        }
    }

    // AI Chat Panel — show for milestone, risk_review, and schedule events
    const chatContainer = document.getElementById('calendarAIChatContainer');
    if ((type === 'milestone' || type === 'risk_review' || type === 'schedule') && typeof AIChatPanel !== 'undefined') {
        chatContainer.classList.remove('hidden');
        const chatContextType = type === 'risk_review' ? 'risk' : type === 'schedule' ? 'schedule' : 'milestone';
        const chatContextId = type === 'risk_review'
            ? (ep.riskId || event.id)
            : type === 'schedule'
            ? (ep.tableId || event.id)
            : (ep.milestone ? (ep.milestone.id || ep.milestone.name) : event.id);
        if (window._calendarChatPanel) {
            window._calendarChatPanel.updateContext(chatContextType, chatContextId, ep.programCode || ep.program);
        } else {
            window._calendarChatPanel = new AIChatPanel('calendarAIChatContainer', {
                contextType: chatContextType,
                contextId: chatContextId,
                projectCode: ep.programCode || ep.program,
                programName: ep.programName || ep.program || ''
            });
        }
    } else {
        chatContainer.classList.add('hidden');
    }
    
    // Load sibling tasks if this is a milestone
    if (type === 'milestone' && ep.milestone && ep.programCode) {
        loadSiblingTasks(ep.programCode, ep.milestone.id || ep.milestone.name);
    }
    } catch (error) {
        console.error('Error in showEventModal:', error);
        showToast('Could not open event details: ' + error.message, 'error');
    }
}

async function loadSiblingTasks(projectCode, milestoneId) {
    try {
        console.log(`🔍 loadSiblingTasks: code=${projectCode} id=${JSON.stringify(milestoneId)}`);
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const response = await fetch(`/api/milestones/${projectCode}/siblings/${encodeURIComponent(milestoneId)}`, { signal: controller.signal });
        clearTimeout(timeout);
        if (!response.ok) {
            throw new Error('Failed to load sibling tasks');
        }
        
        const data = await response.json();
        console.log('🔍 siblings response:', data);
        const container = document.getElementById('siblingTasksContainer');
        
        if (!container) return;
        
        if (!data.siblings || data.siblings.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-500 italic">No related tasks found</p>';
            return;
        }
        
        // Render sibling tasks with checkboxes — active first, completed last
        let html = '';
        const sortedSibs = [...data.siblings].sort((a, b) => {
            const ac = a.status === 'COMPLETED' || Number(a.completion_percentage) === 100;
            const bc = b.status === 'COMPLETED' || Number(b.completion_percentage) === 100;
            return ac - bc;
        });
        const activeCount = sortedSibs.filter(s => !(s.status === 'COMPLETED' || Number(s.completion_percentage) === 100)).length;
        let activeIdx = 0;
        sortedSibs.forEach((sibling) => {
            const isCompleted = sibling.status === 'COMPLETED' || Number(sibling.completion_percentage) === 100;
            const checkboxId = `sibling-${sibling.id}`;
            const icon = sibling.is_milestone ? '🎯' : '📋';
            const pIdx = isCompleted ? -1 : activeIdx++;
            
            html += `
                <div class="sibling-row group ${isCompleted ? 'is-completed' : ''}" id="row-${checkboxId}" draggable="true" data-sib-id="${sibling.id}" style="background:${isCompleted ? '#F9FAFB' : getPriorityColor(pIdx, activeCount)}">
                    <span class="subtask-drag-handle" title="Drag to reorder">⠿</span>
                    <span class="priority-label">${isCompleted ? '' : 'P' + (pIdx + 1)}</span>
                    <input type="checkbox" 
                           id="${checkboxId}" 
                           class="sibling-checkbox w-4 h-4 text-indigo-600 rounded flex-shrink-0"
                           data-task-id="${sibling.id}"
                           data-project-code="${projectCode}"
                           ${isCompleted ? 'checked' : ''}
                           onchange="updateTaskStatus(this)">
                    <label for="${checkboxId}" class="flex-1 text-sm cursor-pointer select-none flex items-center gap-2">
                        <span>${icon} ${sibling.name}</span>
                        ${sibling.recurrence_occurrence ? `<span class="text-xs bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">&#x1F504; ${sibling.recurrence_occurrence}</span>` : ''}
                        ${sibling.target_date ? `<span class="text-xs text-gray-400">${sibling.target_date}</span>` : ''}
                    </label>
                    <span class="text-xs px-2 py-0.5 rounded-full ${isCompleted ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}" id="badge-${checkboxId}">${isCompleted ? 'Done' : sibling.completion_percentage + '%'}</span>
                </div>
            `;
        });
        
        container.innerHTML = html;

        // Init drag-reorder for siblings
        if (data.siblings.length > 1) {
            initSubtaskDrag(container, (cont) => {
                const ids = [...cont.querySelectorAll('.sibling-row[data-sib-id]')].map(r => r.dataset.sibId);
                fetch(`/api/milestones/${encodeURIComponent(projectCode)}/siblings/reorder`, {
                    method: 'PUT', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({ order: ids })
                }).catch(err => console.error('Sibling reorder failed:', err));
            });
        }
    } catch (error) {
        console.error('Error loading sibling tasks:', error);
        const container = document.getElementById('siblingTasksContainer');
        if (container) {
            container.innerHTML = '<p class="text-sm text-red-500">Could not load related tasks</p>';
        }
    }
}

async function updateTaskStatus(checkbox) {
    const taskId = checkbox.dataset.taskId;
    const projectCode = checkbox.dataset.projectCode;
    const shouldComplete = checkbox.checked;
    const csrfToken = document.getElementById('csrfToken')?.value || '';
    const checkboxId = checkbox.id;
    const row = document.getElementById(`row-${checkboxId}`);
    const badge = document.getElementById(`badge-${checkboxId}`);

    // Optimistic UI update
    checkbox.disabled = true;
    if (row) row.style.opacity = '0.6';

    try {
        const response = await fetch('/api/milestones/update-task-status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-csrf-token': csrfToken
            },
            body: JSON.stringify({
                project_code: projectCode,
                task_id: taskId,
                status: shouldComplete ? 'COMPLETED' : 'IN_PROGRESS'
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const result = await response.json();
        if (!result.success) {
            throw new Error(result.message || 'Update failed');
        }

        // Confirm UI updates
        if (row) {
            row.style.opacity = '1';
            if (shouldComplete) {
                row.classList.add('is-completed');
            } else {
                row.classList.remove('is-completed');
            }
        }
        if (badge) {
            if (shouldComplete) {
                badge.textContent = 'Done';
                badge.className = 'text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700';
            } else {
                badge.textContent = 'In Progress';
                badge.className = 'text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700';
            }
        }

        if (result.all_tasks_complete && result.milestone_name) {
            // All sibling tasks done — milestone auto-completed
            showMilestoneAchieved(result.milestone_name);
        } else {
            // Reorder: move completed items to bottom
            reorderSubTaskRows(document.getElementById('siblingTasksContainer'));
            showToast(shouldComplete ? 'Task marked complete ✓' : 'Task reopened', 'success');
            refreshCalendar();
            _scheduleDeferredSync();
        }

    } catch (error) {
        console.error('Error updating task status:', error);
        checkbox.checked = !shouldComplete;
        if (row) row.style.opacity = '1';
        showToast('Could not update task — please try again', 'error');
    } finally {
        checkbox.disabled = false;
    }
}

function showMilestoneAchieved(milestoneName) {
    // Capture event ID before modifying DOM
    const eventId = currentEventData?.eventId;

    // Replace the modal body content with a celebration banner
    const body = document.getElementById('eventModalBody');
    if (body) {
        body.innerHTML = `
            <div class="flex flex-col items-center justify-center py-8 gap-4 text-center">
                <div style="font-size:3rem;line-height:1">🎉</div>
                <h3 class="text-xl font-bold text-green-700">Milestone Achieved!</h3>
                <p class="text-gray-600 text-sm max-w-xs">
                    <span class="font-semibold text-gray-800">${milestoneName}</span>
                    has been marked complete — all tasks done.
                </p>
                <div class="w-full bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700 font-medium">
                    ✓ Removing from calendar…
                </div>
            </div>`;
    }

    // Immediately remove from in-memory events for instant UI update
    if (eventId) {
        allEvents = allEvents.filter(e => e.id !== eventId);
        if (calendarInstance) {
            const fcEvent = calendarInstance.getEventById(eventId);
            if (fcEvent) fcEvent.remove();
        }
    }

    // After a short celebration, close and refresh
    setTimeout(() => {
        closeEventModal();
        refreshCalendar();
        _scheduleDeferredSync(500);
        showToast(`🎉 "${milestoneName}" complete!`, 'success', 5000);
    }, 2800);
}

async function _loadScheduleAllFields(program, tableId, rowId) {
    const container = document.getElementById('schedAllFieldsContent');
    if (!container || !program || !tableId || !rowId) {
        if (container) container.innerHTML = '<p class="text-sm text-gray-400 italic">No field data available</p>';
        return;
    }
    try {
        const resp = await fetch(`/api/calendar/schedule-event-detail?program=${encodeURIComponent(program)}&tableId=${encodeURIComponent(tableId)}&rowId=${encodeURIComponent(rowId)}`);
        if (!resp.ok) throw new Error('Failed to load');
        const data = await resp.json();
        const allDataById = data.allDataById || {};
        // Store on currentEventData for save flow
        if (currentEventData) currentEventData.allDataById = allDataById;
        if (Object.keys(allDataById).length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-400 italic">No fields</p>';
            return;
        }
        container.className = 'py-1';
        container.innerHTML = '<div class="space-y-3">' + Object.entries(allDataById).map(([colId, col]) => {
            const isDate = col.type === 'date' || /^\d{4}-\d{2}-\d{2}/.test(col.value || '');
            const safeVal = (col.value || '').replace(/"/g, '&quot;');
            const inputType = isDate ? 'date' : 'text';
            const inputVal = isDate ? (col.value || '').split('T')[0] : safeVal;
            return `<div>
                <label class="text-gray-500 text-xs uppercase font-semibold block mb-1">${col.header}</label>
                <input type="${inputType}" data-col-id="${colId}" data-orig-value="${safeVal}" value="${inputVal}"
                       class="schedFieldInput w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white">
            </div>`;
        }).join('') + '</div>';
    } catch (e) {
        container.innerHTML = '<p class="text-sm text-red-400 italic">Failed to load fields</p>';
    }
}

function closeEventModal() {
    document.getElementById('eventModal').classList.add('hidden');
    currentEventData = null;
}

function editEventFromCalendar() {
    // No-op — handled by the 'Open in Milestones Tab' link in the modal footer.
}

async function markScheduleDone() {
    if (!currentEventData || !currentEventData.scheduleProgram || !currentEventData.tableId || !currentEventData.rowId) {
        showToast('Cannot determine schedule item to complete', 'error');
        return;
    }
    if (!confirm('Mark this schedule item as complete? This cannot be undone from the calendar.')) return;
    const { scheduleProgram, tableId, rowId, eventId } = currentEventData;

    // ── Optimistic: remove immediately and close modal ──
    allEvents = allEvents.filter(e => e.id !== eventId);
    if (calendarInstance) {
        const fcEvent = calendarInstance.getEventById(eventId);
        if (fcEvent) fcEvent.remove();
    }
    closeEventModal();
    showToast('✓ Schedule item marked complete', 'success');
    applyFilters();

    // ── Persist in background ──
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/complete`,
            { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' }, signal: controller.signal }
        );
        clearTimeout(timeout);
        if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
        _scheduleDeferredSync();
    } catch (err) {
        console.error('markScheduleDone error:', err);
        const msg = err.name === 'AbortError' ? 'Request timed out — server may be restarting' : 'Could not mark as done — please try again';
        showToast(msg, 'error');
        // Revert: re-fetch all events
        await reloadCalendarEvents();
    }
}

async function deleteScheduleEvent() {
    if (!currentEventData || !currentEventData.scheduleProgram || !currentEventData.tableId || !currentEventData.rowId) {
        showToast('Cannot determine schedule item to delete', 'error');
        return;
    }
    const { scheduleProgram, tableId, rowId, eventId } = currentEventData;
    const title = currentEventData.description || currentEventData.title || 'this item';
    const confirmed = await showConfirm(`Delete "${title}" from the schedule? This cannot be undone.`);
    if (!confirmed) return;

    const btn = document.getElementById('schedDeleteBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = `<svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Deleting…`; }

    // Optimistic removal
    allEvents = allEvents.filter(e => {
        // Remove all events from this row (may have multiple date columns)
        const ep = e.extendedProps || {};
        return !(ep.type === 'schedule' && ep.program === scheduleProgram && ep.tableId === tableId && ep.rowId === rowId);
    });
    if (calendarInstance) {
        const fcEvent = calendarInstance.getEventById(eventId);
        if (fcEvent) fcEvent.remove();
    }
    closeEventModal();
    refreshCalendar();
    applyFilters();

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}`,
            { method: 'DELETE', signal: controller.signal, headers: { 'x-csrf-token': csrfToken } }
        );
        clearTimeout(timeout);
        if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
        showToast('Schedule item deleted', 'success');
        _scheduleDeferredSync();
    } catch (err) {
        console.error('deleteScheduleEvent error:', err);
        const msg = err.name === 'AbortError' ? 'Request timed out — please try again' : 'Could not delete — please try again';
        showToast(msg, 'error');
        await reloadCalendarEvents();
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg> Delete`; }
    }
}

async function saveScheduleFromCalendar() {
    if (!currentEventData || !currentEventData.scheduleProgram || !currentEventData.tableId || !currentEventData.rowId) {
        showToast('Cannot determine schedule item to save', 'error');
        return;
    }
    const { scheduleProgram, tableId, rowId, dateColId, eventId } = currentEventData;
    const csrfToken = document.getElementById('csrfToken')?.value || '';
    const btn = document.getElementById('schedSaveBtn');
    const saveBtnOriginal = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = `<svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Saving…`; }

    try {
        const newNotes = document.getElementById('schedEditNotes')?.value || '';
        const newDate = document.getElementById('schedEditDueDate')?.value || '';
        const origDate = currentEventData._origDueDate || '';

        // Build parallel save promises (independent operations run concurrently)
        const saves = [];
        const abortCtrl = new AbortController();
        const abortTimer = setTimeout(() => abortCtrl.abort(), 15000);

        // 1. Save notes
        saves.push(
            fetch(
                `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/notes`,
                { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken }, body: JSON.stringify({ notes: newNotes }), signal: abortCtrl.signal }
            ).then(r => { if (!r.ok) throw new Error('Failed to save notes'); })
        );

        // 2. Reschedule date if changed
        if (newDate && newDate !== origDate && dateColId) {
            saves.push(
                fetch(
                    `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/reschedule`,
                    { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken }, body: JSON.stringify({ date_col_id: dateColId, new_date: newDate }), signal: abortCtrl.signal }
                ).then(r => { if (!r.ok) throw new Error('Failed to update date'); })
            );
        }

        // 3. Save any changed "All Fields" cell values
        const fieldInputs = document.querySelectorAll('.schedFieldInput');
        const cellUpdates = {};
        fieldInputs.forEach(input => {
            const colId = input.dataset.colId;
            const origVal = input.dataset.origValue || '';
            const newVal = input.value || '';
            if (newVal !== origVal) {
                cellUpdates[colId] = newVal;
            }
        });
        if (Object.keys(cellUpdates).length > 0) {
            saves.push(
                fetch(
                    `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/cells`,
                    { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken }, body: JSON.stringify({ updates: cellUpdates }), signal: abortCtrl.signal }
                ).then(r => { if (!r.ok) throw new Error('Failed to update fields'); })
            );
        }

        await Promise.all(saves);
        clearTimeout(abortTimer);

        closeEventModal();
        showToast('Schedule item saved', 'success');

        // Optimistic: update in-memory event then deferred sync
        const evtIdx = allEvents.findIndex(e => e.id === eventId);
        if (evtIdx !== -1) {
            if (newDate && newDate !== origDate) allEvents[evtIdx].start = newDate;
        }
        refreshCalendar();
        _scheduleDeferredSync();

        // Navigate calendar to the new date so the user sees the pill
        if (newDate && newDate !== origDate && calendarInstance) {
            calendarInstance.gotoDate(newDate);
        }
    } catch (err) {
        console.error('saveScheduleFromCalendar error:', err);
        showToast('Could not save: ' + err.message, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = saveBtnOriginal; }
    }
}

async function toggleScheduleSubTask(checkbox) {
    if (!currentEventData) return;
    const { scheduleProgram, tableId, rowId } = currentEventData;
    const stId = checkbox.dataset.stId;
    const completed = checkbox.checked;
    const csrfToken = document.getElementById('csrfToken')?.value || '';
    const row = document.getElementById(`st-row-${stId}`);

    checkbox.disabled = true;
    if (row) row.style.opacity = '0.6';

    try {
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/sub-tasks/${encodeURIComponent(stId)}`,
            { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken }, body: JSON.stringify({ completed }) }
        );
        if (!resp.ok) throw new Error('Update failed');
        if (row) {
            row.style.opacity = '1';
            row.classList.toggle('is-completed', completed);
        }

        // Update in-memory data so re-opening modal shows correct state
        const eventId = currentEventData.eventId;
        if (eventId) {
            const cached = allEvents.find(e => e.id === eventId);
            if (cached && cached.extendedProps?.sub_tasks) {
                const st = cached.extendedProps.sub_tasks.find(s => s.id === stId);
                if (st) st.completed = completed;
            }
            const fcEvent = calendarInstance?.getEventById(eventId);
            if (fcEvent) {
                const fcSubs = (fcEvent.extendedProps.sub_tasks || []).map(s =>
                    s.id === stId ? { ...s, completed } : s
                );
                fcEvent.setExtendedProp('sub_tasks', fcSubs);
            }
        }

        // Reorder: move completed items to bottom
        reorderSubTaskRows(document.getElementById('schedSubTasksContainer'));

        showToast(completed ? 'Sub-task completed ✓' : 'Sub-task reopened', 'success');
    } catch (err) {
        console.error('toggleScheduleSubTask error:', err);
        checkbox.checked = !completed;
        if (row) row.style.opacity = '1';
        showToast('Could not update sub-task', 'error');
    } finally {
        checkbox.disabled = false;
    }
}

/** Move completed .sibling-row items to the bottom, re-number active P-labels */
function reorderSubTaskRows(container) {
    if (!container) return;
    const rows = [...container.querySelectorAll('.sibling-row')];
    const active = rows.filter(r => !r.classList.contains('is-completed'));
    const done = rows.filter(r => r.classList.contains('is-completed'));
    // Re-number priority labels on active items only
    active.forEach((r, i) => {
        const lbl = r.querySelector('.priority-label');
        if (lbl) lbl.textContent = `P${i + 1}`;
        r.style.background = getPriorityColor(i, active.length);
    });
    // Append in order: active first, then completed
    [...active, ...done].forEach(r => container.appendChild(r));
}

async function addScheduleSubTask() {
    if (!currentEventData) return;
    const { scheduleProgram, tableId, rowId } = currentEventData;
    const input = document.getElementById('schedNewSubTask');
    const title = (input?.value || '').trim();
    if (!title) return;
    const csrfToken = document.getElementById('csrfToken')?.value || '';

    input.disabled = true;
    try {
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/sub-tasks`,
            { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken }, body: JSON.stringify({ title }) }
        );
        if (!resp.ok) throw new Error('Add failed');
        const data = await resp.json();
        const st = data.sub_task;

        // Append to DOM
        const container = document.getElementById('schedSubTasksContainer');
        if (container) {
            // Remove the "No sub-tasks yet" placeholder if present
            const placeholder = container.querySelector('p.italic');
            if (placeholder) placeholder.remove();

            const div = document.createElement('div');
            div.className = 'sibling-row group';
            div.id = `st-row-${st.id}`;
            div.draggable = true;
            div.dataset.stId = st.id;
            div.dataset.stNotes = '';
            div.innerHTML = `
                <span class="subtask-drag-handle" title="Drag to reorder">⠿</span>
                <span class="priority-label"></span>
                <input type="checkbox" class="sched-subtask-cb w-4 h-4 text-indigo-600 rounded flex-shrink-0"
                       data-st-id="${st.id}"
                       onchange="toggleScheduleSubTask(this)">
                <label class="flex-1 text-sm cursor-pointer select-none" ondblclick="openSchedSubTaskMini('${st.id}')" title="Double-click to edit details">${st.title.replace(/</g, '&lt;')}</label>
                <button onclick="deleteScheduleSubTask('${st.id}')" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition p-0.5" title="Remove sub-task">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
            `;
            container.appendChild(div);

            // Wire up double-click to open mini modal on the new sub-task label
            const lbl = div.querySelector('label');
            if (lbl) {
                lbl.ondblclick = () => openSchedSubTaskMini(st.id);
                lbl.title = 'Double-click to edit details';
            }

            // Re-apply gradient colors and re-init drag
            applyPriorityColors(container);
            if (container.querySelectorAll('.sibling-row').length > 1) {
                initSubtaskDrag(container, (cont) => {
                    const ids = [...cont.querySelectorAll('.sibling-row[data-st-id]')].map(r => r.dataset.stId);
                    fetch(`/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/sub-tasks/reorder`, {
                        method: 'PUT', headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({ order: ids })
                    }).catch(err => console.error('Sub-task reorder failed:', err));
                });
            }
        }
        input.value = '';
        showToast('Sub-task added', 'success');
    } catch (err) {
        console.error('addScheduleSubTask error:', err);
        showToast('Could not add sub-task', 'error');
    } finally {
        input.disabled = false;
        input.focus();
    }
}

async function deleteScheduleSubTask(stId) {
    if (!currentEventData) return;
    const { scheduleProgram, tableId, rowId } = currentEventData;
    const csrfToken = document.getElementById('csrfToken')?.value || '';
    const row = document.getElementById(`st-row-${stId}`);
    if (row) row.style.opacity = '0.4';

    try {
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(scheduleProgram)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/sub-tasks/${encodeURIComponent(stId)}`,
            { method: 'DELETE', headers: { 'x-csrf-token': csrfToken } }
        );
        if (!resp.ok) throw new Error('Delete failed');
        if (row) row.remove();

        // If no sub-tasks left, show placeholder
        const container = document.getElementById('schedSubTasksContainer');
        if (container && container.children.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-400 italic">No sub-tasks yet</p>';
        }
        showToast('Sub-task removed', 'success');
    } catch (err) {
        console.error('deleteScheduleSubTask error:', err);
        if (row) row.style.opacity = '1';
        showToast('Could not remove sub-task', 'error');
    }
}

// ── Sub-Task Mini Modal ──────────────────────────────────────────────────────
let _miniModalContext = null; // { source: 'schedule'|'standalone', stId, program, tableId, rowId, taskId }
let _miniModalScheduleData = null; // cached programs/tables from API

function openSchedSubTaskMini(stId) {
    if (!currentEventData) return;
    const row = document.getElementById(`st-row-${stId}`);
    const title = row?.querySelector('label')?.textContent || '';
    const notes = row?.dataset?.stNotes || '';
    openSubTaskMiniModal(stId, title, notes, 'schedule', {
        program: currentEventData.scheduleProgram,
        tableId: currentEventData.tableId,
        rowId: currentEventData.rowId
    });
}

function openSubTaskMiniModal(stId, title, notes, source, ctx) {
    _miniModalContext = { stId, source, ...ctx };
    document.getElementById('stMiniTitleInput').value = title || '';
    document.getElementById('stMiniNotes').value = notes || '';
    document.getElementById('stMiniTitle').textContent = title || 'Sub-Task Detail';
    // Reset move selects
    document.getElementById('stMiniMoveDest').value = '';
    document.getElementById('stMiniMoveProgram').classList.add('hidden');
    document.getElementById('stMiniMoveTable').classList.add('hidden');
    document.getElementById('stMiniMoveRow').classList.add('hidden');
    document.getElementById('stMiniMoveTask').classList.add('hidden');
    document.getElementById('stMiniSaveBtn').disabled = false;
    document.getElementById('subTaskMiniModal').classList.remove('hidden');
}

function closeSubTaskMiniModal() {
    document.getElementById('subTaskMiniModal').classList.add('hidden');
    _miniModalContext = null;
}

async function onMiniMoveDestChange() {
    const rawDest = document.getElementById('stMiniMoveDest').value;
    const dest = rawDest.replace('copy_', ''); // Normalize: copy_schedule → schedule
    const progSel = document.getElementById('stMiniMoveProgram');
    const tableSel = document.getElementById('stMiniMoveTable');
    const rowSel = document.getElementById('stMiniMoveRow');
    const taskSel = document.getElementById('stMiniMoveTask');

    progSel.classList.add('hidden'); tableSel.classList.add('hidden');
    rowSel.classList.add('hidden'); taskSel.classList.add('hidden');

    if (dest === 'schedule') {
        // Load programs + tables
        if (!_miniModalScheduleData) {
            try {
                const resp = await fetch('/dashboard/api/schedule/all-programs/tables');
                _miniModalScheduleData = (await resp.json()).programs || [];
            } catch (e) { _miniModalScheduleData = []; }
        }
        progSel.innerHTML = '<option value="">Select program…</option>' +
            _miniModalScheduleData.map(p => `<option value="${p.project_name}">${p.project_name}</option>`).join('');
        progSel.classList.remove('hidden');
    } else if (dest === 'standalone') {
        try {
            const resp = await fetch('/api/standalone-tasks');
            const tasks = (await resp.json()).tasks || [];
            taskSel.innerHTML = '<option value="">Select task…</option>' +
                tasks.map(t => `<option value="${t.id}">${(t.title || t.name || t.id).replace(/</g, '&lt;')}</option>`).join('');
            taskSel.classList.remove('hidden');
        } catch (e) {
            taskSel.innerHTML = '<option value="">Error loading tasks</option>';
            taskSel.classList.remove('hidden');
        }
    }
}

function onMiniMoveProgramChange() {
    const prog = document.getElementById('stMiniMoveProgram').value;
    const tableSel = document.getElementById('stMiniMoveTable');
    const rowSel = document.getElementById('stMiniMoveRow');
    tableSel.classList.add('hidden'); rowSel.classList.add('hidden');
    if (!prog || !_miniModalScheduleData) return;
    const p = _miniModalScheduleData.find(x => x.project_name === prog);
    if (!p) return;
    tableSel.innerHTML = '<option value="">Select table…</option>' +
        p.tables.map(t => `<option value="${t.id}">${t.name} (${t.row_count} rows)</option>`).join('');
    tableSel.classList.remove('hidden');
}

async function onMiniMoveTableChange() {
    const prog = document.getElementById('stMiniMoveProgram').value;
    const tableId = document.getElementById('stMiniMoveTable').value;
    const rowSel = document.getElementById('stMiniMoveRow');
    rowSel.classList.add('hidden');
    if (!prog || !tableId) return;
    try {
        const resp = await fetch(`/dashboard/api/schedule/${encodeURIComponent(prog)}/tables/${encodeURIComponent(tableId)}`);
        const table = await resp.json();
        const rows = table.rows || [];
        const cols = table.columns || [];
        const titleKeywords = ['task', 'activity', 'item', 'name', 'description', 'action'];
        const titleCol = cols.find(c => c.type === 'text' && titleKeywords.some(k => (c.header || '').toLowerCase().includes(k)))
                       || cols.find(c => c.type === 'text');
        const titleColId = titleCol ? titleCol.id : null;
        rowSel.innerHTML = '<option value="">Select row…</option>' +
            rows.map(r => {
                const label = (titleColId && r.data?.[titleColId]) || r.id;
                return `<option value="${r.id}">${String(label).replace(/</g, '&lt;')}</option>`;
            }).join('');
        rowSel.classList.remove('hidden');
    } catch (e) {
        rowSel.innerHTML = '<option value="">Error loading rows</option>';
        rowSel.classList.remove('hidden');
    }
}

async function saveSubTaskMiniModal() {
    if (!_miniModalContext) return;
    const ctx = _miniModalContext;
    const title = document.getElementById('stMiniTitleInput').value.trim();
    const notes = document.getElementById('stMiniNotes').value.trim();
    const moveDest = document.getElementById('stMiniMoveDest').value;
    const isCopy = moveDest.startsWith('copy_');
    const destType = moveDest.replace('copy_', ''); // normalize
    const csrfToken = document.getElementById('csrfToken')?.value || '';
    const saveBtn = document.getElementById('stMiniSaveBtn');
    saveBtn.disabled = true;

    try {
        // 1. Save title + notes to current location
        if (ctx.source === 'schedule') {
            await fetch(
                `/dashboard/api/schedule/${encodeURIComponent(ctx.program)}/tables/${encodeURIComponent(ctx.tableId)}/rows/${encodeURIComponent(ctx.rowId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
                  body: JSON.stringify({ title, notes }) }
            );
        } else if (ctx.source === 'standalone') {
            await fetch(
                `/api/standalone-tasks/${encodeURIComponent(ctx.taskId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
                  body: JSON.stringify({ title, notes }) }
            );
        }

        // Update in-memory data for schedule sub-tasks
        if (ctx.source === 'schedule' && currentEventData?.eventId) {
            const cached = allEvents.find(e => e.id === currentEventData.eventId);
            if (cached?.extendedProps?.sub_tasks) {
                const st = cached.extendedProps.sub_tasks.find(s => s.id === ctx.stId);
                if (st) { st.title = title; st.notes = notes; }
            }
            const fcEvent = calendarInstance?.getEventById(currentEventData.eventId);
            if (fcEvent) {
                const fcSubs = (fcEvent.extendedProps.sub_tasks || []).map(s =>
                    s.id === ctx.stId ? { ...s, title, notes } : s
                );
                fcEvent.setExtendedProp('sub_tasks', fcSubs);
            }
        }

        // Update DOM label and notes data attribute
        const row = document.getElementById(`st-row-${ctx.stId}`);
        if (row) {
            const lbl = row.querySelector('label');
            if (lbl) lbl.textContent = title;
            row.dataset.stNotes = notes;
        }

        // 2. Handle move/copy if requested
        if (destType === 'schedule') {
            const destProg = document.getElementById('stMiniMoveProgram').value;
            const destTable = document.getElementById('stMiniMoveTable').value;
            const destRow = document.getElementById('stMiniMoveRow').value;
            if (!destProg || !destTable || !destRow) {
                showToast('Please select a destination row', 'error');
                saveBtn.disabled = false;
                return;
            }
            // Create on destination (include notes)
            const addResp = await fetch(
                `/dashboard/api/schedule/${encodeURIComponent(destProg)}/tables/${encodeURIComponent(destTable)}/rows/${encodeURIComponent(destRow)}/sub-tasks`,
                { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
                  body: JSON.stringify({ title, notes }) }
            );
            if (!addResp.ok) throw new Error('Failed to create on destination');

            if (!isCopy) {
                // Delete from source (move only)
                if (ctx.source === 'schedule') {
                    await fetch(
                        `/dashboard/api/schedule/${encodeURIComponent(ctx.program)}/tables/${encodeURIComponent(ctx.tableId)}/rows/${encodeURIComponent(ctx.rowId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                        { method: 'DELETE', headers: { 'x-csrf-token': csrfToken } }
                    );
                } else if (ctx.source === 'standalone') {
                    await fetch(
                        `/api/standalone-tasks/${encodeURIComponent(ctx.taskId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                        { method: 'DELETE', headers: { 'x-csrf-token': csrfToken } }
                    );
                }
                if (row) row.remove();
            }
            showToast(`${isCopy ? 'Copied' : 'Moved'} "${title}" to schedule row`, 'success');
        } else if (destType === 'standalone') {
            const destTask = document.getElementById('stMiniMoveTask').value;
            if (!destTask) {
                showToast('Please select a destination task', 'error');
                saveBtn.disabled = false;
                return;
            }
            // Create on destination (include notes)
            const addResp = await fetch(
                `/api/standalone-tasks/${encodeURIComponent(destTask)}/sub-tasks`,
                { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
                  body: JSON.stringify({ title, notes }) }
            );
            if (!addResp.ok) throw new Error('Failed to create on destination');

            if (!isCopy) {
                // Delete from source (move only)
                if (ctx.source === 'schedule') {
                    await fetch(
                        `/dashboard/api/schedule/${encodeURIComponent(ctx.program)}/tables/${encodeURIComponent(ctx.tableId)}/rows/${encodeURIComponent(ctx.rowId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                        { method: 'DELETE', headers: { 'x-csrf-token': csrfToken } }
                    );
                } else if (ctx.source === 'standalone') {
                    await fetch(
                        `/api/standalone-tasks/${encodeURIComponent(ctx.taskId)}/sub-tasks/${encodeURIComponent(ctx.stId)}`,
                        { method: 'DELETE', headers: { 'x-csrf-token': csrfToken } }
                    );
                }
                if (row) row.remove();
            }
            showToast(`${isCopy ? 'Copied' : 'Moved'} "${title}" to standalone task`, 'success');
        } else {
            showToast('Sub-task updated', 'success');
        }

        closeSubTaskMiniModal();
    } catch (err) {
        console.error('saveSubTaskMiniModal error:', err);
        showToast('Could not save sub-task', 'error');
        saveBtn.disabled = false;
    }
}

function acknowledgeCalendarEvent() {
    if (!currentEventData || !currentEventData.eventId) return;
    const eventId = currentEventData.eventId;

    // Persist acknowledgment server-side (syncs across devices)
    fetch('/api/calendar/acknowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ eventId })
    }).catch(err => console.error('Acknowledge failed:', err));

    // Remove from in-memory list and re-render
    allEvents = allEvents.filter(e => e.id !== eventId);
    refreshCalendar();
    closeEventModal();
    showToast('Acknowledged — removed from calendar', 'success');
}

async function deleteEventFromCalendar() {
    if (!currentEventData || !currentEventData.milestone) {
        showToast('Only milestone events can be deleted from the calendar', 'info');
        return;
    }
    const milestone = currentEventData.milestone;
    const projectCode = currentEventData.projectCode;
    const eventId = currentEventData.eventId;
    const confirmed = await showConfirm(`Delete "${milestone.name}"? This cannot be undone.`);
    if (!confirmed) return;
    
    const btn = document.getElementById('deleteEventBtn');
    if (btn) btn.disabled = true;
    
    try {
        const milestoneId = milestone.id || milestone.name;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 20000);
        
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const resp = await fetch(
            `/api/milestones/${encodeURIComponent(projectCode)}/${encodeURIComponent(milestoneId)}`,
            { method: 'DELETE', signal: controller.signal, headers: { 'x-csrf-token': csrfToken } }
        );
        clearTimeout(timeoutId);
        
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server returned ${resp.status}`);
        }
        closeEventModal();
        showToast(`Deleted "${milestone.name}"`, 'success');
        // Remove from in-memory events and refresh calendar
        allEvents = allEvents.filter(e => e.id !== eventId);
        refreshCalendar();
    } catch (err) {
        console.error('deleteEventFromCalendar error:', err);
        const msg = err.name === 'AbortError' ? 'Request timed out — please try again' : err.message;
        showToast('Could not delete: ' + msg, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function markRiskMitigated() {
    if (!currentEventData || currentEventData.type !== 'risk_review') {
        showToast('No risk event selected', 'info');
        return;
    }
    const { riskId, riskProgram, eventId } = currentEventData;
    if (!riskId || !riskProgram) {
        showToast('Missing risk details', 'error');
        return;
    }

    const btn = document.getElementById('markMitigatedBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Saving…`;
    }

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const resp = await fetch(
            `/risks/update/${encodeURIComponent(riskProgram)}/${encodeURIComponent(riskId)}`,
            {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'Mitigated' }),
                signal: controller.signal
            }
        );
        clearTimeout(timeout);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server ${resp.status}`);
        }
        closeEventModal();
        showToast('✓ Risk marked as mitigated — removed from calendar', 'success');
        // Optimistic: remove from local events + deferred sync
        if (eventId) {
            allEvents = allEvents.filter(e => e.id !== eventId);
        }
        refreshCalendar();
        _scheduleDeferredSync();
    } catch (err) {
        console.error('markRiskMitigated error:', err);
        showToast('Could not update risk: ' + err.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Mark Mitigated`;
        }
    }
}

async function rescheduleRiskFromModal() {
    if (!currentEventData || currentEventData.type !== 'risk_review') return;
    const newDate = document.getElementById('riskRescheduleDate')?.value;
    if (!newDate) { showToast('Please select a date', 'info'); return; }
    const { riskId, riskProgram, eventId } = currentEventData;
    if (!riskId || !riskProgram) { showToast('Missing risk details', 'error'); return; }

    const btn = document.getElementById('riskRescheduleBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Moving…'; }

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const resp = await fetch(
            `/risks/reschedule/${encodeURIComponent(riskProgram)}/${encodeURIComponent(riskId)}`,
            { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_date: newDate }), signal: controller.signal }
        );
        clearTimeout(timeout);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server ${resp.status}`);
        }
        closeEventModal();
        showToast('✓ Risk review rescheduled', 'success');
        // Optimistic: update in-memory event + deferred sync
        if (eventId) {
            const evtIdx = allEvents.findIndex(e => e.id === eventId);
            if (evtIdx !== -1) allEvents[evtIdx].start = newDate;
        }
        refreshCalendar();
        _scheduleDeferredSync();
        if (calendarInstance) calendarInstance.gotoDate(newDate);
    } catch (err) {
        console.error('rescheduleRiskFromModal error:', err);
        const msg = err.name === 'AbortError' ? 'Request timed out' : err.message;
        showToast('Could not reschedule: ' + msg, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Move'; }
    }
}

async function saveEventFromCalendar() {
    if (!currentEventData || !currentEventData.milestone) {
        showToast('Only milestone events can be saved', 'info');
        return;
    }
    const milestone = currentEventData.milestone;
    const projectCode = currentEventData.projectCode || milestone.project;
    
    // Read values from form inputs
    const newName = document.getElementById('calEditName')?.value?.trim() || milestone.name;
    const newTargetDate = document.getElementById('calEditTargetDate')?.value || milestone.target_date;
    const newStartDate = document.getElementById('calEditStartDate')?.value || milestone.start_date;
    const newStatus = document.getElementById('calEditStatus')?.value || milestone.status;
    const newCompletion = parseInt(document.getElementById('calEditCompletion')?.value || '0', 10);
    const newNotes = document.getElementById('calEditNotes')?.value || '';
    const newResources = document.getElementById('calEditResources')?.value || '';
    const newOwner = document.getElementById('calEditOwner')?.value || '';
    
    // Check if target date changed — need confirmation for change record
    const dateChanged = milestone.target_date && newTargetDate && milestone.target_date !== newTargetDate;
    let confirmedDateChange = false;
    
    if (dateChanged) {
        confirmedDateChange = await showDateChangeConfirm(milestone.target_date, newTargetDate, newName);
        if (confirmedDateChange === null) return;  // user cancelled entirely
    }
    
    const btn = document.getElementById('saveEventBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = `<svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Saving…`; }
    
    const saveButtonOriginalHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg> Save`;
    try {
        const payload = {
            project_code: projectCode,
            milestone: {
                id: milestone.id,
                name: newName,
                target_date: newTargetDate,
                start_date: newStartDate,
                status: newStatus,
                completion_percentage: newCompletion,
                notes: newNotes,
                resources: newResources,
                owner: newOwner,
                parent_project: milestone.parent_project,
                is_true_milestone: milestone.is_true_milestone,
                outline_level: milestone.outline_level,
                parent_levels: milestone.parent_levels
            },
            confirmed_date_change: confirmedDateChange
        };
        
        // Use AbortController to enforce a 20s timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 20000);
        
        const resp = await fetch('/milestones/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server returned ${resp.status}`);
        }
        
        const result = await resp.json();
        console.log('📝 Save response:', result);
        
        // Verify server persisted the correct target_date
        if (result.saved_target_date && result.saved_target_date !== newTargetDate) {
            console.error('⚠️ DATE MISMATCH: sent', newTargetDate, 'server saved', result.saved_target_date);
        }
        
        closeEventModal();
        showToast('Milestone saved successfully', 'success');
        
        // Optimistic: update in-memory events + deferred sync
        // Completed milestones should be removed from calendar
        if (newStatus === 'COMPLETED') {
            allEvents = allEvents.filter(e => {
                const mid = e.extendedProps?.milestone;
                return !(e.extendedProps?.type === 'milestone' && mid && mid.id === milestone.id && e.extendedProps?.programCode === projectCode);
            });
        } else {
            // Update matching milestone events in-place
            allEvents.forEach(e => {
                const mid = e.extendedProps?.milestone;
                if (e.extendedProps?.type === 'milestone' && mid && mid.id === milestone.id && e.extendedProps?.programCode === projectCode) {
                    if (e.id.startsWith('milestone-start-')) e.start = newStartDate || e.start;
                    if (e.id.startsWith('milestone-end-')) e.start = newTargetDate || e.start;
                }
            });
        }
        refreshCalendar();
        _scheduleDeferredSync();
        
        // Navigate to the new date so the user sees the pill at its updated position
        if (newTargetDate && calendarInstance) {
            calendarInstance.gotoDate(newTargetDate);
        }
    } catch (err) {
        console.error('saveEventFromCalendar error:', err);
        const msg = err.name === 'AbortError' ? 'Request timed out — please try again' : err.message;
        showToast('Could not save: ' + msg, 'error');
    } finally {
        // Always reset button state so it never stays stuck spinning
        if (btn) { btn.disabled = false; btn.innerHTML = saveButtonOriginalHTML; }
    }
}

// Date change confirmation dialog (mirrors milestones.html pattern)
function showDateChangeConfirm(oldDate, newDate, milestoneName) {
    return new Promise(resolve => {
        const oldFmt = formatDate(oldDate);
        const newFmt = formatDate(newDate);
        const daysDiff = Math.round((new Date(newDate) - new Date(oldDate)) / 86400000);
        const direction = daysDiff > 0 ? 'delayed' : 'accelerated';
        const absDays = Math.abs(daysDiff);
        
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-[10001] flex items-center justify-center bg-black/50';
        overlay.innerHTML = `
            <div class="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                        <svg class="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    </div>
                    <h3 class="text-lg font-bold text-gray-800">Date Change Detected</h3>
                </div>
                <p class="text-sm text-gray-600 mb-3"><strong>${milestoneName}</strong> will be ${direction} by <strong>${absDays} day${absDays !== 1 ? 's' : ''}</strong>.</p>
                <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg mb-4">
                    <div class="text-center flex-1">
                        <p class="text-xs text-gray-500">From</p>
                        <p class="text-sm font-bold text-red-600 line-through">${oldFmt}</p>
                    </div>
                    <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
                    <div class="text-center flex-1">
                        <p class="text-xs text-gray-500">To</p>
                        <p class="text-sm font-bold text-green-600">${newFmt}</p>
                    </div>
                </div>
                <p class="text-xs text-gray-500 mb-4">A change record will be created to track this date change.</p>
                <div class="flex justify-end gap-3">
                    <button id="dcCancel" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm">Cancel</button>
                    <button id="dcSaveOnly" class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 text-sm">Save Without Record</button>
                    <button id="dcConfirm" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Confirm & Record</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#dcConfirm').onclick = () => { overlay.remove(); resolve(true); };
        overlay.querySelector('#dcSaveOnly').onclick = () => { overlay.remove(); resolve(false); };
        overlay.querySelector('#dcCancel').onclick = () => { overlay.remove(); resolve(null); };
    });
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch (e) {
        return dateStr;
    }
}

// ── Custom List View ───────────────────────────────────────────────────
let clvDragSrcIdx = null;
let clvDragSrcDate = null;
let _clvDragInProgress = false;
let _clvRenderQueued = false;
let _deferredSyncTimer = null;

/** Schedule a deferred background sync (debounced). Optimistic UI stays stable
 *  for the delay period; the 60s polling catches any remaining drift. */
function _scheduleDeferredSync(delayMs = 3000) {
    if (_deferredSyncTimer) clearTimeout(_deferredSyncTimer);
    _deferredSyncTimer = setTimeout(() => {
        _deferredSyncTimer = null;
        syncEventsQuietly();
    }, delayMs);
}

function getListSortOrder() {
    return _serverListOrder;
}
function saveListSortOrder(orderMap) {
    _serverListOrder = orderMap;
    // Persist to server (fire-and-forget) — syncs across devices
    fetch('/api/calendar/list-order', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: orderMap })
    }).catch(err => console.error('Save list order failed:', err));
}

function renderCustomListView() {
    const body = document.getElementById('clvBody');
    const countEl = document.getElementById('clvCount');
    const titleEl = document.getElementById('clvTitle');
    if (!body) return;

    // Cache type colors for badge rendering
    const _clvTypeColors = getTypeColors();

    // Use filteredEvents (matches current filter checkboxes)
    applyFilters();
    const events = [...filteredEvents];

    // Get current month/year from FullCalendar view
    let monthLabel = '';
    if (calendarInstance) {
        const viewDate = calendarInstance.getDate();
        monthLabel = viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        // Filter to events within the current month view
        const viewStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
        const viewEnd = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0, 23, 59, 59);
        events.splice(0, events.length, ...events.filter(e => {
            const d = new Date(e.start);
            return d >= viewStart && d <= viewEnd;
        }));
    }
    if (titleEl) titleEl.textContent = monthLabel ? `List — ${monthLabel}` : 'List View';
    if (countEl) countEl.textContent = `${events.length} item${events.length !== 1 ? 's' : ''}`;

    if (events.length === 0) {
        body.innerHTML = '<div class="clv-empty">No events this month matching current filters</div>';
        return;
    }

    // Sort: user sort order (localStorage) → then by date
    const orderMap = getListSortOrder();
    events.sort((a, b) => {
        const oa = orderMap[a.id] ?? 9999;
        const ob = orderMap[b.id] ?? 9999;
        if (oa !== ob) return oa - ob;
        return (a.start || '').localeCompare(b.start || '');
    });

    // Group by date
    const groups = {};
    events.forEach(e => {
        const dateKey = (e.start || '').split('T')[0];
        if (!groups[dateKey]) groups[dateKey] = [];
        groups[dateKey].push(e);
    });

    const typeLabels = { milestone: 'MIL', schedule: 'SCH', risk_review: 'RSK', change: 'CHG', metric_target: 'MET', standalone: 'TSK' };
    const doneLabels = { milestone: 'Done ✓', schedule: 'Done ✓', risk_review: 'Mitigated ✓', change: 'Ack ✓', metric_target: 'Ack ✓', standalone: 'Complete ✓' };

    let html = '';
    let globalIdx = 0;
    const sortedDates = Object.keys(groups).sort();

    for (const dateKey of sortedDates) {
        const d = new Date(dateKey + 'T00:00:00');
        const label = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
        html += `<div class="clv-group-label" data-date="${dateKey}">${label}</div>`;

        const dayItems = groups[dateKey];
        const dayTotal = dayItems.length;
        dayItems.forEach((evt, dayIdx) => {
            const ep = evt.extendedProps || {};
            const type = ep.type || 'milestone';
            const statusCat = ep.status_category || 'not-started';
            const program = ep.programName || ep.program || '';
            const evtId = evt.id;
            const idx = globalIdx++;

            html += `<div class="clv-row" draggable="true" data-idx="${idx}" data-event-id="${evtId}" data-event-type="${type}" data-date="${dateKey}" style="background:${getPriorityColor(dayIdx, dayTotal)}">`;
            html += `<span class="clv-drag-handle" title="Drag to reorder">⠿</span>`;
            html += `<span class="priority-label">P${dayIdx + 1}</span>`;
            const badgeColor = ep.tableColor || _clvTypeColors[type] || '';
            const badgeTextColor = badgeColor ? getContrastColor(badgeColor) : '';
            const badgeStyle = badgeColor ? ` style="background:${badgeColor}; color:${badgeTextColor}"` : '';
            html += `<span class="clv-type-badge clv-type-${type}"${badgeStyle}>${typeLabels[type] || type.substring(0,3).toUpperCase()}</span>`;
            html += `<span class="clv-status-dot status-dot-${statusCat}"></span>`;
            html += `<span class="clv-title" data-event-id="${evtId}">${escapeHtml(evt.title)}</span>`;
            html += `<span class="clv-program">${escapeHtml(program)}</span>`;
            html += `<span class="clv-date">${dateKey}</span>`;
            html += `<button class="clv-done-btn clv-done-btn-${type}" data-event-id="${evtId}" data-event-type="${type}" onclick="event.stopPropagation(); clvQuickDone(this)">${doneLabels[type] || 'Done ✓'}</button>`;
            if (type === 'schedule') {
                html += `<button class="clv-delete-btn" data-event-id="${evtId}" onclick="event.stopPropagation(); clvDeleteSchedule(this)" title="Delete from schedule">✕</button>`;
            }
            html += `</div>`;
        });
    }

    body.innerHTML = html;

    // Wire up click-to-open-modal on title spans
    body.querySelectorAll('.clv-title').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const eid = el.dataset.eventId;
            const row = el.closest('.clv-row');
            if (row && row.dataset.eventType === 'standalone') {
                const fcEvt = calendarInstance?.getEventById(eid);
                if (fcEvt) openEditStandaloneTaskModal(fcEvt.extendedProps.taskId);
                return;
            }
            if (calendarInstance) {
                const fcEvent = calendarInstance.getEventById(eid);
                if (fcEvent) showEventModal(fcEvent);
            }
        });
    });

    // Wire up row click (excluding button and handle clicks)
    body.querySelectorAll('.clv-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('.clv-done-btn') || e.target.closest('.clv-delete-btn') || e.target.closest('.clv-drag-handle')) return;
            const eid = row.dataset.eventId;
            if (row.dataset.eventType === 'standalone') {
                const fcEvt = calendarInstance?.getEventById(eid);
                if (fcEvt) openEditStandaloneTaskModal(fcEvt.extendedProps.taskId);
                return;
            }
            if (calendarInstance) {
                const fcEvent = calendarInstance.getEventById(eid);
                if (fcEvent) showEventModal(fcEvent);
            }
        });
    });

    // Wire up drag-and-drop
    clvInitDrag(body);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function clvInitDrag(container) {
    const rows = container.querySelectorAll('.clv-row');
    rows.forEach(row => {
        row.addEventListener('dragstart', (e) => {
            clvDragSrcIdx = parseInt(row.dataset.idx);
            clvDragSrcDate = row.dataset.date;
            _clvDragInProgress = true;
            row.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', row.dataset.idx);
        });
        row.addEventListener('dragend', () => {
            _clvDragInProgress = false;
            row.classList.remove('dragging');
            container.querySelectorAll('.clv-row').forEach(r => {
                r.classList.remove('drag-over-top', 'drag-over-bottom');
            });
            container.querySelectorAll('.clv-group-label').forEach(l => {
                l.classList.remove('drag-over-day');
            });
            // Flush queued re-render if a background sync completed during the drag
            if (_clvRenderQueued) {
                _clvRenderQueued = false;
                renderCustomListView();
            }
        });
        row.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const rect = row.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            row.classList.toggle('drag-over-top', e.clientY < midY);
            row.classList.toggle('drag-over-bottom', e.clientY >= midY);
        });
        row.addEventListener('dragleave', () => {
            row.classList.remove('drag-over-top', 'drag-over-bottom');
        });
        row.addEventListener('drop', (e) => {
            e.preventDefault();
            row.classList.remove('drag-over-top', 'drag-over-bottom');
            const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
            const toIdx = parseInt(row.dataset.idx);
            if (fromIdx === toIdx || isNaN(fromIdx) || isNaN(toIdx)) return;
            clvReorder(container, fromIdx, toIdx, e);
        });
    });

    // Group labels as cross-day drop targets
    container.querySelectorAll('.clv-group-label').forEach(label => {
        label.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            label.classList.add('drag-over-day');
        });
        label.addEventListener('dragleave', () => {
            label.classList.remove('drag-over-day');
        });
        label.addEventListener('drop', (e) => {
            e.preventDefault();
            label.classList.remove('drag-over-day');
            const targetDate = label.dataset.date;
            if (!clvDragSrcDate || !targetDate || clvDragSrcDate === targetDate) return;
            // Find the source row
            const srcRow = container.querySelector(`.clv-row[data-idx="${clvDragSrcIdx}"]`);
            if (!srcRow) return;
            const eventId = srcRow.dataset.eventId;
            const eventType = srcRow.dataset.eventType;
            clvCrossDayMove(eventId, eventType, targetDate);
        });
    });
}

function clvReorder(container, fromIdx, toIdx, dropEvent) {
    // Get all rows in current order
    const rows = Array.from(container.querySelectorAll('.clv-row'));
    const srcRow = rows[fromIdx];
    const tgtRow = rows[toIdx];
    if (!srcRow || !tgtRow) return;

    // Cross-day move: if source and target are on different dates, reschedule
    const srcDate = srcRow.dataset.date;
    const tgtDate = tgtRow.dataset.date;
    if (srcDate && tgtDate && srcDate !== tgtDate) {
        clvCrossDayMove(srcRow.dataset.eventId, srcRow.dataset.eventType, tgtDate);
        return;
    }

    // Same-day reorder
    const eventIds = rows.map(r => r.dataset.eventId);
    const movedId = eventIds[fromIdx];
    eventIds.splice(fromIdx, 1);

    // Determine insert position based on drop position
    const targetRow = rows[toIdx];
    const rect = targetRow.getBoundingClientRect();
    const insertBefore = dropEvent.clientY < (rect.top + rect.height / 2);
    let insertIdx = toIdx;
    if (fromIdx < toIdx) insertIdx--;
    if (!insertBefore) insertIdx++;
    eventIds.splice(insertIdx, 0, movedId);

    // Save new order to localStorage
    const orderMap = {};
    eventIds.forEach((id, i) => { orderMap[id] = i; });
    saveListSortOrder(orderMap);

    // Re-render
    renderCustomListView();
    showToast('Order updated', 'success', 2000);
}

async function clvCrossDayMove(eventId, eventType, newDate) {
    // Only milestone, schedule, risk_review, standalone can be rescheduled
    if (!['milestone', 'schedule', 'risk_review', 'standalone'].includes(eventType)) {
        showToast('This item type cannot be rescheduled', 'error');
        return;
    }

    const evt = allEvents.find(e => e.id === eventId);
    if (!evt) { showToast('Event not found', 'error'); return; }
    const ep = evt.extendedProps || {};

    // ── Optimistic UI: move the item immediately ──
    const oldDate = evt.start;
    const oldEnd = evt.end || evt.start;
    const dayDelta = Math.round((new Date(newDate) - new Date(oldDate.split('T')[0])) / 86400000);
    const newEnd = new Date(new Date(oldEnd.split('T')[0]).getTime() + dayDelta * 86400000).toISOString().split('T')[0];
    const idx = allEvents.findIndex(e => e.id === eventId);
    if (idx !== -1) {
        allEvents[idx].start = newDate;
        allEvents[idx].end = newEnd;
    }
    refreshCalendar();
    showToast('✓ Rescheduled', 'success');

    // ── Fire API in background (no await) ──
    _clvPersistReschedule(eventId, eventType, ep, newDate, oldDate);
}

/** Persist a reschedule to the server; revert optimistic update on failure */
async function _clvPersistReschedule(eventId, eventType, ep, newDate, oldDate) {
    try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 15000);
        let resp;

        if (eventType === 'schedule') {
            const { program: prog, tableId, rowId, dateColId } = ep;
            if (!prog || !tableId || !rowId || !dateColId) throw new Error('Missing schedule data');
            resp = await fetch(
                `/dashboard/api/schedule/${encodeURIComponent(prog)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/reschedule`,
                {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' },
                    body: JSON.stringify({ date_col_id: dateColId, new_date: newDate }),
                    signal: ctrl.signal
                }
            );
        } else if (eventType === 'milestone') {
            const ms = ep.milestone || {};
            const projectCode = ep.programCode || ms.project;
            if (!projectCode || !ms.name) throw new Error('Missing milestone data');
            // Determine which end was dragged and shift both dates to preserve duration
            const isStartEvent = eventId.startsWith('milestone-start-');
            const curStart = (ep.startDate || ms.start_date || '').split('T')[0];
            const curTarget = (ep.targetDate || ms.target_date || '').split('T')[0];
            let newStart, newTarget;
            if (isStartEvent) {
                newStart = newDate;
                // Shift target by the same delta to preserve duration
                const delta = curStart ? Math.round((new Date(newDate) - new Date(curStart)) / 86400000) : 0;
                newTarget = curTarget ? new Date(new Date(curTarget).getTime() + delta * 86400000).toISOString().split('T')[0] : newDate;
            } else {
                newTarget = newDate;
                // Shift start by the same delta to preserve duration
                const delta = curTarget ? Math.round((new Date(newDate) - new Date(curTarget)) / 86400000) : 0;
                newStart = curStart ? new Date(new Date(curStart).getTime() + delta * 86400000).toISOString().split('T')[0] : newDate;
            }
            resp = await fetch('/milestones/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_code: projectCode,
                    milestone: {
                        id: ms.id || ms.name, name: ms.name,
                        target_date: newTarget,
                        start_date: newStart,
                        status: ep.status || ms.status || 'NOT_STARTED',
                        completion_percentage: ep.completionPct || 0,
                        notes: ep.notes || '',
                        resources: ep.resources || ms.resources || '',
                        parent_project: ep.parentProject || ms.parent_project || '',
                        is_true_milestone: ms.is_true_milestone,
                        outline_level: ms.outline_level,
                        parent_levels: ms.parent_levels
                    },
                    confirmed_date_change: false
                }),
                signal: ctrl.signal
            });
        } else if (eventType === 'risk_review') {
            const riskId = ep.riskId;
            const riskProgram = ep.program;
            if (!riskId || !riskProgram) throw new Error('Missing risk data');
            resp = await fetch(
                `/risks/reschedule/${encodeURIComponent(riskProgram)}/${encodeURIComponent(riskId)}`,
                {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_date: newDate }),
                    signal: ctrl.signal
                }
            );
        } else if (eventType === 'standalone') {
            const taskId = ep.taskId;
            if (!taskId) throw new Error('Missing standalone task data');
            // Calculate day delta to shift both start and due dates (preserving duration)
            const oldStartStr = (oldDate || '').split('T')[0];
            const oldDueStr = (ep.due_date || oldDate || '').split('T')[0];
            const delta = Math.round((new Date(newDate) - new Date(oldStartStr)) / 86400000);
            const shiftedDue = new Date(new Date(oldDueStr).getTime() + delta * 86400000).toISOString().split('T')[0];
            resp = await fetch(
                `/api/standalone-tasks/${encodeURIComponent(taskId)}/reschedule`,
                {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' },
                    body: JSON.stringify({ new_due_date: shiftedDue, new_start_date: newDate }),
                    signal: ctrl.signal
                }
            );
        }

        clearTimeout(t);
        if (!resp || !resp.ok) throw new Error(`Server ${resp?.status || 'error'}`);

        // Deferred background sync — lets optimistic UI settle before refetching
        _scheduleDeferredSync();

    } catch (err) {
        console.error('_clvPersistReschedule error:', err);
        // ── Revert optimistic update ──
        const idx = allEvents.findIndex(e => e.id === eventId);
        if (idx !== -1) allEvents[idx].start = oldDate;
        refreshCalendar();
        const msg = err.name === 'AbortError' ? 'Request timed out — server may be restarting' : err.message;
        showToast('Could not reschedule — ' + msg, 'error');
    }
}

async function clvQuickDone(btn) {
    const eventId = btn.dataset.eventId;
    const eventType = btn.dataset.eventType;
    if (!confirm('Mark this item as done?')) return;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    // Find the event data
    const evt = allEvents.find(e => e.id === eventId);
    if (!evt) {
        showToast('Event not found', 'error');
        btn.disabled = false;
        return;
    }
    const ep = evt.extendedProps || {};

    // ── Optimistic UI: remove immediately ──
    const removedEvt = { ...evt };
    allEvents = allEvents.filter(e => e.id !== eventId);
    if (calendarInstance) {
        const fcEvent = calendarInstance.getEventById(eventId);
        if (fcEvent) fcEvent.remove();
    }
    applyFilters();

    // Animate row removal
    const row = btn.closest('.clv-row');
    if (row) {
        row.style.transition = 'opacity 0.2s, transform 0.2s';
        row.style.opacity = '0';
        row.style.transform = 'translateX(30px)';
        setTimeout(() => {
            row.remove();
            const countEl = document.getElementById('clvCount');
            const remaining = document.querySelectorAll('#clvBody .clv-row').length;
            if (countEl) countEl.textContent = `${remaining} item${remaining !== 1 ? 's' : ''}`;
            if (remaining === 0) {
                document.getElementById('clvBody').innerHTML = '<div class="clv-empty">No events this month matching current filters</div>';
            }
        }, 220);
    }

    const doneMsg = { milestone: 'Milestone completed', schedule: 'Schedule item done', risk_review: 'Risk mitigated', change: 'Change acknowledged', metric_target: 'Metric acknowledged', standalone: 'Task completed' };
    showToast(`✓ ${doneMsg[eventType] || 'Done'}`, 'success');

    // ── Fire API in background ──
    _clvPersistDone(eventId, eventType, ep, removedEvt);
}

async function clvDeleteSchedule(btn) {
    const eventId = btn.dataset.eventId;
    const evt = allEvents.find(e => e.id === eventId);
    if (!evt) { showToast('Event not found', 'error'); return; }
    const ep = evt.extendedProps || {};
    if (ep.type !== 'schedule' || !ep.program || !ep.tableId || !ep.rowId) {
        showToast('Cannot delete this event type', 'error');
        return;
    }
    if (!confirm(`Delete "${evt.title}" from the schedule? This cannot be undone.`)) return;

    // Optimistic removal — remove all events from same row (multi-date-column rows)
    const { program, tableId, rowId } = ep;
    allEvents = allEvents.filter(e => {
        const eep = e.extendedProps || {};
        return !(eep.type === 'schedule' && eep.program === program && eep.tableId === tableId && eep.rowId === rowId);
    });
    if (calendarInstance) {
        const fcEvent = calendarInstance.getEventById(eventId);
        if (fcEvent) fcEvent.remove();
    }
    applyFilters();

    // Animate row removal
    const row = btn.closest('.clv-row');
    if (row) {
        row.style.transition = 'opacity 0.2s, transform 0.2s';
        row.style.opacity = '0';
        row.style.transform = 'translateX(30px)';
        setTimeout(() => {
            row.remove();
            const countEl = document.getElementById('clvCount');
            const remaining = document.querySelectorAll('#clvBody .clv-row').length;
            if (countEl) countEl.textContent = `${remaining} item${remaining !== 1 ? 's' : ''}`;
            if (remaining === 0) {
                document.getElementById('clvBody').innerHTML = '<div class="clv-empty">No events this month matching current filters</div>';
            }
        }, 220);
    }

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const resp = await fetch(
            `/dashboard/api/schedule/${encodeURIComponent(program)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}`,
            { method: 'DELETE', signal: controller.signal, headers: { 'x-csrf-token': csrfToken } }
        );
        clearTimeout(timeout);
        if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
        showToast('Schedule item deleted', 'success');
        _scheduleDeferredSync();
    } catch (err) {
        console.error('clvDeleteSchedule error:', err);
        showToast('Could not delete — please try again', 'error');
        await reloadCalendarEvents();
    }
}

/** Persist a done/complete action to the server; revert optimistic removal on failure */
async function _clvPersistDone(eventId, eventType, ep, removedEvt) {
    try {
        if (eventType === 'milestone') {
            const ms = ep.milestone || {};
            const projectCode = ep.programCode || ms.project;
            if (!projectCode || !ms.name) throw new Error('Missing milestone data');
            const ctrl1 = new AbortController();
            const t1 = setTimeout(() => ctrl1.abort(), 15000);
            const resp = await fetch('/milestones/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_code: projectCode,
                    milestone: {
                        id: ms.id || ms.name, name: ms.name,
                        target_date: ep.targetDate || ms.target_date || '',
                        start_date: ep.startDate || ms.start_date || '',
                        status: 'COMPLETED', completion_percentage: 100,
                        notes: ep.notes || '', resources: ep.resources || ms.resources || '',
                        parent_project: ep.parentProject || ms.parent_project || '',
                        is_true_milestone: ms.is_true_milestone,
                        outline_level: ms.outline_level,
                        parent_levels: ms.parent_levels
                    },
                    confirmed_date_change: false
                }),
                signal: ctrl1.signal
            });
            clearTimeout(t1);
            if (!resp.ok) throw new Error(`Server ${resp.status}`);

        } else if (eventType === 'schedule') {
            const { program, tableId, rowId } = ep;
            if (!program || !tableId || !rowId) throw new Error('Missing schedule data');
            const ctrl2 = new AbortController();
            const t2 = setTimeout(() => ctrl2.abort(), 15000);
            const resp = await fetch(
                `/dashboard/api/schedule/${encodeURIComponent(program)}/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}/complete`,
                { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' }, signal: ctrl2.signal }
            );
            clearTimeout(t2);
            if (!resp.ok) throw new Error(`Server ${resp.status}`);

        } else if (eventType === 'risk_review') {
            const { riskId, program } = ep;
            if (!riskId || !program) throw new Error('Missing risk data');
            const ctrl3 = new AbortController();
            const t3 = setTimeout(() => ctrl3.abort(), 15000);
            const resp = await fetch(
                `/risks/update/${encodeURIComponent(program)}/${encodeURIComponent(riskId)}`,
                { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'Mitigated' }), signal: ctrl3.signal }
            );
            clearTimeout(t3);
            if (!resp.ok) throw new Error(`Server ${resp.status}`);

        } else if (eventType === 'standalone') {
            const taskId = ep.taskId;
            if (!taskId) throw new Error('Missing standalone task data');
            const ctrl4 = new AbortController();
            const t4 = setTimeout(() => ctrl4.abort(), 15000);
            const resp = await fetch(`/api/standalone-tasks/${encodeURIComponent(taskId)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'x-csrf-token': document.getElementById('csrfToken')?.value || '' },
                body: JSON.stringify({ status: 'COMPLETED' }),
                signal: ctrl4.signal
            });
            clearTimeout(t4);
            if (!resp.ok) throw new Error(`Server ${resp.status}`);

        } else if (eventType === 'change' || eventType === 'metric_target') {
            await fetch('/api/calendar/acknowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ eventId })
            });
        }

        // Deferred background sync to pick up server-side side-effects
        _scheduleDeferredSync();

    } catch (err) {
        console.error('_clvPersistDone error:', err);
        // ── Revert: re-add the event ──
        allEvents.push(removedEvt);
        refreshCalendar();
        const errMsg = err.name === 'AbortError' ? 'Request timed out — server may be restarting' : err.message;
        showToast('Could not complete: ' + errMsg, 'error');
    }
}

// ── Toast notification system ──────────────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span style="font-size:1rem;flex-shrink:0">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastOut 0.25s ease-in forwards';
        setTimeout(() => toast.remove(), 260);
    }, duration);
}

// In-app confirm dialog (replaces browser confirm())
function showConfirm(message) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-[10001] flex items-center justify-center bg-black/50';
        overlay.innerHTML = `
            <div class="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4">
                <p class="text-gray-800 font-medium mb-5">${message}</p>
                <div class="flex justify-end gap-3">
                    <button id="confirmNo" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm">Cancel</button>
                    <button id="confirmYes" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium">Delete</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#confirmYes').onclick = () => { overlay.remove(); resolve(true); };
        overlay.querySelector('#confirmNo').onclick  = () => { overlay.remove(); resolve(false); };
    });
}
// ── Standalone Task Modal ──────────────────────────────────────────────
let _stModalMode = 'create';  // 'create' | 'edit'
let _stTaskId = null;
let _stSubTaskData = [];  // [{id, title, completed}] for edit mode
let _stOriginalCadence = null;  // cadence already persisted on the task being edited

function openNewStandaloneTaskModal(date = null) {
    _stModalMode = 'create';
    _stTaskId = null;
    _stSubTaskData = [];
    _stOriginalCadence = null;
    _resetStForm();
    if (date) document.getElementById('stDueDate').value = date;
    document.getElementById('stModalTypeLabel').textContent = 'New Task';
    document.getElementById('stModalHeading').textContent = 'Create Task';
    document.getElementById('stSaveBtnLabel').textContent = 'Save Task';
    document.getElementById('stDeleteBtn').classList.add('hidden');
    document.getElementById('standaloneTaskModal').classList.remove('hidden');
    setTimeout(() => document.getElementById('stTitle').focus(), 60);
}

async function openEditStandaloneTaskModal(taskId) {
    _stTaskId = taskId;
    _stModalMode = 'edit';
    _stSubTaskData = [];
    _resetStForm();
    document.getElementById('stModalTypeLabel').textContent = 'Edit Task';
    document.getElementById('stModalHeading').textContent = 'Edit Task';
    document.getElementById('stSaveBtnLabel').textContent = 'Save Changes';
    document.getElementById('stDeleteBtn').classList.remove('hidden');

    try {
        const resp = await fetch(`/api/standalone-tasks/${encodeURIComponent(taskId)}`, { cache: 'no-store' });
        if (!resp.ok) throw new Error(`Could not load task (${resp.status})`);
        const data = await resp.json();
        const t = data.task;

        document.getElementById('stTitle').value = t.title || '';
        document.getElementById('stDueDate').value = t.due_date || '';
        document.getElementById('stStartDate').value = t.start_date || '';
        document.getElementById('stStatus').value = t.status || 'NOT_STARTED';
        document.getElementById('stPriority').value = t.priority || 'MEDIUM';
        document.getElementById('stOwner').value = t.owner || '';
        document.getElementById('stResources').value = t.resources || '';
        document.getElementById('stCategory').value = t.category || '';
        document.getElementById('stDescription').value = t.description || '';

        // Recurrence — track the stored cadence so submit can detect new selections
        _stOriginalCadence = t.recurrence_cadence || null;
        if (t.recurrence_cadence) {
            document.getElementById('stCadence').value = t.recurrence_cadence;
            document.getElementById('stCadence').disabled = true;
            document.getElementById('stRecurrenceCount').disabled = true;
            onCadenceChange();
            const previewEl = document.getElementById('recurrencePreview');
            if (previewEl) {
                previewEl.textContent = `Part of a recurring series${t.recurrence_occurrence ? ' — ' + t.recurrence_occurrence : ''}. Cadence cannot be changed after creation.`;
                previewEl.classList.remove('hidden');
            }
            // Open recurrence section so user can see it
            const section = document.getElementById('recurrenceSection');
            const chevron = document.getElementById('recurrenceChevron');
            if (section) section.classList.remove('hidden');
            if (chevron) chevron.style.transform = 'rotate(180deg)';
        } else {
            _stOriginalCadence = null;
            // Leave recurrence fields enabled so user can convert task to a series
        }

        // Sub-tasks
        _stSubTaskData = (t.sub_tasks || []).map(s => ({ ...s }));
        if (_stSubTaskData.length > 0) {
            _renderSubTaskList();
            const section = document.getElementById('subTaskSection');
            const chevron = document.getElementById('subTaskChevron');
            if (section) section.classList.remove('hidden');
            if (chevron) chevron.style.transform = 'rotate(180deg)';
        }

    } catch (err) {
        console.error('openEditStandaloneTaskModal error:', err);
        document.getElementById('stModalError').textContent = 'Failed to load task: ' + err.message;
        document.getElementById('stModalError').classList.remove('hidden');
    }

    document.getElementById('standaloneTaskModal').classList.remove('hidden');
}

function closeStandaloneTaskModal() {
    document.getElementById('standaloneTaskModal').classList.add('hidden');
    _resetStForm();
}

function _resetStForm() {
    document.getElementById('stTitle').value = '';
    document.getElementById('stDueDate').value = '';
    document.getElementById('stStartDate').value = '';
    document.getElementById('stStatus').value = 'NOT_STARTED';
    document.getElementById('stPriority').value = 'MEDIUM';
    document.getElementById('stOwner').value = '';
    document.getElementById('stResources').value = '';
    document.getElementById('stCategory').value = '';
    document.getElementById('stDescription').value = '';
    document.getElementById('stCadence').value = '';
    document.getElementById('stCadence').disabled = false;
    document.getElementById('stRecurrenceCount').value = '4';
    document.getElementById('stRecurrenceCount').disabled = false;
    document.getElementById('occurrencesField').classList.add('hidden');
    document.getElementById('recurrencePreview').classList.add('hidden');
    document.getElementById('recurrenceSection').classList.add('hidden');
    document.getElementById('recurrenceChevron').style.transform = '';
    document.getElementById('subTaskSection').classList.add('hidden');
    document.getElementById('subTaskChevron').style.transform = '';
    document.getElementById('stSubTaskInput').value = '';
    document.getElementById('stSubTaskList').innerHTML = '';
    document.getElementById('subTaskBadge').classList.add('hidden');
    document.getElementById('stModalError').classList.add('hidden');
    document.getElementById('stSaveBtn').disabled = false;
    _stSubTaskData = [];
}

function toggleRecurrenceSection() {
    const section = document.getElementById('recurrenceSection');
    const chevron = document.getElementById('recurrenceChevron');
    const isHidden = section.classList.contains('hidden');
    section.classList.toggle('hidden', !isHidden);
    chevron.style.transform = isHidden ? 'rotate(180deg)' : '';
}

function toggleSubTaskSection() {
    const section = document.getElementById('subTaskSection');
    const chevron = document.getElementById('subTaskChevron');
    const isHidden = section.classList.contains('hidden');
    section.classList.toggle('hidden', !isHidden);
    chevron.style.transform = isHidden ? 'rotate(180deg)' : '';
}

function onCadenceChange() {
    const cadence = document.getElementById('stCadence').value;
    const occField = document.getElementById('occurrencesField');
    const previewEl = document.getElementById('recurrencePreview');
    if (cadence) {
        occField.classList.remove('hidden');
        previewEl.classList.remove('hidden');
        const count = parseInt(document.getElementById('stRecurrenceCount').value) || 4;
        const labels = { daily: 'day', weekly: 'week', biweekly: '2 weeks', monthly: 'month' };
        previewEl.textContent = `Will create ${count} tasks, one every ${labels[cadence] || cadence}`;
    } else {
        occField.classList.add('hidden');
        previewEl.classList.add('hidden');
    }
}

function addSubTaskToForm() {
    const input = document.getElementById('stSubTaskInput');
    const title = (input.value || '').trim();
    if (!title) return;
    _stSubTaskData.push({ id: 'new-' + Date.now(), title, completed: false });
    input.value = '';
    _renderSubTaskList();
    input.focus();
}

function _renderSubTaskList() {
    const list = document.getElementById('stSubTaskList');
    const badge = document.getElementById('subTaskBadge');
    list.innerHTML = '';
    // Sort: active first, completed last (stable sort preserves original order within groups)
    const activeItems = _stSubTaskData.map((s, i) => ({ ...s, _origIdx: i })).filter(s => !s.completed);
    const doneItems = _stSubTaskData.map((s, i) => ({ ...s, _origIdx: i })).filter(s => s.completed);
    const sorted = [...activeItems, ...doneItems];
    const activeCount = activeItems.length;
    let activeIdx = 0;
    sorted.forEach((sub) => {
        const idx = sub._origIdx;
        const isActive = !sub.completed;
        const pIdx = isActive ? activeIdx++ : -1;
        const el = document.createElement('div');
        el.className = `sibling-row group ${sub.completed ? 'is-completed' : ''}`;
        el.draggable = true;
        el.dataset.stIdx = idx;
        el.style.background = isActive ? getPriorityColor(pIdx, activeCount) : '#F9FAFB';
        el.innerHTML = `
            <span class="subtask-drag-handle" title="Drag to reorder">⠿</span>
            <span class="priority-label">${isActive ? 'P' + (pIdx + 1) : ''}</span>
            <input type="checkbox" ${sub.completed ? 'checked' : ''} onchange="_stSubTaskData[${idx}].completed = this.checked; _renderSubTaskList();"
                class="rounded text-indigo-600 focus:ring-indigo-500 flex-shrink-0 w-4 h-4">
            <label class="flex-1 text-sm cursor-pointer select-none">${_escapeHtml(sub.title)}</label>
            <button type="button" onclick="_stSubTaskData.splice(${idx},1);_renderSubTaskList();"
                class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition p-0.5">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>`;
        list.appendChild(el);
        // Wire up double-click to open mini modal on standalone sub-task label
        const lbl = el.querySelector('label');
        if (lbl && _stTaskId && sub.id && !sub.id.startsWith('new-')) {
            const capturedId = sub.id;
            const capturedNotes = sub.notes || '';
            lbl.ondblclick = () => openSubTaskMiniModal(capturedId, sub.title, capturedNotes, 'standalone', { taskId: _stTaskId });
            lbl.title = 'Double-click to edit details';
        }
    });
    const count = _stSubTaskData.length;
    badge.textContent = count > 0 ? count : '';
    badge.classList.toggle('hidden', count === 0);
    // Init drag-reorder for standalone sub-tasks (reorders in-memory array)
    if (_stSubTaskData.length > 1) {
        initSubtaskDrag(list, (cont) => {
            const rows = [...cont.querySelectorAll('.sibling-row')];
            const newOrder = rows.map(r => parseInt(r.dataset.stIdx));
            const reordered = newOrder.map(i => _stSubTaskData[i]).filter(Boolean);
            // Fallback: if any indices are stale, just keep the current DOM order
            if (reordered.length === _stSubTaskData.length) {
                _stSubTaskData.splice(0, _stSubTaskData.length, ...reordered);
            }
            // Re-render to update indices and colors
            _renderSubTaskList();
            // If editing an existing task, persist the reorder via API
            if (_stTaskId) {
                const ids = _stSubTaskData.map(s => s.id);
                fetch(`/api/standalone-tasks/${encodeURIComponent(_stTaskId)}/sub-tasks/reorder`, {
                    method: 'PUT', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({ order: ids })
                }).catch(err => console.error('Standalone sub-task reorder failed:', err));
            }
        });
    }
}

function _escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function submitStandaloneTaskForm() {
    const title = document.getElementById('stTitle').value.trim();
    const dueDate = document.getElementById('stDueDate').value;
    const errEl = document.getElementById('stModalError');
    errEl.classList.add('hidden');

    if (!title) { errEl.textContent = 'Title is required.'; errEl.classList.remove('hidden'); return; }
    if (!dueDate) { errEl.textContent = 'Due date is required.'; errEl.classList.remove('hidden'); return; }

    const saveBtn = document.getElementById('stSaveBtn');
    saveBtn.disabled = true;
    document.getElementById('stSaveBtnLabel').textContent = 'Saving…';

    const payload = {
        title,
        due_date: dueDate,
        start_date: document.getElementById('stStartDate').value || null,
        status: document.getElementById('stStatus').value,
        priority: document.getElementById('stPriority').value,
        owner: document.getElementById('stOwner').value.trim() || null,
        resources: document.getElementById('stResources').value.trim() || null,
        category: document.getElementById('stCategory').value.trim() || null,
        description: document.getElementById('stDescription').value.trim() || null,
        sub_tasks: _stSubTaskData.map(s => ({ id: s.id, title: s.title, completed: s.completed, created_at: s.created_at || new Date().toISOString() })),
    };

    // Include recurrence when:
    //   - creating with a cadence selected, OR
    //   - editing a non-recurring task and the user has just selected a cadence
    const cadence = document.getElementById('stCadence').value;
    if (cadence && !_stOriginalCadence) {
        payload.recurrence_cadence = cadence;
        payload.recurrence_count = parseInt(document.getElementById('stRecurrenceCount').value) || 4;
    }

    try {
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const url = _stModalMode === 'edit' ? `/api/standalone-tasks/${encodeURIComponent(_stTaskId)}` : '/api/standalone-tasks';
        const method = _stModalMode === 'edit' ? 'PUT' : 'POST';
        const resp = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `Server ${resp.status}`);
        }
        const result = await resp.json();
        closeStandaloneTaskModal();
        let toastMsg = '✓ Task saved';
        if (result.converted) {
            toastMsg = `✓ Converted to recurring series (${result.total} occurrences)`;
        } else if (result.tasks && result.tasks.length > 1) {
            toastMsg = `✓ Created ${result.tasks.length} recurring tasks`;
        }
        showToast(toastMsg, 'success');
        // Fetch fresh events from server so all new occurrences appear immediately
        await reloadCalendarEvents();
    } catch (err) {
        console.error('submitStandaloneTaskForm error:', err);
        errEl.textContent = 'Save failed: ' + err.message;
        errEl.classList.remove('hidden');
        saveBtn.disabled = false;
        document.getElementById('stSaveBtnLabel').textContent = _stModalMode === 'edit' ? 'Save Changes' : 'Save Task';
    }
}

async function deleteStandaloneTask() {
    if (!_stTaskId) return;
    const isRecurring = !!document.getElementById('stCadence').value;

    if (isRecurring) {
        // Custom multi-option confirm for recurring tasks
        const choice = await _showRecurrenceDeleteConfirm();
        if (!choice) return;  // cancelled
        const deleteSeriesParam = choice === 'series' ? '?delete_series=true' : '';
        await _doDeleteStandaloneTask(_stTaskId, deleteSeriesParam);
    } else {
        const ok = await showConfirm('Delete this task? This cannot be undone.');
        if (!ok) return;
        await _doDeleteStandaloneTask(_stTaskId, '');
    }
}

async function _doDeleteStandaloneTask(taskId, queryString) {
    try {
        const csrfToken = document.getElementById('csrfToken')?.value || '';
        const resp = await fetch(`/api/standalone-tasks/${encodeURIComponent(taskId)}${queryString}`, {
            method: 'DELETE',
            headers: { 'x-csrf-token': csrfToken },
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `Server ${resp.status}`);
        }
        const result = await resp.json();
        closeStandaloneTaskModal();
        showToast(`🗑️ Deleted ${result.deleted || 1} task${(result.deleted || 1) > 1 ? 's' : ''}`, 'success');
        // Optimistic: remove from local events + deferred sync
        allEvents = allEvents.filter(e => !(e.extendedProps?.type === 'standalone' && e.extendedProps?.taskId === taskId));
        refreshCalendar();
        _scheduleDeferredSync();
    } catch (err) {
        console.error('deleteStandaloneTask error:', err);
        showToast('Could not delete: ' + err.message, 'error');
    }
}

function _showRecurrenceDeleteConfirm() {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-[10002] flex items-center justify-center bg-black/50';
        overlay.innerHTML = `
            <div class="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4">
                <h4 class="text-gray-800 font-semibold mb-2">Delete recurring task</h4>
                <p class="text-sm text-gray-600 mb-5">This task is part of a recurring series. What would you like to delete?</p>
                <div class="flex flex-col gap-2">
                    <button id="delThis" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm text-left">This occurrence only</button>
                    <button id="delSeries" class="px-4 py-2 bg-red-100 text-red-700 border border-red-200 rounded-lg hover:bg-red-200 text-sm text-left">Entire series (all ${document.getElementById('stCadence').value ? 'recurrences' : 'occurrences'})</button>
                    <button id="delCancel" class="px-4 py-2 bg-white border border-gray-200 text-gray-500 rounded-lg hover:bg-gray-50 text-sm text-left">Cancel</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#delThis').onclick   = () => { overlay.remove(); resolve('single'); };
        overlay.querySelector('#delSeries').onclick = () => { overlay.remove(); resolve('series'); };
        overlay.querySelector('#delCancel').onclick = () => { overlay.remove(); resolve(null); };
    });
}

// Close standalone modal on backdrop click
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('standaloneTaskModal').addEventListener('click', function(e) {
        if (e.target === this) closeStandaloneTaskModal();
    });
});

