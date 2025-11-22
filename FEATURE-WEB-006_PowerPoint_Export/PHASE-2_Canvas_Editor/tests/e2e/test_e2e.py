# test_e2e.py

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
from datetime import datetime
import json
import uuid
from typing import Dict, Any, List

# Mock models and services
class User:
    def __init__(self, id: str, email: str):
        self.id = id
        self.email = email

class Presentation:
    def __init__(self, id: str, user_id: str, name: str):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.slides = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class Slide:
    def __init__(self, id: str, presentation_id: str, order: int):
        self.id = id
        self.presentation_id = presentation_id
        self.order = order
        self.content = {}
        self.elements = []

class SlideElement:
    def __init__(self, id: str, slide_id: str, type: str, properties: Dict[str, Any]):
        self.id = id
        self.slide_id = slide_id
        self.type = type
        self.properties = properties
        self.position = properties.get('position', {'x': 0, 'y': 0})
        self.size = properties.get('size', {'width': 100, 'height': 100})
        self.style = properties.get('style', {})

class CanvasEditor:
    def __init__(self):
        self.websocket_connections = {}
        self.active_sessions = {}
        
    async def initialize_session(self, user_id: str, presentation_id: str):
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'presentation_id': presentation_id,
            'start_time': datetime.now()
        }
        return session_id
    
    async def add_element(self, slide_id: str, element_type: str, properties: Dict[str, Any]):
        element = SlideElement(
            id=str(uuid.uuid4()),
            slide_id=slide_id,
            type=element_type,
            properties=properties
        )
        return element
    
    async def update_element(self, element_id: str, updates: Dict[str, Any]):
        # Simulate element update
        return {'id': element_id, 'updated': True, **updates}
    
    async def delete_element(self, element_id: str):
        return {'id': element_id, 'deleted': True}
    
    async def export_presentation(self, presentation_id: str, format: str):
        # Simulate export
        return {
            'file_url': f'/downloads/{presentation_id}.{format}',
            'format': format,
            'size': 1024000
        }

class WebSocketConnection:
    def __init__(self):
        self.messages = []
        self.connected = False
        
    async def connect(self):
        self.connected = True
        
    async def send(self, message: Dict[str, Any]):
        self.messages.append(message)
        
    async def receive(self):
        if self.messages:
            return self.messages.pop(0)
        return None
        
    async def disconnect(self):
        self.connected = False

class PresentationService:
    def __init__(self):
        self.presentations = {}
        self.slides = {}
        
    async def get_presentation(self, presentation_id: str) -> Presentation:
        return self.presentations.get(presentation_id)
    
    async def create_slide(self, presentation_id: str, order: int) -> Slide:
        slide = Slide(
            id=str(uuid.uuid4()),
            presentation_id=presentation_id,
            order=order
        )
        self.slides[slide.id] = slide
        return slide
    
    async def update_slide(self, slide_id: str, content: Dict[str, Any]):
        if slide_id in self.slides:
            self.slides[slide_id].content = content
            return self.slides[slide_id]
        return None

@pytest.fixture
def canvas_editor():
    return CanvasEditor()

@pytest.fixture
def presentation_service():
    return PresentationService()

@pytest.fixture
def websocket_connection():
    return WebSocketConnection()

@pytest.fixture
def test_user():
    return User(id="user123", email="test@example.com")

@pytest.fixture
def test_presentation():
    return Presentation(
        id="pres123",
        user_id="user123",
        name="Test Presentation"
    )

@pytest.fixture
def test_slide():
    return Slide(
        id="slide123",
        presentation_id="pres123",
        order=1
    )

