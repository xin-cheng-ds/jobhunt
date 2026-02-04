import streamlit as st
from jobspy import scrape_jobs
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import company_monitor

def check_url(row):
    """Check if the direct application URL returns a valid response."""
    direct_url = row.get('job_url') # We check the main URL now
    
    result = {'index': row.name, 'status': None, 'url_to_use': None}
    
    if pd.isna(direct_url) or not direct_url:
        result['status'] = 'Missing Link'
        return result

    headers = company_monitor.DEFAULT_HEADERS
    
    try:
        # Use GET with stream=True to be more reliable than HEAD for some ATS
        resp = requests.get(str(direct_url), headers=headers, timeout=10, stream=True)
        
        # Check for soft 404s (redirects to error pages)
        final_url_lower = resp.url.lower()
        error_keywords = ['error', 'expired', 'notfound', 'job-closed', 'job_closed']
        
        if any(keyword in final_url_lower for keyword in error_keywords):
            result['status'] = 'Unavailable (Redirected)'
            result['url_to_use'] = resp.url
        elif resp.status_code == 200:
            result['status'] = '200 OK'
            result['url_to_use'] = resp.url
        else:
            result['status'] = f"Status {resp.status_code}"
            result['url_to_use'] = resp.url
            
    except Exception:
        result['status'] = 'Error'
    
    return result

st.set_page_config(page_title="Job Hunt", page_icon="🎯", layout="wide")

st.title("🎯 Job Hunt")

# Create Tabs
tab1, tab2 = st.tabs(["Global Search", "Dream Company Watchlist"])

with tab1:
    st.markdown("Search **Indeed, LinkedIn, Glassdoor** AND your **ATS Targets** (Greenhouse/Lever) simultaneously.")

    # Sidebar Configuration (Global Search specific)
    with st.sidebar:
        st.header("Search Parameters")
        search_term = st.text_input(
            "Job Title / Keywords", 
            value="research scientist",
            help="Enter multiple job titles separated by commas."
        )
        location = st.text_input("Location", value="Georgia")

        site_options = ["indeed", "linkedin", "glassdoor", "ziprecruiter"]
        sites = st.multiselect("Sites to Scrape", options=site_options, default=["indeed", "linkedin"])

        max_results = st.number_input("Max Results (per site)", min_value=1, max_value=1000, value=20)

        days_old = st.number_input("Days Old", min_value=1, max_value=30, value=7)
        hours_old = days_old * 24

        job_type_options = ["fulltime", "parttime", "contract", "internship", "temporary"]
        job_types = st.multiselect("Job Type", options=job_type_options, default=[])

        is_remote = st.checkbox("Remote Only", value=False)
        st.markdown("---")
        include_ats = st.checkbox("Include ATS Targets", value=True, help="Also search companies listed in 'ats_companies' in companies.yaml")
        auto_add = st.checkbox("Auto-Add New Companies", value=True, help="Automatically add any Greenhouse/Lever companies found in search results to your monitoring list.")
        verify_links = st.checkbox("Verify Links", value=False, help="Check if the links are still valid (takes longer).")

    # Main Search Logic
    if st.button("Search Jobs", type="primary", key="global_search_btn"):
        if not sites:
            st.error("Please select at least one site to scrape.")
        else:
            with st.spinner(f"Searching for '{search_term}'..."):
                try:
                    search_terms = [t.strip() for t in search_term.split(',') if t.strip()]
                    if not search_terms:
                        search_terms = [""] 

                    combined_results = []
                    status_text = st.empty()
                    
                    # 1. JobSpy Search
                    job_type_list = job_types if job_types else [None]
                    for term in search_terms:
                        for j_type in job_type_list:
                            label = f"'{term}'" + (f" ({j_type})" if j_type else "")
                            status_text.text(f"Scraping Job Boards for {label}...")
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
                                st.warning(f"JobSpy error for {label}: {inner_e}")
                    
                    # 2. ATS Direct Search
                    if include_ats:
                        status_text.text("Scanning ATS Targets (Greenhouse/Lever)...")
                        try:
                            ats_results = company_monitor.scrape_ats_companies(keyword_filter=search_term)
                            if not ats_results.empty:
                                combined_results.append(ats_results)
                        except Exception as e:
                            st.warning(f"ATS Search Error: {e}")

                    status_text.empty()
                    
                    if combined_results:
                        jobs = pd.concat(combined_results, ignore_index=True)
                        jobs = jobs.drop_duplicates(subset=['job_url'], keep='first')
                    else:
                        jobs = pd.DataFrame()

                    if jobs.empty:
                        st.warning("No jobs found with the current parameters.")
                    else:
                        st.success(f"Found {len(jobs)} jobs!")
                        
                        # 4. Optional Link Verification
                        if verify_links:
                            st.info("Verifying links... this may take a moment.")
                            progress_bar = st.progress(0)
                            results = []
                            total_jobs = len(jobs)
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
                                jobs['best_url'] = url_df['url_to_use'] # Store the real URL

                        # 3. Auto-Discovery Logic (moved after verification to use better URLs)
                        if auto_add:
                            # Use the verified 'best_url' if available, otherwise fallback to 'job_url'
                            # We create a temporary column to feed the detector
                            jobs_for_discovery = jobs.copy()
                            if 'best_url' in jobs_for_discovery.columns:
                                # Prioritize best_url, fill missing with job_url
                                jobs_for_discovery['job_url'] = jobs_for_discovery['best_url'].fillna(jobs_for_discovery['job_url'])
                            
                            new_count = company_monitor.auto_add_companies(jobs_for_discovery)
                            if new_count > 0:
                                st.toast(f"✨ Auto-discovered {new_count} new ATS companies for your watchlist!", icon="🚀")

                        display_cols = [
                            'title', 'company', 'location', 'date_posted', 'job_type', 
                            'interval', 'min_amount', 'max_amount', 'is_remote', 
                            'emails', 'site', 'job_url', 'source'
                        ]
                        
                        if verify_links and 'url_status' in jobs.columns:
                            display_cols.append('url_status')
                            if 'best_url' in jobs.columns:
                                display_cols.append('best_url') # Show the direct link column if we have it
                        
                        # Add 'source' col if not present
                        if 'source' not in jobs.columns:
                            jobs['source'] = 'Job Board'

                        existing_cols = [c for c in display_cols if c in jobs.columns]
                        
                        st.dataframe(
                            jobs[existing_cols],
                            column_config={
                                "job_url": st.column_config.LinkColumn("Apply Link", display_text="View Posting"),
                            },
                            use_container_width=True
                        )
                        
                        csv = jobs.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Results as CSV",
                            data=csv,
                            file_name='job_search_results.csv',
                            mime='text/csv',
                        )
                except Exception as e:
                    st.error(f"An error occurred: {e}")

