from jobspy import scrape_jobs
import pandas as pd

# 1. Define a specific, verifiable target
SITE = "indeed"
COMPANY = "Emory University"
SEARCH_TERM = "Research Scientist"
LOCATION = "Atlanta, GA"
# Set this higher than the expected number of jobs to test "saturation"
LIMIT = 100 

print(f"--- STARTING COVERAGE TEST ---")
print(f"Target: {SEARCH_TERM} at {COMPANY} in {LOCATION}")
print(f"Limit set to: {LIMIT} (We want to see fewer than this to confirm we got everything)")
print(f"------------------------------")

jobs = scrape_jobs(
    site_name=[SITE],
    search_term=f'"{SEARCH_TERM}"', # Use quotes for exact phrase match
    location=LOCATION,
    results_wanted=LIMIT,
    country_indeed='USA',
    hours_old=168, # Last 7 days
)

# Filter explicitly for the company to ensure clean comparison
# (Sometimes fuzzy matching returns other companies)
if not jobs.empty:
    jobs = jobs[jobs['company'].str.contains(COMPANY, case=False, na=False)]

print(f"\n--- RESULTS ---")
print(f"Jobs Found: {len(jobs)}")

if len(jobs) == LIMIT:
    print(f"⚠️  WARNING: We hit the limit of {LIMIT}. There are likely more jobs available.")
    print(f"   Action: Increase 'results_wanted' in your main script.")
elif len(jobs) == 0:
    print(f"⚠️  WARNING: Found 0 jobs. Either none exist, or the scraper is being blocked.")
else:
    print(f"✅ SUCCESS: Found {len(jobs)} jobs (below the limit of {LIMIT}).")
    print(f"   This indicates we likely scraped ALL available jobs for this specific query.")

print(f"\n--- TITLES FOUND ---")
print(jobs[['title', 'date_posted']].to_string(index=False))

print(f"\n------------------------------")
print(f"TO VERIFY MANUALLY:")
print(f"1. Go to https://www.indeed.com")
print(f"2. Search 'what': \"{SEARCH_TERM}\"")
print(f"3. Search 'where': {LOCATION}")
print(f"4. Filter by Company: {COMPANY}")
print(f"5. Filter by Date: Last 7 days")
print(f"6. Compare the total count with {len(jobs)}")