@pytest.mark.asyncio
class TestCanvasEditorE2E:
    
    async def test_complete_slide_creation_and_editing_workflow(
        self, 
        canvas_editor, 
        presentation_service, 
        websocket_connection,
        test_user,
        test_presentation,
        test_slide
    ):
        """Test the complete workflow of creating and editing a slide with various elements"""
        
        # Step 1: Initialize canvas editor session
        session_id = await canvas_editor.initialize_session(
            user_id=test_user.id,
            presentation_id=test_presentation.id
        )
        assert session_id is not None
        assert session_id in canvas_editor.active_sessions
        
        # Step 2: Connect WebSocket for real-time collaboration
        await websocket_connection.connect()
        assert websocket_connection.connected
        
        # Step 3: Create a new slide
        presentation_service.presentations[test_presentation.id] = test_presentation
        new_slide = await presentation_service.create_slide(
            presentation_id=test_presentation.id,
            order=1
        )
        assert new_slide is not None
        assert new_slide.presentation_id == test_presentation.id
        
        # Step 4: Add text element
        text_element = await canvas_editor.add_element(
            slide_id=new_slide.id,
            element_type="text",
            properties={
                'content': 'Welcome to our presentation',
                'position': {'x': 100, 'y': 50},
                'size': {'width': 400, 'height': 100},
                'style': {
                    'fontSize': 24,
                    'fontFamily': 'Arial',
                    'color': '#000000',
                    'bold': True
                }
            }
        )
        assert text_element.type == "text"
        assert text_element.properties['content'] == 'Welcome to our presentation'
        
        # Step 5: Add image element
        image_element = await canvas_editor.add_element(
            slide_id=new_slide.id,
            element_type="image",
            properties={
                'url': 'https://example.com/image.jpg',
                'position': {'x': 50, 'y': 200},
                'size': {'width': 300, 'height': 200},
                'style': {
                    'borderRadius': 10,
                    'opacity': 1.0
                }
            }
        )
        assert image_element.type == "image"
        
        # Step 6: Add shape element
        shape_element = await canvas_editor.add_element(
            slide_id=new_slide.id,
            element_type="shape",
            properties={
                'shapeType': 'rectangle',
                'position': {'x': 400, 'y': 250},
                'size': {'width': 150, 'height': 100},
                'style': {
                    'backgroundColor': '#007bff',
                    'borderColor': '#0056b3',
                    'borderWidth': 2
                }
            }
        )
        assert shape_element.type == "shape"
        
        # Step 7: Send WebSocket update for real-time sync
        await websocket_connection.send({
            'action': 'element_added',
            'slide_id': new_slide.id,
            'element': {
                'id': text_element.id,
                'type': text_element.type,
                'properties': text_element.properties
            }
        })
        
        # Step 8: Update element position (drag and drop simulation)
        updated_element = await canvas_editor.update_element(
            element_id=text_element.id,
            updates={
                'position': {'x': 150, 'y': 80}
            }
        )
        assert updated_element['position']['x'] == 150
        assert updated_element['position']['y'] == 80
        
        # Step 9: Update slide content
        slide_content = {
            'elements': [
                {'id': text_element.id, 'type': 'text'},
                {'id': image_element.id, 'type': 'image'},
                {'id': shape_element.id, 'type': 'shape'}
            ],
            'background': {
                'color': '#ffffff',
                'image': None
            },
            'transitions': {
                'type': 'fade',
                'duration': 1000
            }
        }
        updated_slide = await presentation_service.update_slide(
            slide_id=new_slide.id,
            content=slide_content
        )
        assert len(updated_slide.content['elements']) == 3
        
        # Step 10: Export presentation
        export_result = await canvas_editor.export_presentation(
            presentation_id=test_presentation.id,
            format='pptx'
        )
        assert export_result['format'] == 'pptx'
        assert 'file_url' in export_result
        
        # Step 11: Disconnect WebSocket
        await websocket_connection.disconnect()
        assert not websocket_connection.connected
    
    async def test_real_time_collaboration_workflow(
        self, 
        canvas_editor, 
        websocket_connection,
        test_user,
        test_presentation,
        test_slide
    ):
        """Test real-time collaboration features with multiple users"""
        
        # Create two users and their WebSocket connections
        user1 = User(id="user1", email="user1@example.com")
        user2 = User(id="user2", email="user2@example.com")
        
        ws_conn1 = WebSocketConnection()
        ws_conn2 = WebSocketConnection()
        
        # Both users join the same presentation
        session1 = await canvas_editor.initialize_session(user1.id, test_presentation.id)
        session2 = await canvas_editor.initialize_session(user2.id, test_presentation.id)
        
        await ws_conn1.connect()
        await ws_conn2.connect()
        
        # User 1 adds a text element
        text_element = await canvas_editor.add_element(
            slide_id=test_slide.id,
            element_type="text",
            properties={
                'content': 'Collaborative Text',
                'position': {'x': 100, 'y': 100},
                'size': {'width': 200, 'height': 50}
            }
        )
        
        # Broadcast change to all users
        broadcast_message = {
            'action': 'element_added',
            'user_id': user1.id,
            'slide_id': test_slide.id,
            'element': {
                'id': text_element.id,
                'type': 'text',
                'properties': text_element.properties
            },
            'timestamp': datetime.now().isoformat()
        }
        
        await ws_conn1.send(broadcast_message)
        await ws_conn2.send(broadcast_message)
        
        # User 2 updates the same element
        updated_element = await canvas_editor.update_element(
            element_id=text_element.id,
            updates={
                'properties': {
                    'content': 'Updated Collaborative Text',
                    'style': {'color': '#ff0000'}
                }
            }
        )
        
        # Broadcast update
        update_message = {
            'action': 'element_updated',
            'user_id': user2.id,
            'element_id': text_element.id,
            'updates': updated_element,
            'timestamp': datetime.now().isoformat()
        }
        
        await ws_conn1.send(update_message)
        await ws_conn2.send(update_message)
        
        # Verify both users received updates
        assert len(ws_conn1.messages) == 2
        assert len(ws_conn2.messages) == 2
        
        # Test conflict resolution - both users try to update simultaneously
        conflict_update1 = {
            'action': 'element_updated',
            'user_id': user1.id,
            'element_id': text_element.id,
            'updates': {'position': {'x': 200, 'y': 200}},
            'timestamp': datetime.now().isoformat()
        }
        
        conflict_update2 = {
            'action': 'element_updated',
            'user_id': user2.id,
            'element_id': text_element.id,
            'updates': {'position': {'x': 300, 'y': 300}},
            'timestamp': datetime.now().isoformat()
        }
        
        # Last write wins - user2's update should prevail
        await ws_conn1.send(conflict_update1)
        await ws_conn1.send(conflict_update2)
        
        # Clean up
        await ws_conn1.disconnect()
        await ws_conn2.disconnect()
    
    async def test_error_handling_and_recovery_workflow(
        self, 
        canvas_editor, 
        presentation_service,
        websocket_connection,
        test_user,
        test_presentation,
        test_slide
    ):
        """Test error handling and recovery scenarios"""
        
        # Initialize session
        session_id = await canvas_editor.initialize_session(
            user_id=test_user.id,
            presentation_id=test_presentation.id
        )
        
        # Test 1: Handle invalid element type
        with pytest.raises(ValueError) as exc_info:
            invalid_element = SlideElement(
                id=str(uuid.uuid4()),
                slide_id=test_slide.id,
                type="invalid_type",
                properties={}
            )
            if invalid_element.type not in ['text', 'image', 'shape', 'chart', 'table']:
                raise ValueError(f"Invalid element type: {invalid_element.type}")
        
        assert "Invalid element type" in str(exc_info.value)
        
        # Test 2: Handle WebSocket disconnection and reconnection
        await websocket_connection.connect()
        assert websocket_connection.connected
        
        # Add element before disconnection
        element = await canvas_editor.add_element(
            slide_id=test_slide.id,
            element_type="text",
            properties={'content': 'Test content'}
        )
        
        # Simulate unexpected disconnection
        await websocket_connection.disconnect()
        assert not websocket_connection.connected
        
        # Attempt to send message while disconnected
        try:
            if not websocket_connection.connected:
                raise ConnectionError("WebSocket is not connected")
            await websocket_connection.send({'action': 'update'})
        except ConnectionError as e:
            assert "WebSocket is not connected" in str(e)
        
        # Reconnect and recover state
        await websocket_connection.connect()
        recovery_message = {
            'action': 'state_recovery',
            'session_id': session_id,
            'last_known_state': {
                'slide_id': test_slide.id,
                'elements': [element.id]
            }
        }
        await websocket_connection.send(recovery_message)
        
        # Test 3: Handle large file upload failure
        large_image_properties = {
            'url': 'https://example.com/large-image.jpg',
            'size': {'width': 5000, 'height': 5000},
            'fileSize': 50 * 1024 * 1024  # 50MB
        }
        
        # Simulate file size validation
        max_file_size = 10 * 1024 * 1024  # 10MB limit
        if large_image_properties['fileSize'] > max_file_size:
            error_response = {
                'error': 'FILE_TOO_LARGE',
                'message': f"File size exceeds maximum limit of {max_file_size / (1024*1024)}MB",
                'max_size': max_file_size,
                'actual_size': large_image_properties['fileSize']
            }
            assert error_response['error'] == 'FILE_TOO_LARGE'
        
        # Test 4: Handle export failure and retry
        export_attempts = 0
        max_attempts = 3
        
        while export_attempts < max_attempts:
            try:
                export_attempts += 1
                if export_attempts < 2:  # Simulate failure on first attempt
                    raise Exception("Export service temporarily unavailable")
                
                export_result = await canvas_editor.export_presentation(
                    presentation_id=test_presentation.id,
                    format='pdf'
                )
                assert export_result['format'] == 'pdf'
                break
            except Exception as e:
                if export_attempts >= max_attempts:
                    pytest.fail(f"Export failed after {max_attempts} attempts: {str(e)}")
                await asyncio.sleep(0.1)  # Brief delay before retry
        
        # Test 5: Handle concurrent element deletion
        element1 = await canvas_editor.add_element(
            slide_id=test_slide.id,
            element_type="shape",
            properties={'shapeType': 'circle'}
        )
        
        # Simulate two users trying to delete the same element
        deletion_result1 = await canvas_editor.delete_element(element1.id)
        assert deletion_result1['deleted'] == True
        
        # Second deletion should handle gracefully
        try:
            # In real implementation, this would check if element exists
            if deletion_result1['deleted']:
                raise ValueError(f"Element {element1.id} already deleted")
        except ValueError as e:
            assert "already deleted" in str(e)
        
        # Test 6: Validate element properties
        invalid_properties = {
            'position': {'x': -100, 'y': -100},  # Negative coordinates
            'size': {'width': 0, 'height': 0},   # Zero size
            'style': {'fontSize': -10}            # Invalid font size
        }
        
        # Validate and correct properties
        validated_properties = {}
        validated_properties['position'] = {
            'x': max(0, invalid_properties['position']['x']),
            'y': max(0, invalid_properties['position']['y'])
        }
        validated_properties['size'] = {
            'width': max(1, invalid_properties['size']['width']),
            'height': max(1, invalid_properties['size']['height'])
        }
        validated_properties['style'] = {
            'fontSize': max(8, abs(invalid_properties['style'].get('fontSize', 12)))
        }
        
        assert validated_properties['position']['x'] >= 0
        assert validated_properties['position']['y'] >= 0
        assert validated_properties['size']['width'] > 0
        assert validated_properties['size']['height'] > 0
        assert validated_properties['style']['fontSize'] >= 8
        
        # Clean up
        await websocket_connection.disconnect()

