from typing import Dict, List, Union, Optional
import json
from datetime import datetime


class InvalidMilestoneError(Exception):
    """Raised when milestone data is invalid."""
    pass


class MilestoneCategorizerError(Exception):
    """Base exception for MilestoneCategorizeer errors."""
    pass


class MilestoneCategorizer:
    """
    Categorizes milestones based on their attributes and relationships.
    
    This class processes milestone data and categorizes them according to
    predefined rules and criteria.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the MilestoneCategorizer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.categories = {
            'planning': ['design', 'planning', 'research', 'analysis'],
            'development': ['coding', 'development', 'implementation', 'build'],
            'testing': ['test', 'qa', 'quality', 'validation'],
            'deployment': ['deploy', 'release', 'launch', 'rollout'],
            'maintenance': ['support', 'maintenance', 'fix', 'patch']
        }
        self._initialized = True
        
    def categorize(self, milestones: Union[List[Dict], Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize milestones based on their attributes.
        
        Args:
            milestones: List of milestone dictionaries or single milestone
            
        Returns:
            Dictionary with categories as keys and lists of milestones as values
            
        Raises:
            InvalidMilestoneError: If milestone data is invalid
            MilestoneCategorizerError: For other categorization errors
        """
        if not isinstance(milestones, (list, dict)):
            raise InvalidMilestoneError("Milestones must be a list or dictionary")
            
        if isinstance(milestones, dict):
            milestones = [milestones]
            
        if not milestones:
            return {}
            
        categorized = {category: [] for category in self.categories}
        categorized['uncategorized'] = []
        
        for milestone in milestones:
            if not isinstance(milestone, dict):
                raise InvalidMilestoneError(f"Invalid milestone format: {type(milestone)}")
                
            if not milestone:
                continue
                
            self._validate_milestone(milestone)
            category = self._determine_category(milestone)
            
            if category in categorized:
                categorized[category].append(milestone)
            else:
                categorized['uncategorized'].append(milestone)
                
        # Remove empty categories
        return {k: v for k, v in categorized.items() if v}
        
    def _validate_milestone(self, milestone: Dict) -> None:
        """
        Validate milestone data structure.
        
        Args:
            milestone: Milestone dictionary to validate
            
        Raises:
            InvalidMilestoneError: If milestone is invalid
        """
        required_fields = {'name', 'status'}
        milestone_keys = set(milestone.keys())
        
        missing_fields = required_fields - milestone_keys
        if missing_fields:
            raise InvalidMilestoneError(f"Missing required fields: {missing_fields}")
            
        if not milestone.get('name'):
            raise InvalidMilestoneError("Milestone name cannot be empty")
            
    def _determine_category(self, milestone: Dict) -> str:
        """
        Determine the category of a milestone.
        
        Args:
            milestone: Milestone dictionary
            
        Returns:
            Category name as string
        """
        name = milestone.get('name', '').lower()
        description = milestone.get('description', '').lower()
        tags = milestone.get('tags', [])
        
        # Check tags first
        if isinstance(tags, list):
            for tag in tags:
                tag_lower = str(tag).lower()
                for category, keywords in self.categories.items():
                    if any(keyword in tag_lower for keyword in keywords):
                        return category
                        
        # Check name and description
        combined_text = f"{name} {description}"
        
        for category, keywords in self.categories.items():
            if any(keyword in combined_text for keyword in keywords):
                return category
                
        # Check status-based categorization
        status = milestone.get('status', '').lower()
        if status in ['completed', 'done']:
            if 'deploy' in combined_text:
                return 'deployment'
        elif status == 'in_progress':
            if any(keyword in combined_text for keyword in ['code', 'develop']):
                return 'development'
                
        return 'uncategorized'
        
    def process_batch(self, milestone_batches: List[List[Dict]]) -> List[Dict[str, List[Dict]]]:
        """
        Process multiple batches of milestones.
        
        Args:
            milestone_batches: List of milestone batches
            
        Returns:
            List of categorization results for each batch
            
        Raises:
            MilestoneCategorizerError: If batch processing fails
        """
        if not isinstance(milestone_batches, list):
            raise MilestoneCategorizerError("Batches must be provided as a list")
            
        results = []
        
        for i, batch in enumerate(milestone_batches):
            try:
                result = self.categorize(batch)
                results.append(result)
            except Exception as e:
                raise MilestoneCategorizerError(f"Failed to process batch {i}: {str(e)}")
                
        return results
        
    def add_category(self, category_name: str, keywords: List[str]) -> None:
        """
        Add a new category with associated keywords.
        
        Args:
            category_name: Name of the new category
            keywords: List of keywords for the category
            
        Raises:
            ValueError: If category name or keywords are invalid
        """
        if not category_name or not isinstance(category_name, str):
            raise ValueError("Category name must be a non-empty string")
            
        if not keywords or not isinstance(keywords, list):
            raise ValueError("Keywords must be a non-empty list")
            
        if not all(isinstance(k, str) and k for k in keywords):
            raise ValueError("All keywords must be non-empty strings")
            
        self.categories[category_name.lower()] = [k.lower() for k in keywords]
        
    def get_statistics(self, categorized_data: Dict[str, List[Dict]]) -> Dict[str, Union[int, float]]:
        """
        Calculate statistics for categorized milestones.
        
        Args:
            categorized_data: Categorized milestone data
            
        Returns:
            Dictionary containing statistics
        """
        total_count = sum(len(milestones) for milestones in categorized_data.values())
        
        stats = {
            'total_milestones': total_count,
            'categories_count': len(categorized_data)
        }
        
        for category, milestones in categorized_data.items():
            stats[f'{category}_count'] = len(milestones)
            if total_count > 0:
                stats[f'{category}_percentage'] = (len(milestones) / total_count) * 100
            else:
                stats[f'{category}_percentage'] = 0.0
                
        return stats
        
    def export_categorization(self, categorized_data: Dict[str, List[Dict]], 
                            format: str = 'json') -> Union[str, Dict]:
        """
        Export categorization results in specified format.
        
        Args:
            categorized_data: Categorized milestone data
            format: Export format ('json' or 'dict')
            
        Returns:
            Exported data in specified format
            
        Raises:
            ValueError: If format is not supported
        """
        if format not in ['json', 'dict']:
            raise ValueError(f"Unsupported format: {format}")
            
        if format == 'json':
            return json.dumps(categorized_data, indent=2)
        else:
            return categorized_data
            
    def filter_by_category(self, categorized_data: Dict[str, List[Dict]], 
                          categories: List[str]) -> Dict[str, List[Dict]]:
        """
        Filter categorized data to include only specified categories.
        
        Args:
            categorized_data: Categorized milestone data
            categories: List of categories to include
            
        Returns:
            Filtered categorization data
        """
        return {
            category: milestones 
            for category, milestones in categorized_data.items() 
            if category in categories
        }
        
    def merge_categorizations(self, *categorizations: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Merge multiple categorization results.
        
        Args:
            *categorizations: Variable number of categorization dictionaries
            
        Returns:
            Merged categorization data
        """
        merged = {}
        
        for categorization in categorizations:
            for category, milestones in categorization.items():
                if category not in merged:
                    merged[category] = []
                merged[category].extend(milestones)
                
        return merged


def create_categorizer(config: Optional[Dict] = None) -> MilestoneCategorizer:
    """
    Factory function to create a MilestoneCategorizer instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        MilestoneCategorizer instance
    """
    return MilestoneCategorizer(config)
