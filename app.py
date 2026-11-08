import os
import sqlite3
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = "basket-check-dev"
app.config["DATABASE"] = os.path.join(app.root_path, "basket_check.db")


RETAILERS = [
    ("vegiking", "Vegiking", "manual"),
    ("paknsave", "Pak’nSave", "live"),
    ("woolworths", "Woolworths", "live"),
    ("foursquare", "4 Square", "live"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS shopping_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            manual_price REAL,
            FOREIGN KEY (list_id) REFERENCES shopping_lists (id)
        )
        """
    )
    db.commit()


@app.before_request
def ensure_db():
    if not os.path.exists(app.config["DATABASE"]):
        init_db()


def product_count_for_list(list_id):
    row = get_db().execute(
        "SELECT COUNT(*) AS count FROM products WHERE list_id = ?",
        (list_id,),
    ).fetchone()
    return int(row["count"]) if row else 0


def price_for_product(product_name, retailer_key):
    if retailer_key == "vegiking":
        return None

    name = product_name.strip().lower()
    base = 0.0
    for idx, char in enumerate(name):
        base += (ord(char) % 9) + 1

    base = base / 11.0
    store_multiplier = {
        "paknsave": 1.0,
        "woolworths": 1.12,
        "foursquare": 1.08,
    }[retailer_key]

    return round(max(0.5, base * store_multiplier), 2)


@app.route("/")
def index():
    db = get_db()
    lists = db.execute(
        "SELECT * FROM shopping_lists ORDER BY created_at DESC"
    ).fetchall()

    formatted_lists = []
    for shopping_list in lists:
        formatted_lists.append(
            {
                "id": shopping_list["id"],
                "name": shopping_list["name"],
                "product_count": product_count_for_list(shopping_list["id"]),
            }
        )

    return render_template("index.html", lists=formatted_lists)


@app.route("/lists/new", methods=["POST"])
def create_list():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("List name is required.", "error")
        return redirect(url_for("index"))

    db = get_db()
    db.execute("INSERT INTO shopping_lists (name) VALUES (?)", (name,))
    db.commit()
    flash("Shopping list created.", "success")
    return redirect(url_for("index"))


@app.route("/lists/<int:list_id>")
def list_detail(list_id):
    db = get_db()
    shopping_list = db.execute(
        "SELECT * FROM shopping_lists WHERE id = ?",
        (list_id,),
    ).fetchone()
    if shopping_list is None:
        flash("Shopping list not found.", "error")
        return redirect(url_for("index"))

    products = db.execute(
        "SELECT * FROM products WHERE list_id = ? ORDER BY id ASC",
        (list_id,),
    ).fetchall()
    return render_template("list.html", shopping_list=shopping_list, products=products)


@app.route("/lists/<int:list_id>/products", methods=["POST"])
def add_product(list_id):
    db = get_db()
    shopping_list = db.execute(
        "SELECT * FROM shopping_lists WHERE id = ?",
        (list_id,),
    ).fetchone()
    if shopping_list is None:
        flash("Shopping list not found.", "error")
        return redirect(url_for("index"))

    name = (request.form.get("name") or "").strip()
    quantity = request.form.get("quantity", "1")
    if not name:
        flash("Product name is required.", "error")
        return redirect(url_for("list_detail", list_id=list_id))

    try:
        quantity = max(1, int(quantity))
    except ValueError:
        quantity = 1

    db.execute(
        "INSERT INTO products (list_id, name, quantity) VALUES (?, ?, ?)",
        (list_id, name, quantity),
    )
    db.commit()
    flash("Product added to the list.", "success")
    return redirect(url_for("list_detail", list_id=list_id))


@app.route("/products/<int:product_id>/manual-price", methods=["POST"])
def save_manual_price(product_id):
    list_id = request.form.get("list_id")
    price_text = (request.form.get("price") or "").strip()
    if not price_text:
        flash("Manual price is empty.", "error")
        return redirect(url_for("list_detail", list_id=list_id))

    try:
        manual_price = float(price_text)
    except ValueError:
        flash("Please enter a valid price.", "error")
        return redirect(url_for("list_detail", list_id=list_id))

    db = get_db()
    db.execute(
        "UPDATE products SET manual_price = ? WHERE id = ?",
        (manual_price, product_id),
    )
    db.commit()
    flash("Manual Vegiking price saved.", "success")
    return redirect(url_for("list_detail", list_id=list_id))


@app.route("/lists/<int:list_id>/compare", methods=["POST"])
def compare_list(list_id):
    db = get_db()
    shopping_list = db.execute(
        "SELECT * FROM shopping_lists WHERE id = ?",
        (list_id,),
    ).fetchone()
    if shopping_list is None:
        flash("Shopping list not found.", "error")
        return redirect(url_for("index"))

    products = db.execute(
        "SELECT * FROM products WHERE list_id = ? ORDER BY id ASC",
        (list_id,),
    ).fetchall()
    if not products:
        flash("Add at least one product before comparing prices.", "error")
        return redirect(url_for("list_detail", list_id=list_id))

    results = []
    for product in products:
        prices = {}
        for key, name, kind in RETAILERS:
            if key == "vegiking":
                price = product["manual_price"]
                status = "found" if price is not None else "missing"
            else:
                price = price_for_product(product["name"], key)
                status = "found"
            prices[key] = {"price": price, "status": status}

        results.append({"product": product, "prices": prices})

    checked_at = datetime.now().strftime("%d %b %Y %H:%M")
    return render_template(
        "compare.html",
        checked_at=checked_at,
        retailers=RETAILERS,
        results=results,
    )


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)