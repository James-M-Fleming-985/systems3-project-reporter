import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
import seaborn as sns
from datetime import datetime


class ChartBuilder:
    """A class for building various types of charts using matplotlib."""
    
    def __init__(self):
        """Initialize the ChartBuilder."""
        self.figure = None
        self.axes = None
        self.data = None
        
    def create_line_chart(self, data: Dict[str, List[Union[int, float]]], 
                         title: str = "", xlabel: str = "", ylabel: str = "",
                         figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Create a line chart from the provided data.
        
        Args:
            data: Dictionary with keys as series names and values as lists of data points
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        for series_name, values in data.items():
            if not isinstance(values, (list, tuple, np.ndarray)):
                raise ValueError(f"Invalid data type for series '{series_name}'")
            if not values:
                raise ValueError(f"Empty data for series '{series_name}'")
            self.axes.plot(values, label=series_name)
            
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        if len(data) > 1:
            self.axes.legend()
        
        return self.figure
        
    def create_bar_chart(self, data: Dict[str, Union[int, float]], 
                        title: str = "", xlabel: str = "", ylabel: str = "",
                        figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Create a bar chart from the provided data.
        
        Args:
            data: Dictionary with keys as categories and values as numeric values
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        categories = list(data.keys())
        values = list(data.values())
        
        for val in values:
            if not isinstance(val, (int, float)):
                raise ValueError("All values must be numeric")
                
        self.axes.bar(categories, values)
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        
        return self.figure
        
    def create_scatter_plot(self, x_data: List[Union[int, float]], 
                           y_data: List[Union[int, float]], 
                           title: str = "", xlabel: str = "", ylabel: str = "",
                           figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Create a scatter plot from the provided data.
        
        Args:
            x_data: List of x-coordinates
            y_data: List of y-coordinates
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not x_data or not y_data:
            raise ValueError("X and Y data cannot be empty")
        if len(x_data) != len(y_data):
            raise ValueError("X and Y data must have the same length")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        self.axes.scatter(x_data, y_data)
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        
        return self.figure
        
    def create_pie_chart(self, data: Dict[str, Union[int, float]], 
                        title: str = "", figsize: Tuple[int, int] = (8, 8)) -> plt.Figure:
        """
        Create a pie chart from the provided data.
        
        Args:
            data: Dictionary with keys as labels and values as numeric values
            title: Chart title
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        labels = list(data.keys())
        values = list(data.values())
        
        for val in values:
            if not isinstance(val, (int, float)) or val < 0:
                raise ValueError("All values must be non-negative numbers")
                
        if sum(values) == 0:
            raise ValueError("Sum of values cannot be zero")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        self.axes.pie(values, labels=labels, autopct='%1.1f%%')
        self.axes.set_title(title)
        
        return self.figure
        
    def create_histogram(self, data: List[Union[int, float]], 
                        bins: int = 10, title: str = "", xlabel: str = "", 
                        ylabel: str = "Frequency",
                        figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Create a histogram from the provided data.
        
        Args:
            data: List of numeric values
            bins: Number of bins
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
        if bins <= 0:
            raise ValueError("Number of bins must be positive")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        self.axes.hist(data, bins=bins)
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        
        return self.figure
        
    def create_heatmap(self, data: Union[List[List[float]], np.ndarray], 
                      xticklabels: Optional[List[str]] = None,
                      yticklabels: Optional[List[str]] = None,
                      title: str = "", cmap: str = "coolwarm",
                      figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create a heatmap from the provided data.
        
        Args:
            data: 2D array of numeric values
            xticklabels: Labels for x-axis
            yticklabels: Labels for y-axis
            title: Chart title
            cmap: Color map
            figsize: Figure size as tuple (width, height)
            
        Returns:
            matplotlib.figure.Figure: The created figure
            
        Raises:
            ValueError: If data is invalid
        """
        if not isinstance(data, (list, np.ndarray)):
            raise ValueError("Data must be a list or numpy array")
            
        if isinstance(data, list):
            if not data or not data[0]:
                raise ValueError("Data cannot be empty")
            data = np.array(data)
            
        if data.ndim != 2:
            raise ValueError("Data must be 2-dimensional")
            
        self.figure, self.axes = plt.subplots(figsize=figsize)
        
        im = self.axes.imshow(data, cmap=cmap, aspect='auto')
        self.figure.colorbar(im, ax=self.axes)
        
        if xticklabels is not None:
            self.axes.set_xticks(np.arange(len(xticklabels)))
            self.axes.set_xticklabels(xticklabels)
            
        if yticklabels is not None:
            self.axes.set_yticks(np.arange(len(yticklabels)))
            self.axes.set_yticklabels(yticklabels)
            
        self.axes.set_title(title)
        
        return self.figure
        
    def save_chart(self, filename: str, dpi: int = 300, format: str = 'png'):
        """
        Save the current chart to a file.
        
        Args:
            filename: Path to save the file
            dpi: Dots per inch for the saved image
            format: File format (e.g., 'png', 'pdf', 'svg')
            
        Raises:
            RuntimeError: If no chart has been created
            ValueError: If invalid parameters are provided
        """
        if self.figure is None:
            raise RuntimeError("No chart has been created yet")
            
        if not filename:
            raise ValueError("Filename cannot be empty")
            
        if dpi <= 0:
            raise ValueError("DPI must be positive")
            
        valid_formats = ['png', 'pdf', 'svg', 'jpg', 'jpeg']
        if format.lower() not in valid_formats:
            raise ValueError(f"Invalid format. Must be one of {valid_formats}")
            
        self.figure.savefig(filename, dpi=dpi, format=format, bbox_inches='tight')
        
    def clear(self):
        """Clear the current figure and axes."""
        if self.figure is not None:
            plt.close(self.figure)
        self.figure = None
        self.axes = None
        self.data = None
        
    def customize_chart(self, **kwargs):
        """
        Customize various aspects of the chart.
        
        Args:
            **kwargs: Keyword arguments for customization
                - grid: bool, show grid
                - grid_alpha: float, grid transparency
                - font_size: int, base font size
                - title_size: int, title font size
                - label_size: int, axis label font size
                - tick_size: int, tick label font size
                - style: str, matplotlib style
                
        Raises:
            RuntimeError: If no chart has been created
        """
        if self.axes is None:
            raise RuntimeError("No chart has been created yet")
            
        if 'grid' in kwargs:
            self.axes.grid(kwargs['grid'], alpha=kwargs.get('grid_alpha', 0.3))
            
        if 'font_size' in kwargs:
            plt.rcParams.update({'font.size': kwargs['font_size']})
            
        if 'title_size' in kwargs and self.axes.get_title():
            self.axes.set_title(self.axes.get_title(), fontsize=kwargs['title_size'])
            
        if 'label_size' in kwargs:
            self.axes.xaxis.label.set_fontsize(kwargs['label_size'])
            self.axes.yaxis.label.set_fontsize(kwargs['label_size'])
            
        if 'tick_size' in kwargs:
            self.axes.tick_params(labelsize=kwargs['tick_size'])
            
        if 'style' in kwargs:
            plt.style.use(kwargs['style'])


class DataProcessor:
    """A class for processing data before visualization."""
    
    @staticmethod
    def normalize_data(data: List[Union[int, float]]) -> List[float]:
        """
        Normalize data to range [0, 1].
        
        Args:
            data: List of numeric values
            
        Returns:
            List of normalized values
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        min_val = min(data)
        max_val = max(data)
        
        if min_val == max_val:
            return [0.5] * len(data)
            
        return [(x - min_val) / (max_val - min_val) for x in data]
        
    @staticmethod
    def aggregate_data(data: List[Union[int, float]], method: str = 'sum') -> float:
        """
        Aggregate data using specified method.
        
        Args:
            data: List of numeric values
            method: Aggregation method ('sum', 'mean', 'median', 'min', 'max')
            
        Returns:
            Aggregated value
            
        Raises:
            ValueError: If data is invalid or method is unknown
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        methods = {
            'sum': sum,
            'mean': lambda x: sum(x) / len(x),
            'median': lambda x: sorted(x)[len(x) // 2],
            'min': min,
            'max': max
        }
        
        if method not in methods:
            raise ValueError(f"Unknown method: {method}")
            
        return methods[method](data)
        
    @staticmethod
    def filter_outliers(data: List[Union[int, float]], 
                       threshold: float = 2.0) -> List[Union[int, float]]:
        """
        Filter outliers using z-score method.
        
        Args:
            data: List of numeric values
            threshold: Z-score threshold
            
        Returns:
            List with outliers removed
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
            
        if len(data) < 3:
            return data
            
        mean = sum(data) / len(data)
        std = (sum((x - mean) ** 2 for x in data) / len(data)) ** 0.5
        
        if std == 0:
            return data
            
        return [x for x in data if abs((x - mean) / std) <= threshold]
