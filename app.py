import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from scraper import compare_product

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "prices.db"
app = Flask(__name__)
app.config["SECRET_KEY"] = "local-development-key"

RETAILERS = [
    ("paknsave", "Pak'nSave", "online"),
    ("woolworths", "Woolworths NZ", "online"),
    ("foursquare", "4 Square", "online"),
    ("vegiking", "Vegiking", "manual"),
]


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                manual_price REAL,
                manual_checked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS scrape_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                retailer TEXT NOT NULL,
                price REAL,
                unit TEXT,
                url TEXT,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL
            );
            """
        )


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.route("/")
def index():
    with get_db() as db:
        lists = db.execute(
            "SELECT l.*, COUNT(p.id) AS product_count FROM lists l "
            "LEFT JOIN products p ON p.list_id = l.id GROUP BY l.id ORDER BY l.id DESC"
        ).fetchall()
    return render_template("index.html", lists=lists)


@app.route("/lists", methods=["POST"])
def create_list():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give your shopping list a name.", "error")
        return redirect(url_for("index"))
    with get_db() as db:
        db.execute("INSERT INTO lists (name, created_at) VALUES (?, ?)", (name, now()))
    return redirect(url_for("index"))


@app.route("/lists/<int:list_id>")
def list_detail(list_id):
    with get_db() as db:
        shopping_list = db.execute("SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()
        products = db.execute("SELECT * FROM products WHERE list_id = ? ORDER BY id", (list_id,)).fetchall()
    if shopping_list is None:
        return "List not found", 404
    return render_template("list.html", shopping_list=shopping_list, products=products, retailers=RETAILERS)


@app.route("/lists/<int:list_id>/products", methods=["POST"])
def add_product(list_id):
    name = request.form.get("name", "").strip()
    try:
        quantity = max(1, int(request.form.get("quantity", "1")))
    except ValueError:
        quantity = 1
    if not name:
        flash("Enter a product name.", "error")
        return redirect(url_for("list_detail", list_id=list_id))
    with get_db() as db:
        db.execute("INSERT INTO products (list_id, name, quantity) VALUES (?, ?, ?)", (list_id, name, quantity))
    return redirect(url_for("list_detail", list_id=list_id))


@app.route("/products/<int:product_id>/manual-price", methods=["POST"])
def save_manual_price(product_id):
    raw_price = request.form.get("price", "").strip()
    list_id = request.form.get("list_id")
    try:
        price = float(raw_price) if raw_price else None
        if price is not None and price < 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid non-negative price.", "error")
        return redirect(url_for("list_detail", list_id=list_id))
    with get_db() as db:
        db.execute("UPDATE products SET manual_price = ?, manual_checked_at = ? WHERE id = ?", (price, now(), product_id))
    return redirect(url_for("list_detail", list_id=list_id))


@app.route("/lists/<int:list_id>/compare", methods=["POST"])
def compare_list(list_id):
    with get_db() as db:
        products = db.execute("SELECT * FROM products WHERE list_id = ? ORDER BY id", (list_id,)).fetchall()
    if not products:
        flash("Add at least one product before scraping.", "error")
        return redirect(url_for("list_detail", list_id=list_id))
    results = []
    with get_db() as db:
        for product in products:
            product_results = compare_product(product["name"])
            for retailer, result in product_results.items():
                db.execute(
                    "INSERT INTO scrape_results (product_id, retailer, price, unit, url, status, checked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (product["id"], retailer, result.get("price"), result.get("unit"), result.get("url"), result["status"], now()),
                )
            results.append({"product": dict(product), "prices": product_results})
    return render_template("compare.html", results=results, checked_at=now(), retailers=RETAILERS)


@app.context_processor
def inject_helpers():
    return {"json_dumps": lambda value: json.dumps(value)}


init_db()

if __name__ == "__main__":
    app.run(debug=True)
