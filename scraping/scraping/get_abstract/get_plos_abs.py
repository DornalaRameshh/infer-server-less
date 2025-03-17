import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Union
from fastapi import FastAPI, HTTPException, Query

app = FastAPI()

def extract_article_data(url: str) -> Dict[str, Union[str, List[str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Error fetching the article: HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract title
    title_element = soup.find('h1', {'id': 'artTitle'})
    title = title_element.get_text(strip=True) if title_element else "Title not found"

    # Extract authors
    author_elements = soup.select('ul#author-list li a.author-name')
    authors = [author.get_text(strip=True).replace(",", "") for author in author_elements] if author_elements else []

    # Extract DOI
    doi_element = soup.find('li', {'id': 'artDoi'})
    doi = doi_element.find('a')['href'] if doi_element and doi_element.find('a') else "DOI not found"

    # Extract abstract
    abstract_element = soup.find('div', {'class': 'abstract'})
    abstract_text = abstract_element.get_text(strip=True) if abstract_element else "Abstract not found"

    # Format output correctly
    data = {
        "title": title,
        "doi": doi,
        "authors": authors,
        "abstract": abstract_text,  # Ensures abstract is separate
        "full_text_url": url  # Ensures full_text_url is separate
    }
    
    return data

@app.get("/extract-article-data")
def extract_data(url: str = Query(..., title="Article URL")):
    try:
        article_data = extract_article_data(url)
        return article_data
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching the article: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
