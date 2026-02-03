from googlesearch import search
import pandas as pd
import logging
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def discover_ats_jobs(keyword, num_results=20):
    """
    Uses Google Dorks to find job postings directly on ATS subdomains.
    Queries:
      - site:boards.greenhouse.io "keyword"
      - site:jobs.lever.co "keyword"
      - site:jobs.ashbyhq.com "keyword"
    """
    
    ats_domains = [
        "site:boards.greenhouse.io",
        "site:jobs.lever.co",
        "site:jobs.ashbyhq.com"
    ]
    
    results = []
    
    for domain in ats_domains:
        query = f'{domain} "{keyword}"'
        logger.info(f"Searching Google for: {query}")
        
        try:
            # googlesearch-python yields URLs
            # pause to be polite to Google
            count = 0
            for url in search(query, num_results=10, advanced=True):
                # Advanced search returns objects with title and description
                # Note: 'googlesearch-python' search() with advanced=True returns SearchResult objects
                
                # Check if it's a valid job link (basic heuristic)
                if "greenhouse.io" in url.url or "lever.co" in url.url or "ashbyhq.com" in url.url:
                    
                    # Extract Company Name (approximate)
                    company = "Unknown"
                    try:
                        if "greenhouse.io" in url.url:
                            parts = url.url.split("boards.greenhouse.io/")
                            if len(parts) > 1:
                                company = parts[1].split("/")[0]
                        elif "lever.co" in url.url:
                            parts = url.url.split("jobs.lever.co/")
                            if len(parts) > 1:
                                company = parts[1].split("/")[0]
                        elif "ashbyhq.com" in url.url:
                             parts = url.url.split("jobs.ashbyhq.com/")
                             if len(parts) > 1:
                                company = parts[1].split("/")[0]
                    except:
                        pass

                    results.append({
                        'title': url.title, # Provided by advanced=True
                        'company': company.capitalize(),
                        'location': 'Check Listing', # Google snippet doesn't reliably give this
                        'job_url': url.url,
                        'source': 'ATS Discovery (Google)',
                        'description': url.description
                    })
                    count += 1
                    if count >= num_results:
                        break
                
            time.sleep(random.uniform(1, 3)) # Respect rate limits
            
        except Exception as e:
            logger.error(f"Error searching {domain}: {e}")

    return pd.DataFrame(results)

if __name__ == "__main__":
    # Test
    df = discover_ats_jobs("Research Scientist", num_results=5)
    print(df)
