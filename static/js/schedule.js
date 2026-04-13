const _schedBridge = document.getElementById("schedule-data-bridge");
const projectName = _schedBridge.dataset.projectName;
let tablesData = JSON.parse(_schedBridge.dataset.tablesData);

console.log('📋 Schedule loaded for:', projectName);

// ==================== STYLED MODAL HELPERS ====================
function showConfirmModal(title, message, confirmText, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl max-w-md mx-4 p-6">
            <div class="flex items-start mb-4">
                <div class="flex-shrink-0">
                    <svg class="h-12 w-12 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                </div>
                <div class="ml-4">
                    <h3 class="text-lg font-semibold text-gray-900">${title}</h3>
                    <p class="mt-2 text-sm text-gray-600 whitespace-pre-line">${message}</p>
                </div>
            </div>
            
            <div class="flex gap-3">
                <button onclick="this.closest('.fixed').remove()" class="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors font-medium">
                    Cancel
                </button>
                <button id="confirmYes" class="flex-1 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors font-medium">
                    ${confirmText}
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#confirmYes').addEventListener('click', () => {
        modal.remove();
        if (onConfirm) onConfirm();
    });
}

function showErrorModal(title, message) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl max-w-md mx-4 p-6">
            <div class="flex items-start mb-4">
                <div class="flex-shrink-0">
                    <svg class="h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
                <div class="ml-4">
                    <h3 class="text-lg font-semibold text-gray-900">${title}</h3>
                    <p class="mt-2 text-sm text-gray-600">${message}</p>
                </div>
            </div>
            <button onclick="this.closest('.fixed').remove();" class="w-full bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors font-medium">
                OK
            </button>
        </div>
    `;
    document.body.appendChild(modal);
}

function showSuccessModal(title, message) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl max-w-md mx-4 p-6">
            <div class="flex items-start mb-4">
                <div class="flex-shrink-0">
                    <svg class="h-12 w-12 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
                <div class="ml-4">
                    <h3 class="text-lg font-semibold text-gray-900">${title}</h3>
                    <p class="mt-2 text-sm text-gray-600">${message}</p>
                </div>
            </div>
            <button onclick="this.closest('.fixed').remove();" class="w-full bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors font-medium">
                OK
            </button>
        </div>
    `;
    document.body.appendChild(modal);
}
console.log('Tables:', tablesData.tables?.length || 0);

// =============================================================================
// Column Resize by Dragging
// =============================================================================
let resizeState = {
    isResizing: false,
    tableId: null,
    colId: null,
    startX: 0,
    startWidth: 0,
    th: null
};

function startColumnResize(event, tableId, colId) {
    event.preventDefault();
    event.stopPropagation();
    
    const th = event.target.closest('th');
    if (!th) return;
    
    resizeState = {
        isResizing: true,
        tableId,
        colId,
        startX: event.clientX,
        startWidth: th.offsetWidth,
        th
    };
    
    th.draggable = false; // Disable drag during resize
    event.target.classList.add('resizing');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    document.addEventListener('mousemove', handleColumnResize);
    document.addEventListener('mouseup', stopColumnResize);
}

function handleColumnResize(event) {
    if (!resizeState.isResizing) return;
    
    const diff = event.clientX - resizeState.startX;
    const newWidth = Math.max(50, resizeState.startWidth + diff);
    resizeState.th.style.width = newWidth + 'px';
}

function stopColumnResize(event) {
    if (!resizeState.isResizing) return;
    
    const { tableId, colId, th } = resizeState;
    const newWidth = th.offsetWidth;
    
    // Re-enable drag
    th.draggable = true;
    th.querySelector('.col-resize-handle')?.classList.remove('resizing');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    
    document.removeEventListener('mousemove', handleColumnResize);
    document.removeEventListener('mouseup', stopColumnResize);
    
    resizeState.isResizing = false;
    
    // Save the new width to server
    saveColumnWidth(tableId, colId, newWidth);
}

async function saveColumnWidth(tableId, colId, width) {
    const table = tablesData.tables?.find(t => t.id === tableId);
    if (!table) return;
    
    const columns = table.columns.map(c => {
        if (c.id === colId) {
            return { ...c, width };
        }
        return c;
    });
    
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ columns })
        });
        
        if (response.ok) {
            // Update local data
            const col = table.columns.find(c => c.id === colId);
            if (col) col.width = width;
            console.log('✅ Column width saved:', colId, width);
        }
    } catch (error) {
        console.error('Error saving column width:', error);
    }
}

// =============================================================================
// Column Drag & Drop Reordering
// =============================================================================
let draggedColId = null;
let draggedTableId = null;

function handleDragStart(event, tableId, colId) {
    // Don't start drag if we're resizing
    if (resizeState.isResizing) {
        event.preventDefault();
        return;
    }
    draggedColId = colId;
    draggedTableId = tableId;
    event.target.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', colId);
    console.log('🎯 Drag start:', colId);
}

function handleDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
}

