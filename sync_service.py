# sync_service.py (Corrected for actual Access schema)
import asyncio
import json
import pyodbc
import hashlib
import os
import time
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, List
from dbfread import DBF
import dbf

# ==================== CONFIGURATION ====================
ACCESS_DB_PATH = r"D:\Gestiune_og\omnigest2018.accdb"
ACCESS_DB_PASSWORD = "qaz"
DBF_PATH = r"D:\gestiune_touch_mm_2_retea\Fisiere\vanzare.dbf"
HOST = "0.0.0.0"
PORT = 8000

# =======================================================
# CORRECT COLUMN NAMES FOR YOUR DATABASE
# =======================================================
CAT_ID_COL = "cod"
CAT_NAME_COL = "den_raion"
PROD_GRUPA_COL = "grupa"
PROD_NAME_COL = "den"
PROD_PRICE_COL = "pretv"   # selling price
# =======================================================

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- Access Database Helper -------------------
def get_access_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=' + ACCESS_DB_PATH + ';'
        f'PWD={ACCESS_DB_PASSWORD};'
    )
    return pyodbc.connect(conn_str)

# ------------------- Fetch Products with Categories -------------------
def fetch_products():
    try:
        conn = get_access_connection()
        cursor = conn.cursor()

        print(f"[Products] Using category columns: {CAT_ID_COL}, {CAT_NAME_COL}")
        print(f"[Products] Using product columns: {PROD_GRUPA_COL}, {PROD_NAME_COL}, {PROD_PRICE_COL}")

        # Fetch categories
        cursor.execute(f"SELECT [{CAT_ID_COL}], [{CAT_NAME_COL}] FROM RAIOANE ORDER BY [{CAT_NAME_COL}]")
        categories = []
        cat_map = {}
        for row in cursor.fetchall():
            cat_id = row[0]
            cat_name = (row[1] or "").strip()
            if not cat_name:
                cat_name = "Unnamed"
            cat = {
                "id": cat_id,
                "name": cat_name,
                "emoji": "📁",
                "products": []
            }
            categories.append(cat)
            cat_map[cat_id] = cat

        # Fetch products
        cursor.execute(f"""
            SELECT [{PROD_GRUPA_COL}], [{PROD_NAME_COL}], [{PROD_PRICE_COL}]
            FROM CATALOG_PRODUSE
            WHERE [{PROD_NAME_COL}] IS NOT NULL AND TRIM([{PROD_NAME_COL}]) <> ''
            ORDER BY [{PROD_NAME_COL}]
        """)
        for row in cursor.fetchall():
            grupa = row[0]
            name = (row[1] or "").strip()
            price = row[2] if row[2] is not None else 0.0
            if grupa in cat_map and name:
                cat_map[grupa]["products"].append({
                    "name": name,
                    "emoji": "📋",
                    "price": float(price)
                })

        conn.close()

        # Remove categories with no products
        categories = [c for c in categories if c["products"]]
        print(f"[Products] Loaded {sum(len(c['products']) for c in categories)} products in {len(categories)} categories.")
        return categories

    except Exception as e:
        print("\n=== ERROR FETCHING PRODUCTS ===")
        traceback.print_exc()
        print("================================\n")
        return [{
            "id": 0,
            "name": f"Error: {str(e)}",
            "emoji": "⚠️",
            "products": []
        }]

# ------------------- Simple DBF Reader -------------------
def load_orders_from_dbf():
    orders = {i: [] for i in range(1, 13)}
    if not os.path.exists(DBF_PATH):
        print(f"[Warning] DBF file not found at {DBF_PATH}")
        return orders

    try:
        table = DBF(DBF_PATH, ignore_missing_memofile=True)
        for record in table:
            den = (record.get('DEN') or '').strip()
            cantitate = record.get('CANTITATE', 0)
            nr_masa = record.get('NR_MASA', 0)
            if den and nr_masa and 1 <= int(nr_masa) <= 12:
                orders[int(nr_masa)].append({
                    "name": den,
                    "emoji": "📋",
                    "qty": int(float(cantitate)) if cantitate else 1,
                    "price": 0.0
                })
        print("[DBF] Read successful.")
    except Exception as e:
        print(f"[DBF] Read error: {e}")

    return orders

