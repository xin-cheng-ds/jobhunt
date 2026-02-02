"""
Search for Research Associate and Research Scientist jobs in Georgia
"""
from jobspy import scrape_jobs
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_url(row):
    """Check if the direct application URL returns a valid response."""
    direct_url = row.get('job_url_direct')
    
    result = {'index': row.name, 'status': None, 'url_to_use': None}
    
    if pd.isna(direct_url) or not direct_url:
        result['status'] = 'Missing Direct Link'
        return result

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        # Use GET with stream=True to be more reliable than HEAD for some ATS
        resp = requests.get(str(direct_url), headers=headers, timeout=10, stream=True)
        result['status'] = resp.status_code
        result['url_to_use'] = direct_url
    except Exception:
        result['status'] = 'Error'
    
    return result

# Search for research associate jobs
print("Searching for Research Associate jobs...")
research_associate = scrape_jobs(
    site_name=["indeed", "linkedin"],
    search_term="research associate",
    location="Georgia",
    results_wanted=20,
    hours_old=168,  # 7 days = 168 hours
    country_indeed='USA',
)

# Search for research scientist jobs
print("Searching for Research Scientist jobs...")
research_scientist = scrape_jobs(
    site_name=["indeed", "linkedin"],
    search_term="research scientist",
    location="Georgia",
    results_wanted=20,
    hours_old=168,  # 7 days = 168 hours
    country_indeed='USA',
)

# Combine results and remove duplicates
all_jobs = pd.concat([research_associate, research_scientist], ignore_index=True)
all_jobs = all_jobs.drop_duplicates(subset=['job_url'], keep='first')

# Run URL checks in parallel
print("Checking URLs (this may take a moment)...")

results = []
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(check_url, row): idx for idx, row in all_jobs.iterrows()}
    for future in as_completed(futures):
        results.append(future.result())

# Add results back to dataframe
if results:
    url_df = pd.DataFrame(results).set_index('index')
    all_jobs['url_status'] = url_df['status']
    all_jobs['best_url'] = url_df['url_to_use']

    # Filter for valid direct links only
    all_jobs = all_jobs[all_jobs['url_status'] == 200]
    print(f"✓ Found {len(all_jobs)} jobs with valid direct links")

print(f"\n{'='*80}")
print(f"Final Job List ({len(all_jobs)} items)")
print(f"{'='*80}\n")

# Display results
for idx, job in all_jobs.iterrows():
    print(f"{job['title']}")
    print(f"   Company: {job['company']}")
    print(f"   Location: {job['location']}")
    print(f"   Direct URL: {job['best_url']}")
    print()

# Save to CSV
all_jobs.to_csv("research_jobs_georgia.csv", index=False)
print(f"\nResults saved to research_jobs_georgia.csv")