function handleDragEnter(event) {
    event.preventDefault();
    const th = event.target.closest('th');
    if (th && th.dataset.colId && th.dataset.colId !== draggedColId) {
        th.classList.add('drag-over');
    }
}

function handleDragLeave(event) {
    const th = event.target.closest('th');
    if (th) {
        th.classList.remove('drag-over');
    }
}

function handleDragEnd(event) {
    event.target.classList.remove('dragging');
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
    draggedColId = null;
    draggedTableId = null;
}

async function handleDrop(event, tableId, targetColId) {
    event.preventDefault();
    const th = event.target.closest('th');
    if (th) th.classList.remove('drag-over');
    
    if (!draggedColId || draggedColId === targetColId || tableId !== draggedTableId) {
        return;
    }
    
    console.log('📦 Drop:', draggedColId, 'before', targetColId);
    
    // Get current table
    const table = tablesData.tables?.find(t => t.id === tableId);
    if (!table) return;
    
    // Reorder columns
    const columns = [...table.columns];
    const draggedIndex = columns.findIndex(c => c.id === draggedColId);
    const targetIndex = columns.findIndex(c => c.id === targetColId);
    
    if (draggedIndex === -1 || targetIndex === -1) return;
    
    // Remove dragged column and insert at target position
    const [draggedCol] = columns.splice(draggedIndex, 1);
    columns.splice(targetIndex, 0, draggedCol);
    
    // Save new order
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ columns })
        });
        
        if (response.ok) {
            // Reload to reflect new order
            reloadWithActiveTab();
        } else {
            showErrorModal('Save Failed', 'Could not save the column order. Please try again.');
        }
    } catch (error) {
        console.error('Error saving column order:', error);
        showErrorModal('Error', 'An unexpected error occurred while saving column order.');
    }
}

// =============================================================================
// Tab switching
// =============================================================================
function switchTab(tableId) {
    // Update tab buttons
    document.querySelectorAll('.schedule-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tableId === tableId) {
            tab.classList.add('active');
        }
    });
    
    // Update panels
    document.querySelectorAll('.table-panel').forEach(panel => {
        panel.classList.add('hidden');
    });
    const panel = document.getElementById(`panel-${tableId}`);
    if (panel) panel.classList.remove('hidden');
    
    // Store active tab in localStorage for persistence
    localStorage.setItem(`schedule_active_tab_${projectName}`, tableId);
}

// Reload page while preserving the active tab via ?table= query param
function reloadWithActiveTab(targetTableId) {
    const tableId = targetTableId || document.querySelector('.schedule-tab.active')?.dataset?.tableId;
    const url = new URL(window.location.href);
    if (tableId) url.searchParams.set('table', tableId);
    window.location.href = url.toString();
}

// Restore active tab from localStorage
function restoreActiveTab() {
    const savedTab = localStorage.getItem(`schedule_active_tab_${projectName}`);
    if (savedTab) {
        const tabExists = document.querySelector(`.schedule-tab[data-table-id="${savedTab}"]`);
        if (tabExists) {
            switchTab(savedTab);
        }
    }
}

// Modal helpers
function showModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideModal(id) {
    document.getElementById(id).classList.add('hidden');
}

// State for table creation mode
let tableMode = 'new';
let availablePrograms = [];

function showCreateTableModal() {
    // Reset form
    document.getElementById('tableName').value = '';
    document.getElementById('copyTableName').value = '';
    document.getElementById('sourceProgram').value = '';
    document.getElementById('sourceTable').innerHTML = '<option value="">-- Select source program first --</option>';
    document.getElementById('sourceTable').disabled = true;
    document.getElementById('includeData').checked = true;
    document.getElementById('copyPreview').classList.add('hidden');
    
    // Reset to 'new' mode
    setTableMode('new');
    
    // Load available programs for copy feature
    loadAvailablePrograms();
    
    showModal('createTableModal');
}

function setTableMode(mode) {
    tableMode = mode;
    
    const newBtn = document.getElementById('modeNewBtn');
    const copyBtn = document.getElementById('modeCopyBtn');
    const newSection = document.getElementById('newTableSection');
    const copySection = document.getElementById('copyTableSection');
    const submitBtn = document.getElementById('createTableBtn');
    
    if (mode === 'new') {
        newBtn.className = 'flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all bg-white shadow text-blue-600';
        copyBtn.className = 'flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all text-gray-600 hover:bg-gray-50';
        newSection.classList.remove('hidden');
        copySection.classList.add('hidden');
        submitBtn.textContent = 'Create Table';
    } else {
        copyBtn.className = 'flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all bg-white shadow text-blue-600';
        newBtn.className = 'flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all text-gray-600 hover:bg-gray-50';
        newSection.classList.add('hidden');
        copySection.classList.remove('hidden');
        submitBtn.textContent = 'Copy Table';
    }
}