# ------------------- DBF Write (with retries) -------------------
def save_order_to_dbf(table, action, item, qty=None):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            dbf_file = dbf.Table(DBF_PATH)
            dbf_file.open(mode=dbf.READ_WRITE)
            try:
                if action == "add":
                    found = False
                    for rec in dbf_file:
                        if rec.NR_MASA == table and rec.DEN.strip() == item["name"]:
                            rec.CANTITATE = rec.CANTITATE + 1
                            dbf.write(rec)
                            found = True
                            break
                    if not found:
                        new_rec = dbf_file.new_record()
                        new_rec.NR_MASA = table
                        new_rec.DEN = item["name"]
                        new_rec.CANTITATE = 1
                        dbf.write(new_rec)
                elif action == "remove":
                    for rec in dbf_file:
                        if rec.NR_MASA == table and rec.DEN.strip() == item["name"]:
                            if rec.CANTITATE > 1:
                                rec.CANTITATE = rec.CANTITATE - 1
                                dbf.write(rec)
                            else:
                                dbf.delete(rec)
                            break
                elif action == "set_qty":
                    if qty <= 0:
                        for rec in dbf_file:
                            if rec.NR_MASA == table and rec.DEN.strip() == item["name"]:
                                dbf.delete(rec)
                                break
                    else:
                        found = False
                        for rec in dbf_file:
                            if rec.NR_MASA == table and rec.DEN.strip() == item["name"]:
                                rec.CANTITATE = qty
                                dbf.write(rec)
                                found = True
                                break
                        if not found:
                            new_rec = dbf_file.new_record()
                            new_rec.NR_MASA = table
                            new_rec.DEN = item["name"]
                            new_rec.CANTITATE = qty
                            dbf.write(new_rec)
                dbf_file.pack()
                dbf_file.close()
                return True
            except Exception:
                dbf_file.close()
                raise
        except PermissionError:
            time.sleep(0.5 * (2 ** attempt))
        except Exception as e:
            print(f"Write error attempt {attempt+1}: {e}")
            time.sleep(0.5)
    return False

# ------------------- WebSocket Manager -------------------
class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
    async def broadcast(self, msg: dict):
        for ws in self.connections:
            try:
                await ws.send_json(msg)
            except:
                pass

manager = ConnectionManager()
orders_cache = load_orders_from_dbf()
last_hash = ""

def hash_orders(orders):
    return hashlib.md5(json.dumps(orders, sort_keys=True).encode()).hexdigest()

# ------------------- HTTP Endpoints -------------------
@app.get("/products")
async def get_products():
    return fetch_products()

@app.get("/orders")
async def get_orders():
    return orders_cache

@app.post("/order")
async def update_order(data: dict):
    table = data.get("table")
    action = data.get("action")
    item = data.get("item")
    qty = data.get("qty")
    if not save_order_to_dbf(table, action, item, qty):
        return {"status": "error", "message": "DBF write failed"}
    global orders_cache, last_hash
    orders_cache = load_orders_from_dbf()
    last_hash = hash_orders(orders_cache)
    await manager.broadcast({"type": "orders_update", "data": orders_cache})
    return {"status": "ok"}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({"type": "orders_update", "data": orders_cache})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ------------------- Polling -------------------
async def poll_dbf():
    global orders_cache, last_hash
    while True:
        await asyncio.sleep(2)
        fresh = load_orders_from_dbf()
        new_hash = hash_orders(fresh)
        if new_hash != last_hash:
            orders_cache = fresh
            last_hash = new_hash
            await manager.broadcast({"type": "orders_update", "data": orders_cache})
            print("DBF change broadcasted.")

@app.on_event("startup")
async def startup():
    global last_hash
    last_hash = hash_orders(orders_cache)
    asyncio.create_task(poll_dbf())

if __name__ == "__main__":
    print(f"Sync service running at http://{HOST}:{PORT}")
    print(f"Reading DBF from: {DBF_PATH}")
    uvicorn.run(app, host=HOST, port=PORT)