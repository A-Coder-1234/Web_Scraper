import os
import secrets
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from scraper import RETAILERS as SCRAPER_RETAILERS
from scraper import RetailerAdapter, ScraperError, search_product


RETAILERS = [
    ("vegiking", "Vegiking", "manual"),
    ("paknsave", "Pak’nSave", "live"),
    ("woolworths", "Woolworths", "live"),
    ("foursquare", "4 Square", "unsupported"),
]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.root_path, "basket_check.db"),
    )
    if test_config:
        app.config.update(test_config)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS shopping_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK(length(name) <= 100),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK(length(name) <= 200),
                quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity BETWEEN 1 AND 9999),
                manual_price REAL CHECK(manual_price IS NULL OR manual_price >= 0)
            );
            CREATE TABLE IF NOT EXISTS price_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
                checked_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL REFERENCES price_checks(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                retailer_key TEXT NOT NULL,
                status TEXT NOT NULL,
                product_name TEXT,
                price REAL CHECK(price IS NULL OR price >= 0),
                unit_price TEXT,
                product_url TEXT,
                message TEXT NOT NULL
            );
            """
        )
        db.commit()

    @app.before_request
    def ensure_db():
        if not g.get("db_initialized"):
            init_db()
            g.db_initialized = True

    def find_list(list_id):
        return get_db().execute(
            "SELECT * FROM shopping_lists WHERE id = ?", (list_id,)
        ).fetchone()

    def parse_price(value):
        try:
            price = Decimal(value)
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not price.is_finite() or price < 0 or price > Decimal("999999.99"):
            return None
        exponent = price.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            return None
        return price

    @app.route("/")
    def index():
        lists = get_db().execute(
            """
            SELECT l.id, l.name, COUNT(p.id) AS product_count
            FROM shopping_lists AS l
            LEFT JOIN products AS p ON p.list_id = l.id
            GROUP BY l.id
            ORDER BY l.created_at DESC, l.id DESC
            """
        ).fetchall()
        return render_template("index.html", lists=lists)

    @app.route("/lists/new", methods=["POST"])
    def create_list():
        name = (request.form.get("name") or "").strip()
        if not name or len(name) > 100:
            flash("Enter a list name of 1–100 characters.", "error")
            return redirect(url_for("index"))
        cursor = get_db().execute(
            "INSERT INTO shopping_lists (name) VALUES (?)", (name,)
        )
        get_db().commit()
        flash("Shopping list created.", "success")
        return redirect(url_for("list_detail", list_id=cursor.lastrowid))

    @app.route("/lists/<int:list_id>")
    def list_detail(list_id):
        shopping_list = find_list(list_id)
        if shopping_list is None:
            abort(404)
        db = get_db()
        products = db.execute(
            "SELECT * FROM products WHERE list_id = ? ORDER BY id",
            (list_id,),
        ).fetchall()
        latest_check = db.execute(
            """
            SELECT id, checked_at FROM price_checks
            WHERE list_id = ? ORDER BY checked_at DESC, id DESC LIMIT 1
            """,
            (list_id,),
        ).fetchone()
        return render_template(
            "list.html",
            shopping_list=shopping_list,
            products=products,
            latest_check=latest_check,
        )

    @app.route("/lists/<int:list_id>/products", methods=["POST"])
    def add_product(list_id):
        shopping_list = find_list(list_id)
        if shopping_list is None:
            abort(404)
        name = (request.form.get("name") or "").strip()
        quantity_text = (request.form.get("quantity") or "1").strip()
        try:
            quantity = int(quantity_text)
        except ValueError:
            quantity = 0
        if not name or len(name) > 200:
            flash("Enter a product name of 1–200 characters.", "error")
        elif not 1 <= quantity <= 9999:
            flash("Quantity must be between 1 and 9,999.", "error")
        else:
            get_db().execute(
                "INSERT INTO products (list_id, name, quantity) VALUES (?, ?, ?)",
                (list_id, name, quantity),
            )
            get_db().commit()
            flash("Product added to the list.", "success")
        return redirect(url_for("list_detail", list_id=list_id))

    @app.route("/products/<int:product_id>/manual-price", methods=["POST"])
    def save_manual_price(product_id):
        product = get_db().execute(
            "SELECT id, list_id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            abort(404)
        list_id = product["list_id"]
        value = (request.form.get("price") or "").strip()
        price = None if not value else parse_price(value)
        if value and price is None:
            flash("Enter a non-negative price with no more than two decimal places.", "error")
        else:
            get_db().execute(
                "UPDATE products SET manual_price = ? WHERE id = ?",
                (float(price) if price is not None else None, product_id),
            )
            get_db().commit()
            flash("Manual Vegiking price saved." if value else "Manual price cleared.", "success")
        return redirect(url_for("list_detail", list_id=list_id))

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def delete_product(product_id):
        product = get_db().execute(
            "SELECT list_id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            abort(404)
        list_id = product["list_id"]
        get_db().execute("DELETE FROM products WHERE id = ?", (product_id,))
        get_db().commit()
        flash("Product removed.", "success")
        return redirect(url_for("list_detail", list_id=list_id))

    @app.route("/lists/<int:list_id>/delete", methods=["POST"])
    def delete_list(list_id):
        if find_list(list_id) is None:
            abort(404)
        db = get_db()
        db.execute(
            "DELETE FROM price_checks WHERE list_id = ?", (list_id,)
        )
        db.execute("DELETE FROM products WHERE list_id = ?", (list_id,))
        db.execute("DELETE FROM shopping_lists WHERE id = ?", (list_id,))
        db.commit()
        flash("Shopping list deleted.", "success")
        return redirect(url_for("index"))

    @app.route("/lists/<int:list_id>/compare", methods=["POST"])
    def compare_list(list_id):
        if find_list(list_id) is None:
            abort(404)
        db = get_db()
        products = db.execute(
            "SELECT * FROM products WHERE list_id = ? ORDER BY id", (list_id,)
        ).fetchall()
        if not products:
            flash("Add at least one product before comparing prices.", "error")
            return redirect(url_for("list_detail", list_id=list_id))

        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = db.execute(
            "INSERT INTO price_checks (list_id, checked_at) VALUES (?, ?)",
            (list_id, checked_at),
        )
        check_id = cursor.lastrowid

        adapters = {}
        for product in products:
            for key, name, kind in RETAILERS:
                if key == "vegiking":
                    manual_price = product["manual_price"]
                    result = {
                        "status": "found" if manual_price is not None else "missing",
                        "product_name": product["name"] if manual_price is not None else None,
                        "price": manual_price,
                        "unit_price": None,
                        "product_url": None,
                        "message": "Manual entry" if manual_price is not None else "No manual price entered.",
                    }
                elif key == "foursquare":
                    result = {
                        "status": "unsupported",
                        "product_name": None,
                        "price": None,
                        "unit_price": None,
                        "product_url": None,
                        "message": "Automated lookup is not configured for this store.",
                    }
                else:
                    try:
                        if key not in adapters:
                            adapters[key] = RetailerAdapter(SCRAPER_RETAILERS[key])
                        result = search_product(
                            key, product["name"], adapter=adapters[key]
                        )
                    except ScraperError:
                        app.logger.exception(
                            "Price lookup failed for retailer %s and product %s",
                            key,
                            product["id"],
                        )
                        result = {
                            "status": "error",
                            "product_name": None,
                            "price": None,
                            "unit_price": None,
                            "product_url": None,
                            "message": "Lookup failed. Check retailer availability and try again.",
                        }
                db.execute(
                    """
                    INSERT INTO price_results (
                        check_id, product_id, retailer_key, status,
                        product_name, price, unit_price, product_url, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        check_id,
                        product["id"],
                        key,
                        result.get("status", "error"),
                        result.get("product_name"),
                        result.get("price"),
                        result.get("unit_price"),
                        result.get("product_url"),
                        result.get("message", "No result details provided."),
                    ),
                )
        db.commit()
        return redirect(url_for("show_check", check_id=check_id))

    @app.route("/checks/<int:check_id>")
    def show_check(check_id):
        check = get_db().execute(
            """
            SELECT c.id, c.list_id, c.checked_at, l.name AS list_name
            FROM price_checks AS c
            JOIN shopping_lists AS l ON l.id = c.list_id
            WHERE c.id = ?
            """,
            (check_id,),
        ).fetchone()
        if check is None:
            abort(404)
        rows = get_db().execute(
            """
            SELECT p.id AS product_id, p.name, p.quantity,
                   r.retailer_key, r.status, r.product_name, r.price,
                   r.unit_price, r.product_url, r.message
            FROM price_results AS r
            JOIN products AS p ON p.id = r.product_id
            WHERE r.check_id = ?
            ORDER BY p.id, r.id
            """,
            (check_id,),
        ).fetchall()
        results_by_product = {}
        for row in rows:
            entry = results_by_product.setdefault(
                row["product_id"],
                {
                    "product": row,
                    "prices": {},
                    "total": Decimal("0"),
                    "complete": True,
                },
            )
            entry["prices"][row["retailer_key"]] = row
            if row["price"] is None:
                entry["complete"] = False
            else:
                entry["total"] += Decimal(str(row["price"])) * row["quantity"]

        return render_template(
            "compare.html",
            check=check,
            retailers=RETAILERS,
            results=list(results_by_product.values()),
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
