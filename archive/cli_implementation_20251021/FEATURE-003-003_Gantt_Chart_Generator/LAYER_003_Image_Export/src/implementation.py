"""
Image export functionality for handling various image formats and transformations.
"""

import os
import json
from typing import Dict, Any, List, Optional, Union, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from datetime import datetime
import io
import base64
import hashlib
import tempfile
import shutil
from pathlib import Path


class ImageExporter:
    """Handles image export operations with support for multiple formats and transformations."""
    
    SUPPORTED_FORMATS = ['PNG', 'JPEG', 'GIF', 'BMP', 'TIFF', 'WEBP']
    DEFAULT_QUALITY = 85
    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize ImageExporter with optional configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.quality = self.config.get('quality', self.DEFAULT_QUALITY)
        self.output_dir = self.config.get('output_dir', 'exports')
        self.metadata_enabled = self.config.get('metadata_enabled', True)
        self._ensure_output_dir()
    
    def _ensure_output_dir(self) -> None:
        """Ensure output directory exists."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_image(self, image_data: Union[Image.Image, np.ndarray, bytes, str], 
                    output_path: str, 
                    format: Optional[str] = None,
                    options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Export image to specified format and location.
        
        Args:
            image_data: Image data in various formats
            output_path: Output file path
            format: Target image format
            options: Additional export options
            
        Returns:
            Dictionary containing export results and metadata
            
        Raises:
            ValueError: For invalid input data or parameters
            IOError: For file operation errors
        """
        if not image_data:
            raise ValueError("Image data cannot be empty")
        
        options = options or {}
        
        # Convert image data to PIL Image
        image = self._convert_to_pil_image(image_data)
        
        # Determine format
        if not format:
            format = self._get_format_from_path(output_path)
        
        format = format.upper()
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}")
        
        # Apply transformations if specified
        if 'transformations' in options:
            image = self._apply_transformations(image, options['transformations'])
        
        # Prepare export parameters
        export_params = self._prepare_export_params(format, options)
        
        # Export image
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            
            # Handle format-specific requirements
            if format == 'JPEG' and image.mode in ('RGBA', 'LA', 'P'):
                # Convert to RGB for JPEG
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = rgb_image
            
            # Save image
            image.save(output_path, format=format, **export_params)
            
            # Generate metadata
            metadata = self._generate_metadata(image, output_path, format, options)
            
            return {
                'status': 'success',
                'path': output_path,
                'format': format,
                'size': os.path.getsize(output_path),
                'dimensions': image.size,
                'metadata': metadata
            }
            
        except Exception as e:
            raise IOError(f"Failed to export image: {str(e)}")
    
    def batch_export(self, images: List[Dict[str, Any]], 
                    options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Export multiple images in batch.
        
        Args:
            images: List of image dictionaries with data and parameters
            options: Common options for all exports
            
        Returns:
            List of export results
        """
        if not images:
            raise ValueError("No images provided for batch export")
        
        results = []
        for idx, image_info in enumerate(images):
            try:
                image_data = image_info.get('data')
                output_path = image_info.get('output_path', f'image_{idx}')
                format = image_info.get('format')
                image_options = {**options} if options else {}
                image_options.update(image_info.get('options', {}))
                
                result = self.export_image(image_data, output_path, format, image_options)
                results.append(result)
            except Exception as e:
                results.append({
                    'status': 'error',
                    'error': str(e),
                    'index': idx
                })
        
        return results
    
    def convert_format(self, input_path: str, output_path: str, 
                      target_format: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert image from one format to another.
        
        Args:
            input_path: Source image path
            output_path: Destination image path
            target_format: Target image format
            options: Conversion options
            
        Returns:
            Conversion result dictionary
        """
        if not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        with Image.open(input_path) as image:
            return self.export_image(image, output_path, target_format, options)
    
    def export_with_metadata(self, image_data: Union[Image.Image, np.ndarray], 
                           output_path: str, 
                           metadata: Dict[str, Any],
                           format: Optional[str] = None) -> Dict[str, Any]:
        """
        Export image with custom metadata.
        
        Args:
            image_data: Image data
            output_path: Output file path
            metadata: Custom metadata to embed
            format: Target format
            
        Returns:
            Export result dictionary
        """
        options = {
            'metadata': metadata,
            'preserve_metadata': True
        }
        
        result = self.export_image(image_data, output_path, format, options)
        
        # Write metadata sidecar if enabled
        if self.metadata_enabled:
            metadata_path = f"{output_path}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            result['metadata_path'] = metadata_path
        
        return result
    
    def _convert_to_pil_image(self, image_data: Union[Image.Image, np.ndarray, bytes, str]) -> Image.Image:
        """Convert various image data types to PIL Image."""
        if isinstance(image_data, Image.Image):
            return image_data
        elif isinstance(image_data, np.ndarray):
            return Image.fromarray(image_data.astype('uint8'))
        elif isinstance(image_data, bytes):
            return Image.open(io.BytesIO(image_data))
        elif isinstance(image_data, str):
            if os.path.exists(image_data):
                return Image.open(image_data)
            elif image_data.startswith('data:image'):
                # Handle base64 data URL
                header, data = image_data.split(',', 1)
                return Image.open(io.BytesIO(base64.b64decode(data)))
            else:
                # Try as base64
                return Image.open(io.BytesIO(base64.b64decode(image_data)))
        else:
            raise ValueError(f"Unsupported image data type: {type(image_data)}")
    
    def _get_format_from_path(self, path: str) -> str:
        """Extract format from file path."""
        ext = os.path.splitext(path)[1].lower()
        format_map = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.png': 'PNG',
            '.gif': 'GIF',
            '.bmp': 'BMP',
            '.tiff': 'TIFF',
            '.tif': 'TIFF',
            '.webp': 'WEBP'
        }
        return format_map.get(ext, 'PNG')
    
    def _apply_transformations(self, image: Image.Image, 
                             transformations: List[Dict[str, Any]]) -> Image.Image:
        """Apply transformations to image."""
        for transform in transformations:
            transform_type = transform.get('type')
            params = transform.get('params', {})
            
            if transform_type == 'resize':
                size = params.get('size')
                if size:
                    image = image.resize(tuple(size), Image.Resampling.LANCZOS)
            elif transform_type == 'crop':
                box = params.get('box')
                if box:
                    image = image.crop(tuple(box))
            elif transform_type == 'rotate':
                angle = params.get('angle', 0)
                image = image.rotate(angle, expand=True)
            elif transform_type == 'flip':
                direction = params.get('direction', 'horizontal')
                if direction == 'horizontal':
                    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif direction == 'vertical':
                    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            elif transform_type == 'filter':
                filter_type = params.get('filter_type')
                if filter_type == 'blur':
                    image = image.filter(ImageFilter.BLUR)
                elif filter_type == 'sharpen':
                    image = image.filter(ImageFilter.SHARPEN)
                elif filter_type == 'edge_enhance':
                    image = image.filter(ImageFilter.EDGE_ENHANCE)
        
        return image
    
    def _prepare_export_params(self, format: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare format-specific export parameters."""
        params = {}
        
        if format == 'JPEG':
            params['quality'] = options.get('quality', self.quality)
            params['optimize'] = options.get('optimize', True)
            params['progressive'] = options.get('progressive', False)
        elif format == 'PNG':
            params['compress_level'] = options.get('compress_level', 9)
            params['optimize'] = options.get('optimize', True)
        elif format == 'GIF':
            params['save_all'] = options.get('save_all', False)
            params['duration'] = options.get('duration', 100)
            params['loop'] = options.get('loop', 0)
        elif format == 'WEBP':
            params['quality'] = options.get('quality', self.quality)
            params['method'] = options.get('method', 4)
        
        # Add common parameters
        if 'dpi' in options:
            params['dpi'] = options['dpi']
        
        return params
    
    def _generate_metadata(self, image: Image.Image, output_path: str, 
                         format: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata for exported image."""
        metadata = {
            'export_date': datetime.now().isoformat(),
            'format': format,
            'dimensions': {
                'width': image.size[0],
                'height': image.size[1]
            },
            'mode': image.mode,
            'file_size': os.path.getsize(output_path),
            'checksum': self._calculate_checksum(output_path)
        }
        
        # Add EXIF data if available
        if hasattr(image, '_getexif') and image._getexif():
            metadata['exif'] = dict(image._getexif())
        
        # Add custom metadata if provided
        if 'metadata' in options:
            metadata['custom'] = options['metadata']
        
        return metadata
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b''):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


