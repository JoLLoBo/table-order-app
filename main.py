# mobile_app.py (Complete – Configurable server IP via file storage)
import flet as ft
import requests
import json
import asyncio
import websockets
import os

# ==================== CONFIG FILE ====================
CONFIG_FILE = "server_config.json"


def load_config():
    """Load IP and port from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return data.get("ip"), data.get("port")
        except:
            pass
    return None, None


def save_config_to_file(ip, port):
    """Save IP and port to JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"ip": ip, "port": port}, f)


# ==================== GLOBAL CONFIG (will be set after load) ====================
SERVER_IP = None
SERVER_PORT = None
BASE_URL = None
WS_URL = None


def set_global_config(ip, port):
    """Update global variables and rebuild URLs."""
    global SERVER_IP, SERVER_PORT, BASE_URL, WS_URL
    SERVER_IP = ip
    SERVER_PORT = port
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws"


# ================================================================================


def main(page: ft.Page):
    page.title = "Table Orders"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # ------------------- Global State -------------------
    products = []
    orders = {i: [] for i in range(1, 13)}
    current_table = None
    current_update_order_list = None
    price_lookup = {}  # product name -> price

    # ------------------- UI Components -------------------
    grid = ft.Row(
        wrap=True, spacing=20, run_spacing=20, alignment=ft.MainAxisAlignment.CENTER
    )
    status_text = ft.Text("", color=ft.Colors.GREY_500)

    # ------------------- Configuration Screen -------------------
    def show_config_screen():
        """Display form to enter server IP and port."""
        page.controls.clear()
        page.overlay.clear()

        saved_ip, saved_port = load_config()

        ip_field = ft.TextField(
            label="Server IP Address", value=saved_ip if saved_ip else "", width=300
        )
        port_field = ft.TextField(
            label="Port", value=str(saved_port) if saved_port else "", width=150
        )
        error_text = ft.Text("", color=ft.Colors.RED_500)

        loading_overlay = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Text("Testing connection...", size=16),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=20,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            visible=False,
        )

        async def test_connection(ip: str, port: int) -> bool:
            url = f"http://{ip}:{port}/products"
            try:
                resp = await asyncio.to_thread(requests.get, url, timeout=3)
                resp.raise_for_status()
                return True
            except Exception:
                return False

        def on_save(e):
            ip = ip_field.value.strip()
            port_str = port_field.value.strip()
            if not ip or not port_str:
                error_text.value = "Both fields are required."
                page.update()
                return
            try:
                port = int(port_str)
                if not (1 <= port <= 65535):
                    raise ValueError
            except ValueError:
                error_text.value = "Port must be a number between 1 and 65535."
                page.update()
                return

            loading_overlay.visible = True
            error_text.value = ""
            page.update()

            async def connect_and_proceed():
                success = await test_connection(ip, port)
                if success:
                    save_config_to_file(ip, port)
                    set_global_config(ip, port)
                    page.overlay.clear()
                    page.controls.clear()
                    initialize_app()
                else:
                    loading_overlay.visible = False
                    error_text.value = "Connection failed. Check IP and port."
                    page.update()

            page.run_task(connect_and_proceed)

        def go_back(e):
            # Only go back if a valid configuration exists
            if SERVER_IP and SERVER_PORT:
                page.controls.clear()
                page.overlay.clear()
                initialize_app()
            else:
                error_text.value = "No previous configuration found."
                page.update()

        # Back button (only shown if we have a config to return to)
        back_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK, on_click=go_back, tooltip="Back to tables"
        )

        config_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row([back_btn], alignment=ft.MainAxisAlignment.START),
                        ft.Text(
                            "Connect to Server", size=28, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            "Enter the IP address and port of the PC running sync_service.py"
                        ),
                        ip_field,
                        port_field,
                        error_text,
                        ft.ElevatedButton("Test & Connect", on_click=on_save),
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=30,
                width=400,
            ),
            elevation=5,
        )

        page.add(
            ft.Stack(
                [
                    ft.Row([config_card], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Column(
                        [
                            ft.Row(
                                [loading_overlay], alignment=ft.MainAxisAlignment.CENTER
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True,
                    ),
                ],
                expand=True,
            )
        )
        page.update()

    # ------------------- Main App Initialization -------------------
    def initialize_app():
        page.controls.clear()
        page.overlay.clear()

        settings_btn = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            tooltip="Change server IP/port",
            on_click=lambda _: show_config_screen(),
        )

        page.add(
            ft.Row(
                [
                    ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD),
                    settings_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )
        page.add(grid)
        page.add(status_text)

        loading_overlay = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Text("Loading menu and orders...", size=16),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=20,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            visible=True,
        )
        page.overlay.append(loading_overlay)
        page.update()

        async def load_initial_data():
            try:
                await asyncio.to_thread(fetch_products)
                await asyncio.to_thread(fetch_orders)
            except Exception as e:
                print(f"Initial load failed: {e}")
                page.overlay.clear()
                show_config_screen()
                return

            page.overlay.clear()
            show_table_grid()
            page.run_task(websocket_listener)
            page.update()

        page.run_task(load_initial_data)

    # ------------------- Table Grid Display -------------------
    def show_table_grid():
        grid.controls.clear()
        for t in range(1, 13):
            table_items = orders.get(t, [])
            item_count = len(table_items)
            total = 0.0
            for item in table_items:
                price = price_lookup.get(item["name"], 0.0)
                total += price * item["qty"]

            # Color logic: gray when empty, green when items present
            if item_count == 0:
                bg_color = ft.Colors.GREY_400
            else:
                bg_color = ft.Colors.GREEN_400

            btn = ft.FilledButton(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"Table {t}", size=24, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{item_count} items", size=14),
                            ft.Text(
                                f"{total:.2f} RON", size=16, weight=ft.FontWeight.W_500
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=15,
                ),
                bgcolor=bg_color,
                color=ft.Colors.WHITE,  # white text works well on both gray and green
                width=180,
                height=150,
                on_click=lambda e, table=t: select_table(table),
            )
            grid.controls.append(btn)
        page.update()

    # ------------------- Network Functions -------------------
    def fetch_products():
        nonlocal products, price_lookup
        try:
            resp = requests.get(f"{BASE_URL}/products", timeout=3)
            resp.raise_for_status()
            products = resp.json()
            # Build price lookup dictionary
            price_lookup.clear()
            for cat in products:
                for p in cat.get("products", []):
                    price_lookup[p["name"]] = p.get("price", 0.0)
            print(f"Fetched {len(products)} categories, {len(price_lookup)} products")
            status_text.value = "Connected"
            status_text.color = ft.Colors.GREEN_500
        except Exception as e:
            status_text.value = f"Error: {e}"
            status_text.color = ft.Colors.RED_500
            products = [{"id": 0, "name": "Offline", "emoji": "❌", "products": []}]
            price_lookup.clear()
        page.update()

    def fetch_orders():
        nonlocal orders
        try:
            resp = requests.get(f"{BASE_URL}/orders", timeout=3)
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
        page.overlay.clear()
        nonlocal current_table, current_update_order_list
        current_table = table
        page.controls.clear()

        # Header with back button
        page.add(
            ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK, on_click=lambda _: back_to_grid()
                    ),
                    ft.Text(f"Table {table}", size=28, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

        order_list = ft.ListView(expand=True, spacing=10)
        total_price_text = ft.Text("", size=20, weight=ft.FontWeight.BOLD)

        def update_order_list():
            order_list.controls.clear()
            table_orders = orders.get(table, [])
            total = 0.0

            # Build a quick lookup map: product name -> price
            price_lookup = {}
            for cat in products:
                for p in cat.get("products", []):
                    price_lookup[p["name"]] = p.get("price", 0.0)

            for item in table_orders:
                # Get price from lookup; default to 0 if not found
                price = price_lookup.get(item["name"], 0.0)
                qty = item["qty"]
                total += price * qty

                row = ft.Row(
                    [
                        ft.Text(
                            f"{item['emoji']} {item['name']}", expand=True, size=18
                        ),
                        ft.Text(
                            f"{price:.2f} RON" if price > 0 else "",
                            size=16,
                            color=ft.Colors.BLUE_700,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REMOVE,
                            on_click=lambda e, i=item: change_qty(i, -1),
                        ),
                        ft.Text(
                            str(qty), width=40, text_align=ft.TextAlign.CENTER, size=18
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            on_click=lambda e, i=item: change_qty(i, 1),
                        ),
                    ]
                )
                order_list.controls.append(row)

            total_price_text.value = f"Total: {total:.2f} RON"
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

        # Build expandable category tiles (tap anywhere on header)
        category_tiles = []
        for cat in products:
            if not cat.get("products"):
                continue
            product_buttons = []
            for p in cat["products"]:
                price_text = f"  {p['price']:.2f} RON" if p.get("price", 0) > 0 else ""
                product_buttons.append(
                    ft.FilledButton(
                        content=ft.Text(f"{p['emoji']} {p['name']}{price_text}"),
                        on_click=lambda e, prod=p: add_item(prod),
                    )
                )
            tile = ft.ExpansionTile(
                title=ft.Text(
                    f"{cat['emoji']} {cat['name']}",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Column(product_buttons, scroll=ft.ScrollMode.AUTO)],
            )
            category_tiles.append(tile)

        # Wrap tiles in a scrollable column
        menu_section = ft.Column(category_tiles, scroll=ft.ScrollMode.AUTO)

        page.add(
            ft.Text("Current order:", size=20, weight=ft.FontWeight.BOLD),
            order_list,
            ft.Divider(),
            total_price_text,
            ft.Divider(),
            ft.Text("Add item:", size=20, weight=ft.FontWeight.BOLD),
            menu_section,
        )
        update_order_list()

    def back_to_grid():
        nonlocal current_table, current_update_order_list
        current_table = None
        current_update_order_list = None
        page.controls.clear()
        page.overlay.clear()

        # Rebuild main screen with settings button
        settings_btn = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            tooltip="Change server IP/port",
            on_click=lambda _: show_config_screen(),
        )

        page.add(
            ft.Row(
                [
                    ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD),
                    settings_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )
        page.add(grid)
        page.add(status_text)
        show_table_grid()

    # ------------------- Startup Flow -------------------
    saved_ip, saved_port = load_config()
    if saved_ip and saved_port:
        set_global_config(saved_ip, saved_port)
        initialize_app()
    else:
        show_config_screen()


ft.app(target=main)
