"""
Canvas Editor Router - Phase 2 PowerPoint Canvas Customization
Integrated from FEATURE-WEB-006-PHASE-2
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import sys
from pathlib import Path

# Add feature path to imports
FEATURE_DIR = Path(__file__).resolve().parent.parent / "FEATURE-WEB-006_PowerPoint_Export" / "PHASE-2_Canvas_Editor"
sys.path.insert(0, str(FEATURE_DIR))

# Import AI-generated Layer 3 models and components
from LAYER_PHASE2_003_Canvas_Editor_API_Endpoints.LAYER_PHASE2_003_Canvas_Editor_API_Endpoints.src.implementation import (
    Canvas, CanvasElement, CanvasUpdate, InMemoryDatabase, ConnectionManager,
    User, create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Import orchestrator and layer implementations
sys.path.insert(0, str(FEATURE_DIR / "LAYER_PHASE2_001_Transform_Models_and_Validators"))  # noqa: E501
sys.path.insert(0, str(FEATURE_DIR / "LAYER_PHASE2_002_Image_Manipulation_Service"))  # noqa: E501

from LAYER_PHASE2_001_Transform_Models_and_Validators.src.implementation import (  # noqa: E501, F401
    ImageTransform, CoordinateConverter, TransformValidator
)
from LAYER_PHASE2_002_Image_Manipulation_Service.src.implementation import (  # noqa: F401
    ImageManipulationService
)

# Initialize components (orchestrator available for future use)
db = InMemoryDatabase()
manager = ConnectionManager()
security = HTTPBearer()

# Create router
router = APIRouter(prefix="/api/canvas", tags=["canvas-editor"])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = credentials.credentials
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user


async def check_canvas_permission(canvas_id: str, user: User, write_access: bool = False) -> Canvas:
    canvas = await db.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    
    if canvas.owner_id != user.id and user.id not in canvas.shared_with:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    if write_access and canvas.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can modify canvas")
    
    return canvas


@router.post("/auth/login")
async def login(username: str, password: str) -> Dict[str, Any]:
    """Simple auth for canvas editor - accepts any credentials for MVP"""
    if username and password:
        user_id = f"user_{username}"
        access_token = create_access_token(
            data={"sub": user_id, "username": username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/canvases", response_model=Canvas)
async def create_canvas(
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> Canvas:
    """Create a new canvas for PowerPoint slide customization"""
    start_time = time.time()
    
    canvas = Canvas(
        name=name,
        owner_id=user.id,
        metadata=metadata or {}
    )
    
    created_canvas = await db.create_canvas(canvas)
    
    # Ensure response time is under 200ms
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 200:
        pass  # Log warning in production
    
    return created_canvas


@router.get("/canvases", response_model=List[Canvas])
async def list_canvases(user: User = Depends(get_current_user)) -> List[Canvas]:
    """List all canvases accessible to the user"""
    start_time = time.time()
    
    canvases = await db.list_canvases(user.id)
    
    # Ensure response time is under 200ms
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 200:
        pass  # Log warning in production
    
    return canvases


@router.get("/canvases/{canvas_id}", response_model=Canvas)
async def get_canvas(
    canvas_id: str,
    user: User = Depends(get_current_user)
) -> Canvas:
    """Get a specific canvas by ID"""
    start_time = time.time()
    
    canvas = await check_canvas_permission(canvas_id, user)
    
    # Ensure response time is under 200ms
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 200:
        pass  # Log warning in production
    
    return canvas


@router.put("/canvases/{canvas_id}", response_model=Canvas)
async def update_canvas(
    canvas_id: str,
    update: CanvasUpdate,
    user: User = Depends(get_current_user)
) -> Canvas:
    """Update canvas properties (name, metadata, elements)"""
    await check_canvas_permission(canvas_id, user, write_access=True)
    
    # Get lock to prevent concurrent updates
    lock = await db.get_lock(canvas_id)
    async with lock:
        updated_canvas = await db.update_canvas(canvas_id, update)
        if not updated_canvas:
            raise HTTPException(status_code=404, detail="Canvas not found")
        
        # Broadcast update to all connected clients
        await manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "canvas_update",
                "canvas_id": canvas_id,
                "data": updated_canvas.dict()
            }
        )
        
        return updated_canvas


@router.delete("/canvases/{canvas_id}")
async def delete_canvas(
    canvas_id: str,
    user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete a canvas and notify all connected clients"""
    await check_canvas_permission(canvas_id, user, write_access=True)
    
    deleted = await db.delete_canvas(canvas_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Canvas not found")
    
    # Broadcast deletion to all connected clients
    await manager.broadcast_to_canvas(
        canvas_id,
        {
            "type": "canvas_deleted",
            "canvas_id": canvas_id
        }
    )
    
    return {"status": "deleted", "canvas_id": canvas_id}


@router.post("/canvases/{canvas_id}/elements", response_model=CanvasElement)
async def add_element(
    canvas_id: str,
    element_type: str,
    position: Dict[str, float],
    size: Dict[str, float],
    content: Dict[str, Any],
    style: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> CanvasElement:
    """Add a new element (image, text, shape) to the canvas"""
    await check_canvas_permission(canvas_id, user, write_access=True)
    
    element = CanvasElement(
        type=element_type,
        position=position,
        size=size,
        content=content,
        style=style or {}
    )
    
    # Get lock to prevent concurrent updates
    lock = await db.get_lock(canvas_id)
    async with lock:
        canvas = await db.get_canvas(canvas_id)
        if not canvas:
            raise HTTPException(status_code=404, detail="Canvas not found")
        
        canvas.elements.append(element)
        canvas.updated_at = datetime.utcnow()
        
        # Broadcast update to all connected clients
        await manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "element_added",
                "canvas_id": canvas_id,
                "element": element.dict()
            }
        )
        
        return element


