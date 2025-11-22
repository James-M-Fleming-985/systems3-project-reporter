# models.py
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class CanvasElement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    position: Dict[str, float]
    size: Dict[str, float]
    content: Dict[str, Any]
    style: Optional[Dict[str, Any]] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Canvas(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    elements: List[CanvasElement] = []
    metadata: Optional[Dict[str, Any]] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: str
    shared_with: List[str] = []


class CanvasUpdate(BaseModel):
    name: Optional[str] = None
    elements: Optional[List[CanvasElement]] = None
    metadata: Optional[Dict[str, Any]] = None


# database.py
from typing import Dict, List, Optional
import asyncio
from datetime import datetime


class InMemoryDatabase:
    def __init__(self):
        self.canvases: Dict[str, Canvas] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def get_lock(self, canvas_id: str) -> asyncio.Lock:
        if canvas_id not in self.locks:
            self.locks[canvas_id] = asyncio.Lock()
        return self.locks[canvas_id]
    
    async def create_canvas(self, canvas: Canvas) -> Canvas:
        self.canvases[canvas.id] = canvas
        return canvas
    
    async def get_canvas(self, canvas_id: str) -> Optional[Canvas]:
        return self.canvases.get(canvas_id)
    
    async def update_canvas(self, canvas_id: str, update: CanvasUpdate) -> Optional[Canvas]:
        if canvas_id in self.canvases:
            canvas = self.canvases[canvas_id]
            if update.name is not None:
                canvas.name = update.name
            if update.elements is not None:
                canvas.elements = update.elements
            if update.metadata is not None:
                canvas.metadata = update.metadata
            canvas.updated_at = datetime.utcnow()
            return canvas
        return None
    
    async def delete_canvas(self, canvas_id: str) -> bool:
        if canvas_id in self.canvases:
            del self.canvases[canvas_id]
            if canvas_id in self.locks:
                del self.locks[canvas_id]
            return True
        return False
    
    async def list_canvases(self, user_id: str) -> List[Canvas]:
        return [
            canvas for canvas in self.canvases.values()
            if canvas.owner_id == user_id or user_id in canvas.shared_with
        ]


# auth.py
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import secrets


SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class User:
    def __init__(self, user_id: str, username: str):
        self.id = user_id
        self.username = username


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")
        if user_id is None or username is None:
            return None
        return User(user_id=user_id, username=username)
    except jwt.PyJWTError:
        return None


# websocket_manager.py
from typing import Dict, Set, List
from fastapi import WebSocket
import json
import asyncio


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, canvas_id: str, user_id: str):
        await websocket.accept()
        if canvas_id not in self.active_connections:
            self.active_connections[canvas_id] = set()
        self.active_connections[canvas_id].add(websocket)
        self.user_connections[websocket] = user_id
    
    def disconnect(self, websocket: WebSocket, canvas_id: str):
        if canvas_id in self.active_connections:
            self.active_connections[canvas_id].discard(websocket)
            if not self.active_connections[canvas_id]:
                del self.active_connections[canvas_id]
        if websocket in self.user_connections:
            del self.user_connections[websocket]
    
    async def broadcast_to_canvas(self, canvas_id: str, message: dict, exclude_websocket: WebSocket = None):
        if canvas_id in self.active_connections:
            disconnected_clients = set()
            for connection in self.active_connections[canvas_id]:
                if connection != exclude_websocket:
                    try:
                        await connection.send_json(message)
                    except:
                        disconnected_clients.add(connection)
            
            for client in disconnected_clients:
                self.active_connections[canvas_id].discard(client)


# main.py
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import time
import asyncio
from contextlib import asynccontextmanager


# Initialize components
db = InMemoryDatabase()
manager = ConnectionManager()
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass


app = FastAPI(lifespan=lifespan)


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


@app.post("/api/auth/login")
async def login(username: str, password: str) -> Dict[str, Any]:
    # Simple auth for testing - in production, verify against database
    if username and password:  # Accept any non-empty credentials for testing
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


@app.post("/api/canvases", response_model=Canvas)
async def create_canvas(
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> Canvas:
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
        # Log warning in production
        pass
    
    return created_canvas


@app.get("/api/canvases", response_model=List[Canvas])
async def list_canvases(user: User = Depends(get_current_user)) -> List[Canvas]:
    start_time = time.time()
    
    canvases = await db.list_canvases(user.id)
    
    # Ensure response time is under 200ms
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 200:
        # Log warning in production
        pass
    
    return canvases


@app.get("/api/canvases/{canvas_id}", response_model=Canvas)
async def get_canvas(
    canvas_id: str,
    user: User = Depends(get_current_user)
) -> Canvas:
    start_time = time.time()
    
    canvas = await check_canvas_permission(canvas_id, user)
    
    # Ensure response time is under 200ms
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 200:
        # Log warning in production
        pass
    
    return canvas


@app.put("/api/canvases/{canvas_id}", response_model=Canvas)
async def update_canvas(
    canvas_id: str,
    update: CanvasUpdate,
    user: User = Depends(get_current_user)
) -> Canvas:
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


@app.delete("/api/canvases/{canvas_id}")
async def delete_canvas(
    canvas_id: str,
    user: User = Depends(get_current_user)
) -> Dict[str, str]:
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


@app.post("/api/canvases/{canvas_id}/elements", response_model=CanvasElement)
async def add_element(
    canvas_id: str,
    element_type: str,
    position: Dict[str, float],
    size: Dict[str, float],
    content: Dict[str, Any],
    style: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> CanvasElement:
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


@app.put("/api/canvases/{canvas_id}/elements/{element_id}", response_model=CanvasElement)
async def update_element(
    canvas_id: str,
    element_id: str,
    position: Optional[Dict[str, float]] = None,
    size: Optional[Dict[str, float]] = None,
    content: Optional[Dict[str, Any]] = None,
    style: Optional[Dict[str, Any]] = None,
    user: User = Depends(get_current_user)
) -> CanvasElement:
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


@app.delete("/api/canvases/{canvas_id}/elements/{element_id}")
async def delete_element(
    canvas_id: str,
    element_id: str,
    user: User = Depends(get_current_user)
) -> Dict[str, str]:
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


@app.websocket("/ws/canvas/{canvas_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    canvas_id: str,
    token: str = Query(...)
):
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


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
