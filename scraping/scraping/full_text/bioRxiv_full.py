import json
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

def extract_content_from_biorxiv(url: str) -> Dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.RequestException:
        return {"status": "error", "detail": "Error making request to the URL"}

    if response.status_code != 200:
        return {"status": "error", "detail": "Failed to fetch the URL"}

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        content_blocks: List[Dict] = []

        # Extract title
        title = soup.find('h1', {'class': 'highwire-cite-title'}).get_text(strip=True) if soup.find('h1', {'class': 'highwire-cite-title'}) else "No Title Found"
        if title:
            content_blocks.append({'type': 'title', 'content': title})

         # Extract DOI
        doi_tag = soup.find('span', {'class': 'highwire-cite-metadata-doi'})
        doi = doi_tag.get_text(strip=True).replace("doi:", "").strip() if doi_tag else "No DOI Found"
        if doi:
            content_blocks.append({'type': 'doi', 'content': doi})

        # Extract citation (excluding title)
        citation_tag = soup.find('div', {'class': 'highwire-citation-info'})
        citation_text = ""

        if citation_tag:
            citation_parts = [part.get_text(strip=True) for part in citation_tag.find_all(recursive=False)]
            citation_text = " ".join(citation_parts).strip()
            if title in citation_text:
                citation_text = citation_text.replace(title, "").strip()
            
            # Ensure newline before bioRxiv reference
            citation_text = citation_text.replace("bioRxiv", "\nbioRxiv")

        if citation_text:
            content_blocks.append({'type': 'citation', 'content': citation_text})


        # Extract main article content from full text
        full_text_section = soup.find('div', {'class': 'article fulltext-view'})
        if full_text_section:
            last_captions = set()
            for section in full_text_section.find_all(['h2', 'h3', 'p', 'figure', 'table', 'span']):
                if section.name == 'h2':
                    heading_text = section.get_text(strip=True)
                    if heading_text:
                        content_blocks.append({'type': 'heading', 'content': heading_text})

                elif section.name == 'h3':
                    subheading_text = section.get_text(strip=True)
                    if subheading_text:
                        content_blocks.append({'type': 'subheading', 'content': subheading_text})

                elif section.name == 'p':
                    paragraph_text = section.get_text(strip=True)
                    if paragraph_text:
                        content_blocks.append({'type': 'text', 'content': paragraph_text})

                elif section.name in ['figure', 'span']:
                    img_tag = section.find('img', {'class': 'highwire-fragment fragment-image'})
                    heading_text = ""
                    if img_tag and 'alt' in img_tag.attrs:
                        heading_text = img_tag['alt']
                    if img_tag and 'src' in img_tag.attrs:
                        img_url = img_tag['src']
                        if img_url.startswith("/"):
                            img_url = f"https://www.medrxiv.org{img_url}"
                        download_url = f"{img_url}?download=true"

                        caption_title_tag = section.find('span', {'class': 'caption-title'})
                        if not caption_title_tag:
                            caption_title_tag = section.find_next('span', {'class': 'caption-title'})
                        caption_title = caption_title_tag.get_text(strip=True) if caption_title_tag else None
                        image_content = {"url": img_url, "caption": heading_text, "downloads": download_url}

                        if caption_title:
                            image_content["caption-title"] = caption_title
                        content_blocks.append({'type': 'image', 'content': image_content})

                elif section.name == 'table':
                    table_label = ""
                    caption_title = ""
                    table_caption_div = section.find_previous('div', {'class': 'table-caption'})
                    if table_caption_div:
                        table_label_tag = table_caption_div.find('span', {'class': 'table-label'})
                        table_label = table_label_tag.get_text(strip=True) if table_label_tag else ""
                        caption_title_tag = table_caption_div.find('span', {'class': 'caption-title'})
                        caption_title = caption_title_tag.get_text(strip=True) if caption_title_tag else ""
                    if table_label or caption_title:
                        heading_text = f"{table_label} {caption_title}".strip()
                        content_blocks.append({'type': 'table-caption', 'content': heading_text})


        # Assuming `soup` is your BeautifulSoup object
        references_section = soup.find('ol', {'class': 'cit-list'})
        references = []

        if references_section:
            for idx, ref_item in enumerate(references_section.find_all('li')):
                citation_text = ref_item.get_text(strip=True)[4:]  # Trim the first 4 characters

                links = []
                google_scholar_url = None

                for link in ref_item.find_all('a', href=True):
                    # Exclude hidden links with `display: none`
                    if link.has_attr('style') and "display:none" in link['style']:
                        continue

                    link_text = link.get_text(strip=True)
                    link_url = link['href']

                    # Construct full URL if needed
                    full_url = f"https://www.medrxiv.org{link_url}" if not link_url.startswith("http") else link_url

                    # Skip unwanted links like "↵" and "OpenUrl"
                    if link_text in ["↵", "OpenUrl"]:
                        continue

                    # Identify Google Scholar links dynamically
                    if "google-scholar" in link_url.lower() or "gs_type=article" in link_url.lower():
                        google_scholar_url = full_url
                    else:
                        links.append({"source": link_text, "url": full_url})

                # If Google Scholar link was found, add it separately
                if google_scholar_url:
                    links.append({"source": "Google Scholar", "url": google_scholar_url})

                # Store the reference details
                reference_entry = {"id": f"ref{idx}", "citation": citation_text}
                if links:
                    reference_entry["links"] = links
                references.append(reference_entry)

        # Add references to content_blocks if they exist
        if references:
            content_blocks.append({"type": "references", "content": references})





        return  content_blocks

    except Exception as e:
        return {"status": "error", "detail": "Error processing content"}



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
            return {"statusCode": 400, "headers":HEADERS, 'body': json.dumps({"status": "error", "detail": "URL query parameter is required"})}

        result = extract_content_from_biorxiv(url)

        return {"statusCode": 200, "headers":HEADERS,'body': result}
    except Exception as e:
        return {"statusCode": 500, "headers":HEADERS, 'body': json.dumps({"status": "error", "detail": str(e)})}
