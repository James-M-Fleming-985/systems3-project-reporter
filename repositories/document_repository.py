"""
Document Repository - Server-side persistence for project documents
Stores documents with version control and metadata in a SharePoint-like structure
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime
import uuid
import re
import shutil
import hashlib

logger = logging.getLogger(__name__)


# Standard document categories for programs/projects
DOCUMENT_CATEGORIES = {
    'governance': {
        'name': 'Governance',
        'icon': '📜',
        'types': [
            {'id': 'charter', 'name': 'Project Charter', 'description': 'Authorizing document for the project'},
            {'id': 'business_case', 'name': 'Business Case', 'description': 'Justification and benefits analysis'},
            {'id': 'pmp', 'name': 'Project Management Plan', 'description': 'Overall project management approach'},
            {'id': 'governance_framework', 'name': 'Governance Framework', 'description': 'Decision-making structure'},
        ]
    },
    'scope': {
        'name': 'Scope',
        'icon': '🎯',
        'types': [
            {'id': 'scope_statement', 'name': 'Scope Statement', 'description': 'Detailed scope definition'},
            {'id': 'wbs', 'name': 'Work Breakdown Structure (WBS)', 'description': 'Hierarchical decomposition of work'},
            {'id': 'requirements', 'name': 'Requirements Document', 'description': 'Stakeholder and technical requirements'},
            {'id': 'scope_baseline', 'name': 'Scope Baseline', 'description': 'Approved scope baseline'},
        ]
    },
    'breakdown_structures': {
        'name': 'Breakdown Structures',
        'icon': '🏗️',
        'types': [
            {'id': 'pbs', 'name': 'Product Breakdown Structure (PBS)', 'description': 'Product hierarchy'},
            {'id': 'cbs', 'name': 'Cost Breakdown Structure (CBS)', 'description': 'Cost hierarchy'},
            {'id': 'obs', 'name': 'Organizational Breakdown Structure (OBS)', 'description': 'Organizational hierarchy'},
            {'id': 'rbs', 'name': 'Resource Breakdown Structure (RBS)', 'description': 'Resource categorization'},
            {'id': 'risk_breakdown', 'name': 'Risk Breakdown Structure', 'description': 'Risk categorization'},
        ]
    },
    'schedule': {
        'name': 'Schedule',
        'icon': '📅',
        'types': [
            {'id': 'master_schedule', 'name': 'Master Schedule', 'description': 'High-level program schedule'},
            {'id': 'detailed_schedule', 'name': 'Detailed Schedule', 'description': 'Detailed project schedule'},
            {'id': 'milestone_plan', 'name': 'Milestone Plan', 'description': 'Key milestones and dates'},
            {'id': 'schedule_baseline', 'name': 'Schedule Baseline', 'description': 'Approved schedule baseline'},
        ]
    },
    'financial': {
        'name': 'Financial',
        'icon': '💰',
        'types': [
            {'id': 'budget', 'name': 'Budget', 'description': 'Project budget allocation'},
            {'id': 'cost_estimate', 'name': 'Cost Estimate', 'description': 'Cost estimation documentation'},
            {'id': 'cost_baseline', 'name': 'Cost Baseline', 'description': 'Approved cost baseline'},
            {'id': 'funding_profile', 'name': 'Funding Profile', 'description': 'Funding timeline and sources'},
        ]
    },
    'risk': {
        'name': 'Risk & Quality',
        'icon': '⚠️',
        'types': [
            {'id': 'risk_register', 'name': 'Risk Register', 'description': 'Identified risks and responses'},
            {'id': 'risk_plan', 'name': 'Risk Management Plan', 'description': 'Risk management approach'},
            {'id': 'quality_plan', 'name': 'Quality Management Plan', 'description': 'Quality assurance approach'},
            {'id': 'issue_log', 'name': 'Issue Log', 'description': 'Current issues and actions'},
        ]
    },
    'stakeholder': {
        'name': 'Stakeholder & Comms',
        'icon': '👥',
        'types': [
            {'id': 'stakeholder_register', 'name': 'Stakeholder Register', 'description': 'Stakeholder identification'},
            {'id': 'comms_plan', 'name': 'Communications Plan', 'description': 'Communication strategy'},
            {'id': 'raci', 'name': 'RACI Matrix', 'description': 'Responsibility assignment'},
            {'id': 'org_chart', 'name': 'Organization Chart', 'description': 'Project organization structure'},
        ]
    },
    'reports': {
        'name': 'Reports',
        'icon': '📊',
        'types': [
            {'id': 'status_report', 'name': 'Status Reports', 'description': 'Periodic status updates'},
            {'id': 'dashboard', 'name': 'Dashboard/Metrics', 'description': 'Performance dashboards'},
            {'id': 'lessons_learned', 'name': 'Lessons Learned', 'description': 'Project learnings'},
            {'id': 'closure_report', 'name': 'Project Closure Report', 'description': 'Final project report'},
        ]
    },
    'other': {
        'name': 'Other Documents',
        'icon': '📁',
        'types': [
            {'id': 'contract', 'name': 'Contracts/Agreements', 'description': 'Contractual documents'},
            {'id': 'change_request', 'name': 'Change Requests', 'description': 'Change control documents'},
            {'id': 'meeting_minutes', 'name': 'Meeting Minutes', 'description': 'Meeting records'},
            {'id': 'other', 'name': 'Miscellaneous', 'description': 'Other project documents'},
        ]
    }
}


class DocumentRepository:
    """Repository for persisting project documents with version control"""
    
    def __init__(self, storage_dir: Path):
        """Initialize repository with storage directory"""
        self.storage_dir = storage_dir / "documents"
        self.files_dir = self.storage_dir / "files"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentRepository initialized: {self.storage_dir}")
    
    def _clean_project_name(self, project_name: str) -> str:
        """Clean project name by removing version numbers and file extensions."""
        clean = project_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '')
        clean = re.sub(r'-\d+$', '', clean)
        return clean.strip()
    
    def _get_metadata_file_path(self, project_name: str) -> Path:
        """Get the file path for a project's document metadata"""
        clean_name = self._clean_project_name(project_name)
        clean_name = clean_name.replace('/', '_').replace('\\', '_')
        return self.storage_dir / f"{clean_name}_documents.yaml"
    
    def _get_project_files_dir(self, project_name: str) -> Path:
        """Get the directory for storing project files"""
        clean_name = self._clean_project_name(project_name)
        clean_name = clean_name.replace('/', '_').replace('\\', '_')
        project_dir = self.files_dir / clean_name
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def _generate_file_hash(self, content: bytes) -> str:
        """Generate SHA256 hash for file content"""
        return hashlib.sha256(content).hexdigest()[:16]
    
    def get_documents(self, project_name: str) -> Dict[str, Any]:
        """
        Get all documents metadata for a project
        
        Returns:
            Dict with 'documents' list containing document metadata
        """
        try:
            file_path = self._get_metadata_file_path(project_name)
            
            if not file_path.exists():
                return {
                    'project_name': project_name,
                    'documents': [],
                    'last_updated': None
                }
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            logger.info(f"📄 Loaded {len(data.get('documents', []))} documents for '{project_name}'")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error loading documents for '{project_name}': {e}")
            return {'project_name': project_name, 'documents': [], 'last_updated': None}
    
    def save_metadata(self, project_name: str, data: Dict[str, Any]) -> bool:
        """Save document metadata for a project"""
        try:
            file_path = self._get_metadata_file_path(project_name)
            
            data['project_name'] = project_name
            data['last_updated'] = datetime.now().isoformat()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving documents metadata for '{project_name}': {e}")
            return False
    
    def upload_document(
        self,
        project_name: str,
        category: str,
        doc_type: str,
        file_content: bytes,
        original_filename: str,
        uploaded_by: str = "System",
        description: str = None,
        existing_doc_id: str = None
    ) -> Dict[str, Any]:
        """
        Upload a new document or new version of existing document
        
        Args:
            project_name: Project name
            category: Document category (e.g., 'governance', 'scope')
            doc_type: Document type within category (e.g., 'charter', 'wbs')
            file_content: Binary content of the file
            original_filename: Original filename
            uploaded_by: Username of uploader
            description: Optional description
            existing_doc_id: If provided, creates new version of existing document
            
        Returns:
            Document metadata dict
        """
        try:
            data = self.get_documents(project_name)
            documents = data.get('documents', [])
            
            # Get file extension
            file_ext = Path(original_filename).suffix.lower()
            
            # Generate unique file ID and hash
            file_hash = self._generate_file_hash(file_content)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if existing_doc_id:
                # Find existing document and increment revision
                existing_doc = next((d for d in documents if d['id'] == existing_doc_id), None)
                if existing_doc:
                    doc_id = existing_doc_id
                    current_revision = existing_doc.get('revision', 0)
                    new_revision = current_revision + 1
                    
                    # Store current version in history
                    if 'version_history' not in existing_doc:
                        existing_doc['version_history'] = []
                    
                    existing_doc['version_history'].append({
                        'revision': current_revision,
                        'filename': existing_doc['filename'],
                        'stored_filename': existing_doc['stored_filename'],
                        'uploaded_by': existing_doc.get('uploaded_by'),
                        'uploaded_at': existing_doc.get('uploaded_at'),
                        'file_size': existing_doc.get('file_size'),
                        'description': existing_doc.get('description')
                    })
                    
                    # Update document with new version
                    stored_filename = f"{doc_id}_v{new_revision}_{file_hash}{file_ext}"
                    existing_doc['revision'] = new_revision
                    existing_doc['filename'] = original_filename
                    existing_doc['stored_filename'] = stored_filename
                    existing_doc['uploaded_by'] = uploaded_by
                    existing_doc['uploaded_at'] = datetime.now().isoformat()
                    existing_doc['file_size'] = len(file_content)
                    existing_doc['file_extension'] = file_ext
                    if description:
                        existing_doc['description'] = description
                    
                    doc = existing_doc
                else:
                    raise ValueError(f"Document {existing_doc_id} not found")
            else:
                # Create new document
                doc_id = str(uuid.uuid4())[:8]
                stored_filename = f"{doc_id}_v1_{file_hash}{file_ext}"
                
                doc = {
                    'id': doc_id,
                    'category': category,
                    'doc_type': doc_type,
                    'filename': original_filename,
                    'stored_filename': stored_filename,
                    'revision': 1,
                    'uploaded_by': uploaded_by,
                    'uploaded_at': datetime.now().isoformat(),
                    'file_size': len(file_content),
                    'file_extension': file_ext,
                    'description': description or '',
                    'version_history': []
                }
                documents.append(doc)
            
            # Save file to disk
            project_dir = self._get_project_files_dir(project_name)
            file_path = project_dir / doc['stored_filename']
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Save metadata
            data['documents'] = documents
            self.save_metadata(project_name, data)
            
            logger.info(f"✅ Uploaded document: {original_filename} (rev {doc['revision']}) for '{project_name}'")
            return doc
            
        except Exception as e:
            logger.error(f"❌ Error uploading document: {e}")
            raise
    
    def get_document(self, project_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata by ID"""
        data = self.get_documents(project_name)
        for doc in data.get('documents', []):
            if doc['id'] == doc_id:
                return doc
        return None
    
    def get_document_file(self, project_name: str, doc_id: str, revision: int = None) -> Optional[tuple]:
        """
        Get document file content
        
        Args:
            project_name: Project name
            doc_id: Document ID
            revision: Optional specific revision (None = latest)
            
        Returns:
            Tuple of (file_content, filename, content_type) or None
        """
        try:
            doc = self.get_document(project_name, doc_id)
            if not doc:
                return None
            
            if revision and revision != doc['revision']:
                # Find in version history
                for hist in doc.get('version_history', []):
                    if hist['revision'] == revision:
                        stored_filename = hist['stored_filename']
                        original_filename = hist['filename']
                        break
                else:
                    return None
            else:
                stored_filename = doc['stored_filename']
                original_filename = doc['filename']
            
            project_dir = self._get_project_files_dir(project_name)
            file_path = project_dir / stored_filename
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine content type
            ext = Path(original_filename).suffix.lower()
            content_types = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.ppt': 'application/vnd.ms-powerpoint',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.txt': 'text/plain',
                '.csv': 'text/csv',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
            }
            content_type = content_types.get(ext, 'application/octet-stream')
            
            return (content, original_filename, content_type)
            
        except Exception as e:
            logger.error(f"❌ Error getting document file: {e}")
            return None
    
    def delete_document(self, project_name: str, doc_id: str, delete_files: bool = True) -> bool:
        """Delete a document and optionally its files"""
        try:
            data = self.get_documents(project_name)
            documents = data.get('documents', [])
            
            doc = next((d for d in documents if d['id'] == doc_id), None)
            if not doc:
                return False
            
            if delete_files:
                project_dir = self._get_project_files_dir(project_name)
                
                # Delete current file
                current_file = project_dir / doc['stored_filename']
                if current_file.exists():
                    current_file.unlink()
                
                # Delete version history files
                for hist in doc.get('version_history', []):
                    hist_file = project_dir / hist['stored_filename']
                    if hist_file.exists():
                        hist_file.unlink()
            
            # Remove from metadata
            data['documents'] = [d for d in documents if d['id'] != doc_id]
            self.save_metadata(project_name, data)
            
            logger.info(f"🗑️ Deleted document {doc_id} from '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting document: {e}")
            return False
    
    def get_documents_by_category(self, project_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get documents organized by category
        
        Returns:
            Dict with category IDs as keys and lists of documents as values
        """
        data = self.get_documents(project_name)
        documents = data.get('documents', [])
        
        by_category = {}
        for doc in documents:
            cat = doc.get('category', 'other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(doc)
        
        return by_category
    
    def get_document_categories(self) -> Dict[str, Any]:
        """Get the standard document category structure"""
        return DOCUMENT_CATEGORIES


# Export the categories for use elsewhere
def get_document_categories():
    return DOCUMENT_CATEGORIES
