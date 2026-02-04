import yaml
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from jobspy import scrape_jobs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def load_config(config_path="companies.yaml"):
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def scrape_aggregator_companies(config_path="companies.yaml", hours_old=24):
    """
    Scrapes job aggregators (Indeed, LinkedIn, Glassdoor) for specific companies.
    """
    config = load_config(config_path)
    agg_list = config.get('aggregator_companies', [])
    all_jobs = []

    for company in agg_list:
        name = company.get('name')
        term = company.get('search_term', name)
        loc = company.get('location', 'USA')
        
        logger.info(f"Scanning aggregators for {name}...")
        try:
            # Scrape using JobSpy
            jobs = scrape_jobs(
                site_name=["indeed", "linkedin", "glassdoor"],
                search_term=term,
                location=loc,
                results_wanted=20,  # Grab enough to filter
                hours_old=hours_old,
                country_indeed='USA',
            )
            
            if not jobs.empty:
                # Filter: Ensure the company column loosely matches our target
                # This removes "Sales Rep selling TO Boehringer"
                name_lower = name.lower()
                company_matches = jobs[jobs['company'].apply(
                    lambda c: not pd.isna(c) and name_lower in c.lower()
                )].copy()

                # Add source metadata
                company_matches['source'] = 'Aggregator Monitor'
                company_matches['monitored_company'] = name
                
                all_jobs.append(company_matches)
                
        except Exception as e:
            logger.error(f"Error scraping aggregators for {name}: {e}")
            
    if all_jobs:
        return pd.concat(all_jobs, ignore_index=True)
    return pd.DataFrame()

def scrape_greenhouse(company_name, url):
    """Scrapes Greenhouse.io job boards (supports both HTML and new React/JSON structure)."""
    jobs = []
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code != 200:
            logger.error(f"Failed to fetch {url}: Status {response.status_code}")
            return jobs

        content = response.text
        
        # Strategy 1: JSON Extraction (New Greenhouse)
        if "window.__remixContext" in content:
            try:
                start_marker = "window.__remixContext ="
                start_index = content.find(start_marker)
                if start_index != -1:
                    json_start = start_index + len(start_marker)
                    remainder = content[json_start:]
                    end_index = remainder.find("</script>")
                    if end_index != -1:
                        json_str = remainder[:end_index].strip()
                        if json_str.endswith(';'):
                            json_str = json_str[:-1]
                        
                        data = json.loads(json_str)
                        loader_data = data.get('state', {}).get('loaderData', {})
                        
                        for key, value in loader_data.items():
                            if isinstance(value, dict) and 'jobPosts' in value:
                                posts = value['jobPosts'].get('data', [])
                                for post in posts:
                                    jobs.append({
                                        'company': company_name,
                                        'title': post.get('title'),
                                        'location': post.get('location'),
                                        'job_url': post.get('absolute_url'),
                                        'source': 'Greenhouse'
                                    })
                                if jobs:
                                    return jobs # Return immediately if JSON parsing worked
            except Exception as e:
                logger.warning(f"Greenhouse JSON parsing failed for {company_name}, falling back to HTML: {e}")

        # Strategy 2: Legacy HTML Parsing
        soup = BeautifulSoup(response.content, 'html.parser')
        openings = soup.find_all('div', class_='opening')
        
        for opening in openings:
            title_tag = opening.find('a')
            if not title_tag:
                continue
                
            title = title_tag.text.strip()
            link = title_tag['href']
            if not link.startswith('http'):
                link = f"https://boards.greenhouse.io{link}"
                
            location_tag = opening.find('span', class_='location')
            location = location_tag.text.strip() if location_tag else "Unknown"
            
            jobs.append({
                'company': company_name,
                'title': title,
                'location': location,
                'job_url': link,
                'source': 'Greenhouse'
            })
            
    except Exception as e:
        logger.error(f"Error scraping Greenhouse for {company_name}: {e}")
        
    return jobs

