from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import math


class TransformType(Enum):
    SCALE = "scale"
    POSITION = "position"
    CROP = "crop"
    ROTATION = "rotation"


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


@dataclass
class ImageTransform:
    """Model for image transformation parameters"""
    scale: float = 1.0
    position: Tuple[float, float] = (0.0, 0.0)
    crop: Dict[str, float] = field(default_factory=lambda: {
        'top': 0.0,
        'right': 0.0,
        'bottom': 0.0,
        'left': 0.0
    })
    rotation: float = 0.0
    
    def __post_init__(self):
        """Validate transform parameters after initialization"""
        self.validate()
    
    def validate(self):
        """Validate all transform parameters"""
        # Validate scale
        if not isinstance(self.scale, (int, float)):
            raise ValidationError("Scale must be a number")
        if self.scale <= 0:
            raise ValidationError(f"Scale must be positive, got {self.scale}")
        if self.scale > 10:
            raise ValidationError(f"Scale must be <= 10, got {self.scale}")
        
        # Validate position
        if not isinstance(self.position, tuple) or len(self.position) != 2:
            raise ValidationError("Position must be a tuple of (x, y)")
        if not all(isinstance(p, (int, float)) for p in self.position):
            raise ValidationError("Position coordinates must be numbers")
        
        # Validate crop
        if not isinstance(self.crop, dict):
            raise ValidationError("Crop must be a dictionary")
        required_keys = {'top', 'right', 'bottom', 'left'}
        if set(self.crop.keys()) != required_keys:
            raise ValidationError(f"Crop must have keys: {required_keys}")
        
        for key, value in self.crop.items():
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Crop {key} must be a number")
            if value < 0 or value > 100:
                raise ValidationError(f"Crop {key} must be between 0 and 100, got {value}")
        
        # Validate rotation
        if not isinstance(self.rotation, (int, float)):
            raise ValidationError("Rotation must be a number")
        if self.rotation < -360 or self.rotation > 360:
            raise ValidationError(f"Rotation must be between -360 and 360, got {self.rotation}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize transform to dictionary"""
        return {
            'scale': self.scale,
            'position': {
                'x': self.position[0],
                'y': self.position[1]
            },
            'crop': self.crop.copy(),
            'rotation': self.rotation
        }
    
    def get_final_dimensions(self, original_width: float, original_height: float) -> Tuple[float, float]:
        """Calculate final dimensions after crop and scale"""
        # Apply crop first
        crop_width = original_width * (100 - self.crop['left'] - self.crop['right']) / 100
        crop_height = original_height * (100 - self.crop['top'] - self.crop['bottom']) / 100
        
        # Then apply scale
        final_width = crop_width * self.scale
        final_height = crop_height * self.scale
        
        return (final_width, final_height)


class CoordinateConverter:
    """Convert between canvas pixels and PowerPoint EMUs"""
    
    # PowerPoint uses English Metric Units (EMUs)
    # 1 inch = 914400 EMUs
    # Assuming 96 DPI for canvas
    PIXELS_PER_INCH = 96
    EMUS_PER_INCH = 914400
    EMUS_PER_PIXEL = EMUS_PER_INCH / PIXELS_PER_INCH
    
    @classmethod
    def pixels_to_emus(cls, pixels: float) -> int:
        """Convert pixels to EMUs"""
        return int(pixels * cls.EMUS_PER_PIXEL)
    
    @classmethod
    def emus_to_pixels(cls, emus: int) -> float:
        """Convert EMUs to pixels"""
        return emus / cls.EMUS_PER_PIXEL
    
    @classmethod
    def convert_transform(cls, transform: ImageTransform, canvas_width: float, canvas_height: float) -> Dict[str, Any]:
        """Convert transform from canvas coordinates to PowerPoint coordinates"""
        # Convert position
        x_emus = cls.pixels_to_emus(transform.position[0])
        y_emus = cls.pixels_to_emus(transform.position[1])
        
        # Convert dimensions (example, would need original image dimensions)
        width_emus = cls.pixels_to_emus(canvas_width * transform.scale)
        height_emus = cls.pixels_to_emus(canvas_height * transform.scale)
        
        return {
            'x': x_emus,
            'y': y_emus,
            'width': width_emus,
            'height': height_emus,
            'rotation': transform.rotation,
            'crop': transform.crop.copy()
        }


class TransformValidator:
    """Validates transform parameters"""
    
    @staticmethod
    def validate_scale(scale: Any) -> None:
        """Validate scale parameter"""
        if not isinstance(scale, (int, float)):
            raise ValidationError("Scale must be a number")
        if scale <= 0:
            raise ValidationError(f"Scale must be positive, got {scale}")
        if scale > 10:
            raise ValidationError(f"Scale must be <= 10, got {scale}")
    
    @staticmethod
    def validate_position(position: Any) -> None:
        """Validate position parameter"""
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValidationError("Position must be a tuple/list of (x, y)")
        if not all(isinstance(p, (int, float)) for p in position):
            raise ValidationError("Position coordinates must be numbers")
    
    @staticmethod
    def validate_crop(crop: Any) -> None:
        """Validate crop parameter"""
        if not isinstance(crop, dict):
            raise ValidationError("Crop must be a dictionary")
        required_keys = {'top', 'right', 'bottom', 'left'}
        if set(crop.keys()) != required_keys:
            raise ValidationError(f"Crop must have keys: {required_keys}")
        
        for key, value in crop.items():
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Crop {key} must be a number")
            if value < 0 or value > 100:
                raise ValidationError(f"Crop {key} must be between 0 and 100, got {value}")
    
    @staticmethod
    def validate_rotation(rotation: Any) -> None:
        """Validate rotation parameter"""
        if not isinstance(rotation, (int, float)):
            raise ValidationError("Rotation must be a number")
        if rotation < -360 or rotation > 360:
            raise ValidationError(f"Rotation must be between -360 and 360, got {rotation}")


class TransformHistory:
    """Manages transform history for undo/redo functionality"""
    
    def __init__(self):
        self._history: List[ImageTransform] = []
        self._current_index: int = -1
    
    def add(self, transform: ImageTransform) -> None:
        """Add a new transform to history"""
        # Remove any transforms after current index (for new branch)
        self._history = self._history[:self._current_index + 1]
        
        # Add new transform
        self._history.append(transform)
        self._current_index = len(self._history) - 1
    
    def undo(self) -> Optional[ImageTransform]:
        """Move to previous transform"""
        if self._current_index > 0:
            self._current_index -= 1
            return self._history[self._current_index]
        return None
    
    def redo(self) -> Optional[ImageTransform]:
        """Move to next transform"""
        if self._current_index < len(self._history) - 1:
            self._current_index += 1
            return self._history[self._current_index]
        return None
    
    def get_current(self) -> Optional[ImageTransform]:
        """Get current transform"""
        if self._current_index >= 0 and self._current_index < len(self._history):
            return self._history[self._current_index]
        return None
    
    def clear(self) -> None:
        """Clear history"""
        self._history.clear()
        self._current_index = -1


class TransformInterpolator:
    """Interpolates between transforms for smooth transitions"""
    
    @staticmethod
    def lerp(start: float, end: float, t: float) -> float:
        """Linear interpolation between two values"""
        return start + (end - start) * t
    
    @classmethod
    def interpolate(cls, start: ImageTransform, end: ImageTransform, t: float) -> ImageTransform:
        """Interpolate between two transforms"""
        # Clamp t between 0 and 1
        t = max(0, min(1, t))
        
        # Interpolate scale
        scale = cls.lerp(start.scale, end.scale, t)
        
        # Interpolate position
        x = cls.lerp(start.position[0], end.position[0], t)
        y = cls.lerp(start.position[1], end.position[1], t)
        position = (x, y)
        
        # Interpolate crop
        crop = {}
        for key in ['top', 'right', 'bottom', 'left']:
            crop[key] = cls.lerp(start.crop[key], end.crop[key], t)
        
        # Interpolate rotation
        rotation = cls.lerp(start.rotation, end.rotation, t)
        
        return ImageTransform(
            scale=scale,
            position=position,
            crop=crop,
            rotation=rotation
        )
    
    @classmethod
    def generate_frames(cls, start: ImageTransform, end: ImageTransform, num_frames: int) -> List[ImageTransform]:
        """Generate interpolated frames for smooth transition"""
        if num_frames <= 0:
            return []
        if num_frames == 1:
            return [end]
        
        frames = []
        for i in range(num_frames):
            t = i / (num_frames - 1)
            frames.append(cls.interpolate(start, end, t))
        
        return frames