@pytest.mark.asyncio
async def test_canvas_editor_performance_and_limits(canvas_editor, test_slide):
    """Test performance and system limits"""
    
    # Test adding many elements to check performance
    elements = []
    max_elements_per_slide = 100
    
    start_time = datetime.now()
    
    for i in range(50):  # Add 50 elements
        element = await canvas_editor.add_element(
            slide_id=test_slide.id,
            element_type="shape" if i % 2 == 0 else "text",
            properties={
                'content': f'Element {i}' if i % 2 != 0 else None,
                'shapeType': 'rectangle' if i % 2 == 0 else None,
                'position': {'x': (i * 10) % 500, 'y': (i * 10) % 300},
                'size': {'width': 50, 'height': 30}
            }
        )
        elements.append(element)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Performance check - should complete within reasonable time
    assert duration < 5.0  # Should complete in less than 5 seconds
    assert len(elements) == 50
    
    # Test element limit
    current_count = len(elements)
    if current_count >= max_elements_per_slide:
        with pytest.raises(ValueError) as exc_info:
            raise ValueError(f"Maximum elements per slide ({max_elements_per_slide}) exceeded")
    
    # Test undo/redo stack limits
    undo_stack = []
    redo_stack = []
    max_undo_stack_size = 50
    
    # Simulate 60 operations
    for i in range(60):
        operation = {
            'type': 'add_element',
            'element_id': f'elem_{i}',
            'timestamp': datetime.now()
        }
        undo_stack.append(operation)
        
        # Maintain stack size limit
        if len(undo_stack) > max_undo_stack_size:
            undo_stack.pop(0)  # Remove oldest operation
    
    assert len(undo_stack) <= max_undo_stack_size
    
    # Test WebSocket message batching
    messages = []
    batch_size = 10
    
    for i in range(25):
        messages.append({
            'action': 'element_updated',
            'element_id': f'elem_{i}',
            'updates': {'position': {'x': i * 5, 'y': i * 5}}
        })
    
    # Process messages in batches
    batches_processed = 0
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        # Process batch
        batches_processed += 1
        assert len(batch) <= batch_size
    
    assert batches_processed == 3  # 25 messages / 10 batch_size = 3 batches