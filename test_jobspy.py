"""
Simple JobSpy test script
"""
from jobspy import scrape_jobs
import pandas as pd

# Basic job search example
jobs = scrape_jobs(
    site_name=["indeed", "linkedin", "glassdoor"],
    search_term="software engineer",
    location="San Francisco, CA",
    results_wanted=5,  # Keep small for testing
    hours_old=72,  # Jobs posted in last 72 hours
    country_indeed='USA'
)

print(f"Found {len(jobs)} jobs\n")

# Display key columns
if not jobs.empty:
    display_cols = ['title', 'company', 'location', 'date_posted', 'job_url']
    available_cols = [col for col in display_cols if col in jobs.columns]
    print(jobs[available_cols].to_string())

    # Save to CSV
    jobs.to_csv("jobs_output.csv", index=False)
    print("\nResults saved to jobs_output.csv")
else:
    print("No jobs found.")
