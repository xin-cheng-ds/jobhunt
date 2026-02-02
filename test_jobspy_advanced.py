"""
Advanced JobSpy examples showing different features
"""
from jobspy import scrape_jobs

# Example 1: Search single site with more filters
print("=" * 50)
print("Example 1: Indeed only with job type filter")
print("=" * 50)

jobs = scrape_jobs(
    site_name=["indeed"],
    search_term="data scientist",
    location="New York, NY",
    results_wanted=3,
    hours_old=48,
    country_indeed='USA',
    job_type="fulltime",  # fulltime, parttime, internship, contract
)

for idx, job in jobs.iterrows():
    print(f"\n{job['title']} at {job['company']}")
    print(f"  Location: {job['location']}")
    print(f"  URL: {job['job_url']}")

# Example 2: Remote jobs search
print("\n" + "=" * 50)
print("Example 2: Remote jobs")
print("=" * 50)

remote_jobs = scrape_jobs(
    site_name=["linkedin"],
    search_term="python developer",
    location="USA",
    results_wanted=3,
    is_remote=True,
)

for idx, job in remote_jobs.iterrows():
    print(f"\n{job['title']} at {job['company']}")
    print(f"  Location: {job.get('location', 'Remote')}")

# Example 3: Show all available columns
print("\n" + "=" * 50)
print("Example 3: Available data columns")
print("=" * 50)

if not jobs.empty:
    print("Columns available in job data:")
    for col in sorted(jobs.columns):
        print(f"  - {col}")