async function loadAvailablePrograms() {
    try {
        const response = await fetch('/dashboard/api/schedule/all-programs/tables');
        const data = await response.json();
        availablePrograms = data.programs || [];
        
        // Filter out current program
        const filteredPrograms = availablePrograms.filter(p => p.project_name !== projectName);
        
        const select = document.getElementById('sourceProgram');
        select.innerHTML = '<option value="">-- Select a program --</option>';
        
        if (filteredPrograms.length === 0) {
            select.innerHTML = '<option value="">No other programs with tables found</option>';
            return;
        }
        
        filteredPrograms.forEach(program => {
            const option = document.createElement('option');
            option.value = program.project_name;
            option.textContent = `${program.project_name} (${program.tables.length} table${program.tables.length !== 1 ? 's' : ''})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading programs:', error);
    }
}

function loadSourceTables() {
    const sourceProgramName = document.getElementById('sourceProgram').value;
    const sourceTableSelect = document.getElementById('sourceTable');
    const preview = document.getElementById('copyPreview');
    
    preview.classList.add('hidden');
    
    if (!sourceProgramName) {
        sourceTableSelect.innerHTML = '<option value="">-- Select source program first --</option>';
        sourceTableSelect.disabled = true;
        return;
    }
    
    const program = availablePrograms.find(p => p.project_name === sourceProgramName);
    if (!program || !program.tables.length) {
        sourceTableSelect.innerHTML = '<option value="">No tables found</option>';
        sourceTableSelect.disabled = true;
        return;
    }
    
    sourceTableSelect.innerHTML = '<option value="">-- Select a table --</option>';
    program.tables.forEach(table => {
        const option = document.createElement('option');
        option.value = table.id;
        option.textContent = `${table.name} (${table.row_count} rows)`;
        option.dataset.name = table.name;
        option.dataset.rows = table.row_count;
        sourceTableSelect.appendChild(option);
    });
    sourceTableSelect.disabled = false;
    
    // Add change handler for preview
    sourceTableSelect.onchange = function() {
        const selectedOption = this.options[this.selectedIndex];
        if (this.value) {
            preview.innerHTML = `<strong>📋 ${selectedOption.dataset.name}</strong><br>
                <span class="text-gray-600">${selectedOption.dataset.rows} rows will be copied</span>`;
            preview.classList.remove('hidden');
        } else {
            preview.classList.add('hidden');
        }
    };
}

// Create or copy table based on mode
async function createOrCopyTable(event) {
    event.preventDefault();
    
    if (tableMode === 'new') {
        await createNewTable();
    } else {
        await copyTableFromProgram();
    }
}

async function createNewTable() {
    const name = document.getElementById('tableName').value.trim();
    const description = document.getElementById('tableDescription').value.trim();
    if (!name) {
        showErrorModal('Missing Name', 'Please enter a table name before creating.');
        return;
    }
    
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: description || undefined })
        });
        
        if (response.ok) {
            reloadWithActiveTab();
        } else {
            showErrorModal('Creation Failed', 'Could not create the table. Please try again.');
        }
    } catch (error) {
        console.error('Error creating table:', error);
        showErrorModal('Error', 'An unexpected error occurred while creating the table.');
    }
}

async function copyTableFromProgram() {
    const sourceProject = document.getElementById('sourceProgram').value;
    const sourceTableId = document.getElementById('sourceTable').value;
    const newTableName = document.getElementById('copyTableName').value.trim();
    const includeData = document.getElementById('includeData').checked;
    
    if (!sourceProject || !sourceTableId) {
        showErrorModal('Missing Selection', 'Please select a source program and table to copy from.');
        return;
    }
    
    try {
        const submitBtn = document.getElementById('createTableBtn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Copying...';
        
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/copy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_project: sourceProject,
                source_table_id: sourceTableId,
                new_table_name: newTableName || null,
                include_data: includeData
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            reloadWithActiveTab();
        } else {
            const error = await response.json();
            showErrorModal('Copy Failed', 'Could not copy the table: ' + (error.detail || 'Unknown error'));
            submitBtn.disabled = false;
            submitBtn.textContent = 'Copy Table';
        }
    } catch (error) {
        console.error('Error copying table:', error);
        showErrorModal('Error', 'An unexpected error occurred while copying the table.');
        document.getElementById('createTableBtn').disabled = false;
        document.getElementById('createTableBtn').textContent = 'Copy Table';
    }
}

// Add row
async function addRow(tableId) {
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}/rows`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: {} })
        });
        
        if (response.ok) {
            reloadWithActiveTab();
        }
    } catch (error) {
        console.error('Error adding row:', error);
    }
}

// Update cell
let updateTimeout = {};
async function updateCell(tableId, rowId, colId, value) {
    // Debounce updates
    const key = `${tableId}-${rowId}`;
    if (updateTimeout[key]) clearTimeout(updateTimeout[key]);
    
    updateTimeout[key] = setTimeout(async () => {
        // Get current row data
        const table = tablesData.tables?.find(t => t.id === tableId);
        const row = table?.rows?.find(r => r.id === rowId);
        if (!row) return;
        
        // Update the cell value
        const newData = { ...row.data, [colId]: value };
        
        try {
            const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}/rows/${rowId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: newData })
            });
            
            if (response.ok) {
                // Update local data
                row.data = newData;
                console.log('✅ Cell updated:', colId, value);
            }
        } catch (error) {
            console.error('Error updating cell:', error);
        }
    }, 300);
}

