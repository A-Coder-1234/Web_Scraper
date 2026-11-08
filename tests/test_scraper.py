import json
import unittest

from scraper import Retailer, RetailerAdapter, relevance


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return FakeResponse(next(self.responses))


class RetailerAdapterTests(unittest.TestCase):
    def make_adapter(self, robots, offer_currency="NZD"):
        sitemap = (
            "<urlset><url><loc>"
            "https://store.example/product/corn-chips"
            "</loc></url></urlset>"
        )
        product = {
            "@type": "Product",
            "name": "Corn Chips",
            "offers": {
                "@type": "Offer",
                "price": "3.49",
                "priceCurrency": offer_currency,
            },
        }
        html = (
            '<script type="application/ld+json">'
            + json.dumps(product)
            + "</script>"
        )
        session = FakeSession([robots, sitemap, html])
        adapter = RetailerAdapter(
            Retailer("test", "Test", "https://store.example"),
            session=session,
            request_interval=0,
            sleep=lambda _: None,
        )
        return adapter, session

    def test_reads_only_a_verified_nzd_jsonld_offer(self):
        adapter, session = self.make_adapter(
            "User-agent: *\nAllow: /\nSitemap: https://store.example/sitemap.xml"
        )
        result = adapter.search("corn chips")
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["price"], 3.49)
        self.assertEqual(len(session.urls), 3)

    def test_does_not_fetch_robots_disallowed_product(self):
        adapter, session = self.make_adapter(
            "User-agent: *\nDisallow: /product/\n"
            "Sitemap: https://store.example/sitemap.xml"
        )
        result = adapter.search("corn chips")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(session.urls), 2)

    def test_rejects_unknown_currency(self):
        adapter, _ = self.make_adapter(
            "User-agent: *\nAllow: /\nSitemap: https://store.example/sitemap.xml",
            offer_currency="USD",
        )
        result = adapter.search("corn chips")
        self.assertEqual(result["status"], "no_price")
        self.assertNotIn("price", result)

    def test_relevance_prefers_exact_product_name(self):
        exact = relevance("corn chips", "corn chips")
        unrelated = relevance("corn chips", "corn flakes")
        self.assertGreater(exact, unrelated)
        self.assertGreaterEqual(exact, 0.45)


if __name__ == "__main__":
    unittest.main()
