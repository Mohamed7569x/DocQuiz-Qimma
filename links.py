import requests
from bs4 import BeautifulSoup
import json

URL = "https://www.w3schools.com/python/"

def scrape_links(url):
    print(f"Scraping: {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for a in soup.find_all("a", href=True, target="_top"):
        title = a.get_text(strip=True)
        href = a["href"]

        # skip empty titles
        if title:
            results.append({
                "title": title,
                "href": href
            })

    return results


if __name__ == "__main__":
    data = scrape_links(URL)

    with open("links.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Done! Saved {len(data)} links to links.json")