// Update status cell color based on selected option
function updateStatusColor(selectEl, colId, tableId) {
    console.log('updateStatusColor called', {selectEl, colId, tableId});
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const color = selectedOption?.dataset?.color;
    console.log('Status color found:', color, 'from option:', selectedOption?.textContent);
    
    if (color) {
        // Set background color with multiple methods for cross-browser support
        selectEl.style.setProperty('background-color', color, 'important');
        selectEl.style.setProperty('background', color, 'important');
        // Determine text color based on background brightness
        const rgb = hexToRgb(color);
        if (rgb) {
            const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
            const textColor = brightness > 128 ? '#1f2937' : '#ffffff';
            selectEl.style.setProperty('color', textColor, 'important');
        }
        console.log('Applied color:', color, 'to select element');
    } else {
        selectEl.style.setProperty('background-color', '#f3f4f6', 'important');
        selectEl.style.setProperty('background', '#f3f4f6', 'important');
        selectEl.style.setProperty('color', '#374151', 'important');
    }
}

// Update priority cell color based on selected option
function updatePriorityColor(selectEl, colId, tableId) {
    console.log('updatePriorityColor called', {selectEl, colId, tableId});
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const color = selectedOption?.dataset?.color;
    console.log('Priority color found:', color, 'from option:', selectedOption?.textContent);
    
    if (color) {
        // Set background color with multiple methods for cross-browser support
        selectEl.style.setProperty('background-color', color, 'important');
        selectEl.style.setProperty('background', color, 'important');
        // Determine text color based on background brightness
        const rgb = hexToRgb(color);
        if (rgb) {
            const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
            const textColor = brightness > 128 ? '#1f2937' : '#ffffff';
            selectEl.style.setProperty('color', textColor, 'important');
        }
        console.log('Applied color:', color, 'to select element');
    } else {
        selectEl.style.setProperty('background-color', '#f3f4f6', 'important');
        selectEl.style.setProperty('background', '#f3f4f6', 'important');
        selectEl.style.setProperty('color', '#374151', 'important');
    }
}

// Convert hex to RGB
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

// Update dropdown cell color based on selected option
function updateDropdownColor(selectEl) {
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const color = selectedOption?.dataset?.color;
    
    if (color && color !== '') {
        selectEl.style.setProperty('background-color', color, 'important');
        selectEl.style.setProperty('background', color, 'important');
        selectEl.style.setProperty('border-radius', '6px', 'important');
        selectEl.style.setProperty('font-weight', '600', 'important');
        selectEl.style.setProperty('text-align', 'center', 'important');
        const rgb = hexToRgb(color);
        if (rgb) {
            const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
            selectEl.style.setProperty('color', brightness > 128 ? '#1f2937' : '#ffffff', 'important');
        }
    } else {
        selectEl.style.removeProperty('background-color');
        selectEl.style.removeProperty('background');
        selectEl.style.removeProperty('color');
        selectEl.style.removeProperty('font-weight');
        selectEl.style.removeProperty('text-align');
    }
}

// Dropdown option form helpers
function addDropdownOptionRow(label, color) {
    const list = document.getElementById('dropdownOptionsList');
    const row = document.createElement('div');
    row.className = 'flex items-center gap-2';
    row.innerHTML = `
        <input type="color" value="${color || '#3B82F6'}" class="dropdown-color-input h-8 border-0 cursor-pointer rounded" style="flex:1;min-width:32px">
        <input type="text" value="${label}" placeholder="Option label" class="dropdown-label-input p-2 border border-gray-300 rounded text-sm" style="flex:3">
        <button type="button" class="text-red-500 hover:text-red-700 px-2" onclick="this.parentElement.remove()">✕</button>
    `;
    list.appendChild(row);
}

function renderDropdownOptions(dropdownOptions) {
    const list = document.getElementById('dropdownOptionsList');
    list.innerHTML = '';
    (dropdownOptions || []).forEach(opt => {
        addDropdownOptionRow(opt.label || opt, opt.color || '');
    });
}

function getDropdownOptionsFromForm() {
    const list = document.getElementById('dropdownOptionsList');
    const rows = list.querySelectorAll('.flex');
    const options = [];
    rows.forEach(row => {
        const color = row.querySelector('.dropdown-color-input').value;
        const label = row.querySelector('.dropdown-label-input').value.trim();
        if (label) {
            options.push({ label, color });
        }
    });
    return options;
}

