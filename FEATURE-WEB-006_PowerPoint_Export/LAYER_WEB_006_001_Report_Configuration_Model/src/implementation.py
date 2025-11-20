from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator
import json


class TemplateSettings(BaseModel):
    """PowerPoint template settings.
    
    Example:
        >>> settings = TemplateSettings(
        ...     template_path="templates/default.pptx",
        ...     theme_name="Corporate",
        ...     color_scheme={"primary": "#007bff", "secondary": "#6c757d"}
        ... )
        >>> print(settings.template_path)
        templates/default.pptx
    """
    template_path: str = Field(..., description="Path to PowerPoint template file")
    theme_name: str = Field(..., description="Name of the theme")
    color_scheme: Dict[str, str] = Field(..., description="Color scheme mapping")
    
    @validator('template_path')
    def validate_template_path(cls, v):
        if not v:
            raise ValueError("Template path cannot be empty")
        return v
    
    @validator('theme_name')
    def validate_theme_name(cls, v):
        if not v:
            raise ValueError("Theme name cannot be empty")
        return v


class SlideConfiguration(BaseModel):
    """Configuration for individual slides.
    
    Example:
        >>> slide = SlideConfiguration(
        ...     slide_type="title",
        ...     layout_index=0,
        ...     content_mappings={"title": "report.title", "subtitle": "report.date"}
        ... )
        >>> print(slide.slide_type)
        title
    """
    slide_type: str = Field(..., description="Type of slide")
    layout_index: int = Field(..., ge=0, description="Layout index in template")
    content_mappings: Dict[str, str] = Field(..., description="Mapping of content to slide elements")
    
    @validator('slide_type')
    def validate_slide_type(cls, v):
        if not v:
            raise ValueError("Slide type cannot be empty")
        return v


class ExportSettings(BaseModel):
    """Export settings for PowerPoint generation.
    
    Example:
        >>> settings = ExportSettings(
        ...     file_format="pptx",
        ...     compression_enabled=True,
        ...     include_speaker_notes=False
        ... )
        >>> print(settings.file_format)
        pptx
    """
    file_format: str = Field(default="pptx", description="Output file format")
    compression_enabled: bool = Field(default=True, description="Enable compression")
    include_speaker_notes: bool = Field(default=False, description="Include speaker notes")
    
    @validator('file_format')
    def validate_file_format(cls, v):
        allowed_formats = ["pptx", "pdf"]
        if v not in allowed_formats:
            raise ValueError(f"File format must be one of {allowed_formats}")
        return v


class DataSourceMapping(BaseModel):
    """Mapping configuration for data sources.
    
    Example:
        >>> mapping = DataSourceMapping(
        ...     source_type="database",
        ...     connection_string="postgresql://localhost/reports",
        ...     query_template="SELECT * FROM reports WHERE id = :report_id"
        ... )
        >>> print(mapping.source_type)
        database
    """
    source_type: str = Field(..., description="Type of data source")
    connection_string: str = Field(..., description="Connection string")
    query_template: Optional[str] = Field(None, description="Query template for data retrieval")
    
    @validator('source_type')
    def validate_source_type(cls, v):
        allowed_types = ["database", "api", "file", "memory"]
        if v not in allowed_types:
            raise ValueError(f"Source type must be one of {allowed_types}")
        return v
    
    @validator('connection_string')
    def validate_connection_string(cls, v):
        if not v:
            raise ValueError("Connection string cannot be empty")
        return v


class ValidationRule(BaseModel):
    """Validation rules for report data.
    
    Example:
        >>> rule = ValidationRule(
        ...     field_name="revenue",
        ...     rule_type="range",
        ...     parameters={"min": 0, "max": 1000000}
        ... )
        >>> print(rule.field_name)
        revenue
    """
    field_name: str = Field(..., description="Field to validate")
    rule_type: str = Field(..., description="Type of validation rule")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")
    error_message: Optional[str] = Field(None, description="Custom error message")
    
    @validator('field_name')
    def validate_field_name(cls, v):
        if not v:
            raise ValueError("Field name cannot be empty")
        return v
    
    @validator('rule_type')
    def validate_rule_type(cls, v):
        allowed_types = ["required", "range", "pattern", "custom"]
        if v not in allowed_types:
            raise ValueError(f"Rule type must be one of {allowed_types}")
        return v


