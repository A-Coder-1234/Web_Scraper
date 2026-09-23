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
search = "cornchips" #sys.argv[1]
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

# Fetches the robots.txt file from Pak'nSave and extracts the sitemap URL
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
                url = 'https://www.woolworths.co.nz/sitemaps/products.xml'
                target = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(target) as response:
                    data = response.read().decode('utf-8')
                    print(data)
            else:
                print("error: expected sitemap \"https://www.woolworths.co.nz/sitemaps/products.xml\" in woolworths sitemap extracted from robots.txt")
