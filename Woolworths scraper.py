# Woolworths robots.txt: www.woolworths.co.nz/robots.txt

# Imports the required library for making HTTP requests, and butiful soup for decoding the HTML/XML requests. SequenceMatcher for sorting the URLs by rellevance. SYS for paring arguments from the GUI.
import urllib.request
import urllib.error
import urllib.parse
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import sys

