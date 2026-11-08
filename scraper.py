"""Conservative, robots.txt-aware product price lookup for supported stores."""

import json
import re
import time
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup


USER_AGENT = "BasketCheck/1.0 (personal grocery price comparison)"
REQUEST_TIMEOUT = 15
MAX_SITEMAPS = 10
MAX_PRODUCT_PAGES = 4
MIN_MATCH_SCORE = 0.45


class ScraperError(Exception):
    """Raised when a retailer cannot be checked safely or reliably."""


@dataclass(frozen=True)
class Retailer:
    key: str
    name: str
    base_url: str


RETAILERS = {
    "paknsave": Retailer(
        "paknsave", "Pak’nSave", "https://www.paknsave.co.nz"
    ),
    "woolworths": Retailer(
        "woolworths", "Woolworths", "https://www.woolworths.co.nz"
    ),
}


def _words(value):
    return re.findall(r"[a-z0-9]+", value.casefold())


def relevance(query, candidate):
    query_words = set(_words(query))
    candidate_words = set(_words(candidate))
    if not query_words or not candidate_words:
        return 0.0
    coverage = len(query_words & candidate_words) / len(query_words)
    similarity = SequenceMatcher(
        None, " ".join(sorted(query_words)), " ".join(sorted(candidate_words))
    ).ratio()
    return coverage * 0.8 + similarity * 0.2


def _jsonld_products(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        pending = data if isinstance(data, list) else [data]
        while pending:
            item = pending.pop()
            if isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, dict):
                graph = item.get("@graph")
                if isinstance(graph, list):
                    pending.extend(graph)
                item_type = item.get("@type", [])
                if isinstance(item_type, str):
                    item_type = [item_type]
                if any(
                    str(value).rstrip("/").rsplit("/", 1)[-1] == "Product"
                    for value in item_type
                ):
                    yield item


def _extract_offer(product):
    offers = product.get("offers", [])
    pending = offers if isinstance(offers, list) else [offers]
    while pending:
        offer = pending.pop(0)
        if isinstance(offer, list):
            pending[0:0] = offer
        elif isinstance(offer, dict):
            nested_offers = offer.get("offers")
            if nested_offers:
                pending.append(nested_offers)
            price_value = offer.get("price", offer.get("lowPrice"))
            currency = offer.get("priceCurrency")
            if price_value is None and isinstance(offer.get("priceSpecification"), dict):
                specification = offer["priceSpecification"]
                price_value = specification.get("price")
                currency = specification.get("priceCurrency", currency)
            try:
                price = Decimal(str(price_value))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if price.is_finite() and price >= 0 and currency == "NZD":
                return float(price)
    return None