with tab2:
    st.header("Dream Company Watchlist")
    
    # Load config first for all sections
    config = company_monitor.load_config()
    if not config:
        st.error("Could not load companies.yaml")

    # --- New Aggregator Monitor Section ---
    st.divider()
    st.subheader("Active Company Monitoring (via Indeed/LinkedIn/Glassdoor)")
    st.markdown("Use this to watch companies that don't have public ATS boards (e.g., Boehringer Ingelheim). We search job aggregators by company name. Use keywords to filter results to relevant roles.")
    
    # Display current monitored list as an editable table
    agg_companies = config.get('aggregator_companies', [])

    if not agg_companies:
        st.info("No companies configured. Add one below!")

    df_agg = pd.DataFrame(agg_companies) if agg_companies else pd.DataFrame(columns=["name", "location", "keywords"])
    # Drop legacy search_term column if present
    if 'search_term' in df_agg.columns:
        df_agg = df_agg.drop(columns=['search_term'])
    if 'keywords' in df_agg.columns and not df_agg.empty:
        df_agg['keywords'] = df_agg['keywords'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
    else:
        df_agg['keywords'] = ""

    edited_df = st.data_editor(
        df_agg,
        column_config={
            "name": "Company Name",
            "location": "Location",
            "keywords": "Filter Keywords (comma sep)"
        },
        use_container_width=True,
        num_rows="dynamic",
        key="agg_editor"
    )

    if st.button("Save Changes", type="primary", key="save_agg_changes"):
        cleaned_companies = []
        for _, row in edited_df.iterrows():
            if row['name']:
                keywords_list = [k.strip() for k in str(row['keywords']).split(',') if k.strip()]
                cleaned_companies.append({
                    "name": row['name'],
                    "location": row['location'],
                    "keywords": keywords_list
                })

        config['aggregator_companies'] = cleaned_companies
        with open("companies.yaml", "w") as f:
            yaml.dump(config, f, sort_keys=False)

        st.toast("Watchlist updated successfully!", icon="💾")
        st.rerun()


    if st.button("Scan Aggregators Now", type="secondary", key="agg_monitor_btn"):
        with st.spinner("Scanning aggregators for target companies..."):
            try:
                agg_jobs = company_monitor.scrape_aggregator_companies()
                
                if agg_jobs.empty:
                    st.info("No new jobs found for these companies in the last 24h.")
                else:
                    st.success(f"Found {len(agg_jobs)} recent jobs!")
                    st.dataframe(
                        agg_jobs[['title', 'company', 'location', 'date_posted', 'job_url', 'site']],
                        column_config={
                            "job_url": st.column_config.LinkColumn("Apply Link", display_text="View Posting"),
                        },
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error scanning aggregators: {e}")

