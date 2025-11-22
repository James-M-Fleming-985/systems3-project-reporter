import time
from typing import Optional, Tuple, List, Dict, Any
from PIL import Image
import io
import copy


class ImageManipulationService:
    """Service for handling image manipulation operations with undo/redo support."""
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.current_index: int = -1
        
    def resize_image(self, image_data: bytes, width: Optional[int] = None, 
                    height: Optional[int] = None, maintain_aspect_ratio: bool = True) -> bytes:
        """
        Resize an image to specified dimensions.
        
        Args:
            image_data: Image data in bytes
            width: Target width (optional)
            height: Target height (optional)
            maintain_aspect_ratio: Whether to maintain aspect ratio
            
        Returns:
            Resized image data in bytes
        """
        start_time = time.time()
        
        # Open image
        image = Image.open(io.BytesIO(image_data))
        original_width, original_height = image.size
        
        # Calculate new dimensions
        if maintain_aspect_ratio:
            if width and height:
                # Use the dimension that results in smaller image
                ratio_w = width / original_width
                ratio_h = height / original_height
                ratio = min(ratio_w, ratio_h)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
            elif width:
                ratio = width / original_width
                new_width = width
                new_height = int(original_height * ratio)
            elif height:
                ratio = height / original_height
                new_width = int(original_width * ratio)
                new_height = height
            else:
                new_width = original_width
                new_height = original_height
        else:
            new_width = width if width else original_width
            new_height = height if height else original_height
        
        # Resize image
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert back to bytes
        output = io.BytesIO()
        format_name = image.format if image.format else 'PNG'
        resized_image.save(output, format=format_name)
        result = output.getvalue()
        
        # Store in history
        self._add_to_history({
            'operation': 'resize',
            'original': image_data,
            'result': result,
            'params': {
                'width': width,
                'height': height,
                'maintain_aspect_ratio': maintain_aspect_ratio
            }
        })
        
        # Check performance requirement
        elapsed = time.time() - start_time
        if len(image_data) >= 5 * 1024 * 1024 and elapsed >= 2.0:
            raise RuntimeError(f"Performance requirement not met: {elapsed:.2f}s for 5MB image")
        
        return result
    
    def crop_image(self, image_data: bytes, x: int, y: int, width: int, height: int) -> bytes:
        """
        Crop an image to specified region.
        
        Args:
            image_data: Image data in bytes
            x: X coordinate of top-left corner
            y: Y coordinate of top-left corner
            width: Width of crop region
            height: Height of crop region
            
        Returns:
            Cropped image data in bytes
        """
        start_time = time.time()
        
        # Open image
        image = Image.open(io.BytesIO(image_data))
        
        # Validate crop parameters
        img_width, img_height = image.size
        if x < 0 or y < 0 or x + width > img_width or y + height > img_height:
            raise ValueError("Crop region exceeds image boundaries")
        
        # Crop image
        cropped_image = image.crop((x, y, x + width, y + height))
        
        # Convert back to bytes
        output = io.BytesIO()
        format_name = image.format if image.format else 'PNG'
        cropped_image.save(output, format=format_name)
        result = output.getvalue()
        
        # Store in history
        self._add_to_history({
            'operation': 'crop',
            'original': image_data,
            'result': result,
            'params': {
                'x': x,
                'y': y,
                'width': width,
                'height': height
            }
        })
        
        # Check performance requirement
        elapsed = time.time() - start_time
        if len(image_data) >= 5 * 1024 * 1024 and elapsed >= 2.0:
            raise RuntimeError(f"Performance requirement not met: {elapsed:.2f}s for 5MB image")
        
        return result
    
    def rotate_image(self, image_data: bytes, angle: float) -> bytes:
        """
        Rotate an image by specified angle.
        
        Args:
            image_data: Image data in bytes
            angle: Rotation angle in degrees (positive = counter-clockwise)
            
        Returns:
            Rotated image data in bytes
        """
        start_time = time.time()
        
        # Open image
        image = Image.open(io.BytesIO(image_data))
        
        # Rotate image
        # Use negative angle for clockwise rotation (PIL uses counter-clockwise)
        rotated_image = image.rotate(-angle, expand=True, fillcolor=None)
        
        # Convert back to bytes
        output = io.BytesIO()
        format_name = image.format if image.format else 'PNG'
        rotated_image.save(output, format=format_name, quality=95)
        result = output.getvalue()
        
        # Store in history
        self._add_to_history({
            'operation': 'rotate',
            'original': image_data,
            'result': result,
            'params': {
                'angle': angle
            }
        })
        
        # Check performance requirement
        elapsed = time.time() - start_time
        if len(image_data) >= 5 * 1024 * 1024 and elapsed >= 2.0:
            raise RuntimeError(f"Performance requirement not met: {elapsed:.2f}s for 5MB image")
        
        return result
    
    def undo(self) -> Optional[bytes]:
        """
        Undo the last operation.
        
        Returns:
            Previous image state or None if no operation to undo
        """
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]['original']
        elif self.current_index == 0:
            # Return original of first operation
            return self.history[0]['original']
        return None
    
    def redo(self) -> Optional[bytes]:
        """
        Redo the previously undone operation.
        
        Returns:
            Next image state or None if no operation to redo
        """
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]['result']
        return None
    
    def _add_to_history(self, operation: Dict[str, Any]) -> None:
        """Add an operation to history, removing any forward history."""
        # Remove any operations after current index
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # Add new operation
        self.history.append(operation)
        self.current_index += 1
    
    def get_image_info(self, image_data: bytes) -> Dict[str, Any]:
        """
        Get information about an image.
        
        Args:
            image_data: Image data in bytes
            
        Returns:
            Dictionary with image information
        """
        image = Image.open(io.BytesIO(image_data))
        return {
            'width': image.width,
            'height': image.height,
            'format': image.format,
            'mode': image.mode
        }
