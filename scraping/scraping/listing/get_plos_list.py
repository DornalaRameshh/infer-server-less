import json
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from math import ceil

def fetch_page_content(url: str, context):
    try:
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=5000)
        page.wait_for_selector("dl#searchResultsList", timeout=5000)
        html = page.content()
        page.close()
        return html
    except Exception as e:
        print(f"Error loading page: {str(e)}")
        return ""

def scrape_articles_chunk(article_chunks):
    articles = []
    for dt, dd in article_chunks:
        title_tag = dt.find('a', href=True)
        title = title_tag.get_text(strip=True) if title_tag else "Title not available"
        link = f"https://journals.plos.org{title_tag['href']}" if title_tag else "Link not available"

        authors_tag = dd.find('p', {'class': 'search-results-authors'})
        authors = authors_tag.get_text(strip=True) if authors_tag else "Authors not available"

        article_type_tag = dd.find('span', {'id': lambda x: x and x.endswith('-type')})
        article_type = article_type_tag.get_text(strip=True) if article_type_tag else "Type not available"

        publication_date_tag = dd.find('span', {'id': lambda x: x and x.endswith('-date')})
        publication_date = publication_date_tag.get_text(strip=True) if publication_date_tag else "Date not available"

        doi_tag = dd.find('p', {'class': 'search-results-doi'})
        doi_link_tag = doi_tag.find('a') if doi_tag else None
        doi_link = doi_link_tag['href'] if doi_link_tag else "DOI not available"

        articles.append({
            'title': title,
            'link': link,
            'authors': authors,
            'type': article_type,
            'date': publication_date,
            'doi': doi_link,
            'source': "PLOS ONE"
        })
    return articles

def scrape_plos_articles(query: str, page: int = 1, sort: str = "relevance",start_date=None, end_date=None):
    base_url = f"https://journals.plos.org/plosone/search?filterJournals=PLoSONE"

    # Apply date filters if provided
    if start_date and end_date:
        base_url += f"&filterStartDate={start_date}&filterEndDate={end_date}"

    # Add query and page parameters
    base_url += f"&q={query.replace(' ', '+')}&page={page}"

    # Add sort order
    if sort == "recent":
        sort_order = "DATE_NEWEST_FIRST"
    elif sort == "oldest":
        sort_order = "DATE_OLDEST_FIRST"
    else:
        sort_order = "RELEVANCE"
    
    # Append sort order to the URL
    url = f"{base_url}&sortOrder={sort_order}"
    # Append date filters if they are provided
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright",
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--single-process",
                "--disable-software-rasterizer"
            ]
        )
        context = browser
        html = fetch_page_content(url, context)
        if not html:
            print("Failed to fetch page content")
            return []
         soup = BeautifulSoup(html, 'html.parser')
        search_results = soup.find('dl', {'id': 'searchResultsList'})

        if not search_results:
            print("No search results found")
            return []

        dt_tags = search_results.find_all('dt', {'class': 'search-results-title'})
        dd_tags = search_results.find_all('dd', recursive=False)

        if not dt_tags or not dd_tags:
            print("No articles found in search results")
            return []

        articles_data = list(zip(dt_tags, dd_tags))
        total_articles = len(articles_data)
        chunk_sizes = [ceil(total_articles / 3) for _ in range(3)]
        chunks = [articles_data[start:start + size] for start, size in zip(range(0, total_articles, chunk_sizes[0]), chunk_sizes)]

        articles = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(scrape_articles_chunk, chunk) for chunk in chunks]
            for future in futures:
                try:
                    articles.extend(future.result())
                except Exception as e:
                    print(f"Error processing chunk: {str(e)}")

        context.close()
    return articles

def handler(event, context):
    query = event.get("queryStringParameters", {}).get("query", "")
    page = event.get("queryStringParameters", {}).get("page", 1)
    sort = event.get("queryStringParameters", {}).get("sort", "relevance").lower()
    start_date = event.get('queryStringParameters', {}).get('start_date', None)
    end_date = event.get('queryStringParameters', {}).get('end_date', None)

    try:
        page = int(page)
        if page < 1:
            raise ValueError("Page number must be 1 or greater.")
         if sort not in ["relevance", "recent", "oldest"]:
            raise ValueError("Invalid sort parameter. Must be 'relevance', 'recent', or 'oldest'.")

    except ValueError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)})
        }

    if not query:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Query parameter 'query' is required."})
        }

    try:
        results = scrape_plos_articles(query, page, sort,start_date,end_date)
        return {
            "statusCode": 200,
            "body": json.dumps(results)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }