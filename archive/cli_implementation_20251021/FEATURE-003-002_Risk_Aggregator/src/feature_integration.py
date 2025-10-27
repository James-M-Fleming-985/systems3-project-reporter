"""
Feature Integration Module for Risk Aggregator
Feature ID: FEATURE-003-002

This module orchestrates the Risk File Reader, Risk Filter Logic, and Risk Table Formatter layers
to provide comprehensive risk aggregation functionality.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
import logging
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_001_Risk_File_Reader.src.implementation import RiskData, RiskFileReader, RiskFileProcessor
from LAYER_002_Risk_Filter_Logic.src.implementation import RiskFilter, RiskFilterService
from LAYER_003_Risk_Table_Formatter.src.implementation import RiskTableFormatter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for Risk Aggregator feature"""
    risk_file_paths: List[str]
    filter_enabled: bool = True
    format_output: bool = True
    default_risk_level: str = "medium"
    max_batch_size: int = 100
    enable_caching: bool = True


@dataclass
class FeatureResponse:
    """Unified response structure for feature operations"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class FeatureOrchestrator:
    """
    Orchestrates Risk Aggregator feature by coordinating between:
    - Risk File Reader: Reads and processes risk data from files
    - Risk Filter Logic: Filters and analyzes risk metrics
    - Risk Table Formatter: Formats risk data for presentation
    """

    def __init__(self, config: FeatureConfig):
        """
        Initialize the Risk Aggregator orchestrator

        Args:
            config: Feature configuration parameters
        """
        self.config = config
        self._initialized = False
        
        # Initialize layer components
        try:
            # self.risk_file_reader = RiskFileReader()  # Instantiate when needed with file_path
            self.risk_file_processor = RiskFileProcessor()
            self.risk_filter = RiskFilter()
            self.risk_filter_service = RiskFilterService()
            self.risk_table_formatter = RiskTableFormatter()
            
            self._initialized = True
            logger.info("Risk Aggregator orchestrator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Risk Aggregator: {str(e)}")
            raise

    def process_risk_files(self, file_paths: Optional[List[str]] = None) -> FeatureResponse:
        """
        Process multiple risk files and aggregate the data

        Args:
            file_paths: List of file paths to process. Uses config paths if not provided

        Returns:
            FeatureResponse with aggregated risk data
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            paths = file_paths or self.config.risk_file_paths
            
            # Add files to processor
            for path in paths:
                try:
                    # Read and validate each file
                    # Create reader for this specific file
                    risk_file_reader = RiskFileReader(path)
                    risk_data = risk_file_reader.read(path)
                    if risk_file_reader.validate(risk_data):
                        self.risk_file_processor.add_file(path)
                    else:
                        logger.warning(f"Validation failed for file: {path}")
                except Exception as e:
                    logger.error(f"Error processing file {path}: {str(e)}")
                    continue

            # Process all files
            self.risk_file_processor.process_all()
            
            # Get aggregated summary
            summary = self.risk_file_processor.get_aggregated_summary()

            return FeatureResponse(
                success=True,
                data=summary,
                metadata={
                    "files_processed": len(paths),
                    "timestamp": datetime.now().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"Error in process_risk_files: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def filter_risks_by_trade_batch(self, trades: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Filter risks based on trade batch data

        Args:
            trades: List of trade dictionaries to process

        Returns:
            FeatureResponse with filtered risk metrics
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            if not self.config.filter_enabled:
                return FeatureResponse(
                    success=True,
                    data=trades,
                    metadata={"filter_applied": False}
                )

            # Process trade batch through filter service
            filtered_results = self.risk_filter_service.process_trade_batch(trades)
            
            # Get service status
            service_status = self.risk_filter_service.get_service_status()

            return FeatureResponse(
                success=True,
                data=filtered_results,
                metadata={
                    "filter_applied": True,
                    "service_status": service_status,
                    "trades_processed": len(trades)
                }
            )

        except Exception as e:
            logger.error(f"Error in filter_risks_by_trade_batch: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def get_formatted_risk_report(self, risk_level: Optional[str] = None) -> FeatureResponse:
        """
        Generate a formatted risk report

        Args:
            risk_level: Specific risk level to report on (optional)

        Returns:
            FeatureResponse with formatted risk report
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Get risks by level if specified
            if risk_level:
                risks = self.risk_file_reader.get_risks_by_level(risk_level)
            else:
                risks = self.risk_file_reader.get_all_risks()

            if not risks:
                return FeatureResponse(
                    success=True,
                    data=[],
                    metadata={"risk_level": risk_level, "count": 0}
                )

            # Format the risk data if enabled
            if self.config.format_output:
                formatted_data = []
                for risk in risks:
                    # Validate risk structure
                    if self.risk_table_formatter.validate_risk_structure(risk):
                        # Format individual risk data
                        formatted = self.risk_table_formatter.format_risk_data(risk)
                        # Add formatting metadata
                        formatted_with_meta = self.risk_table_formatter.add_formatting_metadata(formatted)
                        formatted_data.append(formatted_with_meta)
                    else:
                        logger.warning(f"Invalid risk structure: {risk}")
            else:
                formatted_data = risks

            return FeatureResponse(
                success=True,
                data=formatted_data,
                metadata={
                    "risk_level": risk_level,
                    "count": len(formatted_data),
                    "formatted": self.config.format_output
                }
            )

        except Exception as e:
            logger.error(f"Error in get_formatted_risk_report: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def get_risk_summary(self) -> FeatureResponse:
        """
        Get a comprehensive risk summary

        Returns:
            FeatureResponse with risk summary data
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Get risk summary from file reader
            summary = self.risk_file_reader.get_risk_summary()

            # Get risk metrics from filter
            metrics = self.risk_filter.get_risk_metrics()

            # Combine data
            combined_summary = {
                "file_summary": summary,
                "filter_metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }

            return FeatureResponse(
                success=True,
                data=combined_summary,
                metadata={"source": "combined"}
            )

        except Exception as e:
            logger.error(f"Error in get_risk_summary: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def export_risks_to_json(self, output_path: str) -> FeatureResponse:
        """
        Export all risks to a JSON file

        Args:
            output_path: Path where JSON file should be saved

        Returns:
            FeatureResponse indicating success/failure
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Export to JSON using file reader
            self.risk_file_reader.export_to_json(output_path)

            return FeatureResponse(
                success=True,
                data={"output_path": output_path},
                metadata={"exported_at": datetime.now().isoformat()}
            )

        except Exception as e:
            logger.error(f"Error in export_risks_to_json: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def update_risk_metrics(self, pnl_data: Dict[str, float]) -> FeatureResponse:
        """
        Update risk metrics with P&L data

        Args:
            pnl_data: Dictionary of P&L data

        Returns:
            FeatureResponse with update status
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Update P&L in risk filter
            self.risk_filter.update_pnl(pnl_data)

            # Get updated metrics
            updated_metrics = self.risk_filter.get_risk_metrics()

            return FeatureResponse(
                success=True,
                data=updated_metrics,
                metadata={"pnl_updated": True}
            )

        except Exception as e:
            logger.error(f"Error in update_risk_metrics: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def reset_daily_metrics(self) -> FeatureResponse:
        """
        Reset daily risk metrics

        Returns:
            FeatureResponse with reset status
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Reset metrics in risk filter
            self.risk_filter.reset_daily_metrics()

            return FeatureResponse(
                success=True,
                data={"status": "metrics_reset"},
                metadata={"reset_at": datetime.now().isoformat()}
            )

        except Exception as e:
            logger.error(f"Error in reset_daily_metrics: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )

    def get_risk_by_id(self, risk_id: str) -> FeatureResponse:
        """
        Get specific risk by ID

        Args:
            risk_id: ID of the risk to retrieve

        Returns:
            FeatureResponse with risk data
        """
        try:
            if not self._initialized:
                return FeatureResponse(
                    success=False,
                    error="Orchestrator not properly initialized"
                )

            # Get risk by ID
            risk = self.risk_file_reader.get_risk_by_id(risk_id)

            if not risk:
                return FeatureResponse(
                    success=False,
                    error=f"Risk with ID {risk_id} not found"
                )

            # Format if enabled
            if self.config.format_output:
                if self.risk_table_formatter.validate_risk_structure(risk):
                    formatted_risk = self.risk_table_formatter.format_risk_data(risk)
                    risk = self.risk_table_formatter.add_formatting_metadata(formatted_risk)

            return FeatureResponse(
                success=True,
                data=risk,
                metadata={"risk_id": risk_id}
            )

        except Exception as e:
            logger.error(f"Error in get_risk_by_id: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )