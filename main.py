import flet as ft
import pyodbc

# ==================== CONFIGURATION ====================
DB_PATH = r"D:\vsCodeProj\table-order-app\omnigest2018.accdb"
DB_PASSWORD = "qaz"
# =======================================================

def main(page: ft.Page):
    page.title = "Table Orders"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # ==================== DATABASE CONNECTION ====================
    def get_db_connection():
        """Create and return a pyodbc connection to the password‑protected Access database."""
        conn_str = (
            r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
            r'DBQ=' + DB_PATH + ';'
            f'PWD={DB_PASSWORD};'
        )
        return pyodbc.connect(conn_str)

    def get_products():
        """
        Retrieve all items from the RAIOANE table.
        Uses only the 'den_raion' column; supplies a default emoji and zero price.
        """
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT den_raion FROM RAIOANE ORDER BY den_raion")
            rows = c.fetchall()
            conn.close()

            products = []
            for row in rows:
                name = row[0] if row[0] else "Unnamed"
                products.append((name, "📋", 0.0))
            return products

        except pyodbc.Error as e:
            print(f"Database error: {e}")
            # Fallback for when the database cannot be read
            return [("Error loading items", "⚠️", 0.0)]

    # ==================== IN-MEMORY ORDERS ====================
    orders = {i: [] for i in range(1, 13)}
    current_table = None

    # ==================== TABLE GRID ====================
    grid = ft.Row(wrap=True, spacing=20, run_spacing=20, alignment=ft.MainAxisAlignment.CENTER)

    def show_table_grid():
        grid.controls.clear()
        for t in range(1, 13):
            item_count = len(orders[t])
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

    # ==================== ORDER SCREEN ====================
    def select_table(table):
        nonlocal current_table
        current_table = table
        page.controls.clear()

        products = get_products()

        # Header
        page.add(ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: back_to_grid()),
            ft.Text(f"Table {table}", size=28, weight=ft.FontWeight.BOLD),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        order_list = ft.ListView(expand=True, spacing=10)

        def update_order_list():
            order_list.controls.clear()
            for item in orders[table]:
                row = ft.Row([
                    ft.Text(f"{item['emoji']} {item['name']}", expand=True, size=18),
                    ft.Text(f"${item['price']:.2f}" if item['price'] > 0 else "",
                            size=16, color=ft.Colors.BLUE_700),
                    ft.IconButton(icon=ft.Icons.REMOVE, on_click=lambda e, i=item: change_qty(i, -1)),
                    ft.Text(str(item["qty"]), width=40, text_align=ft.TextAlign.CENTER, size=18),
                    ft.IconButton(icon=ft.Icons.ADD, on_click=lambda e, i=item: change_qty(i, 1)),
                ])
                order_list.controls.append(row)
            page.update()

        def change_qty(item, delta):
            item["qty"] = max(1, item["qty"] + delta)
            update_order_list()

        def add_item(name, emoji, price):
            for existing in orders[table]:
                if existing["name"] == name:
                    existing["qty"] += 1
                    update_order_list()
                    return
            orders[table].append({"name": name, "emoji": emoji, "qty": 1, "price": price})
            update_order_list()

        # Menu buttons built from the database
        menu_row = ft.Row(wrap=True, spacing=10, run_spacing=10)
        for name, emoji, price in products:
            price_text = f"  ${price:.2f}" if price > 0 else ""
            menu_row.controls.append(
                ft.FilledButton(
                    content=ft.Text(f"{emoji} {name}{price_text}"),
                    on_click=lambda e, n=name, em=emoji, pr=price: add_item(n, em, pr)
                )
            )

        page.add(
            ft.Text("Current order:", size=20, weight=ft.FontWeight.BOLD),
            order_list,
            ft.Divider(),
            ft.Text("Add item:", size=20, weight=ft.FontWeight.BOLD),
            menu_row
        )
        update_order_list()

    def back_to_grid():
        page.controls.clear()
        page.add(ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD))
        page.add(grid)
        show_table_grid()

    # Start the app
    page.add(ft.Text("Select a Table", size=32, weight=ft.FontWeight.BOLD))
    page.add(grid)
    show_table_grid()


# Correct modern Flet entry point
ft.app(main)