def scrape_lever(company_name, url):
    """Scrapes Lever.co job boards."""
    jobs = []
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code != 200:
            logger.error(f"Failed to fetch {url}: Status {response.status_code}")
            return jobs

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Lever usually lists jobs in a.posting-title or div.posting
        postings = soup.find_all('div', class_='posting')
        
        for posting in postings:
            title_tag = posting.find('h5')
            if not title_tag:
                continue 
            
            title = title_tag.text.strip()
            
            link_tag = posting.find('a', class_='posting-btn-submit')
            link = link_tag['href'] if link_tag else url
            
            # Sometimes the link is on the parent 'a' tag
            if not link or link == url:
                 parent_a = posting.find('a', class_='posting-title')
                 if parent_a:
                     link = parent_a['href']

            location_tag = posting.find('span', class_='sort-by-location')
            location = location_tag.text.strip() if location_tag else "Unknown"
            
            jobs.append({
                'company': company_name,
                'title': title,
                'location': location,
                'job_url': link,
                'source': 'Lever'
            })
            
    except Exception as e:
        logger.error(f"Error scraping Lever for {company_name}: {e}")
        
    return jobs

def scrape_ats_target(company, keyword_filter=None):
    """Helper to scrape a single ATS target and filter by keyword."""
    name = company.get('name')
    url = company.get('url')
    ctype = company.get('type', '').lower()
    
    found_jobs = []
    if ctype == 'greenhouse':
        found_jobs = scrape_greenhouse(name, url)
    elif ctype == 'lever':
        found_jobs = scrape_lever(name, url)
        
    if not found_jobs:
        return []

    # Filter by keyword if provided
    if keyword_filter:
        keywords = [k.strip().lower() for k in keyword_filter.split(',') if k.strip()]
        filtered = []
        for job in found_jobs:
            title_lower = job.get('title', '').lower()
            if any(k in title_lower for k in keywords):
                filtered.append(job)
        return filtered
    
    return found_jobs

def scrape_ats_companies(config_path="companies.yaml", keyword_filter=None):
    """
    Scrapes all companies in the 'ats_companies' list.
    Filters results by keyword_filter (comma separated string) if provided.
    """
    config = load_config(config_path)
    ats_list = config.get('ats_companies', [])
    all_jobs = []
    
    # Run in parallel for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_ats_target, company, keyword_filter): company['name'] for company in ats_list}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                all_jobs.extend(result)
            except Exception as e:
                logger.error(f"Error in thread: {e}")
                
    return pd.DataFrame(all_jobs)

def extract_ats_identifier(job_url):
    """
    Analyzes a job URL to see if it belongs to a supported ATS.
    Returns (company_name, board_url, type) or None.
    Handles various Greenhouse and Lever URL formats.
    """
    if not job_url:
        return None
        
    url_lower = job_url.lower()
    
    # --- Strategy 1: Fast String Matching (No Network) ---
    try:
        # 1. Greenhouse Detection
        if "greenhouse.io" in url_lower:
            # Matches: boards.greenhouse.io/<token>, job-boards.greenhouse.io/<token>, etc.
            # Handle possible trailing slashes or subpaths
            parts = job_url.split("greenhouse.io/")
            if len(parts) > 1:
                subpath = parts[1].lstrip('/')
                if subpath:
                    token = subpath.split("/")[0].split("?")[0]
                    # Choose domain based on what was found
                    domain = "job-boards.greenhouse.io" if "job-boards" in url_lower else "boards.greenhouse.io"
                    return (token, f"https://{domain}/{token}", "greenhouse")

        # 2. Lever Detection
        elif "lever.co" in url_lower:
            # Matches: jobs.lever.co/<token>, etc.
            parts = job_url.split("lever.co/")
            if len(parts) > 1:
                subpath = parts[1].lstrip('/')
                if subpath:
                    token = subpath.split("/")[0].split("?")[0]
                    # Lever usually uses jobs.lever.co
                    return (token, f"https://jobs.lever.co/{token}", "lever")
                
    except Exception as e:
        logger.error(f"Error parsing URL {job_url}: {e}")

    # --- Strategy 2: Content Scanning (Network Fetch) ---
    # Only try this if Strategy 1 failed and it looks like a corporate site (http)
    if job_url.startswith("http"):
        try:
            # Fast timeout, don't hang on this
            response = requests.get(job_url, headers=DEFAULT_HEADERS, timeout=5)
            if response.status_code == 200:
                content = response.text
                
                # Regex for embedded Greenhouse links
                # patterns: boards.greenhouse.io/token, greenhouse.io/embed/job_board?for=token
                # Look for token in standard greenhouse URLs
                gh_match = re.search(r'greenhouse\.io/(?:embed/)?(?:boards/)?([a-zA-Z0-9_]+)', content)
                if gh_match:
                    token = gh_match.group(1)
                    # Filter out common technical keywords that might match regex but aren't tokens
                    if token not in ['api', 'embed', 'v1', 'js']:
                         return (token, f"https://boards.greenhouse.io/{token}", "greenhouse")

                # Regex for embedded Lever links
                # patterns: jobs.lever.co/token
                lv_match = re.search(r'jobs\.lever\.co/([a-zA-Z0-9_]+)', content)
                if lv_match:
                    token = lv_match.group(1)
                    return (token, f"https://jobs.lever.co/{token}", "lever")

        except Exception as e:
             # Log but don't break the app flow
            logger.debug(f"Content scan failed for {job_url}: {e}")
        
    return None

