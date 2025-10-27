import pandas as pd
import numpy as np
from typing import Dict, List, Union, Optional, Any
import json
from datetime import datetime, timedelta
import warnings


class ChartDataPreparation:
    """
    A class for preparing and transforming data for chart visualization.
    Handles various data transformations including aggregation, filtering,
    and formatting for different chart types.
    """
    
    def __init__(self):
        """Initialize the ChartDataPreparation class."""
        self.supported_chart_types = [
            'line', 'bar', 'pie', 'scatter', 'histogram', 
            'box', 'heatmap', 'area', 'bubble', 'radar'
        ]
        self.aggregation_functions = {
            'sum': np.sum,
            'mean': np.mean,
            'median': np.median,
            'count': len,
            'min': np.min,
            'max': np.max,
            'std': np.std,
            'var': np.var
        }
    
    def prepare_data(self, 
                     data: Union[pd.DataFrame, Dict, List],
                     chart_type: str,
                     x_column: Optional[str] = None,
                     y_column: Optional[str] = None,
                     group_by: Optional[str] = None,
                     aggregation: str = 'sum',
                     filters: Optional[Dict[str, Any]] = None,
                     sort_by: Optional[str] = None,
                     sort_order: str = 'asc',
                     top_n: Optional[int] = None,
                     date_format: Optional[str] = None,
                     normalize: bool = False,
                     fill_missing: Optional[Union[str, float]] = None,
                     custom_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Prepare data for chart visualization.
        
        Parameters:
        -----------
        data : Union[pd.DataFrame, Dict, List]
            Input data to be processed
        chart_type : str
            Type of chart to prepare data for
        x_column : Optional[str]
            Column name for x-axis
        y_column : Optional[str]
            Column name for y-axis
        group_by : Optional[str]
            Column to group data by
        aggregation : str
            Aggregation function to apply
        filters : Optional[Dict[str, Any]]
            Filters to apply to the data
        sort_by : Optional[str]
            Column to sort by
        sort_order : str
            Sort order ('asc' or 'desc')
        top_n : Optional[int]
            Number of top items to keep
        date_format : Optional[str]
            Format for date columns
        normalize : bool
            Whether to normalize the data
        fill_missing : Optional[Union[str, float]]
            Value to fill missing data with
        custom_labels : Optional[Dict[str, str]]
            Custom labels for columns
        
        Returns:
        --------
        Dict[str, Any]
            Prepared data ready for chart rendering
        """
        # Validate inputs
        self._validate_inputs(chart_type, aggregation)
        
        # Convert input data to DataFrame
        df = self._convert_to_dataframe(data)
        
        # Apply filters
        if filters:
            df = self._apply_filters(df, filters)
        
        # Handle missing values
        if fill_missing is not None:
            df = self._handle_missing_values(df, fill_missing)
        
        # Process based on chart type
        if chart_type == 'pie':
            result = self._prepare_pie_data(df, y_column, group_by, aggregation)
        elif chart_type == 'scatter':
            result = self._prepare_scatter_data(df, x_column, y_column)
        elif chart_type == 'histogram':
            result = self._prepare_histogram_data(df, y_column)
        elif chart_type == 'box':
            result = self._prepare_box_data(df, y_column, group_by)
        elif chart_type == 'heatmap':
            result = self._prepare_heatmap_data(df, x_column, y_column, group_by)
        elif chart_type == 'bubble':
            result = self._prepare_bubble_data(df, x_column, y_column)
        elif chart_type == 'radar':
            result = self._prepare_radar_data(df, group_by, y_column)
        else:  # line, bar, area
            result = self._prepare_standard_data(df, x_column, y_column, group_by, aggregation)
        
        # Apply sorting
        if sort_by:
            result = self._apply_sorting(result, sort_by, sort_order)
        
        # Apply top N filtering
        if top_n:
            result = self._apply_top_n(result, top_n)
        
        # Apply normalization
        if normalize:
            result = self._normalize_data(result)
        
        # Format dates
        if date_format:
            result = self._format_dates(result, date_format)
        
        # Apply custom labels
        if custom_labels:
            result = self._apply_custom_labels(result, custom_labels)
        
        # Add metadata
        result['metadata'] = {
            'chart_type': chart_type,
            'record_count': len(df),
            'processed_at': datetime.now().isoformat()
        }
        
        return result
    
    def _validate_inputs(self, chart_type: str, aggregation: str) -> None:
        """Validate input parameters."""
        if chart_type not in self.supported_chart_types:
            raise ValueError(f"Unsupported chart type: {chart_type}")
        
        if aggregation not in self.aggregation_functions:
            raise ValueError(f"Unsupported aggregation function: {aggregation}")
    
    def _convert_to_dataframe(self, data: Union[pd.DataFrame, Dict, List]) -> pd.DataFrame:
        """Convert input data to pandas DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data.copy()
        elif isinstance(data, dict):
            return pd.DataFrame(data)
        elif isinstance(data, list):
            return pd.DataFrame(data)
        else:
            raise ValueError("Data must be a pandas DataFrame, dictionary, or list")
    
    def _apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Apply filters to the DataFrame."""
        for column, value in filters.items():
            if column not in df.columns:
                continue
            
            if isinstance(value, dict):
                if 'min' in value:
                    df = df[df[column] >= value['min']]
                if 'max' in value:
                    df = df[df[column] <= value['max']]
                if 'in' in value:
                    df = df[df[column].isin(value['in'])]
                if 'not_in' in value:
                    df = df[~df[column].isin(value['not_in'])]
            else:
                df = df[df[column] == value]
        
        return df
    
    def _handle_missing_values(self, df: pd.DataFrame, fill_value: Union[str, float]) -> pd.DataFrame:
        """Handle missing values in the DataFrame."""
        if isinstance(fill_value, str):
            if fill_value == 'forward':
                return df.fillna(method='ffill')
            elif fill_value == 'backward':
                return df.fillna(method='bfill')
            elif fill_value == 'mean':
                return df.fillna(df.mean())
            elif fill_value == 'median':
                return df.fillna(df.median())
            else:
                return df.fillna(fill_value)
        else:
            return df.fillna(fill_value)
    
    def _prepare_standard_data(self, df: pd.DataFrame, x_column: str, y_column: str, 
                              group_by: Optional[str], aggregation: str) -> Dict[str, Any]:
        """Prepare data for standard charts (line, bar, area)."""
        if not x_column or not y_column:
            raise ValueError("x_column and y_column must be specified")
        
        if group_by:
            grouped = df.groupby([group_by, x_column])[y_column].agg(
                self.aggregation_functions[aggregation]
            ).reset_index()
            
            series = []
            for group_value in grouped[group_by].unique():
                group_data = grouped[grouped[group_by] == group_value]
                series.append({
                    'name': str(group_value),
                    'data': group_data[[x_column, y_column]].values.tolist()
                })
            
            return {
                'series': series,
                'categories': sorted(df[x_column].unique().tolist())
            }
        else:
            agg_data = df.groupby(x_column)[y_column].agg(
                self.aggregation_functions[aggregation]
            ).reset_index()
            
            return {
                'series': [{
                    'name': y_column,
                    'data': agg_data[[x_column, y_column]].values.tolist()
                }],
                'categories': agg_data[x_column].tolist()
            }
    
    def _prepare_pie_data(self, df: pd.DataFrame, value_column: str, 
                         label_column: Optional[str], aggregation: str) -> Dict[str, Any]:
        """Prepare data for pie charts."""
        if not value_column:
            raise ValueError("value_column must be specified for pie charts")
        
        if label_column:
            agg_data = df.groupby(label_column)[value_column].agg(
                self.aggregation_functions[aggregation]
            ).reset_index()
            
            data = []
            for _, row in agg_data.iterrows():
                data.append({
                    'name': str(row[label_column]),
                    'value': float(row[value_column])
                })
        else:
            total = self.aggregation_functions[aggregation](df[value_column])
            data = [{'name': value_column, 'value': float(total)}]
        
        return {'data': data}
    
    def _prepare_scatter_data(self, df: pd.DataFrame, x_column: str, y_column: str) -> Dict[str, Any]:
        """Prepare data for scatter plots."""
        if not x_column or not y_column:
            raise ValueError("x_column and y_column must be specified for scatter plots")
        
        data = df[[x_column, y_column]].dropna()
        
        return {
            'data': data.values.tolist(),
            'x_label': x_column,
            'y_label': y_column
        }
    
    def _prepare_histogram_data(self, df: pd.DataFrame, value_column: str, bins: int = 10) -> Dict[str, Any]:
        """Prepare data for histograms."""
        if not value_column:
            raise ValueError("value_column must be specified for histograms")
        
        values = df[value_column].dropna()
        hist, edges = np.histogram(values, bins=bins)
        
        data = []
        for i in range(len(hist)):
            data.append({
                'range': f"{edges[i]:.2f}-{edges[i+1]:.2f}",
                'count': int(hist[i])
            })
        
        return {'data': data}
    
    def _prepare_box_data(self, df: pd.DataFrame, value_column: str, 
                         group_by: Optional[str]) -> Dict[str, Any]:
        """Prepare data for box plots."""
        if not value_column:
            raise ValueError("value_column must be specified for box plots")
        
        if group_by:
            data = []
            for group_value in df[group_by].unique():
                group_data = df[df[group_by] == group_value][value_column].dropna()
                if len(group_data) > 0:
                    data.append({
                        'name': str(group_value),
                        'min': float(group_data.min()),
                        'q1': float(group_data.quantile(0.25)),
                        'median': float(group_data.median()),
                        'q3': float(group_data.quantile(0.75)),
                        'max': float(group_data.max())
                    })
        else:
            values = df[value_column].dropna()
            data = [{
                'name': value_column,
                'min': float(values.min()),
                'q1': float(values.quantile(0.25)),
                'median': float(values.median()),
                'q3': float(values.quantile(0.75)),
                'max': float(values.max())
            }]
        
        return {'data': data}
    
    def _prepare_heatmap_data(self, df: pd.DataFrame, x_column: str, 
                             y_column: str, value_column: str) -> Dict[str, Any]:
        """Prepare data for heatmaps."""
        if not all([x_column, y_column, value_column]):
            raise ValueError("x_column, y_column, and value_column must be specified for heatmaps")
        
        pivot_table = df.pivot_table(values=value_column, index=y_column, columns=x_column)
        
        data = []
        for y_idx, y_val in enumerate(pivot_table.index):
            for x_idx, x_val in enumerate(pivot_table.columns):
                value = pivot_table.iloc[y_idx, x_idx]
                if not pd.isna(value):
                    data.append([x_idx, y_idx, float(value)])
        
        return {
            'data': data,
            'x_categories': pivot_table.columns.tolist(),
            'y_categories': pivot_table.index.tolist()
        }
    
    def _prepare_bubble_data(self, df: pd.DataFrame, x_column: str, 
                            y_column: str, size_column: Optional[str] = None) -> Dict[str, Any]:
        """Prepare data for bubble charts."""
        if not x_column or not y_column:
            raise ValueError("x_column and y_column must be specified for bubble charts")
        
        columns = [x_column, y_column]
        if size_column:
            columns.append(size_column)
        
        data = df[columns].dropna()
        
        return {
            'data': data.values.tolist(),
            'columns': columns
        }
    
    def _prepare_radar_data(self, df: pd.DataFrame, category_column: str, 
                           value_column: str) -> Dict[str, Any]:
        """Prepare data for radar charts."""
        if not category_column or not value_column:
            raise ValueError("category_column and value_column must be specified for radar charts")
        
        data = df.groupby(category_column)[value_column].mean().to_dict()
        
        return {
            'categories': list(data.keys()),
            'data': [{'values': list(data.values())}]
        }
    
    def _apply_sorting(self, result: Dict[str, Any], sort_by: str, sort_order: str) -> Dict[str, Any]:
        """Apply sorting to the result data."""
        if 'data' in result and isinstance(result['data'], list):
            reverse = sort_order == 'desc'
            if isinstance(result['data'][0], dict):
                if sort_by in result['data'][0]:
                    result['data'] = sorted(result['data'], 
                                          key=lambda x: x.get(sort_by, 0), 
                                          reverse=reverse)
        return result
    
    def _apply_top_n(self, result: Dict[str, Any], n: int) -> Dict[str, Any]:
        """Keep only top N items."""
        if 'data' in result and isinstance(result['data'], list):
            result['data'] = result['data'][:n]
        elif 'series' in result and isinstance(result['series'], list):
            for series in result['series']:
                if 'data' in series and isinstance(series['data'], list):
                    series['data'] = series['data'][:n]
        return result
    
    def _normalize_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize data values."""
        if 'data' in result and isinstance(result['data'], list):
            if isinstance(result['data'][0], dict) and 'value' in result['data'][0]:
                total = sum(item['value'] for item in result['data'])
                if total > 0:
                    for item in result['data']:
                        item['value'] = item['value'] / total
        return result
    
    def _format_dates(self, result: Dict[str, Any], date_format: str) -> Dict[str, Any]:
        """Format date values."""
        # Implementation depends on the structure of the result
        return result
    
    def _apply_custom_labels(self, result: Dict[str, Any], labels: Dict[str, str]) -> Dict[str, Any]:
        """Apply custom labels to the result."""
        if 'series' in result:
            for series in result['series']:
                if series['name'] in labels:
                    series['name'] = labels[series['name']]
        return result
    
    def validate_data(self, data: Any) -> Dict[str, Any]:
        """
        Validate input data and return validation results.
        
        Parameters:
        -----------
        data : Any
            Data to validate
        
        Returns:
        --------
        Dict[str, Any]
            Validation results including status and any errors
        """
        errors = []
        warnings = []
        
        try:
            df = self._convert_to_dataframe(data)
            
            # Check for empty DataFrame
            if df.empty:
                errors.append("Data is empty")
            
            # Check for required columns
            if df.shape[1] == 0:
                errors.append("No columns found in data")
            
            # Check for data types
            numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_columns) == 0:
                warnings.append("No numeric columns found")
            
            # Check for missing values
            missing_counts = df.isnull().sum()
            if missing_counts.any():
                warnings.append(f"Missing values found: {missing_counts[missing_counts > 0].to_dict()}")
            
        except Exception as e:
            errors.append(f"Data validation error: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_chart_recommendations(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Get chart type recommendations based on data characteristics.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame to analyze
        
        Returns:
        --------
        List[Dict[str, Any]]
            List of recommended chart configurations
        """
        recommendations = []
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        date_columns = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        # Recommend based on column types
        if len(numeric_columns) >= 2:
            recommendations.append({
                'chart_type': 'scatter',
                'reason': 'Multiple numeric columns available for correlation analysis',
                'config': {
                    'x_column': numeric_columns[0],
                    'y_column': numeric_columns[1]
                }
            })
        
        if len(categorical_columns) >= 1 and len(numeric_columns) >= 1:
            recommendations.append({
                'chart_type': 'bar',
                'reason': 'Categorical and numeric data available',
                'config': {
                    'x_column': categorical_columns[0],
                    'y_column': numeric_columns[0]
                }
            })
            
            recommendations.append({
                'chart_type': 'pie',
                'reason': 'Good for showing proportions',
                'config': {
                    'label_column': categorical_columns[0],
                    'value_column': numeric_columns[0]
                }
            })
        
        if len(date_columns) >= 1 and len(numeric_columns) >= 1:
            recommendations.append({
                'chart_type': 'line',
                'reason': 'Time series data detected',
                'config': {
                    'x_column': date_columns[0],
                    'y_column': numeric_columns[0]
                }
            })
        
        if len(numeric_columns) >= 1:
            recommendations.append({
                'chart_type': 'histogram',
                'reason': 'Good for distribution analysis',
                'config': {
                    'value_column': numeric_columns[0]
                }
            })
        
        return recommendations
    
    def export_prepared_data(self, result: Dict[str, Any], format: str = 'json') -> Union[str, bytes]:
        """
        Export prepared data in specified format.
        
        Parameters:
        -----------
        result : Dict[str, Any]
            Prepared data to export
        format : str
            Export format ('json', 'csv', 'excel')
        
        Returns:
        --------
        Union[str, bytes]
            Exported data
        """
        if format == 'json':
            return json.dumps(result, default=str, indent=2)
        elif format == 'csv':
            # Convert to DataFrame if possible
            if 'data' in result and isinstance(result['data'], list):
                df = pd.DataFrame(result['data'])
                return df.to_csv(index=False)
            else:
                raise ValueError("Cannot convert this data structure to CSV")
        elif format == 'excel':
            # Would need to implement Excel export
            raise NotImplementedError("Excel export not yet implemented")
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Create a singleton instance for backward compatibility
chart_data_preparation = ChartDataPreparation()

# Expose main methods at module level
prepare_data = chart_data_preparation.prepare_data
validate_data = chart_data_preparation.validate_data
get_chart_recommendations = chart_data_preparation.get_chart_recommendations
export_prepared_data = chart_data_preparation.export_prepared_data
