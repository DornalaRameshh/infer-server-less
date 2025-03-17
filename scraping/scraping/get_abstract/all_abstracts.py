import json
import requests
from typing import Dict, List, Union, Callable
from bs4 import BeautifulSoup

def extract_relevant_plos(section):
   
    if not section:
        return [{"type": "text", "content": "Abstract not available"}]
    
    content = []
    
    # Get the top-level <h2> (e.g., "Abstract")
    h2_tag = section.find("h2")
    if h2_tag:
        content.append({"type": "subsubheading", "content": h2_tag.get_text(strip=True)})
    
    # Find the abstract-content div where the main content resides
    abstract_content = section.find("div", class_="abstract-content")
    if abstract_content:
        # Check for direct <p> tags first ( simpler structure)
        p_tags = abstract_content.find_all("p", recursive=False)
        if p_tags:
            for p_tag in p_tags:
                content.append({"type": "text", "content": str(p_tag)})
        else:
            # Fall back to section-based structure if no direct <p> tags
            for child in abstract_content.children:
                if child.name == "div" and "section" in child.get("class", []):
                    # Extract <h3> subheadings
                    h3_tag = child.find("h3")
                    if h3_tag:
                        content.append({"type": "subsubsubheading", "content": h3_tag.get_text(strip=True)})
                    
                    # Extract <p> paragraphs within this section
                    p_tag = child.find("p")
                    if p_tag:
                        content.append({"type": "text", "content": str(p_tag)})
    
    return content

def extract_relevant_pubmed(abstract_div):
   
    if not abstract_div:
        return [{"type": "text", "content": "Abstract not available"}]
    
    result = []
    h2_title = abstract_div.find("h2", class_="title")
    if h2_title:
        result.append({"type": "subsubheading", "content": h2_title.get_text(strip=True)})
    
    content_div = abstract_div.find("div", class_="abstract-content")
    if content_div:
        # Process each paragraph within the abstract-content div
        for p in content_div.find_all("p", recursive=False):
            strong_tag = p.find("strong", class_="sub-title")
            if strong_tag:
                # Add the subheading
                subheading_text = strong_tag.get_text(strip=True)
                result.append({"type": "subsubsubheading", "content": subheading_text})
                
                # Remove the strong tag and get remaining text
                strong_tag.decompose()
                remaining_text = p.get_text(strip=True)
                if remaining_text:
                    result.append({"type": "text", "content": f"<p>{remaining_text}</p>"})
            else:
                # If no strong tag, treat as plain text
                text_content = p.get_text(strip=True)
                if text_content:
                    result.append({"type": "text", "content": f"<p>{text_content}</p>"})
    
    # Check for any additional <p> tags outside the abstract-content div (e.g., Keywords)
    for p in abstract_div.find_all("p", recursive=False):
        strong_tag = p.find("strong", class_="sub-title")
        if strong_tag:
            subheading_text = strong_tag.get_text(strip=True)
            result.append({"type": "subsubsubheading", "content": subheading_text})
            
            # Remove the strong tag and get remaining text
            strong_tag.decompose()
            remaining_text = p.get_text(strip=True)
            if remaining_text:
                result.append({"type": "text", "content": f"<p>{remaining_text}</p>"})
    
    return result
def extract_relevant_biorxiv(abstract_div) -> List[Dict[str, str]]:
    """Extract relevant content from a bioRxiv abstract section."""
    if not abstract_div:
        return [{"type": "text", "content": "Abstract not available"}]
    
    result = []
    # Get the top-level <h2> (e.g., "ABSTRACT")
    h2_title = abstract_div.find("h2")
    if h2_title:
        result.append({"type": "subsubheading", "content": h2_title.get_text(strip=True)})
    
    # Process each subsection div
    for subsection in abstract_div.find_all("div", class_="subsection"):
        # Each subsection should have a <p> tag
        p_tag = subsection.find("p")
        if p_tag:
            strong_tag = p_tag.find("strong")
            if strong_tag:
                # Add the subheading from <strong>
                subheading_text = strong_tag.get_text(strip=True)
                result.append({"type": "subsubsubheading", "content": subheading_text})
                
                # Remove the strong tag and get remaining text
                strong_tag.decompose()
                remaining_text = p_tag.get_text(strip=True)
                if remaining_text:
                    result.append({"type": "text", "content": f"<p>{remaining_text}</p>"})
            else:
                # If no strong tag, treat as plain text
                text_content = p_tag.get_text(strip=True)
                if text_content:
                    result.append({"type": "text", "content": f"<p>{text_content}</p>"})
    
    return result

