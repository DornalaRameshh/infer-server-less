import requests
from bs4 import BeautifulSoup
import time

class FullArticle:
    def _init_(self, title, doi, authors, abstract, full_text_urls=None):
        self.title = title
        self.doi = doi
        self.authors = authors
        self.abstract = abstract
        self.full_text_urls = full_text_urls

    def _str_(self):
        return (
            f"Title: {self.title}\n"
            f"DOI: {self.doi}\n"
            f"Authors: {', '.join(self.authors)}\n"
            f"Abstract: {self.abstract}\n"
            f"Full Text URLs: {', '.join(self.full_text_urls) if self.full_text_urls else 'None'}"
        )

def parse_biorxiv(soup):
    def get_text_or_default(tag, default="Not available"):
        return tag.get_text(strip=True) if tag else default

    def get_meta_content(soup, meta_name, default="Not available"):
        tag = soup.find("meta", attrs={"name": meta_name})
        return tag["content"] if tag else default

    # Extract Title
    title = get_text_or_default(soup.find("h1", class_="highwire-cite-title"))

    # Extract DOI
    doi = get_meta_content(soup, "citation_doi")

    # Extract Authors
    authors_tag = soup.find_all("meta", attrs={"name": "citation_author"})
    authors = [author["content"] for author in authors_tag] if authors_tag else ["Authors not available"]

    # Extract Abstract
    abstract_tag = soup.find("div", class_="abstract")
    if abstract_tag:
        paragraphs = abstract_tag.find_all("p")
        abstract_content = " ".join([para.get_text(strip=True) for para in paragraphs]) if paragraphs else "Abstract not available"
    else:
        abstract_content = "Abstract not available"

    # Extract Full-Text URLs
    BASE_URL = "https://www.biorxiv.org"
    full_text_section = soup.find("ul", class_="tabs inline panels-ajax-tab")
    full_text_urls = [
        BASE_URL + link["href"]
        for link in full_text_section.find_all("a", href=True, class_="panels-ajax-tab-tab")
    ] if full_text_section else None

    return FullArticle(
        title=title,
        doi=doi,
        authors=authors,
        abstract=abstract_content,
        full_text_urls=full_text_urls
    )

def fetch_biorxiv_article(url):
    try:
        # Fetch the webpage
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        article = parse_biorxiv(soup)
        return article

    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
    except Exception as e:
        print(f"Internal server error: {str(e)}")

if _name_ == "_main_":
    url = input("Enter the bioRxiv article URL: ")
    
    # Start timing
    start_time = time.time()
    
    article = fetch_biorxiv_article(url)
    
    # End timing
    end_time = time.time()
    
    if article:
        print("\nExtracted Article Details:\n")
        print(article)
    
    print(f"\nExecution Time: {end_time - start_time:.2f} seconds")