from jobspy import scrape_jobs
import pandas as pd

def test_multiple_search_terms():
    # Simulate the input from Streamlit
    search_input = "python developer, data scientist"
    location = "Georgia"
    
    # 1. Split the terms (Logic from app.py)
    search_terms = [t.strip() for t in search_input.split(',') if t.strip()]
    print(f"Testing search terms: {search_terms}")
    
    combined_results = []
    
    # 2. Run the loop (Logic from app.py)
    for term in search_terms:
        print(f"Scraping for: '{term}'...")
        try:
            # limiting results to 3 to be fast
            result = scrape_jobs(
                site_name=["indeed"],
                search_term=term,
                location=location,
                results_wanted=3, 
                country_indeed='USA'
            )
            print(f"  -> Found {len(result)} jobs for '{term}'")
            combined_results.append(result)
        except Exception as e:
            print(f"  -> Error: {e}")

    # 3. Combine and Deduplicate
    if combined_results:
        jobs = pd.concat(combined_results, ignore_index=True)
        initial_count = len(jobs)
        jobs = jobs.drop_duplicates(subset=['job_url'], keep='first')
        final_count = len(jobs)
        
        print(f"\nTotal jobs found: {initial_count}")
        print(f"After deduplication: {final_count}")
        
        # Verify we have mixed results
        print("\nSample Titles:")
        print(jobs['title'].head(10))
    else:
        print("No jobs found.")

if __name__ == "__main__":
    test_multiple_search_terms()
