import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app


class BasketCheckAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = os.path.join(self.temp_dir.name, "test.db")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database,
                "SECRET_KEY": "test-key",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_list(self):
        response = self.client.post("/lists/new", data={"name": "Weekly shop"})
        self.assertEqual(response.status_code, 302)
        return int(response.headers["Location"].rsplit("/", 1)[-1])

    def add_product(self, list_id, name="corn chips", quantity="2"):
        return self.client.post(
            f"/lists/{list_id}/products",
            data={"name": name, "quantity": quantity},
        )

    def test_create_list_and_add_product(self):
        list_id = self.create_list()
        self.add_product(list_id)
        response = self.client.get(f"/lists/{list_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Weekly shop", response.data)
        self.assertIn(b"corn chips", response.data)

    def test_invalid_quantity_is_reported_without_adding_product(self):
        list_id = self.create_list()
        self.add_product(list_id, quantity="many")
        response = self.client.get(f"/lists/{list_id}")
        self.assertIn(b"Quantity must be between", response.data)
        self.assertNotIn(b"corn chips", response.data)

    def test_manual_price_is_saved_and_can_be_cleared(self):
        list_id = self.create_list()
        self.add_product(list_id)
        with self.app.app_context():
            import sqlite3

            db = sqlite3.connect(self.database)
            product_id = db.execute(
                "SELECT id FROM products WHERE list_id = ?", (list_id,)
            ).fetchone()[0]
            db.close()

        self.client.post(
            f"/products/{product_id}/manual-price",
            data={"price": "4.25"},
        )
        response = self.client.get(f"/lists/{list_id}")
        self.assertIn(b"4.25", response.data)
        self.client.post(
            f"/products/{product_id}/manual-price",
            data={"price": ""},
        )
        response = self.client.get(f"/lists/{list_id}")
        self.assertIn(b"Manual price cleared", response.data)

    def test_comparison_saves_real_and_unavailable_statuses(self):
        list_id = self.create_list()
        self.add_product(list_id)
        result = {
            "status": "found",
            "product_name": "Corn chips",
            "price": 3.49,
            "unit_price": None,
            "product_url": "https://retailer.example/product",
            "message": "Verified test offer",
        }
        with patch("app.search_product", return_value=result):
            response = self.client.post(f"/lists/{list_id}/compare")

        self.assertEqual(response.status_code, 302)
        check_url = response.headers["Location"]
        check_page = self.client.get(check_url)
        self.assertEqual(check_page.status_code, 200)
        self.assertIn(b"$3.49", check_page.data)
        self.assertIn(b"4 Square", check_page.data)
        self.assertIn(b"not connected", check_page.data)
        self.assertIn(b"Basket total", check_page.data)

        with self.app.app_context():
            import sqlite3

            db = sqlite3.connect(self.database)
            counts = db.execute(
                "SELECT status, COUNT(*) FROM price_results GROUP BY status"
            ).fetchall()
            check_count = db.execute("SELECT COUNT(*) FROM price_checks").fetchone()[0]
            db.close()
        self.assertEqual(check_count, 1)
        self.assertIn(("unsupported", 1), counts)
        self.assertIn(("found", 2), counts)

    def test_delete_list_removes_it_and_its_check_history(self):
        list_id = self.create_list()
        self.add_product(list_id)
        with patch("app.search_product", return_value={"status": "no_match", "message": "No match"}):
            comparison = self.client.post(f"/lists/{list_id}/compare")
        check_id = int(comparison.headers["Location"].rsplit("/", 1)[-1])
        self.client.post(f"/lists/{list_id}/delete")
        self.assertEqual(self.client.get(f"/lists/{list_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/checks/{check_id}").status_code, 404)

    def test_delete_list_works_with_the_legacy_database_schema(self):
        import sqlite3

        legacy_database = os.path.join(self.temp_dir.name, "legacy.db")
        db = sqlite3.connect(legacy_database)
        db.executescript(
            """
            CREATE TABLE shopping_lists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                list_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                manual_price REAL,
                FOREIGN KEY (list_id) REFERENCES shopping_lists(id)
            );
            INSERT INTO shopping_lists (id, name) VALUES (1, 'Old list');
            INSERT INTO products (list_id, name) VALUES (1, 'Old product');
            """
        )
        db.commit()
        db.close()
        legacy_app = create_app(
            {
                "TESTING": True,
                "DATABASE": legacy_database,
                "SECRET_KEY": "test-key",
            }
        )

        response = legacy_app.test_client().post("/lists/1/delete")

        self.assertEqual(response.status_code, 302)
        db = sqlite3.connect(legacy_database)
        self.assertEqual(
            db.execute("SELECT COUNT(*) FROM shopping_lists").fetchone()[0], 0
        )
        self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
