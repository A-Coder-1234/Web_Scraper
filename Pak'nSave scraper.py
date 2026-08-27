# Pak'nSave robots.txt: www.paknsave.co.nz/robots.txt

# Imports the required library for making HTTP requests, and butiful soup for decoding the HTML/XML requests. SequenceMatcher for sorting the URLs by rellevance. SYS for paring arguments from the GUI.
import urllib.request
import urllib.error
import urllib.parse
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import sys

# Defines keywords, later defined by user
search = sys.argv[1]
keywords = search.lower().split()
error_log = []

# Sets the headers to imitate a web browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Fetches the robots.txt file from Pak'nSave
url = 'https://www.paknsave.co.nz/robots.txt'
target = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(target) as response:
    data = response.read().decode('utf-8')

# Checks if the sitemap URL is present in the robots.txt file
if "Sitemap: https://www.paknsave.co.nz/ecomsitemap_index.xml" in data:

    # If the sitemap URL is found, it fetches the sitemap XML file
    url = 'https://www.paknsave.co.nz/ecomsitemap_index.xml'
    target = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(target) as response:
        data = response.read().decode('utf-8')

    # Parse XML to find the product lists and search them for products with the keywords defined by the user
    soup = BeautifulSoup(data, 'xml')
    found_items = []
    catalog_count = len(soup.find_all('loc'))
    
    for tag in soup.find_all('loc'):
        sitemap_url = tag.text.strip()

        if "ecom_sitemap_products" in sitemap_url:
            print("Trying:", sitemap_url)

            target = urllib.request.Request(
                sitemap_url,
                headers=headers
            )

            try:
                with urllib.request.urlopen(target, timeout=30) as response:
                    product_list = response.read().decode('utf-8')
                    soup = BeautifulSoup(product_list, 'xml')
                    for product_tag in soup.find_all('loc'):
                        product_url = product_tag.text.strip()
                        if any(keyword in product_url.lower() for keyword in keywords):
                            found_items.append(product_url)

            except urllib.error.HTTPError as e:
                error_log.append("Some sitemaps could not be fetched. HTTP Error: {} for URL: {}".format(e.code, sitemap_url))
                continue

    def extract_product_name(url):
        """Extracts and cleans the product name from the URL query string."""
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        raw_name = query_params.get('name', [''])[0]
        return raw_name.replace('-', ' ').replace('%27', "'").strip()

    def calculate_keyword_relevance(product_name, keyword_list):
        """
        Calculates relevance based on token matching.
        Returns a score based on percentage of keywords matched + extra weight for early matches.
        """
        product_words = set(product_name.lower().split())
        matched_count = 0
    
        # Clean and lowercase the input keywords
        clean_keywords = [str(kw).lower().strip() for kw in keyword_list]
    
        for kw in clean_keywords:
            if kw in product_words:
                matched_count += 1
            
        # If no words match, score is 0
        if not clean_keywords or matched_count == 0:
            return 0.0
        
        # Base score: percentage of keywords found
        match_ratio = matched_count / len(clean_keywords)
    
        # Tie-breaker density: favors shorter, more concise product titles over long ones
        density_bonus = matched_count / len(product_words)
    
        return match_ratio + (density_bonus * 0.1)

    def sort_urls_by_keywords(url_list, keyword_list):
        """Sorts the URL list by relevance to a list of keywords."""
        scored_urls = []
    
        for url in url_list:
            product_name = extract_product_name(url)
            score = calculate_keyword_relevance(product_name, keyword_list)
            scored_urls.append((url, product_name, score))
    
        # Sort by score descending
        scored_urls.sort(key=lambda x: x[2], reverse=True)
        return scored_urls

    sorted_results = sort_urls_by_keywords(found_items, keywords)
    shortened_results = sorted_results[:5]
    print(shortened_results)
    print(error_log)

    #for i in range(catalog_count):
     #   url = 'https://www.paknsave.co.nz/ecomsitemap_index.xml'
    #    target = urllib.request.Request(url, headers=headers)
     #   with urllib.request.urlopen(target) as response:
    #        data = response.read().decode('utf-8')
else:
    # If the sitemap URL was NOT found the code will notify the user to contact the developer
    print("Sitemap NOT found in robots.txt, contact developer.")