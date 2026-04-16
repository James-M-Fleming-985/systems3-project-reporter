"""
Schedule Repository - Server-side persistence for schedule tables
Stores user-configurable schedule tables in YAML files per project
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime
import uuid
import re

logger = logging.getLogger(__name__)


class ScheduleRepository:
    """Repository for persisting schedule tables on the server"""
    
    def __init__(self, storage_dir: Path):
        """Initialize repository with storage directory"""
        self.storage_dir = storage_dir / "schedules"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ScheduleRepository initialized: {self.storage_dir}")
    
    def _clean_project_name(self, project_name: str) -> str:
        """Clean project name by removing version numbers and file extensions."""
        clean = project_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '')
        clean = re.sub(r'-\d+$', '', clean)
        return clean.strip()
    
    def _get_schedules_file_path(self, project_name: str) -> Path:
        """Get the file path for a project's schedules.
        
        Checks multiple filename patterns to handle both project codes (ZLD-P1)
        and project names (ZnNi Line Development Plan-16.xml).
        """
        clean_name = self._clean_project_name(project_name)
        clean_name = clean_name.replace('/', '_').replace('\\', '_')
        
        # Primary path using cleaned project name
        primary_path = self.storage_dir / f"{clean_name}_schedules.yaml"
        if primary_path.exists():
            logger.info(f"📋 Found schedule file at primary path: {primary_path}")
            return primary_path
        
        # Also check for project code-based filename (e.g., ZLD-P1_schedules.yaml)
        # This handles cases where schedules were saved using project_code
        # Extract potential project code from name (e.g., "ZLD-P1" from context)
        # Check all existing schedule files for a match
        for schedule_file in self.storage_dir.glob("*_schedules.yaml"):
            logger.debug(f"📋 Checking schedule file: {schedule_file.name}")
        
        return primary_path
    
    def _find_schedule_file(self, project_identifier: str) -> Optional[Path]:
        """Find schedule file by project name, code, or partial match."""
        clean_name = self._clean_project_name(project_identifier)
        clean_name = clean_name.replace('/', '_').replace('\\', '_')
        
        # Try exact match first
        exact_path = self.storage_dir / f"{clean_name}_schedules.yaml"
        if exact_path.exists():
            return exact_path
        
        # Try direct project identifier (might be a code like ZLD-P1)
        direct_path = self.storage_dir / f"{project_identifier}_schedules.yaml"
        if direct_path.exists():
            return direct_path
        
        # List all schedule files and look for potential matches
        for schedule_file in self.storage_dir.glob("*_schedules.yaml"):
            file_project = schedule_file.stem.replace('_schedules', '')
            # Check if this file's project identifier is contained in the search term
            # or vice versa (handles ZLD-P1 vs ZnNi Line Development Plan)
            if file_project.lower() in clean_name.lower() or clean_name.lower() in file_project.lower():
                logger.info(f"📋 Found matching schedule file by partial match: {schedule_file}")
                return schedule_file
        
        return None
    
    def get_schedules(self, project_name: str) -> Dict[str, Any]:
        """
        Get all schedules for a project
        
        Returns:
            Dict with 'tables' list containing schedule table configurations
        """
        try:
            # Try to find schedule file by name, code, or partial match
            file_path = self._find_schedule_file(project_name)
            
            if not file_path or not file_path.exists():
                logger.info(f"📋 No schedule file found for '{project_name}'")
                # Return default structure with empty tables
                return {
                    'project_name': project_name,
                    'tables': [],
                    'last_updated': None
                }
            
            logger.info(f"📋 Loading schedules from: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            logger.info(f"📋 Loaded {len(data.get('tables', []))} schedule tables for '{project_name}'")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error loading schedules for '{project_name}': {e}")
            return {'project_name': project_name, 'tables': [], 'last_updated': None}
    
    def save_schedules(self, project_name: str, data: Dict[str, Any]) -> bool:
        """
        Save all schedules for a project
        
        Args:
            project_name: Name of the project
            data: Full schedule data including tables
            
        Returns:
            True if successful
        """
        try:
            file_path = self._get_schedules_file_path(project_name)
            
            data['project_name'] = project_name
            data['last_updated'] = datetime.now().isoformat()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"✅ Saved {len(data.get('tables', []))} schedule tables for '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving schedules for '{project_name}': {e}")
            return False
    
    def create_table(self, project_name: str, table_name: str, columns: List[Dict[str, Any]] = None, description: str = None, color: str = None) -> Dict[str, Any]:
        """
        Create a new schedule table
        
        Args:
            project_name: Project name
            table_name: Name for the new table
            columns: Optional column configuration, uses defaults if not provided
            description: Optional description of the table's purpose
            
        Returns:
            The created table configuration
        """
        data = self.get_schedules(project_name)
        
        # Default columns if none provided
        if columns is None:
            columns = [
                {
                    'id': str(uuid.uuid4())[:8],
                    'header': 'Task',
                    'type': 'text',
                    'width': 250,
                    'visible_in_export': True
                },
                {
                    'id': str(uuid.uuid4())[:8],
                    'header': 'Owner',
                    'type': 'text',
                    'width': 120,
                    'visible_in_export': True
                },
                {
                    'id': str(uuid.uuid4())[:8],
                    'header': 'Due Date',
                    'type': 'date',
                    'width': 120,
                    'visible_in_export': True
                },
                {
                    'id': str(uuid.uuid4())[:8],
                    'header': 'Notes',
                    'type': 'text',
                    'width': 200,
                    'visible_in_export': False  # Internal notes hidden in export
                },
                {
                    'id': str(uuid.uuid4())[:8],
                    'header': 'Status',
                    'type': 'status',  # Special type with color support
                    'width': 130,
                    'visible_in_export': True,
                    'status_options': [
                        {'label': 'Not Started', 'color': '#6B7280'},  # Gray
                        {'label': 'In Progress', 'color': '#F59E0B'},  # Amber
                        {'label': 'Complete', 'color': '#16A34A'},     # Green
                        {'label': 'On Hold', 'color': '#DC2626'},      # Red
                        {'label': 'Blocked', 'color': '#7C3AED'}       # Purple
                    ]
                }
            ]
        
        new_table = {
            'id': str(uuid.uuid4()),
            'name': table_name,
            'description': description or '',
            'color': color or '',
            'created_at': datetime.now().isoformat(),
            'columns': columns,
            'rows': []
        }
        
        # Ensure every column has an id
        for col in new_table['columns']:
            if 'id' not in col:
                col['id'] = str(uuid.uuid4())[:8]
        
        data['tables'].append(new_table)
        self.save_schedules(project_name, data)
        
        logger.info(f"✅ Created schedule table '{table_name}' for '{project_name}'")
        return new_table
    
    def get_table(self, project_name: str, table_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific table by ID"""
        data = self.get_schedules(project_name)
        for table in data.get('tables', []):
            if table.get('id') == table_id:
                return table
        return None
    
    def update_table(self, project_name: str, table_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a schedule table
        
        Args:
            project_name: Project name
            table_id: ID of table to update
            updates: Fields to update (name, columns, rows)
            
        Returns:
            True if successful
        """
        data = self.get_schedules(project_name)
        
        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                # Update allowed fields
                if 'name' in updates:
                    data['tables'][i]['name'] = updates['name']
                if 'description' in updates:
                    data['tables'][i]['description'] = updates['description']
                if 'columns' in updates:
                    new_col_ids = {c.get('id') for c in updates['columns']}
                    old_col_ids = {c.get('id') for c in data['tables'][i].get('columns', [])}
                    removed_col_ids = old_col_ids - new_col_ids
                    if removed_col_ids:
                        for row in data['tables'][i].get('rows', []):
                            row_data = row.get('data', {})
                            for rid in removed_col_ids:
                                row_data.pop(rid, None)
                    data['tables'][i]['columns'] = updates['columns']
                if 'rows' in updates:
                    data['tables'][i]['rows'] = updates['rows']
                if 'color' in updates:
                    data['tables'][i]['color'] = updates['color']
                
                data['tables'][i]['updated_at'] = datetime.now().isoformat()
                return self.save_schedules(project_name, data)
        
        logger.warning(f"Table '{table_id}' not found for project '{project_name}'")
        return False
    
    def delete_table(self, project_name: str, table_id: str) -> bool:
        """Delete a schedule table"""
        data = self.get_schedules(project_name)
        
        original_count = len(data.get('tables', []))
        data['tables'] = [t for t in data.get('tables', []) if t.get('id') != table_id]
        
        if len(data['tables']) < original_count:
            self.save_schedules(project_name, data)
            logger.info(f"🗑️ Deleted table '{table_id}' from '{project_name}'")
            return True
        
        return False
    
    def add_row(self, project_name: str, table_id: str, row_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Add a row to a schedule table
        
        Args:
            project_name: Project name
            table_id: Table to add row to
            row_data: Optional initial row data
            
        Returns:
            The created row
        """
        data = self.get_schedules(project_name)
        
        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                new_row = {
                    'id': str(uuid.uuid4()),
                    'created_at': datetime.now().isoformat(),
                    'data': row_data or {}
                }
                data['tables'][i]['rows'].append(new_row)
                self.save_schedules(project_name, data)
                return new_row
        
        return None
    
    def add_rows_bulk(self, project_name: str, table_id: str, rows_data: list) -> int:
        """
        Add multiple rows in a single file read/write cycle.
        Much faster than calling add_row() in a loop for large imports.

        Args:
            project_name: Project name
            table_id: Table to add rows to
            rows_data: List of row data dicts

        Returns:
            Number of rows added
        """
        if not rows_data:
            return 0
        data = self.get_schedules(project_name)
        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for row_data in rows_data:
                    new_row = {
                        'id': str(uuid.uuid4()),
                        'created_at': datetime.now().isoformat(),
                        'data': row_data or {}
                    }
                    data['tables'][i]['rows'].append(new_row)
                self.save_schedules(project_name, data)
                return len(rows_data)
        return 0

    def update_row(self, project_name: str, table_id: str, row_id: str, row_data: Dict[str, Any]) -> bool:
        """Update a row in a schedule table"""
        data = self.get_schedules(project_name)
        
        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        data['tables'][i]['rows'][j]['data'] = row_data
                        data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                        return self.save_schedules(project_name, data)
        
        return False

    def update_row_notes(self, project_name: str, table_id: str, row_id: str, notes: str) -> bool:
        """Update the notes field on a schedule row (stored separately from row data)."""
        data = self.get_schedules(project_name)

        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        data['tables'][i]['rows'][j]['notes'] = notes
                        data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                        return self.save_schedules(project_name, data)

        return False

    def get_row_sub_tasks(self, project_name: str, table_id: str, row_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get sub-tasks for a schedule row."""
        data = self.get_schedules(project_name)
        for table in data.get('tables', []):
            if table.get('id') == table_id:
                for row in table.get('rows', []):
                    if row.get('id') == row_id:
                        return row.get('sub_tasks', [])
        return None

    def add_sub_task(self, project_name: str, table_id: str, row_id: str, title: str, notes: str = '') -> Optional[Dict[str, Any]]:
        """Add a sub-task to a schedule row."""
        data = self.get_schedules(project_name)

        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        sub_task = {
                            'id': str(uuid.uuid4())[:8],
                            'title': title,
                            'completed': False,
                            'created_at': datetime.now().isoformat()
                        }
                        if notes:
                            sub_task['notes'] = notes
                        if 'sub_tasks' not in data['tables'][i]['rows'][j]:
                            data['tables'][i]['rows'][j]['sub_tasks'] = []
                        data['tables'][i]['rows'][j]['sub_tasks'].append(sub_task)
                        data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                        self.save_schedules(project_name, data)
                        return sub_task

        return None

    def update_sub_task(self, project_name: str, table_id: str, row_id: str,
                        sub_task_id: str, updates: Dict[str, Any]) -> bool:
        """Update a sub-task (toggle completed, rename, etc.)."""
        data = self.get_schedules(project_name)

        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        for k, st in enumerate(row.get('sub_tasks', [])):
                            if st.get('id') == sub_task_id:
                                if 'completed' in updates:
                                    data['tables'][i]['rows'][j]['sub_tasks'][k]['completed'] = updates['completed']
                                if 'title' in updates:
                                    data['tables'][i]['rows'][j]['sub_tasks'][k]['title'] = updates['title']
                                if 'notes' in updates:
                                    data['tables'][i]['rows'][j]['sub_tasks'][k]['notes'] = updates['notes']
                                data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                                return self.save_schedules(project_name, data)

        return False

    def delete_sub_task(self, project_name: str, table_id: str, row_id: str, sub_task_id: str) -> bool:
        """Delete a sub-task from a schedule row."""
        data = self.get_schedules(project_name)

        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        original = len(row.get('sub_tasks', []))
                        data['tables'][i]['rows'][j]['sub_tasks'] = [
                            st for st in row.get('sub_tasks', []) if st.get('id') != sub_task_id
                        ]
                        if len(data['tables'][i]['rows'][j].get('sub_tasks', [])) < original:
                            data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                            return self.save_schedules(project_name, data)

        return False
    
    def reorder_sub_tasks(self, project_name: str, table_id: str, row_id: str, ordered_ids: List[str]) -> bool:
        """Reorder sub-tasks on a schedule row according to the given ID list."""
        data = self.get_schedules(project_name)

        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                for j, row in enumerate(table.get('rows', [])):
                    if row.get('id') == row_id:
                        existing = row.get('sub_tasks', [])
                        by_id = {st['id']: st for st in existing}
                        reordered = [by_id[sid] for sid in ordered_ids if sid in by_id]
                        # Append any sub-tasks whose IDs weren't in the list (safety)
                        seen = set(ordered_ids)
                        for st in existing:
                            if st['id'] not in seen:
                                reordered.append(st)
                        data['tables'][i]['rows'][j]['sub_tasks'] = reordered
                        data['tables'][i]['rows'][j]['updated_at'] = datetime.now().isoformat()
                        return self.save_schedules(project_name, data)

        return False

    def delete_row(self, project_name: str, table_id: str, row_id: str) -> bool:
        """Delete a row from a schedule table"""
        data = self.get_schedules(project_name)
        
        for i, table in enumerate(data.get('tables', [])):
            if table.get('id') == table_id:
                original_count = len(table.get('rows', []))
                data['tables'][i]['rows'] = [r for r in table.get('rows', []) if r.get('id') != row_id]
                
                if len(data['tables'][i]['rows']) < original_count:
                    self.save_schedules(project_name, data)
                    return True
        
        return False
