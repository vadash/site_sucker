This markdown guide provides the essential technical context and logic required for an LLM to implement your SiteSucker-style pipeline using beautifulsoup4 and lxml.
------------------------------
## SiteSucker Clone: HTML Parsing & Rewriting Guide## 1. Environment Requirements
To use the fastest and most feature-complete parser, the LLM should assume the following setup:

pip install beautifulsoup4 lxml

## 2. Core Parser Configuration
The pipeline must use the lxml engine for speed and its ability to handle "broken" HTML often found in old forums or mirrors. [1, 2] 

from bs4 import BeautifulSoup
def get_soup(html_content):
    return BeautifulSoup(html_content, 'lxml')

## 3. Implementation Logic for 4-Pass Pipeline## Pass 1: Local Path Conversion
Goal: Convert internal domain links into relative filesystem paths.

* Logic: Target <a> tags with href attributes.
* Check: If the URL matches the target domain, replace the absolute URL with a relative path based on the directory structure.

## Pass 2 & 3: External Media & CDN Rewriting
Goal: Scan for external resources, deduplicate, and rewrite to local paths.

* Target Tags/Attributes:
* <img>: src, srcset, data-src
   * <link>: href (specifically for .css)
   * <script>: src
   * <video>/<audio>: src, <source src>
* Rewriting Logic:

for img in soup.find_all('img', src=True):
    original_url = img['src']
    if is_external(original_url):
        # Pass 2: Add to parallel download queue
        queue.add(strip_query_params(original_url))
        # Pass 3: Rewrite to local path
        img['src'] = convert_to_local_media_path(original_url)


## Pass 4: Offline Optimization (Sanitization)
This pass uses BeautifulSoup’s .decompose() method to physically remove unwanted elements from the DOM. [3] 

| Task | BS4 Target |
|---|---|
| Remove Tracking | `soup.find_all('script', src=re.compile(r'analytics |
| Remove Feeds | soup.find_all('link', type='application/rss+xml') |
| Strip CORS | del tag['integrity'], del tag['crossorigin'] |
| Clean phpBB | `soup.find_all('a', href=re.compile(r'mode=quote |
| Inject CSS | soup.head.append(new_tag) |

## 4. Handling Settings within the Scraper
The LLM must map your settings table to the following behaviors:

* MaxDepth: The crawler must track depth in its recursive function; if current_depth >= MaxDepth, do not parse <a> tags for further links.
* RejectPatterns / RejectDomains: Before downloading or parsing any URL, run a regex check:

if any(re.search(pattern, url) for pattern in RejectPatterns):
    return  # Skip this URL

* MediaExtensions: When Pass 2 scans the soup, it should only queue files if url.endswith(tuple(MediaExtensions)).
* WaitBetweenRequests: Implement time.sleep() within the download loop to prevent IP bans. [4, 5] 

## 5. Typical BeautifulSoup Code Block for LLM

import refrom bs4 import BeautifulSoup
def process_html_offline(html_content, settings):
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Example Pass 4: Remove Analytics
    for script in soup.find_all('script', src=True):
        if any(domain in script['src'] for domain in settings['RejectDomains']):
            script.decompose()

    # Example Pass 3: Rewrite CDN to local
    for link in soup.find_all('link', href=True):
        if link['href'].startswith('http'):
            link['href'] = "./assets/" + link['href'].split('/')[-1]
            
    return soup.prettify()

------------------------------
