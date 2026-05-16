from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from dotenv import load_dotenv
import os
import json
import asyncio

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM", "HS256")

router = APIRouter(tags=["WebSocket"])

# In-memory connection registry
# { tradie_id: WebSocket }
active_connections: dict[str, WebSocket] = {}

class ConnectionManager:
    async def connect(self, tradie_id: str, websocket: WebSocket):
        await websocket.accept()
        active_connections[tradie_id] = websocket
        print(f"Tradie {tradie_id} connected via WebSocket")

    def disconnect(self, tradie_id: str):
        active_connections.pop(tradie_id, None)
        print(f"Tradie {tradie_id} disconnected")

    async def send_to_tradie(self, tradie_id: str, message: dict):
        ws = active_connections.get(tradie_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(tradie_id)

manager = ConnectionManager()

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # Validate JWT token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tradie_id = payload.get("sub")
        if not tradie_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await manager.connect(tradie_id, websocket)

    try:
        # Keep connection alive — wait for disconnect
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        manager.disconnect(tradie_id)