def discover_ats_by_name(company_name):
    """
    Tries to guess the ATS URL based on the company name.
    Useful when the job link is opaque (e.g., LinkedIn).
    """
    if not company_name:
        return None
        
    # Variant 1: Full name (just alphanumeric) - catches 'eikontherapeutics'
    token_full = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
    
    # Variant 2: Short name (strip suffixes) - catches 'stripe' from 'Stripe, Inc.'
    clean_name = re.sub(r',?\s*(Inc\.?|LLC|Corp\.?|Ltd\.?|Therapeutics|Group|Holdings|Technologies)\b', '', company_name, flags=re.IGNORECASE)
    token_short = re.sub(r'[^a-zA-Z0-9]', '', clean_name).lower()

    tokens_to_try = [token_full]
    if token_short != token_full and len(token_short) > 2:
        tokens_to_try.append(token_short)
        
    candidates = []
    for t in tokens_to_try:
        candidates.append((f"https://boards.greenhouse.io/{t}", "greenhouse"))
        candidates.append((f"https://job-boards.greenhouse.io/{t}", "greenhouse"))
        candidates.append((f"https://jobs.lever.co/{t}", "lever"))

    for url, ats_type in candidates:
        try:
            # fast head check
            response = requests.head(url, headers=DEFAULT_HEADERS, timeout=2, allow_redirects=True)
            if response.status_code == 200:
                # Double check content type to ensure it's not a generic error page
                ct = response.headers.get('Content-Type', '').lower()
                if 'text/html' in ct:
                    # Return the token that worked
                    valid_token = url.split('/')[-1]
                    return (valid_token, url, ats_type)
        except Exception:
            continue
            
    return None

def auto_add_companies(search_results_df):
    """
    Scans search results for new ATS companies and adds them to companies.yaml.
    """
    if search_results_df.empty:
        return 0
    
    config = load_config()
    current_ats = config.get('ats_companies', [])
    
    # Safely handle the case where 'ats_companies' is None
    if current_ats is None:
        current_ats = []
        config['ats_companies'] = []

    # Create a set of existing URLs/Names to avoid duplicates
    existing_urls = {c.get('url', '').lower().rstrip('/') for c in current_ats if c.get('url')}
    existing_names = {c.get('name', '').lower() for c in current_ats if c.get('name')}
    
    new_entries = []
    
    # Iterate through rows to get both URL and Company Name
    for _, row in search_results_df.iterrows():
        job_url = str(row.get('job_url', ''))
        company_name = str(row.get('company', ''))
        
        extracted = None
        
        # 1. Try URL extraction first
        if job_url:
            extracted = extract_ats_identifier(job_url)
            
        # 2. Fallback: Try Company Name guessing if URL failed and we haven't seen this company
        if not extracted and company_name and company_name.lower() not in existing_names:
             extracted = discover_ats_by_name(company_name)
        
        if extracted:
            token, board_url, ats_type = extracted
            
            if board_url.lower() not in existing_urls:
                new_entry = {
                    'name': token.capitalize(), # Use token as name for consistency
                    'url': board_url,
                    'type': ats_type
                }
                
                # Double check name existence again (case insensitive)
                if new_entry['name'].lower() not in existing_names:
                    new_entries.append(new_entry)
                    existing_urls.add(board_url)
                    existing_names.add(new_entry['name'].lower())
                    logger.info(f"Auto-discovered: {new_entry['name']} ({board_url})")
    
    if new_entries:
        logger.info(f"Adding {len(new_entries)} new companies to config.")
        config['ats_companies'].extend(new_entries)
        
        with open("companies.yaml", "w") as f:
            yaml.dump(config, f, sort_keys=False)
            
    return len(new_entries)