from jobspy import scrape_jobs
import pandas as pd

# Test 1: Passing a comma separated string
print("--- Test 1: Comma separated string 'research scientist, software engineer' ---")
try:
    jobs = scrape_jobs(
        site_name=["indeed"],
        search_term="research scientist, software engineer",
        location="Georgia",
        results_wanted=5,
        country_indeed='USA'
    )
    print(f"Found {len(jobs)} jobs")
    if not jobs.empty:
        print(jobs['title'].head())
except Exception as e:
    print(f"Error: {e}")

# Test 2: Passing a list (checking if supported)
print("\n--- Test 2: Passing a list ['research scientist', 'software engineer'] ---")
try:
    jobs = scrape_jobs(
        site_name=["indeed"],
        search_term=["research scientist", "software engineer"],
        location="Georgia",
        results_wanted=5,
        country_indeed='USA'
    )
    print(f"Found {len(jobs)} jobs")
except Exception as e:
    print(f"Error: {e}")