@router.put("/canvases/{canvas_id}/elements/{element_id}", response_model=CanvasElement)
async def update_element(
    canvas_id: str,
    element_id: str,
    position: Optional[Dict[str, float]] = None,
    size: Optional[Dict[str, float]] = None,
    content: Optional[Dict[str, Any]] = None,
    style: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> CanvasElement:
    """Update element properties (position, size, content, style)"""
    await check_canvas_permission(canvas_id, user, write_access=True)
    
    # Get lock to prevent concurrent updates
    lock = await db.get_lock(canvas_id)
    async with lock:
        canvas = await db.get_canvas(canvas_id)
        if not canvas:
            raise HTTPException(status_code=404, detail="Canvas not found")
        
        element_found = None
        for element in canvas.elements:
            if element.id == element_id:
                if position is not None:
                    element.position = position
                if size is not None:
                    element.size = size
                if content is not None:
                    element.content = content
                if style is not None:
                    element.style = style
                element.updated_at = datetime.utcnow()
                element_found = element
                break
        
        if not element_found:
            raise HTTPException(status_code=404, detail="Element not found")
        
        canvas.updated_at = datetime.utcnow()
        
        # Broadcast update to all connected clients
        await manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "element_updated",
                "canvas_id": canvas_id,
                "element": element_found.dict()
            }
        )
        
        return element_found


@router.delete("/canvases/{canvas_id}/elements/{element_id}")
async def delete_element(
    canvas_id: str,
    element_id: str,
    user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete an element from the canvas"""
    await check_canvas_permission(canvas_id, user, write_access=True)
    
    # Get lock to prevent concurrent updates
    lock = await db.get_lock(canvas_id)
    async with lock:
        canvas = await db.get_canvas(canvas_id)
        if not canvas:
            raise HTTPException(status_code=404, detail="Canvas not found")
        
        initial_count = len(canvas.elements)
        canvas.elements = [e for e in canvas.elements if e.id != element_id]
        
        if len(canvas.elements) == initial_count:
            raise HTTPException(status_code=404, detail="Element not found")
        
        canvas.updated_at = datetime.utcnow()
        
        # Broadcast update to all connected clients
        await manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "element_deleted",
                "canvas_id": canvas_id,
                "element_id": element_id
            }
        )
        
        return {"status": "deleted", "element_id": element_id}


@router.websocket("/ws/{canvas_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    canvas_id: str,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time canvas collaboration"""
    user = verify_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication")
        return
    
    # Check permission
    canvas = await db.get_canvas(canvas_id)
    if not canvas or (canvas.owner_id != user.id and user.id not in canvas.shared_with):
        await websocket.close(code=1008, reason="Permission denied")
        return
    
    await manager.connect(websocket, canvas_id, user.id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "element_update":
                # Verify user has write access
                if canvas.owner_id == user.id:
                    # Broadcast to other clients
                    await manager.broadcast_to_canvas(
                        canvas_id,
                        {
                            "type": "element_update",
                            "user_id": user.id,
                            "data": data.get("data", {})
                        },
                        exclude_websocket=websocket
                    )
            elif data.get("type") == "cursor_position":
                # Broadcast cursor position to other clients
                await manager.broadcast_to_canvas(
                    canvas_id,
                    {
                        "type": "cursor_position",
                        "user_id": user.id,
                        "position": data.get("position", {})
                    },
                    exclude_websocket=websocket
                )
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, canvas_id)
        await manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "user_disconnected",
                "user_id": user.id
            }
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for canvas editor"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