class ReportConfiguration(BaseModel):
    """Complete report configuration model.
    
    Example:
        >>> config = ReportConfiguration(
        ...     name="Quarterly Report",
        ...     description="Q4 2023 Financial Report",
        ...     template_settings=TemplateSettings(
        ...         template_path="templates/quarterly.pptx",
        ...         theme_name="Financial",
        ...         color_scheme={"primary": "#003366", "secondary": "#666666"}
        ...     ),
        ...     slides=[
        ...         SlideConfiguration(
        ...             slide_type="title",
        ...             layout_index=0,
        ...             content_mappings={"title": "report.title"}
        ...         )
        ...     ],
        ...     export_settings=ExportSettings(file_format="pptx"),
        ...     data_sources=[
        ...         DataSourceMapping(
        ...             source_type="database",
        ...             connection_string="postgresql://localhost/reports"
        ...         )
        ...     ]
        ... )
        >>> print(config.name)
        Quarterly Report
    """
    name: str = Field(..., description="Report configuration name")
    description: Optional[str] = Field(None, description="Report description")
    template_settings: TemplateSettings = Field(..., description="Template settings")
    slides: List[SlideConfiguration] = Field(..., description="Slide configurations")
    export_settings: ExportSettings = Field(..., description="Export settings")
    data_sources: List[DataSourceMapping] = Field(..., description="Data source mappings")
    validation_rules: List[ValidationRule] = Field(default_factory=list, description="Validation rules")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    @validator('name')
    def validate_name(cls, v):
        if not v:
            raise ValueError("Report name cannot be empty")
        return v
    
    @validator('slides')
    def validate_slides(cls, v):
        if not v:
            raise ValueError("At least one slide must be configured")
        return v
    
    @validator('data_sources')
    def validate_data_sources(cls, v):
        if not v:
            raise ValueError("At least one data source must be configured")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_slide_indices(cls, values):
        slides = values.get('slides', [])
        indices = [slide.layout_index for slide in slides]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate slide layout indices found")
        return values
    
    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return self.json(exclude_none=True, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ReportConfiguration':
        """Create configuration from JSON string."""
        return cls.parse_raw(json_str)
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate data against configured rules."""
        for rule in self.validation_rules:
            field_value = data.get(rule.field_name)
            
            if rule.rule_type == "required":
                if field_value is None:
                    raise ValueError(rule.error_message or f"Field {rule.field_name} is required")
            
            elif rule.rule_type == "range":
                if field_value is not None:
                    min_val = rule.parameters.get("min")
                    max_val = rule.parameters.get("max")
                    if min_val is not None and field_value < min_val:
                        raise ValueError(rule.error_message or f"Field {rule.field_name} is below minimum value {min_val}")
                    if max_val is not None and field_value > max_val:
                        raise ValueError(rule.error_message or f"Field {rule.field_name} is above maximum value {max_val}")
            
            elif rule.rule_type == "pattern":
                if field_value is not None:
                    import re
                    pattern = rule.parameters.get("pattern")
                    if pattern and not re.match(pattern, str(field_value)):
                        raise ValueError(rule.error_message or f"Field {rule.field_name} does not match pattern {pattern}")
        
        return True
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Monthly Sales Report",
                "description": "Sales performance report for the month",
                "template_settings": {
                    "template_path": "templates/sales.pptx",
                    "theme_name": "Sales",
                    "color_scheme": {"primary": "#28a745", "secondary": "#ffc107"}
                },
                "slides": [
                    {
                        "slide_type": "title",
                        "layout_index": 0,
                        "content_mappings": {"title": "report.title", "date": "report.date"}
                    }
                ],
                "export_settings": {
                    "file_format": "pptx",
                    "compression_enabled": True,
                    "include_speaker_notes": False
                },
                "data_sources": [
                    {
                        "source_type": "database",
                        "connection_string": "postgresql://localhost/sales",
                        "query_template": "SELECT * FROM sales WHERE month = :month"
                    }
                ],
                "validation_rules": [
                    {
                        "field_name": "total_sales",
                        "rule_type": "range",
                        "parameters": {"min": 0}
                    }
                ]
            }
        }