class RetailerAdapter:
    def __init__(self, retailer, session=None, request_interval=1.0, sleep=time.sleep):
        self.retailer = retailer
        self.session = session or requests.Session()
        self.request_interval = request_interval
        self.sleep = sleep
        self._last_request = 0.0
        self._robot_parser = None
        self._sitemap_urls = None
        self._product_urls = None
        self._sitemap_limit_reached = False

    def _get(self, url):
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self.request_interval:
            self.sleep(self.request_interval - elapsed)
        self._last_request = time.monotonic()
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def _load_robots(self):
        if self._robot_parser is not None:
            return self._robot_parser
        robots_url = urllib.parse.urljoin(self.retailer.base_url, "/robots.txt")
        try:
            response = self._get(robots_url)
        except requests.RequestException as exc:
            raise ScraperError("Could not verify the retailer’s robots.txt rules.") from exc

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        self._robot_parser = parser
        return parser

    def _is_allowed(self, url):
        parsed = urllib.parse.urlparse(url)
        base = urllib.parse.urlparse(self.retailer.base_url)
        if parsed.scheme != "https" or parsed.netloc.casefold() != base.netloc.casefold():
            return False
        return self._load_robots().can_fetch(USER_AGENT, url)

    def _load_sitemap_urls(self):
        if self._sitemap_urls is not None:
            return self._sitemap_urls
        parser = self._load_robots()
        sitemap_urls = parser.site_maps() or []
        if not sitemap_urls:
            raise ScraperError("No sitemap is listed in the retailer’s robots.txt.")
        permitted = [url for url in sitemap_urls if self._is_allowed(url)]
        if not permitted:
            raise ScraperError("The retailer’s robots.txt does not permit sitemap access.")
        self._sitemap_urls = permitted
        return permitted

    @staticmethod
    def _locations(xml_text):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        return [
            element.text.strip()
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == "loc" and element.text
        ]

    def _load_product_urls(self):
        if self._product_urls is not None:
            return self._product_urls
        sitemap_urls = list(self._load_sitemap_urls())
        product_urls = []
        visited_sitemaps = set()
        visited = 0
        while sitemap_urls and visited < MAX_SITEMAPS:
            sitemap_url = sitemap_urls.pop(0)
            if sitemap_url in visited_sitemaps:
                continue
            visited_sitemaps.add(sitemap_url)
            if not self._is_allowed(sitemap_url):
                continue
            try:
                response = self._get(sitemap_url)
            except requests.RequestException as exc:
                raise ScraperError("A retailer sitemap could not be retrieved.") from exc
            visited += 1
            locations = self._locations(response.text)
            if not locations:
                continue
            for url in locations:
                path = urllib.parse.urlparse(url).path.casefold()
                if path.endswith(".xml") or "sitemap" in path:
                    sitemap_urls.append(url)
                else:
                    product_urls.append(url)

        self._sitemap_limit_reached = bool(sitemap_urls)
        self._product_urls = list(dict.fromkeys(product_urls))
        if not self._product_urls:
            raise ScraperError("No accessible product URLs were found in retailer sitemaps.")
        return self._product_urls

    @staticmethod
    def _url_name(url):
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        name = query.get("name", [""])[0]
        if name:
            return name.replace("-", " ")
        return urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]).replace("-", " ")

    def search(self, query):
        if not query.strip():
            return {"status": "no_match", "message": "Enter a product name."}

        urls = self._load_product_urls()
        candidates = sorted(
            (
                (relevance(query, self._url_name(url)), url)
                for url in urls
                if relevance(query, self._url_name(url)) >= MIN_MATCH_SCORE
            ),
            reverse=True,
        )[:MAX_PRODUCT_PAGES]
        if not candidates:
            if self._sitemap_limit_reached:
                return {
                    "status": "incomplete",
                    "message": "The sitemap search limit was reached before a match was found.",
                }
            return {"status": "no_match", "message": "No close product match was found."}

        products = []
        blocked_count = 0
        for url_score, url in candidates:
            if not self._is_allowed(url):
                blocked_count += 1
                continue
            try:
                response = self._get(url)
            except requests.RequestException:
                continue
            for product in _jsonld_products(response.text):
                name = str(product.get("name", "")).strip()
                score = relevance(query, name) if name else url_score
                products.append(
                    {
                        "product_name": name or self._url_name(url),
                        "price": _extract_offer(product),
                        "product_url": url,
                        "score": score,
                    }
                )

        if not products:
            if blocked_count == len(candidates):
                return {
                    "status": "blocked",
                    "message": "robots.txt disallows the matching product pages.",
                }
            return {
                "status": "unavailable",
                "message": "No verifiable product price was found on the matched pages.",
            }

        best = max(products, key=lambda product: product["score"])
        if best["score"] < MIN_MATCH_SCORE:
            return {"status": "no_match", "message": "No close product match was found."}
        if best["price"] is None:
            return {
                "status": "no_price",
                "product_name": best["product_name"],
                "product_url": best["product_url"],
                "message": "A product matched, but no NZD offer was available.",
            }
        return {
            "status": "found",
            "product_name": best["product_name"],
            "price": best["price"],
            "unit_price": None,
            "product_url": best["product_url"],
            "message": "Price read from the product’s structured data.",
        }


def search_product(retailer_key, query, adapter=None):
    """Look up one product using a supported retailer’s public sitemap."""
    retailer = RETAILERS.get(retailer_key)
    if retailer is None:
        return {
            "status": "unsupported",
            "message": "Automated lookup is not configured for this store.",
        }
    return (adapter or RetailerAdapter(retailer)).search(query)
