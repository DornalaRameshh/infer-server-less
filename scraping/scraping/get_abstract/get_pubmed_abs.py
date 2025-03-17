from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

app = FastAPI()

class ArticleResponse(BaseModel):
    title: str
    doi: str
    authors: List[str]
    abstract: str
    full_text_url: str

@app.get("/fetch-article", response_model=ArticleResponse)
async def fetch_article(url: str = Query(..., description="URL of the PubMed article")):
    try:
        # Fetch the webpage
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch the article")

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract Title
        title_tag = soup.find("h1", class_="heading-title")
        title = title_tag.get_text(strip=True) if title_tag else "Title not available"

        # Extract DOI
        doi_tag = soup.find("span", class_="doi")
        doi = doi_tag.get_text(strip=True).replace("DOI:", "").strip() if doi_tag else "DOI not available"

        # Extract Authors
        authors_tag = soup.find_all("a", class_="full-name")
        authors = list(set([author.get_text(strip=True) for author in authors_tag])) if authors_tag else ["Authors not available"]

        # Extract Abstract
        abstract_tag = soup.find("div", class_="abstract")
        abstract_text = "Abstract not available"
        if abstract_tag:
            paragraphs = abstract_tag.find_all("p")
            abstract_text = " ".join([para.get_text(strip=True) for para in paragraphs]) if paragraphs else "Abstract not available"

        return ArticleResponse(
            title=title,
            doi=doi,
            authors=authors,
            abstract=abstract_text,
            full_text_url=url  # Use the provided URL as full_text_url
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
