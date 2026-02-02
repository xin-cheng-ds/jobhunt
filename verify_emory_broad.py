from jobspy import scrape_jobs
import pandas as pd

# Broad search: Using the Company Name as the search term
SEARCH_TERM = "Emory University"
LOCATION = "Atlanta, GA"
LIMIT = 50

print(f"--- STARTING BROAD COVERAGE TEST ---")
print(f"Search Term: '{SEARCH_TERM}' (To find ALL types of jobs)")
print(f"Location: {LOCATION}")
print(f"Timeframe: Last 7 days")
print(f"------------------------------------")

jobs = scrape_jobs(
    site_name=["indeed"],
    search_term=SEARCH_TERM,
    location=LOCATION,
    results_wanted=LIMIT,
    country_indeed='USA',
    hours_old=168,  # 7 days
)

# Filter to ensure the company name matches (removes accidental keyword matches)
if not jobs.empty:
    jobs = jobs[jobs['company'].str.contains("Emory", case=False, na=False)]

print(f"\n--- RESULTS ---")
print(f"Total Jobs Found: {len(jobs)}")

if len(jobs) > 0:
    print(f"\nSample of jobs found (showing diversity of roles):")
    print(jobs[['title', 'date_posted']].head(20).to_string(index=False))

    # Check for our specific interest within this broad set
    research_jobs = jobs[jobs['title'].str.contains("Research", case=False, na=False)]
    print(f"\n--- 'Research' Jobs within this set ---")
    print(f"Found: {len(research_jobs)}")
    if not research_jobs.empty:
        print(research_jobs[['title', 'date_posted']].to_string(index=False))
else:
    print("No jobs found. The scraper might be blocked or the search term is ineffective.")