class ImageFormatConverter:
    """Handles image format conversions with optimization."""
    
    def __init__(self, exporter: Optional[ImageExporter] = None):
        """
        Initialize format converter.
        
        Args:
            exporter: Optional ImageExporter instance
        """
        self.exporter = exporter or ImageExporter()
    
    def convert(self, source: str, target: str, 
                format: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert image format.
        
        Args:
            source: Source image path
            target: Target image path
            format: Target format
            options: Conversion options
            
        Returns:
            Conversion result
        """
        return self.exporter.convert_format(source, target, format, options)
    
    def batch_convert(self, conversions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch convert multiple images.
        
        Args:
            conversions: List of conversion specifications
            
        Returns:
            List of conversion results
        """
        results = []
        for conversion in conversions:
            try:
                result = self.convert(
                    conversion['source'],
                    conversion['target'],
                    conversion['format'],
                    conversion.get('options')
                )
                results.append(result)
            except Exception as e:
                results.append({
                    'status': 'error',
                    'error': str(e),
                    'source': conversion['source']
                })
        
        return results


class ImageOptimizer:
    """Optimizes images for size and quality."""
    
    def __init__(self, exporter: Optional[ImageExporter] = None):
        """
        Initialize image optimizer.
        
        Args:
            exporter: Optional ImageExporter instance
        """
        self.exporter = exporter or ImageExporter()
    
    def optimize(self, image_path: str, 
                target_size: Optional[int] = None,
                quality_range: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        Optimize image file size and quality.
        
        Args:
            image_path: Path to image
            target_size: Target file size in bytes
            quality_range: Min and max quality values
            
        Returns:
            Optimization result
        """
        quality_range = quality_range or (70, 95)
        
        with Image.open(image_path) as image:
            format = image.format or 'JPEG'
            
            # Binary search for optimal quality
            if target_size:
                optimal_quality = self._find_optimal_quality(
                    image, format, target_size, quality_range
                )
            else:
                optimal_quality = 85
            
            # Export with optimal settings
            optimized_path = f"{os.path.splitext(image_path)[0]}_optimized{os.path.splitext(image_path)[1]}"
            
            result = self.exporter.export_image(
                image, 
                optimized_path,
                format,
                {'quality': optimal_quality, 'optimize': True}
            )
            
            # Calculate savings
            original_size = os.path.getsize(image_path)
            optimized_size = result['size']
            
            result['optimization'] = {
                'original_size': original_size,
                'optimized_size': optimized_size,
                'savings': original_size - optimized_size,
                'savings_percentage': ((original_size - optimized_size) / original_size) * 100,
                'quality': optimal_quality
            }
            
            return result
    
    def _find_optimal_quality(self, image: Image.Image, format: str,
                            target_size: int, quality_range: Tuple[int, int]) -> int:
        """Find optimal quality setting for target file size."""
        min_quality, max_quality = quality_range
        
        while min_quality < max_quality:
            mid_quality = (min_quality + max_quality + 1) // 2
            
            # Test with current quality
            with tempfile.NamedTemporaryFile(suffix=f'.{format.lower()}', delete=False) as tmp:
                image.save(tmp.name, format=format, quality=mid_quality, optimize=True)
                size = os.path.getsize(tmp.name)
                os.unlink(tmp.name)
            
            if size <= target_size:
                min_quality = mid_quality
            else:
                max_quality = mid_quality - 1
        
        return min_quality


def export_image(image_data: Any, output_path: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to export an image.
    
    Args:
        image_data: Image data in various formats
        output_path: Output file path
        **kwargs: Additional export options
        
    Returns:
        Export result dictionary
    """
    exporter = ImageExporter()
    return exporter.export_image(image_data, output_path, **kwargs)


def convert_image_format(source: str, target: str, format: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to convert image format.
    
    Args:
        source: Source image path
        target: Target image path
        format: Target format
        **kwargs: Additional options
        
    Returns:
        Conversion result
    """
    converter = ImageFormatConverter()
    return converter.convert(source, target, format, kwargs)


def optimize_image(image_path: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to optimize an image.
    
    Args:
        image_path: Path to image
        **kwargs: Optimization options
        
    Returns:
        Optimization result
    """
    optimizer = ImageOptimizer()
    return optimizer.optimize(image_path, **kwargs)
