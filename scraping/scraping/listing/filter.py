import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests
import boto3
import re

dynamodb = boto3.resource('dynamodb')
article_url_table = dynamodb.Table('articles_urls')

def get_rated_articles():
    all_items = []
    last_evaluated_key = None
    while True:
        scan_params = {"ExclusiveStartKey": last_evaluated_key} if last_evaluated_key else {}
        response = article_url_table.scan(**scan_params)
        all_items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break
    return all_items

def combine_and_sort_articles(rated_articles, scraped_articles):
    rated_map = {article['url']: article for article in rated_articles}
    for article in scraped_articles:
        url = article.get('url')
        article['average_rating'] = float(rated_map.get(url, {}).get('average_rating', 0))
    scraped_articles.sort(key=lambda x: (-x['average_rating'], -x.get('final_score', 0)))
    return scraped_articles

def normalize(values):
    min_val, max_val = min(values, default=0), max(values, default=1)
    return [1 if min_val == max_val else (v - min_val) / (max_val - min_val) for v in values]


def rank_articles(query, articles):
    titles = [article.get('title', '') for article in articles]
    if not titles:
        return []

    try:
        response = requests.post("https://yf5xrpkaqwg46fzfiyoq5paeza0ibfhn.lambda-url.ap-south-1.on.aws/", json={"documents": [query] + titles})
        response.raise_for_status()
        cosine_sim = json.loads(response.json().get('body', '{}')).get('similarity_matrix', [[]])[0][1:]
    except Exception:
        return []

    citation_scores = normalize([article.get('citation_count', 0) for article in articles])
    for idx, article in enumerate(articles):
        article['final_score'] = 0.7 * (cosine_sim[idx] if idx < len(cosine_sim) else 0) + 0.3 * citation_scores[idx]
    return articles

