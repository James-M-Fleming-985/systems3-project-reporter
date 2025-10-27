"""
Feature Integration Module for Milestone Tracker
Feature ID: FEATURE-003-004

This module orchestrates the Date Calculator, Milestone Categorizer, and
Quadrant Formatter layers to provide comprehensive milestone tracking functionality.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import layer implementations
from LAYER_001_Date_Calculator.src.implementation import DateCalculator
from LAYER_002_Milestone_Categorizer.src.implementation import MilestoneCategorizer
from LAYER_003_Quadrant_Formatter.src.implementation import QuadrantFormatter


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for the Milestone Tracker feature."""
    enable_logging: bool = True
    default_date_format: str = "%Y-%m-%d"
    default_quadrant_format: str = "standard"
    max_batch_size: int = 1000


@dataclass
class FeatureResponse:
    """Unified response structure for feature operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FeatureOrchestrator:
    """
    Feature Orchestrator for Milestone Tracker.
    
    Coordinates Date Calculator, Milestone Categorizer, and Quadrant Formatter
    to provide comprehensive milestone tracking and management functionality.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the Milestone Tracker with all required layers.
        
        Args:
            config: Optional configuration for the feature
        """
        self.config = config or FeatureConfig()
        
        try:
            # Initialize layer instances
            self.date_calculator = DateCalculator()
            self.milestone_categorizer = MilestoneCategorizer()
            self.quadrant_formatter = QuadrantFormatter()
            
            if self.config.enable_logging:
                logger.info("Milestone Tracker initialized successfully")
                
        except Exception as e:
            error_msg = f"Failed to initialize Milestone Tracker: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def track_milestone(self, milestone_data: Dict[str, Any]) -> FeatureResponse:
        """
        Track a single milestone with date calculations and categorization.
        
        Args:
            milestone_data: Dictionary containing milestone information
                Expected keys: 'name', 'start_date', 'end_date', 'category', 'priority'
        
        Returns:
            FeatureResponse with tracking results
        """
        try:
            # Validate input
            required_keys = ['name', 'start_date', 'end_date']
            if not all(key in milestone_data for key in required_keys):
                return FeatureResponse(
                    success=False,
                    error=f"Missing required keys. Required: {required_keys}"
                )
            
            # Parse dates
            start_date = datetime.strptime(
                milestone_data['start_date'], 
                self.config.default_date_format
            ).date()
            end_date = datetime.strptime(
                milestone_data['end_date'], 
                self.config.default_date_format
            ).date()
            
            # Calculate milestone duration and metadata
            duration_days = self.date_calculator.days_between(start_date, end_date)
            start_weekday = self.date_calculator.get_weekday(start_date)
            end_weekday = self.date_calculator.get_weekday(end_date)
            start_quarter = self.date_calculator.get_quarter(start_date)
            end_quarter = self.date_calculator.get_quarter(end_date)
            
            # Prepare milestone for categorization
            categorization_data = {
                'name': milestone_data['name'],
                'duration_days': duration_days,
                'start_quarter': start_quarter,
                'end_quarter': end_quarter,
                'priority': milestone_data.get('priority', 'medium'),
                'category': milestone_data.get('category', 'uncategorized')
            }
            
            # Categorize the milestone
            category_result = self.milestone_categorizer.categorize(categorization_data)
            
            # Prepare response data
            response_data = {
                'milestone': milestone_data['name'],
                'duration': {
                    'days': duration_days,
                    'start_weekday': start_weekday,
                    'end_weekday': end_weekday
                },
                'quarters': {
                    'start': start_quarter,
                    'end': end_quarter
                },
                'categorization': category_result
            }
            
            return FeatureResponse(
                success=True,
                data=response_data,
                metadata={
                    'processed_at': datetime.now().isoformat(),
                    'feature_id': 'FEATURE-003-004'
                }
            )
            
        except Exception as e:
            return FeatureResponse(
                success=False,
                error=f"Error tracking milestone: {str(e)}"
            )
    
    def batch_track_milestones(self, milestones: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Track multiple milestones in batch.
        
        Args:
            milestones: List of milestone dictionaries
        
        Returns:
            FeatureResponse with batch processing results
        """
        try:
            if len(milestones) > self.config.max_batch_size:
                return FeatureResponse(
                    success=False,
                    error=f"Batch size exceeds maximum limit of {self.config.max_batch_size}"
                )
            
            # Process each milestone and collect results
            results = []
            errors = []
            
            for idx, milestone in enumerate(milestones):
                result = self.track_milestone(milestone)
                if result.success:
                    results.append(result.data)
                else:
                    errors.append({
                        'index': idx,
                        'milestone': milestone.get('name', 'Unknown'),
                        'error': result.error
                    })
            
            # Process batch categorization
            categorization_batch = [
                {
                    'name': m.get('name'),
                    'category': m.get('category', 'uncategorized')
                }
                for m in milestones
            ]
            
            batch_categories = self.milestone_categorizer.process_batch(categorization_batch)
            
            return FeatureResponse(
                success=len(errors) == 0,
                data={
                    'processed': len(results),
                    'failed': len(errors),
                    'results': results,
                    'batch_categories': batch_categories,
                    'errors': errors if errors else None
                },
                metadata={
                    'total_milestones': len(milestones),
                    'batch_processed_at': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return FeatureResponse(
                success=False,
                error=f"Error in batch processing: {str(e)}"
            )
    
    def create_milestone_quadrant(self, milestones: List[Dict[str, Any]], 
                                  quadrant_config: Optional[Dict[str, Any]] = None) -> FeatureResponse:
        """
        Create a quadrant view of milestones based on urgency and importance.
        
        Args:
            milestones: List of milestone dictionaries
            quadrant_config: Optional configuration for quadrant formatting
        
        Returns:
            FeatureResponse with quadrant visualization
        """
        try:
            # Calculate days remaining for each milestone
            today = date.today()
            quadrant_data = {
                'Q1': [],  # Urgent & Important
                'Q2': [],  # Not Urgent & Important
                'Q3': [],  # Urgent & Not Important
                'Q4': []   # Not Urgent & Not Important
            }
            
            for milestone in milestones:
                # Parse end date
                end_date = datetime.strptime(
                    milestone['end_date'], 
                    self.config.default_date_format
                ).date()
                
                # Calculate days until deadline
                days_remaining = self.date_calculator.days_between(today, end_date)
                
                # Determine urgency (< 30 days = urgent)
                is_urgent = days_remaining < 30
                
                # Get importance from priority
                is_important = milestone.get('priority', 'medium').lower() in ['high', 'critical']
                
                # Assign to quadrant
                if is_urgent and is_important:
                    quadrant_id = 'Q1'
                elif not is_urgent and is_important:
                    quadrant_id = 'Q2'
                elif is_urgent and not is_important:
                    quadrant_id = 'Q3'
                else:
                    quadrant_id = 'Q4'
                
                quadrant_entry = {
                    'name': milestone['name'],
                    'days_remaining': days_remaining,
                    'priority': milestone.get('priority', 'medium'),
                    'category': milestone.get('category', 'uncategorized')
                }
                
                quadrant_data[quadrant_id].append(quadrant_entry)
            
            # Add quadrants to formatter
            for quad_id, items in quadrant_data.items():
                self.quadrant_formatter.add_quadrant({
                    'id': quad_id,
                    'items': items
                })
            
            # Format the quadrant data
            formatted_result = self.quadrant_formatter.format_quadrant_data(quadrant_data)
            
            # Get the formatted output
            formatted_output = self.quadrant_formatter.get_formatted_output()
            
            return FeatureResponse(
                success=True,
                data={
                    'quadrants': formatted_result,
                    'formatted_output': formatted_output,
                    'summary': {
                        'Q1_count': len(quadrant_data['Q1']),
                        'Q2_count': len(quadrant_data['Q2']),
                        'Q3_count': len(quadrant_data['Q3']),
                        'Q4_count': len(quadrant_data['Q4']),
                        'total_milestones': len(milestones)
                    }
                },
                metadata={
                    'reference_date': today.isoformat(),
                    'urgency_threshold_days': 30
                }
            )
            
        except Exception as e:
            return FeatureResponse(
                success=False,
                error=f"Error creating milestone quadrant: {str(e)}"
            )
        finally:
            # Clear formatter for next use
            self.quadrant_formatter.clear()
    
    def analyze_milestone_timeline(self, milestones: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Analyze timeline characteristics of milestones.
        
        Args:
            milestones: List of milestone dictionaries
        
        Returns:
            FeatureResponse with timeline analysis
        """
        try:
            timeline_analysis = {
                'weekend_impacts': [],
                'business_day_calculations': [],
                'quarterly_distribution': {},
                'duration_statistics': {}
            }
            
            durations = []
            
            for milestone in milestones:
                start_date = datetime.strptime(
                    milestone['start_date'], 
                    self.config.default_date_format
                ).date()
                end_date = datetime.strptime(
                    milestone['end_date'], 
                    self.config.default_date_format
                ).date()
                
                # Check weekend impacts
                if self.date_calculator.is_weekend(start_date):
                    timeline_analysis['weekend_impacts'].append({
                        'milestone': milestone['name'],
                        'impact': 'starts_on_weekend',
                        'suggested_date': self.date_calculator.next_business_day(start_date)
                    })
                
                if self.date_calculator.is_weekend(end_date):
                    timeline_analysis['weekend_impacts'].append({
                        'milestone': milestone['name'],
                        'impact': 'ends_on_weekend',
                        'suggested_date': self.date_calculator.previous_business_day(end_date)
                    })
                
                # Calculate duration
                duration = self.date_calculator.days_between(start_date, end_date)
                durations.append(duration)
                
                # Track quarterly distribution
                quarter = self.date_calculator.get_quarter(start_date)
                quarter_key = f"Q{quarter}"
                timeline_analysis['quarterly_distribution'][quarter_key] = \
                    timeline_analysis['quarterly_distribution'].get(quarter_key, 0) + 1
            
            # Calculate duration statistics
            if durations:
                timeline_analysis['duration_statistics'] = {
                    'average': sum(durations) / len(durations),
                    'min': min(durations),
                    'max': max(durations),
                    'total_days': sum(durations)
                }
            
            # Get categorization statistics
            category_stats = self.milestone_categorizer.get_statistics()
            
            return FeatureResponse(
                success=True,
                data={
                    'timeline_analysis': timeline_analysis,
                    'category_statistics': category_stats,
                    'milestone_count': len(milestones)
                },
                metadata={
                    'analysis_date': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return FeatureResponse(
                success=False,
                error=f"Error analyzing milestone timeline: {str(e)}"
            )
    
    def export_milestone_report(self, milestones: List[Dict[str, Any]], 
                               category_filter: Optional[str] = None) -> FeatureResponse:
        """
        Export a comprehensive milestone report with categorization and formatting.
        
        Args:
            milestones: List of milestone dictionaries
            category_filter: Optional category to filter milestones
        
        Returns:
            FeatureResponse with exported report data
        """
        try:
            # Process milestones for categorization
            categorization_data = []
            for milestone in milestones:
                cat_entry = {
                    'name': milestone['name'],
                    'category': milestone.get('category', 'uncategorized'),
                    'priority': milestone.get('priority', 'medium')
                }
                categorization_data.append(cat_entry)
            
            # Get categorization export
            categorization_export = self.milestone_categorizer.export_categorization()
            
            # Apply category filter if specified
            filtered_milestones = milestones
            if category_filter:
                filtered_results = self.milestone_categorizer.filter_by_category(
                    category_filter
                )
                # Filter original milestones based on categorization results
                filtered_names = [item.get('name') for item in filtered_results]
                filtered_milestones = [
                    m for m in milestones 
                    if m['name'] in filtered_names
                ]
            
            # Create report sections
            report = {
                'summary': {
                    'total_milestones': len(milestones),
                    'filtered_milestones': len(filtered_milestones),
                    'filter_applied': category_filter
                },
                'categorization': categorization_export,
                'milestones': []
            }
            
            # Process each filtered milestone
            for milestone in filtered_milestones:
                start_date = datetime.strptime(
                    milestone['start_date'], 
                    self.config.default_date_format
                ).date()
                end_date = datetime.strptime(
                    milestone['end_date'], 
                    self.config.default_date_format
                ).date()
                
                milestone_report = {
                    'name': milestone['name'],
                    'category': milestone.get('category', 'uncategorized'),
                    'priority': milestone.get('priority', 'medium'),
                    'timeline': {
                        'start_date': milestone['start_date'],
                        'end_date': milestone['end_date'],
                        'duration_days': self.date_calculator.days_between(start_date, end_date),
                        'start_month': self.date_calculator.get_month_name(start_date.month),
                        'end_month': self.date_calculator.get_month_name(end_date.month)
                    }
                }
                report['milestones'].append(milestone_report)
            
            return FeatureResponse(
                success=True,
                data=report,
                metadata={
                    'export_date': datetime.now().isoformat(),
                    'feature_id': 'FEATURE-003-004'
                }
            )
            
        except Exception as e:
            return FeatureResponse(
                success=False,
                error=f"Error exporting milestone report: {str(e)}"
            )


# Feature entry point for external usage
def create_milestone_tracker(config: Optional[FeatureConfig] = None) -> FeatureOrchestrator:
    """
    Factory function to create a Milestone Tracker instance.
    
    Args:
        config: Optional configuration for the feature
    
    Returns:
        FeatureOrchestrator instance
    """
    return FeatureOrchestrator(config)