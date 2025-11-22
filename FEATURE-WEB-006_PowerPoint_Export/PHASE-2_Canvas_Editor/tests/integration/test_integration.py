"""
Integration tests for Canvas Editor for PowerPoint Slide Customization
Feature ID: FEATURE-WEB-006-PHASE-2
Tests integration between Transform Models/Validators, Image Manipulation Service, and Canvas Editor API
"""

import pytest
import json
import io
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import numpy as np
from datetime import datetime

# Assuming these are the modules we're testing
from app.models.transform import (
    TransformModel, 
    TransformValidator,
    TransformationType,
    ValidationError
)
from app.services.image_manipulation import (
    ImageManipulationService,
    ImageProcessor,
    TransformationError
)
from app.api.canvas_editor import (
    CanvasEditorAPI,
    canvas_router,
    TransformRequest,
    TransformResponse
)
from app.core.exceptions import (
    InvalidTransformError,
    ImageProcessingError,
    CanvasNotFoundError
)


class TestCanvasEditorIntegration:
    """Integration tests for Canvas Editor feature across all layers"""

    @pytest.fixture
    def mock_image(self):
        """Create a mock PIL Image for testing"""
        img = Image.new('RGB', (800, 600), color='white')
        return img

    @pytest.fixture
    def mock_canvas_data(self):
        """Mock canvas data structure"""
        return {
            "canvas_id": "test-canvas-123",
            "width": 1920,
            "height": 1080,
            "elements": [
                {
                    "id": "element-1",
                    "type": "image",
                    "src": "test-image.jpg",
                    "x": 100,
                    "y": 100,
                    "width": 400,
                    "height": 300,
                    "rotation": 0,
                    "opacity": 1.0
                }
            ],
            "background": "#ffffff"
        }

    @pytest.fixture
    def transform_validator(self):
        """Initialize transform validator"""
        return TransformValidator()

    @pytest.fixture
    def image_service(self):
        """Initialize image manipulation service"""
        return ImageManipulationService()

    @pytest.fixture
    def canvas_api(self, transform_validator, image_service):
        """Initialize canvas editor API with dependencies"""
        return CanvasEditorAPI(
            validator=transform_validator,
            image_service=image_service
        )

    @pytest.fixture
    def valid_transform_request(self):
        """Valid transformation request data"""
        return {
            "canvas_id": "test-canvas-123",
            "element_id": "element-1",
            "transformations": [
                {
                    "type": "rotate",
                    "angle": 45
                },
                {
                    "type": "scale",
                    "factor": 1.5
                },
                {
                    "type": "translate",
                    "x": 50,
                    "y": -30
                }
            ]
        }

    def test_valid_transformation_flow_end_to_end(
        self, canvas_api, valid_transform_request, mock_image, mock_canvas_data
    ):
        """
        Test 1: Valid transformation request flows through all layers successfully
        - Validator accepts valid transform parameters
        - Image service processes transformations correctly
        - API returns successful response
        """
        # Mock canvas storage
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(canvas_api.image_service, 'apply_transformation') as mock_apply:
                    # Mock successful transformation
                    transformed_image = Image.new('RGB', (600, 450), color='blue')
                    mock_apply.return_value = transformed_image
                    
                    # Execute transformation
                    response = canvas_api.apply_transformations(valid_transform_request)
                    
                    # Verify response
                    assert response['status'] == 'success'
                    assert response['canvas_id'] == 'test-canvas-123'
                    assert response['element_id'] == 'element-1'
                    assert 'timestamp' in response
                    assert len(response['applied_transformations']) == 3
                    
                    # Verify image service was called with validated parameters
                    assert mock_apply.call_count == 3
                    
                    # Verify transformation order
                    calls = mock_apply.call_args_list
                    assert calls[0][0][1]['type'] == 'rotate'
                    assert calls[1][0][1]['type'] == 'scale'
                    assert calls[2][0][1]['type'] == 'translate'

    def test_invalid_transform_validation_error(self, canvas_api, mock_canvas_data):
        """
        Test 2: Invalid transformation parameters are caught by validator
        - Validator rejects invalid parameters
        - Error propagates through layers correctly
        - API returns appropriate error response
        """
        invalid_request = {
            "canvas_id": "test-canvas-123",
            "element_id": "element-1",
            "transformations": [
                {
                    "type": "rotate",
                    "angle": 720  # Invalid: exceeds max rotation
                },
                {
                    "type": "scale",
                    "factor": -2  # Invalid: negative scale factor
                }
            ]
        }
        
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with pytest.raises(ValidationError) as exc_info:
                canvas_api.apply_transformations(invalid_request)
            
            assert "Invalid rotation angle" in str(exc_info.value)
            assert exc_info.value.error_code == "INVALID_TRANSFORM_PARAMS"

    def test_image_processing_error_handling(
        self, canvas_api, valid_transform_request, mock_image, mock_canvas_data
    ):
        """
        Test 3: Image processing errors are handled gracefully
        - Valid request passes validation
        - Image service encounters processing error
        - Error is caught and returned appropriately
        """
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(
                    canvas_api.image_service, 
                    'apply_transformation',
                    side_effect=ImageProcessingError("Failed to apply rotation: corrupted image data")
                ):
                    with pytest.raises(ImageProcessingError) as exc_info:
                        canvas_api.apply_transformations(valid_transform_request)
                    
                    assert "Failed to apply rotation" in str(exc_info.value)
                    assert exc_info.value.element_id == "element-1"
                    assert exc_info.value.transformation_type == "rotate"

    def test_complex_transformation_chain_integration(
        self, canvas_api, mock_image, mock_canvas_data
    ):
        """
        Test 4: Complex transformation chain with multiple elements
        - Multiple transformations on multiple elements
        - Verify correct order of operations
        - Test rollback on partial failure
        """
        complex_request = {
            "canvas_id": "test-canvas-123",
            "batch_transformations": [
                {
                    "element_id": "element-1",
                    "transformations": [
                        {"type": "rotate", "angle": 90},
                        {"type": "flip", "direction": "horizontal"},
                        {"type": "crop", "x": 10, "y": 10, "width": 380, "height": 280}
                    ]
                },
                {
                    "element_id": "element-2",
                    "transformations": [
                        {"type": "scale", "factor": 0.5},
                        {"type": "adjust_opacity", "opacity": 0.7}
                    ]
                }
            ]
        }
        
        # Add second element to canvas
        mock_canvas_data['elements'].append({
            "id": "element-2",
            "type": "image",
            "src": "test-image-2.jpg",
            "x": 500,
            "y": 200,
            "width": 300,
            "height": 200
        })
        
        transformation_log = []
        
        def track_transformation(image, transform):
            transformation_log.append({
                'type': transform['type'],
                'timestamp': datetime.now()
            })
            return image
        
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(
                    canvas_api.image_service, 
                    'apply_transformation',
                    side_effect=track_transformation
                ):
                    response = canvas_api.apply_batch_transformations(complex_request)
                    
                    # Verify all transformations were applied
                    assert len(transformation_log) == 5
                    assert response['total_transformations'] == 5
                    assert response['successful_elements'] == 2
                    
                    # Verify transformation order
                    expected_order = ['rotate', 'flip', 'crop', 'scale', 'adjust_opacity']
                    actual_order = [t['type'] for t in transformation_log]
                    assert actual_order == expected_order

    def test_canvas_state_persistence_integration(
        self, canvas_api, valid_transform_request, mock_image, mock_canvas_data
    ):
        """
        Test 5: Canvas state persistence across transformations
        - Apply transformations
        - Verify canvas state is updated
        - Test undo/redo functionality
        """
        initial_state = mock_canvas_data.copy()
        canvas_states = []
        
        def save_canvas_state(canvas_data):
            canvas_states.append(canvas_data.copy())
        
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(canvas_api, 'save_canvas', side_effect=save_canvas_state):
                    # Apply first transformation
                    response1 = canvas_api.apply_transformations(valid_transform_request)
                    assert response1['status'] == 'success'
                    
                    # Apply second transformation
                    second_transform = {
                        "canvas_id": "test-canvas-123",
                        "element_id": "element-1",
                        "transformations": [
                            {"type": "flip", "direction": "vertical"}
                        ]
                    }
                    response2 = canvas_api.apply_transformations(second_transform)
                    
                    # Verify states were saved
                    assert len(canvas_states) == 2
                    
                    # Test undo functionality
                    undo_response = canvas_api.undo_transformation("test-canvas-123")
                    assert undo_response['status'] == 'success'
                    assert undo_response['restored_state'] == canvas_states[0]
                    
                    # Test redo functionality
                    redo_response = canvas_api.redo_transformation("test-canvas-123")
                    assert redo_response['status'] == 'success'
                    assert redo_response['restored_state'] == canvas_states[1]

    def test_concurrent_transformation_handling(
        self, canvas_api, mock_image, mock_canvas_data
    ):
        """
        Test 6: Concurrent transformation requests are handled properly
        - Test locking mechanism for same canvas
        - Verify queue handling for multiple requests
        """
        import threading
        import time
        
        results = []
        errors = []
        
        def apply_transform_concurrent(transform_data):
            try:
                result = canvas_api.apply_transformations(transform_data)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple transform requests
        transform_requests = [
            {
                "canvas_id": "test-canvas-123",
                "element_id": "element-1",
                "transformations": [{"type": "rotate", "angle": i * 10}]
            }
            for i in range(5)
        ]
        
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(canvas_api.image_service, 'apply_transformation', return_value=mock_image):
                    # Simulate concurrent requests
                    threads = []
                    for request in transform_requests:
                        thread = threading.Thread(
                            target=apply_transform_concurrent,
                            args=(request,)
                        )
                        threads.append(thread)
                        thread.start()
                    
                    # Wait for all threads to complete
                    for thread in threads:
                        thread.join()
                    
                    # Verify all requests were processed
                    assert len(results) + len(errors) == 5
                    
                    # At least some should succeed
                    assert len(results) > 0
                    
                    # Check for proper locking errors if any
                    for error in errors:
                        assert isinstance(error, (CanvasLockError, ConcurrentModificationError))

    def test_error_recovery_and_rollback(
        self, canvas_api, mock_image, mock_canvas_data
    ):
        """
        Test 7: Error recovery and rollback mechanisms
        - Partial transformation failure triggers rollback
        - Canvas state is restored on error
        """
        failing_transform_request = {
            "canvas_id": "test-canvas-123",
            "element_id": "element-1",
            "transformations": [
                {"type": "rotate", "angle": 45},
                {"type": "scale", "factor": 2},
                {"type": "corrupt", "data": "invalid"}  # This will fail
            ]
        }
        
        original_canvas_state = mock_canvas_data.copy()
        transformation_count = 0
        
        def mock_apply_transform(image, transform):
            nonlocal transformation_count
            transformation_count += 1
            if transform['type'] == 'corrupt':
                raise ImageProcessingError("Invalid transformation type")
            return image
        
        with patch.object(canvas_api, 'get_canvas', return_value=mock_canvas_data):
            with patch.object(canvas_api, 'load_element_image', return_value=mock_image):
                with patch.object(
                    canvas_api.image_service,
                    'apply_transformation',
                    side_effect=mock_apply_transform
                ):
                    with patch.object(canvas_api, 'restore_canvas_state') as mock_restore:
                        with pytest.raises(ImageProcessingError):
                            canvas_api.apply_transformations(failing_transform_request)
                        
                        # Verify rollback was triggered
                        mock_restore.assert_called_once_with(
                            "test-canvas-123",
                            original_canvas_state
                        )
                        
                        # Verify partial transformations were attempted
                        assert transformation_count == 3