def scrape_articles_multithreaded(query, page=1, sort="relevance", start_date=None, end_date=None,article_types=None, subject_areas=None):
    try:
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(scrape_pubmed, query, page, sort, start_date, end_date,article_types),
                executor.submit(scrape_biorxiv, query, page, sort, start_date, end_date),                
                executor.submit(scrape_plos_articles, query, page, sort,start_date,end_date,article_types, subject_areas),
            ]
            results = [future.result() for future in futures]
        all_results = sum((res if isinstance(res, list) else [] for res in results), [])
        if not all_results:
            return {"statusCode": 404, "body": json.dumps({"error": "No articles found."})}
        rated_articles = get_rated_articles()
        sorted_articles = combine_and_sort_articles(rated_articles, rank_articles(query, all_results))
        return {"statusCode": 200, "body":{"articles": sorted_articles}}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def scrape_pubmed(query, page=1, sort='relevance',start_date=None, end_date=None,article_types=None):
    base_url = "https://pubmed.ncbi.nlm.nih.gov/"
    search_url = f"{base_url}?term={query.replace(' ', '+')}&page={page}"
    if start_date and end_date:
        search_url += f"&filter=dates.{start_date.replace('-', '%2F')}-{end_date.replace('-', '%2F')}"
        print(search_url)
    if sort == 'recent':
        search_url += "&filter=simsearch1.fha&filter=simsearch2.ffrft&sort=date"
    elif sort == 'oldest':
        search_url += "&sort=date&filter=years.2008-2025"
    else:
        search_url += "&filter=simsearch1.fha&filter=simsearch2.ffrft"
    

    article_type_mapping = {
        "Adaptive Clinical Trial": "pubt.adaptiveclinicaltrial",
        "Clinical Study": "pubt.clinicalstudy",
        "Observational Study": "pubt.observationalstudy",
        "Randomized Controlled Trial": "pubt.randomizedcontrolledtrial",
        "Comparative Study": "pubt.comparativestudy",
        "Published Erratum": "pubt.publishederratum",
        "Corrected and Republished Article": "pubt.correctedrepublishedarticle",
        "Review": "pubt.review",
        "Systematic Review": "pubt.systematicreview",
        "Meta-Analysis": "pubt.metaanalysis",
        "Editorial": "pubt.editorial",
        "Personal Narrative": "pubt.personalnarrative",
        "Comment": "pubt.comment",
        "Letter": "pubt.letter",
        "Practice Guideline": "pubt.practiceguideline",
        "Guideline": "pubt.guideline",
        "Consensus Development Conference": "pubt.consensusdevelopmentconference",
        "Case Reports": "pubt.casereports",
        "Historical Article": "pubt.historicalarticle",
        "Interview": "pubt.interview",
        "Congress": "pubt.congress",
        "Technical Report": "pubt.technicalreport",
        "Dataset": "pubt.dataset",
        "Video-Audio Media": "pubt.videoaudiomedia"
    }



    if article_types:
        for article_type in article_types:
            pubt_filter = article_type_mapping.get(article_type)  
            if pubt_filter:
                search_url += f"&filter={pubt_filter}"
            else:
                print(f"Warning: Unknown article type '{article_type}'. No filter applied.")

    print("Final URL:", search_url)  # Debugging 

    try:
        response = requests.get(search_url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from PubMed (HTTP {response.status_code})")
        soup = BeautifulSoup(response.text, "html.parser")
        total_results = 0
        results_summary = soup.find('label', class_='of-total-pages')
        if results_summary:
            total_results_text = results_summary.get_text(strip=True).replace("of ", "")
            total_results = int(''.join(filter(str.isdigit, total_results_text)))  

        articles = soup.find_all("article", class_="full-docsum")
        if not articles:
            return []
        results = []
        for article in articles[:10]:
            pmid = article.find("span", class_="docsum-pmid").get_text(strip=True)
            pmid_tag = article.find("a", class_="docsum-title")
            title = pmid_tag.get_text(strip=True) if pmid_tag else "Title not available"
            authors_tag = article.find("span", class_="docsum-authors")
            authors = authors_tag.get_text(strip=True) if authors_tag else "Authors not available"
            doi_tag = article.find("span", class_="docsum-journal-citation")
            doi = None
            publication_date = None
            if doi_tag:
                doi_text = doi_tag.get_text(strip=True)
                if "doi:" in doi_text.lower():
                    doi = doi_text.split("doi:")[-1].strip()
                citation_text = doi_tag.get_text(strip=True)
                date_match = re.search(r'\b(\d{4} [A-Za-z]{3,4}(?: \d{1,2})?)\b', citation_text)
                if date_match:
                    raw_date = date_match.group(1)
                    parts = raw_date.split()
                    try:
                        if len(parts) == 2:
                            date_str = f"{parts[0]} {parts[1]} 01"
                        elif len(parts) == 3:
                            date_str = f"{parts[0]} {parts[1]} {parts[2]}"
                        else:
                            raise ValueError
                        parsed_date = datetime.strptime(date_str, "%Y %b %d")
                        publication_date = parsed_date.strftime("%d-%b-%Y")
                    except (ValueError, IndexError):
                        publication_date = None
            url = f"{base_url}{pmid}/"
            results.append({
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "url": url,
                "doi": doi,
                "date": publication_date,  
                "source": "PubMed",
                'total results':total_results
               
            })
        return results
    except Exception as e:
        raise Exception(f"Error occurred while scraping PubMed: {str(e)}")


def scrape_biorxiv(query, page=0, sort='relevance', start_date=None, end_date=None):
    formatted_query = query.replace(' ', '+')
    date_filter = ""

    if start_date and end_date:
        date_filter = f"limit_from%3A{start_date}%20limit_to%3A{end_date}%20"

    if sort == 'recent':
        sort_param = "publication-date%20direction%3Adescending"
    elif sort == 'oldest':
        sort_param = "publication-date%20direction%3Aascending"
    else:
        sort_param = "relevance-rank"

    articles = []

    url = f"https://www.medrxiv.org/search/{formatted_query}%20jcode%3Amedrxiv%20{date_filter}numresults%3A10%20sort%3A{sort_param}%20format_result%3Astandard?page={page}"

    try:
        response = requests.get(url)
        if response.status_code != 200:
            return {"total_results": 0, "articles": []}

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extract total number of results
        total_results = 0
        results_summary = soup.find('h1', id='page-title')
        if results_summary:
            total_results_text = results_summary.get_text(strip=True)
            total_results = int(''.join(filter(str.isdigit, total_results_text)))  # Extract only numbers

        # Extract articles
        article_elements = soup.find_all('div', class_='highwire-article-citation')

        for article in article_elements:
            title_element = article.find('span', class_='highwire-cite-title')
            title = title_element.get_text(strip=True) if title_element else "Title not available"

            link_element = article.find('a', class_='highwire-cite-linked-title')
            link = f"https://www.medrxiv.org{link_element['href']}" if link_element else "Link not available"

            authors_element = article.find('div', class_='highwire-cite-authors')
            authors = authors_element.get_text(strip=True) if authors_element else "Authors not available"

            metadata_element = article.find('div', class_='highwire-cite-metadata')
            doi = "DOI not available"
            formatted_date = "Date not available"

            if metadata_element:
                doi_element = metadata_element.find('span', class_='highwire-cite-metadata-doi')
                if doi_element:
                    doi = doi_element.get_text(strip=True).replace('doi:', '').strip()
                    try:
                        doi_parts = doi.split('/')
                        if len(doi_parts) > 1:
                            date_part = doi_parts[-1].split('.')[:3]
                            if len(date_part) == 3:
                                raw_date = '-'.join(date_part)
                                formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%b-%Y")
                    except ValueError:
                        formatted_date = "Date extraction error from DOI"

                date_element = metadata_element.find('span', class_='highwire-cite-metadata-pages')
                if date_element:
                    raw_date = date_element.get_text(strip=True)
                    try:
                        formatted_date = datetime.strptime(raw_date, "%d-%b-%Y").strftime("%d-%b-%Y")
                    except ValueError:
                        pass

            articles.append({
                'title': title,
                'url': link,
                'source': 'MedRxiv',
                'authors': authors,
                'doi': doi,
                'date': formatted_date,
                'results': total_results
            })

        return articles

    except Exception as e:
        print(f"Error occurred while scraping BioRxiv: {str(e)}")
        return {"total_results": 0, "articles": []}




def scrape_plos_articles(query, page=1, sort="relevance",start_date=None, end_date=None,article_types=None,subject_areas=None):
    api_url = "https://uvdzsuhkzxo7lu4uawyc6dop3u0typdc.lambda-url.ap-south-1.on.aws/"
    # Convert lists to comma-separated strings
    article_types_str = ",".join(article_types) if isinstance(article_types, list) else article_types
    subject_areas_str = ",".join(subject_areas) if isinstance(subject_areas, list) else subject_areas

    params = {
        "query": query,
        "page": page,
        "sort": sort,
        "start_date": start_date,
        "end_date": end_date,
        "article_types": article_types_str,   
        "subject_areas": subject_areas_str    
    }

    print(f"Final API Request Params for PLOS: {params}")  # Debugging statemen
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get('statusCode') == 200:
            articles = json.loads(data.get('body', "[]"))
            parsed_articles = []
            for article in articles:
                raw_date = article.get('date', 'Date not available')
                try:
                    formatted_date = datetime.strptime(raw_date, "published %d %b %Y").strftime("%d-%b-%Y")
                except ValueError:
                    formatted_date = raw_date

                parsed_articles.append({
                    'title': article.get('title', 'Title not available'),
                    'url': article.get('link', 'Link not available'),
                    'authors': article.get('authors', 'Authors not available'),
                    'source': 'PLOS',
                    'date': formatted_date,
                    'doi': article.get('doi', 'DOI not available')
                })

            return parsed_articles
        else:
            return []
    except requests.exceptions.RequestException as e:
        return []
    except json.JSONDecodeError as e:
        return []

def lambda_handler(event, context):
    # Extract query parameters
    query = event.get('queryStringParameters', {}).get('query', '')
    page = int(event.get('queryStringParameters', {}).get('page', 1))
    sort = event.get('queryStringParameters', {}).get('sort', 'relevance')
    start_date = event.get('queryStringParameters', {}).get('start_date', None)
    end_date = event.get('queryStringParameters', {}).get('end_date', None)

    # Convert comma-separated strings into lists
    article_types = event.get("queryStringParameters", {}).get('article_types', None)
    if article_types:
        article_types = [atype.strip() for atype in article_types.split(',')]

    subject_areas = event.get("queryStringParameters", {}).get('subject_areas', None)
    if subject_areas:
        subject_areas = [sarea.strip() for sarea in subject_areas.split(',')]

    response_data = scrape_articles_multithreaded(query, page, sort, start_date, end_date, article_types, subject_areas)
    
    if isinstance(response_data, str):
        body = response_data
    else:
        body = json.dumps(response_data)

    return {
        'statusCode': 200,
        'body': body, 
        'headers': {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    }