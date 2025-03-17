import json
import requests
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Union

def extract_content_with_structure(url: str) -> List[Dict[str, Union[str, Dict]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching the article: HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    content_blocks = []
    base_url = "https://journals.plos.org/digitalhealth"

    # Extract the main title
    main_title = soup.find('h1', {'id': 'artTitle'})
    if main_title:
        content_blocks.append({'type': 'title', 'content': main_title.get_text(strip=True)})

    # Locate the main article content
    main_content = soup.find('div', {'class': 'article-text'})
    if not main_content:
        raise Exception("No article content found")

    

    for child in main_content.descendants:
        if child.name == 'h1':
            content_blocks.append({'type': 'title', 'content': child.get_text(strip=True)})
        elif child.name == 'h2':
            content_blocks.append({'type': 'subheading', 'content': child.get_text(strip=True)})
        elif child.name == 'h3':
            content_blocks.append({'type': 'subsubheading', 'content': child.get_text(strip=True)})
        elif child.name == 'h4':
            content_blocks.append({'type': 'subsubsubheading', 'content': child.get_text(strip=True)})
        elif child.name == 'p':
            content_blocks.append({'type': 'text', 'content': child.get_text(strip=True)})
        elif child.name == 'div' and 'figure' in child.get('class', []):
            figure_data = {}

            # Extract image URL
            img_box = child.find('div', class_='img-box')
            if img_box:
                img_tag = img_box.find('img')
                if img_tag and 'src' in img_tag.attrs:
                    img_src = img_tag['src'].replace("amp;", "")
                    figure_data['image_url'] = f"{base_url}/{img_src}" if not img_src.startswith("http") else img_src

            # Extract caption
            caption = child.find('div', class_='figcaption')
            if caption:
                figure_data['caption'] = caption.get_text(strip=True)

            # Extract download links
            downloads = child.find('div', class_='figure-inline-download')
            if downloads:
                figure_data['downloads'] = {}
                for link in downloads.find_all('a', href=True):
                    file_type = link.find('div', class_='definition-label')
                    if file_type:
                        file_type = file_type.get_text(strip=True)
                        href = link['href'].replace("amp;", "")
                        full_url = f"{base_url}/{href}" if not href.startswith("http") else href
                        figure_data['downloads'][file_type] = full_url

            content_blocks.append({'type': 'figure', 'content': figure_data})
        elif child.name == 'ol' and 'references' in child.get('class', []):
            # Process references list
            references = []
            for li in child.find_all('li', recursive=False):
                ref_id = li.get('id', '')
                order_span = li.find('span', class_='order')
                order = order_span.get_text(strip=True) if order_span else ''
                citation_parts = []
                # Iterate through the elements of the li to build the citation
                for element in li.contents:
                    # Skip the order span and any elements after reflinks
                    if element == order_span:
                        continue
                    if isinstance(element, Tag) and element.name == 'ul' and 'reflinks' in element.get('class', []):
                        break
                    if isinstance(element, str):
                        text = element.strip()
                        if text:
                            citation_parts.append(text)
                    else:
                        text = element.get_text(strip=True)
                        if text:
                            citation_parts.append(text)
                citation = ' '.join(citation_parts).strip()
                # Extract links from reflinks
                links = []
                reflinks = li.find('ul', class_='reflinks')
                if reflinks:
                    for a_tag in reflinks.find_all('a', href=True):
                        link_text = a_tag.get_text(strip=True)
                        link_url = a_tag['href']
                        links.append({'text': link_text, 'url': link_url})
                references.append({
                    'id': ref_id,
                    'citation': citation,
                    'links': links
                })
            content_blocks.append({'type': 'references', 'content': references})

    # Extract publication date and DOI
    pub_date = soup.find('li', {'id': 'artPubDate'})
    if pub_date:
        content_blocks.append({'type': 'publication_date', 'content': pub_date.get_text(strip=True)})

    doi = soup.find('li', {'id': 'artDoi'})
    if doi and doi.find('a'):
        content_blocks.append({'type': 'doi', 'content': doi.find('a')['href']})
        
    # Extract citation from the articleinfo div
    article_info = soup.find('div', {'class': 'articleinfo'})
    if article_info:
        citation_paragraph = article_info.find('p')
        if citation_paragraph and citation_paragraph.find('strong', text='Citation: '):
            citation_text = citation_paragraph.get_text(strip=True).replace("Citation:", '', 1)
            content_blocks.append({'type': 'citation', 'content': citation_text})

    return content_blocks

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}
def lambda_handler(event, context):
    try:
        query_params = event.get('queryStringParameters', {})
        url = query_params.get('url')

        if not url:
            return {
                "statusCode": 400,
                "headers":HEADERS,
                "body": json.dumps({"error": "URL is required in query parameters"})
            }

        structured_content = extract_content_with_structure(url)
        return {
            "statusCode": 200,
            "headers":HEADERS,
            "body": structured_content
        }
    except requests.RequestException as e:
        return {
            "statusCode": 400,
            "headers":HEADERS,
            "body": json.dumps({"error": f"Error fetching the article: {str(e)}"})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers":HEADERS,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"})
        }