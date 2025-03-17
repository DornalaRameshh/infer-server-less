import json
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Union

class ContentBlock:
    def __init__(self, type: str, content: Union[str, list, dict]):
        self.type = type
        self.content = content

    def to_dict(self):
        return {"type": self.type, "content": self.content}

def fetch_pubmed_citation(pmcid: str) -> List[Dict[str, str]]:
    api_url = f"https://pmc.ncbi.nlm.nih.gov/resources/citations/{pmcid}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Referer": "https://www.ncbi.nlm.nih.gov/"
    }
    response = requests.get(api_url, headers=headers)    
    try:
        data = response.json()
    except json.JSONDecodeError:
        return []
    citations = []
    for style in ["ama", "apa", "mla", "nlm"]:
        if style in data:
            citations.append({
                "text": style,
                "format": data[style].get("format", "")
            })
    return citations

def extract_pmcid(soup):
    pmcid = None
    for text in soup.find_all(string=True):
        if "PMCID:" in text:
            pmcid = text.split("PMCID:")[-1].split()[0].strip().replace('PMC', '') if 'PMCID:' in text else None
            break  
    return pmcid



def extract_content_with_front_matter(url: str) -> List[ContentBlock]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    content_blocks = []
    last_caption = ""
    table_count = 0 

    

    # Extract front matter
    front_matter = soup.find('section', {'class': 'front-matter'})
    if front_matter:
        # Title
        title = front_matter.find('h1').get_text(strip=True) if front_matter.find('h1') else "No Title Found"
        content_blocks.append(ContentBlock(type="title", content=title))


        # Extract PMCID
        pmcid = extract_pmcid(soup)  
    
        # Fetch citations if PMCID is found
        if pmcid:
            citations = fetch_pubmed_citation(pmcid)
            if citations:
                content_blocks.append(ContentBlock(type="citations", content=citations))

        # Authors
        authors = front_matter.find('span', {'class': 'collab'})
        if authors:
            content_blocks.append(ContentBlock(type="heading", content="Authors"))
            content_blocks.append(ContentBlock(type="text", content=authors.get_text(strip=True)))

        # Additional panels (Remove Article Notes and License)
        panels = front_matter.find_all('div', {'class': 'd-panel'})
        for panel in panels:
            panel_id = panel.get('id')
            if panel_id == "aip_a":  # Keep only Author Information
                content = panel.get_text(strip=True)
                content_blocks.append(ContentBlock(type="subheading", content="Author Information"))
                content_blocks.append(ContentBlock(type="text", content=content))

        # PMCID and PMID
        identifiers = front_matter.find('div', text=lambda x: "PMCID" in x if x else False)
        if identifiers:
            content_blocks.append(ContentBlock(type="subheading", content="Identifiers"))
            content_blocks.append(ContentBlock(type="text", content=identifiers.get_text(strip=True)))

    # Extract main article content
    article_section = soup.find('section', {'aria-label': 'Article content'})
    if article_section:
        for section in article_section.find_all(['h2', 'h3', 'h4', 'p', 'figure', 'table']):
            if section.name == 'h2':
                content_blocks.append(ContentBlock(type="subheading", content=section.get_text(strip=True)))
            elif section.name == 'h3':
                content_blocks.append(ContentBlock(type="subsubheading", content=section.get_text(strip=True)))
            elif section.name == 'h4':
                content_blocks.append(ContentBlock(type="subsubsubheading", content=section.get_text(strip=True)))
            elif section.name == 'p':
                # Skip text if it matches the last image caption
                if last_caption and last_caption in section.get_text(strip=True):
                    continue
                content_blocks.append(ContentBlock(type="text", content=section.get_text(strip=True)))
            elif section.name == 'figure':
                img_tag = section.find('img')
                fig_caption = section.find('figcaption').get_text(strip=True) if section.find('figcaption') else "No caption provided"
                fig_heading = section.find_previous('h3', class_='obj_head')
                heading_text = fig_heading.get_text(strip=True) if fig_heading else None
                if img_tag and 'src' in img_tag.attrs:
                    # Add image and caption along with the figure heading if available
                    content_blocks.append(ContentBlock(type="image", content={
                        'url': img_tag['src'],
                        'caption': f"{heading_text}: {fig_caption}" if heading_text else fig_caption
                    }))
                    last_caption = fig_caption
            elif section.name == 'table':
                # Increment table count
                table_count += 1
                table_number = f"Table {table_count}"

                # Extract table content
                rows = []
                for row in section.find_all('tr'):
                    cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                    rows.append(cells)

                # Use a real caption if available; otherwise, fallback to table number
                caption = section.find('caption').get_text(strip=True) if section.find('caption') else table_number

                # Only add tables with valid captions
                if caption != "No caption provided":
                    content_blocks.append(ContentBlock(type="table", content={
                        "caption": caption,
                        "rows": rows
                    }))

    references_section = soup.find('section', {'id': 'ref-list1'})
    if references_section:
        references_data = []
        references = references_section.find_all('li')

        for ref in references:
            ref_id = ref.get("id", "unknown")
            ref_text = ref.cite.get_text(strip=True) if ref.cite else ref.get_text(strip=True)
            
            # Extract links
            links_data = []
            for a in ref.find_all('a', href=True):
                link_text = a.get_text(strip=True)
                link_url = a['href']
                links_data.append({
                    "text": link_text,
                    "url": link_url
                })

            references_data.append({
                "id": ref_id,
                "citation": ref_text,
                "links": links_data
            })

        # Append references section in required format
        content_blocks.append(ContentBlock(type="subheading", content="References"))
        content_blocks.append(ContentBlock(type="references", content=references_data))

    return content_blocks


HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

def lambda_handler(event, context):
    try:
        # Extract the URL from query string parameters
        url = event.get('queryStringParameters', {}).get('url')
        if not url:
            return {
                "statusCode": 400,
                "headers": HEADERS,
                "body": json.dumps({"error": "URL is required in the query string parameters."})
            }

        # Extract content from the provided URL
        content_blocks = extract_content_with_front_matter(url)

        # Convert to dictionary for JSON serialization
        result = [block.to_dict() for block in content_blocks]

        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": result
        }

    except requests.RequestException as e:
        return {
            "statusCode": 400,
            "headers": HEADERS,
            "body": json.dumps({"error": f"Error fetching the article: {e}"})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": HEADERS,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"})
        }