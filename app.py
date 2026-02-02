import streamlit as st
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
        
        # Check for soft 404s (redirects to error pages)
        final_url_lower = resp.url.lower()
        error_keywords = ['error', 'expired', 'notfound', 'job-closed', 'job_closed']
        
        if any(keyword in final_url_lower for keyword in error_keywords):
            result['status'] = 'Job Unavailable (Redirected)'
            result['url_to_use'] = resp.url
        elif resp.status_code == 200:
            result['status'] = '200 OK'
            result['url_to_use'] = resp.url
        else:
            result['status'] = f"Status {resp.status_code}"
            result['url_to_use'] = resp.url
            
    except Exception as e:
        result['status'] = 'Error'
    
    return result

st.set_page_config(page_title="Job Hunt", page_icon="🎯", layout="wide")

st.title("🎯 Job Hunt")
st.markdown("Aggregated job search across Indeed, LinkedIn, Glassdoor, and more.")

# Sidebar Configuration
st.sidebar.header("Search Parameters")

search_term = st.sidebar.text_input(
    "Job Title / Keywords", 
    value="research scientist",
    help="Enter multiple job titles separated by commas (e.g., 'Software Engineer, Data Scientist'). logic: (Term A) OR (Term B)."
)
location = st.sidebar.text_input("Location", value="Georgia")

site_options = ["indeed", "linkedin", "glassdoor", "ziprecruiter"]
sites = st.sidebar.multiselect("Sites to Scrape", options=site_options, default=["indeed", "linkedin"])

max_results = st.sidebar.number_input("Max Results (per site)", min_value=1, max_value=1000, value=20)

days_old = st.sidebar.number_input("Days Old", min_value=1, max_value=30, value=7)
hours_old = days_old * 24

job_type_options = ["fulltime", "parttime", "contract", "internship", "temporary"]
job_types = st.sidebar.multiselect("Job Type", options=job_type_options, default=[])

is_remote = st.sidebar.checkbox("Remote Only", value=False)

st.sidebar.markdown("---")
verify_links = st.sidebar.checkbox("Verify Direct Links", value=False, help="Check if the direct application links are valid (takes longer).")

# Main Search Logic
if st.button("Search Jobs", type="primary"):
    if not sites:
        st.error("Please select at least one site to scrape.")
    else:
        with st.spinner(f"Searching for '{search_term}' in '{location}'..."):
            try:
                # Handle Multiple Search Terms (split by comma)
                search_terms = [t.strip() for t in search_term.split(',') if t.strip()]
                if not search_terms:
                    search_terms = [""] # Fallback if empty

                combined_results = []
                
                # Progress container
                status_text = st.empty()
                
                for term in search_terms:
                    # Handle Job Type Multi-select (Nested Loop)
                    if not job_types:
                        # Search for Term + Any Job Type
                        status_text.text(f"Searching for '{term}'...")
                        try:
                            result = scrape_jobs(
                                site_name=sites,
                                search_term=term,
                                location=location,
                                results_wanted=max_results,
                                hours_old=hours_old,
                                job_type=None,
                                is_remote=is_remote,
                                country_indeed='USA',
                            )
                            combined_results.append(result)
                        except Exception as inner_e:
                            st.warning(f"Error scraping for term '{term}': {inner_e}")
                    else:
                        # Search for Term + Specific Job Types
                        for j_type in job_types:
                            status_text.text(f"Searching for '{term}' ({j_type})...")
                            try:
                                result = scrape_jobs(
                                    site_name=sites,
                                    search_term=term,
                                    location=location,
                                    results_wanted=max_results,
                                    hours_old=hours_old,
                                    job_type=j_type,
                                    is_remote=is_remote,
                                    country_indeed='USA',
                                )
                                combined_results.append(result)
                            except Exception as inner_e:
                                st.warning(f"Error scraping for term '{term}' / type '{j_type}': {inner_e}")
                
                status_text.empty() # Clear status
                
                if combined_results:
                    jobs = pd.concat(combined_results, ignore_index=True)
                    # Remove duplicates that might appear (e.g. same job found in both searches)
                    jobs = jobs.drop_duplicates(subset=['job_url'], keep='first')
                else:
                    jobs = pd.DataFrame()

                if jobs.empty:
                    st.warning("No jobs found with the current parameters.")
                else:
                    st.success(f"Found {len(jobs)} jobs!")
                    
                    # Optional Link Verification
                    if verify_links:
                        st.info("Verifying links... this may take a moment.")
                        progress_bar = st.progress(0)
                        results = []
                        total_jobs = len(jobs)
                        
                        # Reset index to ensure it matches
                        jobs = jobs.reset_index(drop=True)
                        
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            futures = {executor.submit(check_url, row): idx for idx, row in jobs.iterrows()}
                            completed_count = 0
                            
                            for future in as_completed(futures):
                                results.append(future.result())
                                completed_count += 1
                                progress_bar.progress(completed_count / total_jobs)
                        
                        if results:
                            url_df = pd.DataFrame(results).set_index('index')
                            jobs['url_status'] = url_df['status']
                            jobs['best_url'] = url_df['url_to_use']
                    
                    # Display Results
                    display_cols = [
                        'title', 'company', 'location', 'date_posted', 'job_type', 
                        'interval', 'min_amount', 'max_amount', 'is_remote', 
                        'emails', 'site', 'job_url'
                    ]
                    
                    # Add Direct URL column - prefer verified one if available
                    if 'best_url' in jobs.columns:
                        display_cols.append('best_url')
                        url_col_name = 'best_url'
                    else:
                        display_cols.append('job_url_direct')
                        url_col_name = 'job_url_direct'

                    # Add url_status if verification was performed
                    if verify_links and 'url_status' in jobs.columns:
                        display_cols.append('url_status')
                    
                    # Ensure columns exist before selecting
                    existing_cols = [c for c in display_cols if c in jobs.columns]
                    
                    st.dataframe(
                        jobs[existing_cols],
                        column_config={
                            url_col_name: st.column_config.LinkColumn("Direct URL"),
                            "job_url": st.column_config.LinkColumn("Board Link", display_text="View Posting"),
                            "emails": st.column_config.TextColumn("Emails"),
                            "url_status": st.column_config.TextColumn("URL Status"),
                        },
                        use_container_width=True
                    )
                    
                    # CSV Download
                    csv = jobs.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Results as CSV",
                        data=csv,
                        file_name='job_search_results.csv',
                        mime='text/csv',
                    )
                    
            except Exception as e:
                st.error(f"An error occurred during scraping: {e}")
