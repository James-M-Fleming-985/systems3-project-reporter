"""
Feature Integration Module for Canvas Editor for PowerPoint Slide Customization
Feature ID: FEATURE-WEB-006-PHASE-2

This module orchestrates the interaction between:
- Transform Models and Validators
- Image Manipulation Service
- Canvas Editor API Endpoints
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_PHASE2_001_Transform_Models_and_Validators.src.implementation import (
    ImageTransform, CoordinateConverter, TransformValidator, 
    TransformHistory, TransformInterpolator
)
from LAYER_PHASE2_002_Image_Manipulation_Service.src.implementation import (
    ImageManipulationService
)
from LAYER_PHASE2_003_Canvas_Editor_API_Endpoints.src.implementation import (
    ConnectionManager
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for Canvas Editor feature"""
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    allowed_formats: List[str] = None
    max_history_size: int = 50
    enable_interpolation: bool = True
    
    def __post_init__(self):
        if self.allowed_formats is None:
            self.allowed_formats = ['png', 'jpg', 'jpeg', 'gif', 'bmp']


@dataclass
class FeatureResponse:
    """Standardized response format for feature operations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CanvasEditorOrchestrator:
    """
    Main orchestrator for Canvas Editor feature that coordinates
    transform validation, image manipulation, and WebSocket connections
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the feature orchestrator
        
        Args:
            config: Optional configuration for the feature
        """
        self.config = config or FeatureConfig()
        
        try:
            # Initialize layer components
            self.transform_validator = TransformValidator()
            self.coordinate_converter = CoordinateConverter()
            self.transform_history = TransformHistory()
            self.transform_interpolator = TransformInterpolator()
            self.image_service = ImageManipulationService()
            self.connection_manager = ConnectionManager()
            
            logger.info("Canvas Editor Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Canvas Editor Orchestrator: {str(e)}")
            raise
    
    def apply_image_transform(self, image_path: str, transform_data: Dict[str, Any]) -> FeatureResponse:
        """
        Apply a series of transformations to an image
        
        Args:
            image_path: Path to the image file
            transform_data: Dictionary containing transform parameters
                {
                    'scale': {'x': float, 'y': float},
                    'position': {'x': int, 'y': int},
                    'rotation': float,
                    'crop': {'x': int, 'y': int, 'width': int, 'height': int}
                }
        
        Returns:
            FeatureResponse with transformed image data
        """
        try:
            # Create ImageTransform instance
            transform = ImageTransform(**transform_data)
            
            # Validate transform
            if not transform.validate():
                return FeatureResponse(
                    success=False,
                    error="Invalid transform parameters"
                )
            
            # Get image info first
            info_result = self.image_service.get_image_info(image_path)
            if not info_result['success']:
                return FeatureResponse(
                    success=False,
                    error=info_result.get('error', 'Failed to get image info')
                )
            
            # Apply transformations in sequence
            current_path = image_path
            transform_results = {}
            
            # Apply resize if scale is provided
            if 'scale' in transform_data:
                scale_valid = self.transform_validator.validate_scale(
                    transform_data['scale']['x'], 
                    transform_data['scale']['y']
                )
                if scale_valid:
                    final_dims = transform.get_final_dimensions(
                        info_result['data']['width'],
                        info_result['data']['height']
                    )
                    resize_result = self.image_service.resize_image(
                        current_path,
                        final_dims['width'],
                        final_dims['height']
                    )
                    if resize_result['success']:
                        current_path = resize_result['data']['output_path']
                        transform_results['resize'] = resize_result['data']
            
            # Apply crop if provided
            if 'crop' in transform_data:
                crop = transform_data['crop']
                crop_valid = self.transform_validator.validate_crop(
                    crop['x'], crop['y'], crop['width'], crop['height'],
                    info_result['data']['width'], info_result['data']['height']
                )
                if crop_valid:
                    crop_result = self.image_service.crop_image(
                        current_path,
                        crop['x'], crop['y'],
                        crop['width'], crop['height']
                    )
                    if crop_result['success']:
                        current_path = crop_result['data']['output_path']
                        transform_results['crop'] = crop_result['data']
            
            # Apply rotation if provided
            if 'rotation' in transform_data:
                rotation_valid = self.transform_validator.validate_rotation(
                    transform_data['rotation']
                )
                if rotation_valid:
                    rotate_result = self.image_service.rotate_image(
                        current_path,
                        transform_data['rotation']
                    )
                    if rotate_result['success']:
                        current_path = rotate_result['data']['output_path']
                        transform_results['rotation'] = rotate_result['data']
            
            # Add to history
            self.transform_history.add(transform)
            
            return FeatureResponse(
                success=True,
                data={
                    'output_path': current_path,
                    'transforms_applied': transform_results,
                    'transform_dict': transform.to_dict()
                },
                metadata={
                    'original_path': image_path,
                    'history_length': len(self.transform_history.history)
                }
            )
            
        except Exception as e:
            logger.error(f"Error applying image transform: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def convert_coordinates(self, 
                          pixels: Tuple[int, int], 
                          to_format: str = 'emu') -> FeatureResponse:
        """
        Convert coordinates between pixels and EMUs
        
        Args:
            pixels: Tuple of (x, y) pixel coordinates
            to_format: Target format ('emu' or 'pixels')
        
        Returns:
            FeatureResponse with converted coordinates
        """
        try:
            if to_format == 'emu':
                emu_x = self.coordinate_converter.pixels_to_emus(pixels[0])
                emu_y = self.coordinate_converter.pixels_to_emus(pixels[1])
                return FeatureResponse(
                    success=True,
                    data={'x': emu_x, 'y': emu_y, 'format': 'emu'}
                )
            elif to_format == 'pixels':
                # Assuming input is in EMUs for reverse conversion
                pixel_x = self.coordinate_converter.emus_to_pixels(pixels[0])
                pixel_y = self.coordinate_converter.emus_to_pixels(pixels[1])
                return FeatureResponse(
                    success=True,
                    data={'x': pixel_x, 'y': pixel_y, 'format': 'pixels'}
                )
            else:
                return FeatureResponse(
                    success=False,
                    error=f"Unknown format: {to_format}"
                )
                
        except Exception as e:
            logger.error(f"Error converting coordinates: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def undo_last_transform(self) -> FeatureResponse:
        """
        Undo the last transform operation
        
        Returns:
            FeatureResponse with undo result
        """
        try:
            # Undo in transform history
            history_undo = self.transform_history.undo()
            if not history_undo:
                return FeatureResponse(
                    success=False,
                    error="No transform to undo in history"
                )
            
            # Undo in image service
            service_undo = self.image_service.undo()
            if service_undo['success']:
                return FeatureResponse(
                    success=True,
                    data={
                        'current_transform': self.transform_history.get_current(),
                        'service_result': service_undo['data']
                    }
                )
            else:
                # Re-add to history if service undo failed
                self.transform_history.redo()
                return FeatureResponse(
                    success=False,
                    error=service_undo.get('error', 'Failed to undo image operation')
                )
                
        except Exception as e:
            logger.error(f"Error undoing transform: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def redo_transform(self) -> FeatureResponse:
        """
        Redo a previously undone transform operation
        
        Returns:
            FeatureResponse with redo result
        """
        try:
            # Redo in transform history
            history_redo = self.transform_history.redo()
            if not history_redo:
                return FeatureResponse(
                    success=False,
                    error="No transform to redo in history"
                )
            
            # Redo in image service
            service_redo = self.image_service.redo()
            if service_redo['success']:
                return FeatureResponse(
                    success=True,
                    data={
                        'current_transform': self.transform_history.get_current(),
                        'service_result': service_redo['data']
                    }
                )
            else:
                # Undo in history if service redo failed
                self.transform_history.undo()
                return FeatureResponse(
                    success=False,
                    error=service_redo.get('error', 'Failed to redo image operation')
                )
                
        except Exception as e:
            logger.error(f"Error redoing transform: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def generate_animation_frames(self,
                                start_transform: Dict[str, Any],
                                end_transform: Dict[str, Any],
                                num_frames: int = 30) -> FeatureResponse:
        """
        Generate interpolated animation frames between two transforms
        
        Args:
            start_transform: Starting transform parameters
            end_transform: Ending transform parameters
            num_frames: Number of frames to generate
        
        Returns:
            FeatureResponse with generated frame data
        """
        try:
            if not self.config.enable_interpolation:
                return FeatureResponse(
                    success=False,
                    error="Animation interpolation is disabled"
                )
            
            # Create transform objects
            start = ImageTransform(**start_transform)
            end = ImageTransform(**end_transform)
            
            # Validate transforms
            if not (start.validate() and end.validate()):
                return FeatureResponse(
                    success=False,
                    error="Invalid transform parameters for animation"
                )
            
            # Generate frames
            frames = self.transform_interpolator.generate_frames(
                start.to_dict(),
                end.to_dict(),
                num_frames
            )
            
            return FeatureResponse(
                success=True,
                data={
                    'frames': frames,
                    'num_frames': len(frames)
                },
                metadata={
                    'start_transform': start.to_dict(),
                    'end_transform': end.to_dict()
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating animation frames: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def disconnect_client(self, websocket) -> FeatureResponse:
        """
        Disconnect a WebSocket client
        
        Args:
            websocket: WebSocket connection to disconnect
        
        Returns:
            FeatureResponse with disconnection result
        """
        try:
            self.connection_manager.disconnect(websocket)
            return FeatureResponse(
                success=True,
                data={'message': 'Client disconnected successfully'}
            )
        except Exception as e:
            logger.error(f"Error disconnecting client: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )
    
    def clear_transform_history(self) -> FeatureResponse:
        """
        Clear all transform history
        
        Returns:
            FeatureResponse confirming history cleared
        """
        try:
            self.transform_history.clear()
            return FeatureResponse(
                success=True,
                data={'message': 'Transform history cleared'}
            )
        except Exception as e:
            logger.error(f"Error clearing transform history: {str(e)}")
            return FeatureResponse(
                success=False,
                error=str(e)
            )


# Example usage
if __name__ == "__main__":
    # Initialize orchestrator
    orchestrator = CanvasEditorOrchestrator()
    
    # Example transform
    transform_data = {
        'scale': {'x': 1.5, 'y': 1.5},
        'rotation': 45.0,
        'crop': {'x': 10, 'y': 10, 'width': 200, 'height': 200}
    }
    
    # Apply transform
    result = orchestrator.apply_image_transform('/path/to/image.png', transform_data)
    print(f"Transform result: {result}")
    
    # Convert coordinates
    coord_result = orchestrator.convert_coordinates((100, 200), 'emu')
    print(f"Coordinate conversion: {coord_result}")
