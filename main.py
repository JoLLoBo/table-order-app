# mobile_app.py (Complete - Expandable category panels)
import flet as ft
import requests
import json
import asyncio
import websockets

# ==================== CONFIGURATION ====================
SERVER_IP = "192.168.1.129"   # <-- CHANGE THIS to your PC's IP
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws"
# =======================================================

def main(page: ft.Page):
    page.title = "Table Orders"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # ------------------- Global State -------------------
    products = []  # List of categories, each with 'products'
    orders = {i: [] for i in range(1, 13)}
    current_table = None
    current_update_order_list = None

    # ------------------- UI Components -------------------
    grid = ft.Row(wrap=True, spacing=20, run_spacing=20, alignment=ft.MainAxisAlignment.CENTER)
    status_text = ft.Text("", color=ft.Colors.GREY_500)

    def show_table_grid():
        grid.controls.clear()
        for t in range(1, 13):
            item_count = len(orders.get(t, []))
            color = ft.Colors.GREEN_400 if item_count == 0 else ft.Colors.ORANGE_400
            btn = ft.FilledButton(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"Table {t}", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{item_count} items", size=14),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=15,
                ),
                bgcolor=color,
                color=ft.Colors.WHITE,
                width=160,
                height=130,
                on_click=lambda e, table=t: select_table(table)
            )
            grid.controls.append(btn)
        page.update()

    # ------------------- Network Functions -------------------
    def fetch_products():
        nonlocal products
        try:
            resp = requests.get(f"{BASE_URL}/products", timeout=5)
            resp.raise_for_status()
            products = resp.json()
            print(f"Fetched {len(products)} categories")
            status_text.value = "Connected"
            status_text.color = ft.Colors.GREEN_500
        except Exception as e:
            status_text.value = f"Error: {e}"
            status_text.color = ft.Colors.RED_500
            products = [{"id": 0, "name": "Offline", "emoji": "❌", "products": []}]
        page.update()

    def fetch_orders():
        nonlocal orders
        try:
            resp = requests.get(f"{BASE_URL}/orders", timeout=5)
            resp.raise_for_status()
            orders = resp.json()
            orders = {int(k): v for k, v in orders.items()}
        except Exception as e:
            print(f"Fetch orders error: {e}")
        show_table_grid()
        page.update()

    def send_order_update(table, action, item, qty=None):
        payload = {"table": table, "action": action, "item": item}
        if qty is not None:
            payload["qty"] = qty
        try:
            requests.post(f"{BASE_URL}/order", json=payload, timeout=3)
        except Exception as e:
            status_text.value = f"Send error: {e}"
            status_text.color = ft.Colors.RED_500
            page.update()

    # ------------------- WebSocket Listener -------------------
    async def websocket_listener():
        while True:
            try:
                async with websockets.connect(WS_URL, ping_interval=None) as websocket:
                    status_text.value = "Connected (live)"
                    status_text.color = ft.Colors.GREEN_500
                    page.update()
                    while True:
                        msg = await websocket.recv()
                        data = json.loads(msg)
                        if data.get("type") == "orders_update":
                            nonlocal orders
                            raw_orders = data["data"]
                            orders = {int(k): v for k, v in raw_orders.items()}
                            if current_table is None:
                                show_table_grid()
                            else:
                                if current_update_order_list:
                                    current_update_order_list()
            except Exception as e:
                status_text.value = f"Reconnecting... ({str(e)[:30]})"
                status_text.color = ft.Colors.ORANGE_500
                page.update()
                await asyncio.sleep(3)

    # ------------------- Table Order Screen -------------------
    def select_table(table):
        nonlocal current_table, current_update_order_list
        current_table = table
        page.controls.clear()

        # Header
        page.add(ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: back_to_grid()),
            ft.Text(f"Table {table}", size=28, weight=ft.FontWeight.BOLD),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        order_list = ft.ListView(expand=True, spacing=10)

        def update_order_list():
            order_list.controls.clear()
            for item in orders.get(table, []):
                row = ft.Row([
                    ft.Text(f"{item['emoji']} {item['name']}", expand=True, size=18),
                    ft.Text(f"${item['price']:.2f}" if item['price'] > 0 else "",
                            size=16, color=ft.Colors.BLUE_700),
                    ft.IconButton(icon=ft.Icons.REMOVE,
                                  on_click=lambda e, i=item: change_qty(i, -1)),
                    ft.Text(str(item["qty"]), width=40, text_align=ft.TextAlign.CENTER, size=18),
                    ft.IconButton(icon=ft.Icons.ADD,
                                  on_click=lambda e, i=item: change_qty(i, 1)),
                ])
                order_list.controls.append(row)
            page.update()

        current_update_order_list = update_order_list

        def change_qty(item, delta):
            new_qty = item["qty"] + delta
            if new_qty <= 0:
                send_order_update(table, "remove", item)
            else:
                send_order_update(table, "set_qty", item, qty=new_qty)

        def add_item(item):
            send_order_update(table, "add", item)

        # Build expandable category panels
        category_panels = []
        for cat in products:
            if not cat.get("products"):
                continue
            product_buttons = []
            for p in cat["products"]:
                price_text = f"  ${p['price']:.2f}" if p.get('price', 0) > 0 else ""
                product_buttons.append(
                    ft.FilledButton(
                        content=ft.Text(f"{p['emoji']} {p['name']}{price_text}"),
                        on_click=lambda e, prod=p: add_item(prod)
                    )
                )
            panel = ft.ExpansionPanel(
                header=ft.ListTile(title=ft.Text(f"{cat['emoji']} {cat['name']}", size=18, weight=ft.FontWeight.BOLD)),
                content=ft.Container(
                    content=ft.Column(product_buttons, scroll=ft.ScrollMode.AUTO),
                    padding=10,
                ),
                expanded=False,
            )
            category_panels.append(panel)

        menu_section = ft.ExpansionPanelList(
            controls=category_panels,
            expanded_header_padding=10,
        )

        page.add(
            ft.Text("Current order:", size=20, weight=ft.FontWeight.BOLD),
            order_list,
            ft.Divider(),
            ft.Text("Add item:", size=20, weight=ft.FontWeight.BOLD),
            menu_section
        )
        update_order_list()

    def back_to_grid():
        nonlocal current_table, current_update_order_list
        current_table = None
        current_update_order_list = None
        page.controls.clear()
        page.add(ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD))
        page.add(grid)
        page.add(status_text)
        show_table_grid()

    # ------------------- Initial Setup -------------------
    fetch_products()
    fetch_orders()
    page.run_task(websocket_listener)

    page.add(ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD))
    page.add(grid)
    page.add(status_text)
    show_table_grid()

ft.app(target=main)