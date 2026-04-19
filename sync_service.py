# sync_service.py (with detailed error logging)
import asyncio
import json
import pyodbc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, List

# ==================== CONFIGURATION ====================
DB_PATH = r"D:\Gestiune_og\omnigest2018.accdb"
DB_PASSWORD = "qaz"
HOST = "0.0.0.0"
PORT = 8000
# =======================================================

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=' + DB_PATH + ';'
        f'PWD={DB_PASSWORD};'
    )
    print(f"Attempting connection with: DRIVER=... DBQ={DB_PATH} PWD=***")
    return pyodbc.connect(conn_str)

def fetch_products_from_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("Connected. Executing query...")
        cursor.execute("SELECT den_raion FROM RAIOANE ORDER BY den_raion")
        rows = cursor.fetchall()
        conn.close()
        products = []
        for row in rows:
            name = row[0] if row[0] else "Unnamed"
            products.append({"name": name, "emoji": "📋", "price": 0.0})
        print(f"Successfully loaded {len(products)} products.")
        return products
    except Exception as e:
        print(f"!!! DATABASE ERROR: {type(e).__name__}: {e}")
        # Also print the full traceback for more detail
        import traceback
        traceback.print_exc()
        return [{"name": f"Error: {str(e)[:50]}", "emoji": "⚠️", "price": 0.0}]

# In-memory orders
orders: Dict[int, List[dict]] = {i: [] for i in range(1, 13)}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/products")
async def get_products():
    return fetch_products_from_db()

@app.get("/orders")
async def get_orders():
    return orders

@app.post("/order")
async def update_order(order_update: dict):
    table = order_update.get("table")
    action = order_update.get("action")
    item = order_update.get("item")

    if table not in orders:
        return {"status": "error", "message": "Invalid table number"}

    if action == "add":
        for existing in orders[table]:
            if existing["name"] == item["name"]:
                existing["qty"] += 1
                break
        else:
            orders[table].append({"name": item["name"], "emoji": item["emoji"],
                                  "qty": 1, "price": item["price"]})
    elif action == "remove":
        for existing in orders[table]:
            if existing["name"] == item["name"]:
                if existing["qty"] > 1:
                    existing["qty"] -= 1
                else:
                    orders[table].remove(existing)
                break
    elif action == "set_qty":
        qty = order_update.get("qty", 1)
        for existing in orders[table]:
            if existing["name"] == item["name"]:
                if qty <= 0:
                    orders[table].remove(existing)
                else:
                    existing["qty"] = qty
                break

    await manager.broadcast({"type": "orders_update", "data": orders})
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "orders_update", "data": orders})
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    print(f"Sync service starting at http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)