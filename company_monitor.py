import yaml
import pandas as pd
import logging
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

def scrape_aggregator_companies(config_path="companies.yaml", sites=None,
                                location="USA", hours_old=24,
                                results_wanted=20, job_type=None,
                                is_remote=False):
    """
    Scrapes job aggregators for specific companies defined in config.
    Search parameters (sites, location, etc.) come from the shared sidebar.
    Keywords are per-company from the config.
    """
    if sites is None:
        sites = ["indeed", "linkedin", "glassdoor"]
    config = load_config(config_path)
    agg_list = config.get('aggregator_companies', [])
    all_jobs = []

    for company in agg_list:
        name = company.get('name')
        keywords = company.get('keywords', [])

        logger.info(f"Scanning aggregators for {name}...")
        try:
            # Scrape using JobSpy, use company name as the search query
            jobs = scrape_jobs(
                site_name=sites,
                search_term=name,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                job_type=job_type,
                is_remote=is_remote,
                country_indeed='USA',
            )

            if not jobs.empty:
                # Filter: Ensure the company column loosely matches our target
                # This removes "Sales Rep selling TO Boehringer"
                name_lower = name.lower()
                company_matches = jobs[jobs['company'].apply(
                    lambda c: not pd.isna(c) and name_lower in c.lower()
                )].copy()

                # Filter by keywords if provided
                if keywords:
                    kw_lower = [k.lower() for k in keywords]
                    company_matches = company_matches[company_matches['title'].apply(
                        lambda t: not pd.isna(t) and any(k in t.lower() for k in kw_lower)
                    )]

                # Add source metadata
                company_matches['source'] = 'Aggregator Monitor'
                company_matches['monitored_company'] = name

                all_jobs.append(company_matches)
                
        except Exception as e:
            logger.error(f"Error scraping aggregators for {name}: {e}")
            
    if all_jobs:
        return pd.concat(all_jobs, ignore_index=True)
    return pd.DataFrame()