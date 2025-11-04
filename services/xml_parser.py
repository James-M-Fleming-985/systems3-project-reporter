"""
MS Project XML Parser Service
Parses Microsoft Project XML files and converts to Project models
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
import xml.etree.ElementTree as ET
from datetime import datetime

from models import Project, Milestone, Risk, Change


class MSProjectXMLParser:
    """Parser for Microsoft Project XML format"""
    
    def __init__(self):
        self.namespace = {
            'ms': 'http://schemas.microsoft.com/project'
        }
        # Common namespace patterns for MS Project XML
        self.ns_patterns = [
            '',  # No namespace
            '{http://schemas.microsoft.com/project}',  # Default MS Project namespace
            'ms:'  # Prefixed namespace
        ]
    
    def parse_file(self, xml_path: Path) -> Project:
        """Parse MS Project XML file and return Project object"""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Extract project information
        project_data = self._extract_project_info(root)
        
        # Extract tasks/milestones
        milestones = self._extract_milestones(root)
        project_data['milestones'] = milestones
        
        # Extract risks (if present in custom fields)
        risks = self._extract_risks(root)
        project_data['risks'] = risks
        
        # Extract changes (if present)
        changes = self._extract_changes(root)
        project_data['changes'] = changes
        
        return Project(**project_data)
    
    def extract_level2_projects(self, xml_path: Path) -> Dict[str, str]:
        """Extract Level 2 project names mapped to their UIDs for roadmap grouping"""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        level2_projects = {}
        tasks = root.findall('.//{http://schemas.microsoft.com/project}Task')
        
        for task in tasks:
            outline_elem = self._find_element(task, 'OutlineLevel')
            name_elem = self._find_element(task, 'Name')
            uid_elem = self._find_element(task, 'UID')
            
            if outline_elem and name_elem and uid_elem:
                level = int(outline_elem.text) if outline_elem.text else 0
                if level == 2:  # Level 2 = Project level (updated from Level 3)
                    level2_projects[uid_elem.text] = name_elem.text
        
        return level2_projects
    
    def parse_string(self, xml_content: str) -> Project:
        """Parse MS Project XML from string"""
        root = ET.fromstring(xml_content)
        
        project_data = self._extract_project_info(root)
        project_data['milestones'] = self._extract_milestones(root)
        project_data['risks'] = self._extract_risks(root)
        project_data['changes'] = self._extract_changes(root)
        
        return Project(**project_data)
    
    def _extract_project_info(self, root: ET.Element) -> Dict[str, Any]:
        """Extract project-level information"""
        data = {}
        
        # Project name (required) - try multiple fields
        name_elem = (self._find_element(root, 'Title') or 
                    self._find_element(root, 'Name'))
        data['project_name'] = (
            name_elem.text if name_elem is not None 
            else "Untitled Project"
        )
        
        # Project code (from custom field or generate from name)
        code_elem = root.find('.//ExtendedAttribute[@FieldID="Text1"]/Value')
        if code_elem is not None:
            data['project_code'] = code_elem.text
        else:
            # Generate code from name (first 3 letters + -P1)
            words = data['project_name'].split()
            data['project_code'] = (
                ''.join([w[0].upper() for w in words[:3]]) + '-P1'
            )
        
        # Status
        status_elem = root.find('.//ExtendedAttribute[@FieldID="Text2"]/Value')
        data['status'] = (
            status_elem.text if status_elem is not None 
            else "IN_PROGRESS"
        )
        
        # Dates
        start_elem = root.find('.//StartDate') or root.find('.//Start')
        if start_elem is not None:
            data['start_date'] = self._parse_date(start_elem.text)
        else:
            data['start_date'] = datetime.now().strftime('%Y-%m-%d')
        
        finish_elem = root.find('.//FinishDate') or root.find('.//Finish')
        if finish_elem is not None:
            data['target_completion'] = self._parse_date(finish_elem.text)
        else:
            data['target_completion'] = datetime.now().strftime('%Y-%m-%d')
        
        # Completion percentage (calculate from tasks or use project level)
        percent_elem = root.find('.//PercentComplete')
        if percent_elem is not None:
            data['completion_percentage'] = int(float(percent_elem.text))
        else:
            # Calculate from tasks
            data['completion_percentage'] = 0
        
        return data
    
    def _extract_milestones(self, root: ET.Element) -> List[Milestone]:
        """
        Extract milestones from MS Project XML
        
        Strategy (Updated for new hierarchy):
        - Skip Level 1 (top-level summary)
        - Level 2 = Projects
        - Extract Level 2+ items ONLY if marked as Milestone
        - Milestone detection: Milestone flag=1 OR Duration=0 OR Work=0
        """
        milestones = []
        
        # First, build a map of Level 2 projects for roadmap grouping
        level2_projects = {}
        
        # Try different namespace patterns to find tasks
        tasks = []
        for ns in self.ns_patterns:
            task_xpath = f'.//{ns}Task' if ns else './/Task'
            found_tasks = root.findall(task_xpath)
            if found_tasks:
                tasks = found_tasks
                break
        
        if not tasks:
            # Try with explicit namespace
            ns_xpath = './/{http://schemas.microsoft.com/project}Task'
            tasks = root.findall(ns_xpath)
            
        # Build complete task hierarchy for parent-child relationships
        task_hierarchy = {}  # uid -> {'name', 'level', 'parent_uid'}
        
        for task in tasks:
            outline_level_elem = self._find_element(task, 'OutlineLevel')
            name_elem = self._find_element(task, 'Name')
            uid_elem = self._find_element(task, 'UID')
            
            if outline_level_elem and name_elem and uid_elem:
                level = int(outline_level_elem.text) if outline_level_elem.text else 999
                task_hierarchy[uid_elem.text] = {
                    'name': name_elem.text,
                    'level': level,
                    'uid': uid_elem.text
                }
                
                if level == 2:  # Level 2 = Projects (updated from Level 3)
                    level2_projects[uid_elem.text] = name_elem.text
        
        # Build parent relationships by finding the nearest higher-level task before each task
        task_list = list(task_hierarchy.values())
        for i, task_info in enumerate(task_list):
            if task_info['level'] > 2:  # Only for tasks below Level 2 (updated)
                # Look backwards for the Level 2 parent
                for j in range(i-1, -1, -1):
                    parent_candidate = task_list[j]
                    if parent_candidate['level'] == 2:  # Level 2 parent (updated)
                        task_info['parent_level2'] = parent_candidate['name']
                        # CRITICAL FIX: Update the original dict, not just the copy
                        task_hierarchy[task_info['uid']]['parent_level2'] = parent_candidate['name']
                        break
                    elif parent_candidate['level'] < task_info['level']:
                        # Found a higher level, but keep looking for Level 2
                        continue
        
        for task in tasks:
            # Get outline level first
            outline_level_elem = self._find_element(task, 'OutlineLevel')
            outline_level = (
                int(outline_level_elem.text)
                if outline_level_elem is not None and outline_level_elem.text
                else 999
            )
            
            # Skip Level 1 only (Level 2 is now project level)
            if outline_level <= 1:
                continue
            
            # Skip summary tasks EXCEPT if they might be milestones
            # (Level 2 projects can be summary tasks but also milestones)
            summary = task.find('Summary')
            is_summary = summary is not None and summary.text == '1'
            
            # If it's a summary task, only skip if it's NOT a milestone
            if is_summary:
                # Check milestone indicators before skipping
                is_milestone_flag = self._find_element(task, 'Milestone')
                has_milestone_flag = (
                    is_milestone_flag is not None and
                    is_milestone_flag.text == '1'
                )
                
                duration_elem = self._find_element(task, 'Duration')
                has_zero_duration = False
                if duration_elem is not None and duration_elem.text:
                    has_zero_duration = (
                        'PT0H0M0S' in duration_elem.text or
                        duration_elem.text.startswith('PT0')
                    )
                
                work_elem = self._find_element(task, 'Work')
                has_zero_work = False
                if work_elem is not None and work_elem.text:
                    has_zero_work = (
                        'PT0H0M0S' in work_elem.text or
                        work_elem.text.startswith('PT0') or
                        work_elem.text == '0'
                    )
                
                # Skip summary task only if it's NOT a milestone
                if not (has_milestone_flag or has_zero_duration or
                        has_zero_work):
                    continue
            
            # Now check if this task is actually a milestone
            # (For non-summary tasks, we need to verify milestone status)
            if not is_summary:
                is_milestone_flag = self._find_element(task, 'Milestone')
                has_milestone_flag = (
                    is_milestone_flag is not None and
                    is_milestone_flag.text == '1'
                )
                
                duration_elem = self._find_element(task, 'Duration')
                has_zero_duration = False
                if duration_elem is not None and duration_elem.text:
                    has_zero_duration = (
                        'PT0H0M0S' in duration_elem.text or
                        duration_elem.text.startswith('PT0')
                    )
                
                work_elem = self._find_element(task, 'Work')
                has_zero_work = False
                if work_elem is not None and work_elem.text:
                    has_zero_work = (
                        'PT0H0M0S' in work_elem.text or
                        work_elem.text.startswith('PT0') or
                        work_elem.text == '0'
                    )
                
                # Skip if not a milestone
                if not (has_milestone_flag or has_zero_duration or
                        has_zero_work):
                    continue
            
            # At this point, we know it's a milestone
            milestone_data = {}
            
            # Name (required)
            name_elem = self._find_element(task, 'Name')
            if name_elem is None or not name_elem.text:
                continue
            milestone_data['name'] = name_elem.text
            
            # Target date
            finish_elem = self._find_element(task, 'Finish')
            if finish_elem is not None:
                milestone_data['target_date'] = self._parse_date(
                    finish_elem.text
                )
            else:
                continue  # Skip if no target date
            
            # Status based on percent complete
            percent_elem = self._find_element(task, 'PercentComplete')
            percent = 0
            if percent_elem is not None and percent_elem.text:
                # MS Project stores as decimal (0-1), convert to 0-100
                raw_value = float(percent_elem.text)
                percent = int(raw_value * 100)
                
                # Debug: Log first few to understand the format
                if len(milestones) < 3:
                    print(f"DEBUG: Milestone '{milestone_data['name']}' - "
                          f"Raw %: {raw_value}, Converted: {percent}")
            
            milestone_data['completion_percentage'] = percent
            
            if percent >= 100:  # Use >= to catch rounding issues
                milestone_data['status'] = 'COMPLETED'
                # Check for actual finish date
                actual_finish = self._find_element(task, 'ActualFinish')
                if actual_finish is not None:
                    milestone_data['completion_date'] = self._parse_date(
                        actual_finish.text
                    )
            elif percent > 0:
                milestone_data['status'] = 'IN_PROGRESS'
            else:
                milestone_data['status'] = 'NOT_STARTED'
            
            # Find parent Level 2 project using the hierarchy (updated)
            current_task_uid = self._find_element(task, 'UID')
            parent_project = None
            
            if current_task_uid and current_task_uid.text in task_hierarchy:
                task_info = task_hierarchy[current_task_uid.text]
                parent_project = task_info.get('parent_level2')  # Updated
            
            milestone_data['parent_project'] = parent_project
            
            # Resources - try multiple possible field names
            resources_elem = self._find_element(task, 'ResourceNames')
            if resources_elem is None:
                # Try alternative field names
                resources_elem = self._find_element(task, 'Resources')
            
            if resources_elem is not None and resources_elem.text:
                milestone_data['resources'] = resources_elem.text
                # Debug: Log first few to verify
                if len(milestones) < 3:
                    print(f"DEBUG: Resource found - '{milestone_data['name']}': "
                          f"{resources_elem.text}")
            else:
                # Debug: Log what elements ARE available for first 3 milestones
                if len(milestones) < 3:
                    print(f"DEBUG: No ResourceNames for '{milestone_data['name']}'")
                    print(f"  Available elements: {[elem.tag.split('}')[-1] for elem in task]}")

            
            # Notes
            notes_elem = self._find_element(task, 'Notes')
            if notes_elem is not None and notes_elem.text:
                milestone_data['notes'] = notes_elem.text
            
            milestones.append(Milestone(**milestone_data))
        
        return milestones
    
    def _extract_risks(self, root: ET.Element) -> List[Risk]:
        """Extract risks from custom table or extended attributes"""
        risks = []
        
        # Try to find risks in custom table
        risk_table = root.find('.//RiskTable')
        if risk_table is not None:
            for risk_elem in risk_table.findall('Risk'):
                risk_data = self._parse_risk_element(risk_elem)
                if risk_data:
                    risks.append(Risk(**risk_data))
        
        return risks
    
    def _parse_risk_element(self, elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse individual risk element"""
        risk_id = elem.find('ID')
        description = elem.find('Description')
        
        if risk_id is None or description is None:
            return None
        
        data = {
            'risk_id': risk_id.text,
            'description': description.text,
            'severity': self._get_text(elem, 'Severity', 'MEDIUM'),
            'probability': self._get_text(elem, 'Probability', 'MEDIUM'),
            'impact': self._get_text(elem, 'Impact'),
            'mitigation': self._get_text(elem, 'Mitigation', 'No mitigation defined'),
            'status': self._get_text(elem, 'Status', 'OPEN')
        }
        
        return data
    
    def _extract_changes(self, root: ET.Element) -> List[Change]:
        """Extract schedule changes from custom table"""
        changes = []
        
        # Try to find changes in custom table
        change_table = root.find('.//ChangeTable')
        if change_table is not None:
            for change_elem in change_table.findall('Change'):
                change_data = self._parse_change_element(change_elem)
                if change_data:
                    changes.append(Change(**change_data))
        
        return changes
    
    def _parse_change_element(self, elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse individual change element"""
        change_id = elem.find('ID')
        
        if change_id is None:
            return None
        
        data = {
            'change_id': change_id.text,
            'date': self._get_text(elem, 'Date', datetime.now().strftime('%Y-%m-%d')),
            'old_date': self._get_text(elem, 'OldDate', ''),
            'new_date': self._get_text(elem, 'NewDate', ''),
            'reason': self._get_text(elem, 'Reason', 'Not specified'),
            'impact': self._get_text(elem, 'Impact', 'Unknown')
        }
        
        return data
    
    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats to YYYY-MM-DD"""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        # Try common formats
        formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # If all fails, return today
        return datetime.now().strftime('%Y-%m-%d')
    
    def _find_element(self, parent: ET.Element, tag: str) -> ET.Element:
        """Find element with namespace support"""
        # Try without namespace first
        elem = parent.find(tag)
        if elem is not None:
            return elem
        
        # Try with MS Project namespace
        ns_tag = f'{{http://schemas.microsoft.com/project}}{tag}'
        elem = parent.find(ns_tag)
        return elem

    def _get_text(self, elem: ET.Element, tag: str, default: str = '') -> str:
        """Safely get text from XML element with namespace support"""
        child = self._find_element(elem, tag)
        return child.text if child is not None and child.text else default