def get_biorxiv(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    title = soup.find("h1", class_="highwire-cite-title").get_text(strip=True) if soup.find("h1", class_="highwire-cite-title") else "Title not available"
    doi = soup.find("meta", {"name": "citation_doi"})["content"] if soup.find("meta", {"name": "citation_doi"}) else "DOI not available"
    authors_tag = soup.find_all("meta", {"name": "citation_author"})
    authors = [author["content"] for author in authors_tag] if authors_tag else ["Authors not available"]
    abstract_section = soup.find("div", class_="abstract")
    full_text_url=url+".full-text"
    abstract = extract_relevant_biorxiv(abstract_section)
    
    return {"title": title, "doi": doi, "authors": authors, "abstract": abstract, "full_text_url":full_text_url}



def get_pubmed(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    title = soup.find("h1", class_="heading-title").get_text(strip=True) if soup.find("h1", class_="heading-title") else "Title not available"
    doi = soup.find("span", class_="doi").get_text(strip=True).replace("DOI:", "").strip() if soup.find("span", class_="doi") else "DOI not available"
    authors = [a.get_text(strip=True) for a in soup.find_all("a", class_="full-name")] or ["Authors not available"]
    # Extract PMC full text URL
    pmc_link = soup.find("a", class_="link-item pmc")
    full_text_url = pmc_link["href"] if pmc_link and "href" in pmc_link.attrs else url  # Fallback to input URL if PMC link not found
    abstract = extract_relevant_pubmed(soup.find("div", class_="abstract"))
    
    return {
        "title": title, 
        "doi": doi, 
        "authors": authors,
        "abstract": abstract, 
        "full_text_url": full_text_url
    }

def get_plos(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {"error": f"Error fetching PLOS article: HTTP {response.status_code}"}
    
    soup = BeautifulSoup(response.text, 'html.parser')
    title_element = soup.find('h1', {'id': 'artTitle'})
    title = title_element.get_text(strip=True) if title_element else "Title not found"
    author_elements = soup.select('ul#author-list li a.author-name')
    authors = [author.get_text(strip=True).replace(",", "") for author in author_elements] if author_elements else []
    doi_element = soup.find('li', {'id': 'artDoi'})
    doi = doi_element.find('a')['href'] if doi_element and doi_element.find('a') else "DOI not found"
    abstract_element = soup.find('div', {'class': 'abstract'})
    abstract_text = extract_relevant_plos(abstract_element)
    
    return {"title": title, "doi": doi, "authors": authors, "abstract": abstract_text, "full_text_url": url}

def lambda_handler(event, context):
    CORS_HEADERS = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    try:
        print("Event Received:", json.dumps(event))

        if event.get("httpMethod") == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps({"message": "Preflight success"})}

        query_params = event.get("queryStringParameters", {}) or {}
        url = query_params.get("url")
        source = query_params.get("source")

        if not url or not source:
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "Missing 'url' or 'source' query parameter"})}

        source = source.lower()
        source_handlers = {
            "medrxiv": get_biorxiv,
            "pubmed": get_pubmed,
            "plos": get_plos,
        }

        handler = source_handlers.get(source)
        if handler is None:
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "Invalid source. Use 'biorxiv', 'pubmed', or 'plos'"})}

        result = handler(url)
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(result)}
    
    except Exception as e:
        return {"statusCode": 500, "headers": CORS_HEADERS, "body": json.dumps({"error": str(e)})}