// Initialize status, priority, and dropdown cell colors on page load
function initStatusColors() {
    const statusSelects = document.querySelectorAll('.cell-status');
    const prioritySelects = document.querySelectorAll('.cell-priority');
    const dropdownColoredSelects = document.querySelectorAll('.cell-dropdown-colored');
    console.log('initStatusColors: Found', statusSelects.length, 'status,', prioritySelects.length, 'priority,', dropdownColoredSelects.length, 'colored dropdown cells');
    
    statusSelects.forEach(select => {
        updateStatusColor(select);
    });
    prioritySelects.forEach(select => {
        updatePriorityColor(select);
    });
    dropdownColoredSelects.forEach(select => {
        updateDropdownColor(select);
    });
}

// Delete row
async function deleteRow(tableId, rowId) {
    showConfirmModal(
        'Delete Row',
        'Are you sure you want to delete this row? This action cannot be undone.',
        'Delete',
        async () => {
            try {
                const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}/rows/${rowId}`, {
                    method: 'DELETE',
                    headers: {
                        'x-csrf-token': document.getElementById('csrfToken')?.value || ''
                    }
                });
        
        if (response.ok) {
            // Remove from DOM
            const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
            if (row) row.remove();
            
            // Update local data
            const table = tablesData.tables?.find(t => t.id === tableId);
            if (table) {
                table.rows = table.rows.filter(r => r.id !== rowId);
            }
        }
            } catch (error) {
                console.error('Error deleting row:', error);
            }
        }
    );
}

// Column modal
function showColumnModal(tableId, columnId = null) {
    document.getElementById('columnTableId').value = tableId;
    document.getElementById('columnId').value = columnId || '';
    document.getElementById('columnModalTitle').textContent = columnId ? 'Edit Column' : 'Add Column';
    
    // Clear all options lists
    document.getElementById('statusOptionsList').innerHTML = '';
    document.getElementById('priorityOptionsList').innerHTML = '';
    document.getElementById('dropdownOptionsList').innerHTML = '';
    
    if (columnId) {
        // Load existing column data
        const table = tablesData.tables?.find(t => t.id === tableId);
        const col = table?.columns?.find(c => c.id === columnId);
        if (col) {
            document.getElementById('columnHeader').value = col.header;
            document.getElementById('columnType').value = col.type;
            document.getElementById('columnWidth').value = col.width || 150;
            document.getElementById('columnExportVisible').checked = col.visible_in_export !== false;
            if (col.dropdown_options && col.dropdown_options.length > 0) {
                renderDropdownOptions(col.dropdown_options);
            } else if (col.options) {
                // Legacy: convert plain options to dropdown_options format
                renderDropdownOptions(col.options.map(o => ({ label: o, color: '' })));
            }
            if (col.status_options && col.status_options.length > 0) {
                renderStatusOptions(col.status_options);
            }
            if (col.priority_options && col.priority_options.length > 0) {
                renderPriorityOptions(col.priority_options);
            }
        }
    } else {
        document.getElementById('columnHeader').value = '';
        document.getElementById('columnType').value = 'text';
        document.getElementById('columnWidth').value = 150;
        document.getElementById('columnExportVisible').checked = true;
    }
    
    toggleDropdownOptions();
    showModal('columnModal');
}

function editColumn(tableId, columnId) {
    showColumnModal(tableId, columnId);
}

function toggleDropdownOptions() {
    const type = document.getElementById('columnType').value;
    const dropdownGroup = document.getElementById('dropdownOptionsGroup');
    const statusGroup = document.getElementById('statusOptionsGroup');
    const priorityGroup = document.getElementById('priorityOptionsGroup');
    
    // Hide all groups first
    dropdownGroup.classList.add('hidden');
    statusGroup.classList.add('hidden');
    priorityGroup.classList.add('hidden');
    
    if (type === 'dropdown') {
        dropdownGroup.classList.remove('hidden');
        // Initialize with empty rows if none exist
        if (!document.getElementById('dropdownOptionsList').children.length) {
            // Add a few empty rows to start
            addDropdownOptionRow('', '');
            addDropdownOptionRow('', '');
            addDropdownOptionRow('', '');
        }
    } else if (type === 'status') {
        statusGroup.classList.remove('hidden');
        // Initialize with default status options if empty
        if (!document.getElementById('statusOptionsList').children.length) {
            renderDefaultStatusOptions();
        }
    } else if (type === 'priority') {
        priorityGroup.classList.remove('hidden');
        // Initialize with default priority options if empty
        if (!document.getElementById('priorityOptionsList').children.length) {
            renderDefaultPriorityOptions();
        }
    }
}

// Default status options with colors
const defaultStatusOptions = [
    { label: 'Not Started', color: '#6B7280' },
    { label: 'In Progress', color: '#F59E0B' },
    { label: 'Complete', color: '#16A34A' },
    { label: 'On Hold', color: '#DC2626' }
];

// Default priority options with colors
const defaultPriorityOptions = [
    { label: 'Critical', color: '#DC2626' },
    { label: 'High', color: '#F97316' },
    { label: 'Medium', color: '#EAB308' },
    { label: 'Low', color: '#22C55E' },
    { label: 'None', color: '#9CA3AF' }
];

function renderDefaultStatusOptions() {
    const list = document.getElementById('statusOptionsList');
    list.innerHTML = '';
    defaultStatusOptions.forEach(opt => {
        addStatusOptionRow(opt.label, opt.color);
    });
}

function renderStatusOptions(statusOptions) {
    const list = document.getElementById('statusOptionsList');
    list.innerHTML = '';
    (statusOptions || []).forEach(opt => {
        addStatusOptionRow(opt.label, opt.color);
    });
}

function addStatusOption() {
    addStatusOptionRow('', '#3B82F6');
}

function addStatusOptionRow(label, color) {
    const list = document.getElementById('statusOptionsList');
    const row = document.createElement('div');
    row.className = 'flex items-center gap-2';
    row.innerHTML = `
        <input type="color" value="${color}" class="status-color-input h-8 border-0 cursor-pointer rounded" style="flex:1;min-width:32px">
        <input type="text" value="${label}" placeholder="Status label" class="status-label-input p-2 border border-gray-300 rounded text-sm" style="flex:3">
        <button type="button" class="text-red-500 hover:text-red-700 px-2" onclick="this.parentElement.remove()">✕</button>
    `;
    list.appendChild(row);
}

function getStatusOptionsFromForm() {
    const list = document.getElementById('statusOptionsList');
    const rows = list.querySelectorAll('.flex');
    const options = [];
    rows.forEach(row => {
        const color = row.querySelector('.status-color-input').value;
        const label = row.querySelector('.status-label-input').value.trim();
        if (label) {
            options.push({ label, color });
        }
    });
    return options;
}

// Priority option functions
function renderDefaultPriorityOptions() {
    const list = document.getElementById('priorityOptionsList');
    list.innerHTML = '';
    defaultPriorityOptions.forEach(opt => {
        addPriorityOptionRow(opt.label, opt.color);
    });
}

function renderPriorityOptions(priorityOptions) {
    const list = document.getElementById('priorityOptionsList');
    list.innerHTML = '';
    (priorityOptions || []).forEach(opt => {
        addPriorityOptionRow(opt.label, opt.color);
    });
}

function addPriorityOption() {
    addPriorityOptionRow('', '#3B82F6');
}

function addPriorityOptionRow(label, color) {
    const list = document.getElementById('priorityOptionsList');
    const row = document.createElement('div');
    row.className = 'flex items-center gap-2';
    row.innerHTML = `
        <input type="color" value="${color}" class="priority-color-input h-8 border-0 cursor-pointer rounded" style="flex:1;min-width:32px">
        <input type="text" value="${label}" placeholder="Priority label" class="priority-label-input p-2 border border-gray-300 rounded text-sm" style="flex:3">
        <button type="button" class="text-red-500 hover:text-red-700 px-2" onclick="this.parentElement.remove()">✕</button>
    `;
    list.appendChild(row);
}

function getPriorityOptionsFromForm() {
    const list = document.getElementById('priorityOptionsList');
    const rows = list.querySelectorAll('.flex');
    const options = [];
    rows.forEach(row => {
        const color = row.querySelector('.priority-color-input').value;
        const label = row.querySelector('.priority-label-input').value.trim();
        if (label) {
            options.push({ label, color });
        }
    });
    return options;
}

async function saveColumn(event) {
    event.preventDefault();
    
    const tableId = document.getElementById('columnTableId').value;
    const columnId = document.getElementById('columnId').value;
    const header = document.getElementById('columnHeader').value.trim();
    const type = document.getElementById('columnType').value;
    const width = parseInt(document.getElementById('columnWidth').value) || 150;
    const visibleInExport = document.getElementById('columnExportVisible').checked;
    
    let options = null;
    let status_options = null;
    let priority_options = null;
    let dropdown_options = null;
    
    if (type === 'dropdown') {
        // Collect dropdown options with colors from the new UI
        const dropdownOpts = getDropdownOptionsFromForm();
        if (dropdownOpts.length > 0) {
            // Check if ANY option has a non-default color
            const hasColors = dropdownOpts.some(o => o.color && o.color !== '' && o.color !== '#000000');
            if (hasColors) {
                // Save as dropdown_options (with colors)
                dropdown_options = dropdownOpts;
            }
            // Always save plain options list for backward compatibility
            options = dropdownOpts.map(o => o.label);
        }
    } else if (type === 'status') {
        status_options = getStatusOptionsFromForm();
    } else if (type === 'priority') {
        priority_options = getPriorityOptionsFromForm();
    }
    
    // Get existing table data
    const table = tablesData.tables?.find(t => t.id === tableId);
    if (!table) return;
    
    let columns = [...table.columns];
    
    if (columnId) {
        // Update existing column
        columns = columns.map(c => {
            if (c.id === columnId) {
                return { ...c, header, type, width, visible_in_export: visibleInExport, options, status_options, priority_options, dropdown_options };
            }
            return c;
        });
    } else {
        // Add new column
        columns.push({
            id: crypto.randomUUID().slice(0, 8),
            header,
            type,
            width,
            visible_in_export: visibleInExport,
            options,
            status_options,
            priority_options,
            dropdown_options
        });
    }
    
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ columns })
        });
        
        if (response.ok) {
            reloadWithActiveTab();
        } else {
            showErrorModal('Save Failed', 'Could not save the column. Please try again.');
        }
    } catch (error) {
        console.error('Error saving column:', error);
        showErrorModal('Error', 'An unexpected error occurred while saving the column.');
    }
}

async function deleteColumn(tableId, columnId) {
    showConfirmModal(
        'Delete Column',
        'Are you sure you want to delete this column? This will remove the column from all rows and cannot be undone.',
        'Delete Column',
        async () => {
    
    const table = tablesData.tables?.find(t => t.id === tableId);
    if (!table) return;
    
    const columns = table.columns.filter(c => c.id !== columnId);
    
    try {
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ columns })
        });
        
        if (response.ok) {
            reloadWithActiveTab();
        }
    } catch (error) {
        console.error('Error deleting column:', error);
    }
        }
    );
}

// Export functions
function exportTable(tableId, format) {
    if (format === 'pdf') {
        // Open print-friendly view in new tab
        window.open(`/dashboard/schedule/print/${encodeURIComponent(projectName)}/${tableId}`, '_blank');
    } else if (format === 'slide') {
        // Open slide preview
        window.open(`/dashboard/schedule/slide/${encodeURIComponent(projectName)}/${tableId}`, '_blank');
    }
}

// Delete table
async function deleteTable(tableId) {
    showConfirmModal(
        'Delete Table',
        'Are you sure you want to delete this entire table? All rows and columns will be permanently removed. This action cannot be undone.',
        'Delete Table',
        async () => {
    
    try {
        console.log('Deleting table:', tableId);
        
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'DELETE',
            headers: {
                'x-csrf-token': document.getElementById('csrfToken')?.value || ''
            }
        });
        
        console.log('Delete response:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Delete failed');
        }
        
        // Success - reload page
        reloadWithActiveTab();
        
    } catch (error) {
        console.error('Error deleting table:', error);
        showErrorModal('Delete Failed', 'Could not delete the table: ' + error.message);
    }
        }
    );
}

function showEditTableModal(tableId) {
    const table = tablesData.tables?.find(t => t.id === tableId);
    if (!table) return;
    
    document.getElementById('editTableId').value = tableId;
    document.getElementById('editTableName').value = table.name || '';
    document.getElementById('editTableDescription').value = table.description || '';
    document.getElementById('editTableColor').value = table.color || '';
    
    // Render color swatches
    const SCHED_PALETTE = ['#6366F1','#3B82F6','#D50000','#E67C73','#F4511E','#F6BF26','#33B679','#0B8043','#039BE5','#3F51B5','#7986CB','#8E24AA','#616161'];
    const container = document.getElementById('editTableColorSwatches');
    container.innerHTML = '';
    const current = table.color || '';
    SCHED_PALETTE.forEach(c => {
        const sw = document.createElement('div');
        sw.style.cssText = `width:26px;height:26px;border-radius:50%;cursor:pointer;border:2px solid ${current===c?'#111827':'transparent'};background:${c};transition:transform 0.1s;flex-shrink:0;`;
        if (current === c) sw.style.boxShadow = '0 0 0 2px #fff, 0 0 0 4px #111827';
        sw.onmouseenter = () => sw.style.transform = 'scale(1.2)';
        sw.onmouseleave = () => sw.style.transform = 'scale(1)';
        sw.onclick = () => { document.getElementById('editTableColor').value = c; container.querySelectorAll('div').forEach(d => { d.style.borderColor='transparent'; d.style.boxShadow='none'; }); sw.style.borderColor='#111827'; sw.style.boxShadow='0 0 0 2px #fff, 0 0 0 4px #111827'; };
        container.appendChild(sw);
    });
    // Reset (no color = default)
    const rs = document.createElement('div');
    rs.style.cssText = `width:26px;height:26px;border-radius:50%;cursor:pointer;border:2px dashed ${!current?'#111827':'#9CA3AF'};background:#F9FAFB;display:flex;align-items:center;justify-content:center;font-size:0.65rem;color:#6B7280;transition:transform 0.1s;`;
    if (!current) rs.style.boxShadow = '0 0 0 2px #fff, 0 0 0 4px #111827';
    rs.textContent = '↺';
    rs.title = 'Reset to default';
    rs.onmouseenter = () => rs.style.transform = 'scale(1.2)';
    rs.onmouseleave = () => rs.style.transform = 'scale(1)';
    rs.onclick = () => { document.getElementById('editTableColor').value = ''; container.querySelectorAll('div').forEach(d => { d.style.borderColor='transparent'; d.style.boxShadow='none'; }); rs.style.borderColor='#111827'; rs.style.boxShadow='0 0 0 2px #fff, 0 0 0 4px #111827'; };
    container.appendChild(rs);

    showModal('editTableModal');
}

async function saveEditTable() {
    const tableId = document.getElementById('editTableId').value;
    const name = document.getElementById('editTableName').value.trim();
    const description = document.getElementById('editTableDescription').value.trim();
    const color = document.getElementById('editTableColor').value.trim();
    
    if (!name) {
        showErrorModal('Missing Name', 'Table name cannot be empty.');
        return;
    }
    
    try {
        const body = { name, description };
        if (color) body.color = color;
        else body.color = '';
        const response = await fetch(`/dashboard/api/schedule/${encodeURIComponent(projectName)}/tables/${tableId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        if (response.ok) {
            reloadWithActiveTab();
        }
    } catch (error) {
        console.error('Error updating table:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing status colors...');
    initStatusColors();
    
    // Check for ?table= query param (e.g. from calendar deep link)
    const urlParams = new URLSearchParams(window.location.search);
    const tableParam = urlParams.get('table');
    if (tableParam) {
        const tabExists = document.querySelector(`.schedule-tab[data-table-id="${tableParam}"]`);
        if (tabExists) {
            switchTab(tableParam);
        } else {
            restoreActiveTab();
        }
    } else {
        restoreActiveTab();
    }
    
    initCellTooltips();
});

// Also run immediately in case DOM is already loaded
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    console.log('DOM already ready, initializing status colors immediately...');
    initStatusColors();
    restoreActiveTab();
    initCellTooltips();
}

// ============================================================
// Cell overflow tooltip system
// Shows a rich tooltip when hovering over any cell whose text
// is truncated (scrollWidth > clientWidth)
// ============================================================
function initCellTooltips() {
    // Create a single shared tooltip element
    let tooltip = document.getElementById('cellTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'cellTooltip';
        tooltip.className = 'cell-tooltip';
        document.body.appendChild(tooltip);
        // Override positioning to be fixed (body-level)
        tooltip.style.position = 'fixed';
        tooltip.style.bottom = 'auto';
        tooltip.style.left = 'auto';
    }
    
    // Delegate events on the schedule tables
    document.querySelectorAll('.schedule-table').forEach(table => {
        table.addEventListener('mouseover', handleCellMouseOver);
        table.addEventListener('mouseout', handleCellMouseOut);
    });
}

function handleCellMouseOver(e) {
    const cell = e.target.closest('.cell-edit, .cell-dropdown, .cell-status, .cell-priority');
    if (!cell) return;
    
    let text = '';
    if (cell.tagName === 'INPUT') {
        text = cell.value;
    } else if (cell.tagName === 'SELECT') {
        text = cell.options[cell.selectedIndex]?.text || '';
    }
    
    if (!text || text.trim() === '' || text === '-- Select --') return;
    
    // Check if text is actually truncated
    const isTruncated = cell.tagName === 'INPUT' 
        ? cell.scrollWidth > cell.clientWidth
        : false;
    // For selects/dropdowns, check by comparing rendered width to text length estimate
    const isLongText = text.length > 15;
    
    // Show tooltip for truncated inputs OR long select values
    if (!isTruncated && !isLongText) return;
    
    const tooltip = document.getElementById('cellTooltip');
    if (!tooltip) return;
    
    tooltip.textContent = text;
    tooltip.style.display = 'block';
    
    // Position above the cell
    const rect = cell.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    let top = rect.top - tooltipRect.height - 8;
    let left = rect.left;
    
    // Keep within viewport
    if (top < 4) top = rect.bottom + 8;
    if (left + tooltipRect.width > window.innerWidth - 8) {
        left = window.innerWidth - tooltipRect.width - 8;
    }
    if (left < 4) left = 4;
    
    tooltip.style.top = top + 'px';
    tooltip.style.left = left + 'px';
}

function handleCellMouseOut(e) {
    const cell = e.target.closest('.cell-edit, .cell-dropdown, .cell-status, .cell-priority');
    if (!cell) return;
    
    const tooltip = document.getElementById('cellTooltip');
    if (tooltip) tooltip.style.display = 'none';
}

// ── AI Chat for Schedule ──
function getActiveTableId() {
    const activeTab = document.querySelector('.schedule-tab.active');
    return activeTab ? activeTab.dataset.tableId : (tablesData.length ? tablesData[0].id : null);
}

function toggleScheduleChat() {
    const sidebar = document.getElementById('scheduleAIChatSidebar');
    const isHidden = sidebar.classList.contains('hidden');
    sidebar.classList.toggle('hidden');
    if (isHidden && typeof AIChatPanel !== 'undefined') {
        const tableId = getActiveTableId();
        if (window._scheduleChatPanel) {
            window._scheduleChatPanel.updateContext('schedule', tableId, projectName);
        } else {
            window._scheduleChatPanel = new AIChatPanel('scheduleAIChatContainer', {
                contextType: 'schedule',
                contextId: tableId,
                projectCode: projectName,
                programName: projectName,
                tableId: tableId
            });
        }
    }
}
