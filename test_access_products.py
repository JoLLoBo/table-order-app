import pyodbc

# ==================== CONFIGURATION ====================
ACCESS_DB_PATH = r"D:\Gestiune_og\omnigest2018.accdb"
ACCESS_DB_PASSWORD = "qaz"
# =======================================================

def get_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=' + ACCESS_DB_PATH + ';'
        f'PWD={ACCESS_DB_PASSWORD};'
    )
    return pyodbc.connect(conn_str)

def main():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Exact table names from your database
        raion_table = "RAIOANE"
        catalog_table = "CATALOG_PRODUSE"

        # Exact column names (discovered from previous run)
        cat_id_col = "cod"
        cat_name_col = "den_raion"
        prod_grupa_col = "grupa"
        prod_name_col = "den"
        prod_price_col = "pretv"   # Selling price (likely)

        print(f"Using tables: [{raion_table}] and [{catalog_table}]")
        print(f"Category columns: {cat_id_col}, {cat_name_col}")
        print(f"Product columns: {prod_grupa_col}, {prod_name_col}, {prod_price_col}")

        # Fetch categories
        cursor.execute(f"""
            SELECT [{cat_id_col}], [{cat_name_col}]
            FROM [{raion_table}]
            ORDER BY [{cat_name_col}]
        """)
        categories = {}
        for row in cursor.fetchall():
            cat_id = row[0]
            cat_name = row[1] if row[1] else "Unnamed"
            categories[cat_id] = cat_name.strip()

        print(f"\nFound {len(categories)} categories.")

        # Fetch products
        cursor.execute(f"""
            SELECT [{prod_grupa_col}], [{prod_name_col}], [{prod_price_col}]
            FROM [{catalog_table}]
            WHERE [{prod_name_col}] IS NOT NULL AND TRIM([{prod_name_col}]) <> ''
            ORDER BY [{prod_name_col}]
        """)
        products_by_cat = {}
        total = 0
        for row in cursor.fetchall():
            grupa = row[0]
            name = row[1] or ""
            price = row[2] if row[2] is not None else 0.0
            if grupa in categories:
                cat_name = categories[grupa]
                if cat_name not in products_by_cat:
                    products_by_cat[cat_name] = []
                products_by_cat[cat_name].append((name.strip(), float(price)))
                total += 1

        conn.close()

        # Print coffee products first (any category containing "cafea", "cafe", "café")
        print("\n=== COFFEE PRODUCTS ===\n")
        coffee_found = False
        for cat, prods in products_by_cat.items():
            if any(word in cat.lower() for word in ['cafea', 'cafe', 'café']):
                coffee_found = True
                print(f"📁 {cat} ({len(prods)} items)")
                for name, price in prods:
                    price_str = f" - ${price:.2f}" if price > 0 else ""
                    print(f"    ☕ {name}{price_str}")
                print()

        if not coffee_found:
            print("No coffee-specific category found. Showing all categories instead:\n")
            for cat, prods in products_by_cat.items():
                print(f"📁 {cat} ({len(prods)} items)")
                for name, price in prods[:3]:
                    price_str = f" - ${price:.2f}" if price > 0 else ""
                    print(f"    📋 {name}{price_str}")
                if len(prods) > 3:
                    print(f"    ... and {len(prods)-3} more")
                print()

        print(f"\n=== TOTAL PRODUCTS: {total} across {len(products_by_cat)} categories ===")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()