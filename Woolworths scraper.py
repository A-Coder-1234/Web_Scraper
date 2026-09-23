# Woolworths robots.txt: www.woolworths.co.nz/robots.txt

# Imports the required library for making HTTP requests, and butiful soup for decoding the HTML/XML requests. SequenceMatcher for sorting the URLs by rellevance. SYS for paring arguments from the GUI.
import urllib.request
import urllib.error
import urllib.parse
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import sys
import re

# Defines keywords, later defined by user
search = "corn chips" #sys.argv[1]
keywords = search.lower().split()
error_log = []

# Sets advanced headers to firmly imitate a real web browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-NZ,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Install a global cookie handler so the script retains cookies across multiple web requests
cookie_processor = urllib.request.HTTPCookieProcessor()
opener = urllib.request.build_opener(cookie_processor)
urllib.request.install_opener(opener)

# Fetches the robots.txt file from Woolworths and extracts the sitemap URL
url = 'https://www.woolworths.co.nz/robots.txt'
target = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(target) as response:
    data = response.read().decode('utf-8')
    match = re.search(r"(?im)^Sitemap:\s*(\S+)", data)
    if match:
        sitemap_url = match.group(1)

        # If the sitemap URL is found, it fetches the sitemap XML file
        url = sitemap_url
        target = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(target) as response:
            data = response.read().decode('utf-8')

            # Checks if the expected sitemap url is in the extracted data
            if 'https://www.woolworths.co.nz/sitemaps/products.xml' in data:

                # Extracts the product list from the sitemap
                found_items = []
                url = 'https://www.woolworths.co.nz/sitemaps/products.xml'
                target = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(target) as response:
                    data = response.read().decode('utf-8')
                    soup = BeautifulSoup(data, 'xml')

                    # Finds products with the specified key words in the product list extracted from the site map
                    for product_tag in soup.find_all('loc'):
                        product_url = product_tag.text.strip()
                        if any(keyword in product_url.lower() for keyword in keywords):
                            found_items.append(product_url)
                    print(found_items)

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

    # Extract data
    overflow = 0
    # Determine the actual number of iterations to prevent crashing if fewer than 5 items are found
    max_items_to_display = min(5, len(sorted_results))

                    
            else:
                print("error: expected sitemap \"https://www.woolworths.co.nz/sitemaps/products.xml\" in woolworths sitemap extracted from robots.txt")
