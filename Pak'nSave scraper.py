# Pak'nSave robots.txt: www.paknsave.co.nz/robots.txt

# Imports the required library for making HTTP requests, and beautiful soup for decoding the HTML/XML requests. SequenceMatcher for sorting the URLs by relevance. SYS for paring arguments from the GUI.
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

# Fetches the robots.txt file from Pak'nSave
url = 'https://www.paknsave.co.nz/robots.txt'
target = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(target) as response:
    data = response.read().decode('utf-8')

# Checks if the sitemap URL is present in the robots.txt file
if "Sitemap:" in data:

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

    # Extract data
    overflow = 0
    # Determine the actual number of iterations to prevent crashing if fewer than 5 items are found
    max_items_to_display = min(5, len(sorted_results))
    
    for i in range(max_items_to_display):
        if (i + overflow) >= len(sorted_results):
            break
            
        url = sorted_results[i + overflow][0]
        target = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(target) as response:
                data = response.read().decode('utf-8')
            
            while "Sorry, this item is not available in" in data:
                overflow = overflow + 1
                if (i + overflow) >= len(sorted_results):
                    break
                # Try the next URL in the list if the current one is unavailable
                url = sorted_results[i + overflow][0]
                target = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(target) as response:
                    data = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            error_log.append("Product page unavailable. HTTP Error: {} for URL: {}".format(e.code, url))
            continue
    
        soup = BeautifulSoup(data, 'html.parser')
        
        # Safe extraction checks for DOM structure parsing
        h1_element = soup.select_one('h1')
        name = h1_element.get_text().strip() if h1_element else "Product Name Unreadable"
        
        price_dol = soup.find('p', attrs={'data-testid': 'price-dollars'})
        price_cent = soup.find('p', attrs={'data-testid': 'price-cents'})
        price = f"${price_dol.get_text().strip()}.{price_cent.get_text().strip()}" if price_dol and price_cent else "Price not found"
        price_per_unit = soup.find('p', attrs={'data-testid': 'non-promo-comparative-price'}).get_text().strip() if soup.find('p', attrs={'data-testid': 'non-promo-comparative-price'}) else "Price per unit not found"

        print(name)
        print(price)
        print(price_per_unit)
        print(url)
        print("-" * 20)
        
    print(error_log)

else:
    # If the sitemap URL was NOT found the code will notify the user to contact the developer
    print("Sitemap NOT found in robots.txt, contact developer.")