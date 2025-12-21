# pages/1_New_Search.py - WORKS WITHOUT API KEYS
import streamlit as st
import requests
import re
import time
import concurrent.futures
from urllib.parse import urlparse, urljoin, quote_plus
import csv
import io
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from login import is_logged_in, get_current_user, logout, get_user_data_dir

st.set_page_config(page_title="New Search", page_icon="🔍", layout="wide")
st.markdown('<style>[data-testid="stSidebarNav"] li:first-child{display:none}</style>', unsafe_allow_html=True)

if not is_logged_in():
    st.warning("🔒 Please login first")
    if st.button("Go to Login", type="primary"):
        st.switch_page("Auth.py")
    st.stop()

with st.sidebar:
    st.divider()
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        logout()
        st.switch_page("Auth.py")

current_user_email = get_current_user()
user_data_dir = get_user_data_dir(current_user_email)

# DATA PERSISTENCE
user_data_dir.mkdir(exist_ok=True)
SAVED_SEARCHES_FILE = user_data_dir / "saved_searches.json"

def load_saved_searches():
    if SAVED_SEARCHES_FILE.exists():
        try:
            with open(SAVED_SEARCHES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_search_to_file(search_name, leads, metadata):
    searches = load_saved_searches()
    searches[search_name] = {
        "leads": leads,
        "metadata": metadata,
        "timestamp": datetime.now().isoformat(),
        "lead_count": len(leads)
    }
    with open(SAVED_SEARCHES_FILE, 'w') as f:
        json.dump(searches, f, indent=2)

def get_all_saved_emails():
    searches = load_saved_searches()
    all_emails = set()
    for search_data in searches.values():
        for lead in search_data.get("leads", []):
            all_emails.add(lead["email"].lower())
    return all_emails

# SESSION STATE
if 'last_search_results' not in st.session_state:
    st.session_state.last_search_results = None
if 'show_save_dialog' not in st.session_state:
    st.session_state.show_save_dialog = False

# NO API KEYS NEEDED - Using Direct Scraping
MAX_WORKERS = 30
HTTP_TIMEOUT = 8
MAX_PAGES_PER_SITE = 15
MAX_DOMAINS = 300

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
})

industries = ["Roofing","Home Renovations","Restoration / Construction","General Contracting",
              "Contracting","Excavation","Tile / Flooring","Home Upgrades","Cleaning Service",
              "Realtor","Plumbing","HVAC","Landscaping","Electrical","Painting"]

countries = ["United States","Canada","Australia","United Kingdom","Germany"]
city_map = {
    "United States": ["Miami","New York","Chicago","Houston","Los Angeles","Dallas","Atlanta","Phoenix","Seattle","Denver","Boston","San Francisco"],
    "Canada": ["Toronto","Vancouver","Montreal","Calgary","Ottawa","Edmonton"],
    "Australia": ["Sydney","Melbourne","Brisbane","Perth","Adelaide","Gold Coast"],
    "United Kingdom": ["London","Manchester","Birmingham","Glasgow","Bristol","Liverpool"],
    "Germany": ["Berlin","Munich","Hamburg","Cologne","Frankfurt","Stuttgart"]
}

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@(hotmail|outlook|live)\.[a-zA-Z.]{2,6}", re.I)

# UI
st.title("⚡ HYPER-TURBO Lead Finder")
st.caption(f"👤 {current_user_email} | Direct Web Scraping (No APIs Required)")
st.divider()

col1, col2 = st.columns(2)
with col1:
    selected_industries = st.multiselect("Industry", industries, default=["Roofing"])
    country = st.selectbox("Country", countries)
with col2:
    available_cities = city_map.get(country, [])
    selected_cities = st.multiselect("Cities", available_cities, default=available_cities[:3])

# DIRECT SCRAPING FUNCTIONS (NO APIs)
def scrape_google(query):
    """Direct Google scraping - No API needed"""
    results = []
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=50"
        r = session.get(url, timeout=HTTP_TIMEOUT)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Extract search results
            for g in soup.find_all('div', class_='g'):
                link_tag = g.find('a')
                if link_tag and link_tag.get('href'):
                    link = link_tag['href']
                    if link.startswith('http') and 'google.com' not in link:
                        title_tag = g.find('h3')
                        results.append({
                            "link": link,
                            "title": title_tag.text if title_tag else ""
                        })
        
        # Add small delay to avoid rate limiting
        time.sleep(0.5)
    except:
        pass
    
    return results

def scrape_bing(query):
    """Direct Bing scraping - No API needed"""
    results = []
    try:
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count=50"
        r = session.get(url, timeout=HTTP_TIMEOUT)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for result in soup.find_all('li', class_='b_algo'):
                link_tag = result.find('a')
                if link_tag and link_tag.get('href'):
                    link = link_tag['href']
                    if link.startswith('http'):
                        title_tag = result.find('h2')
                        results.append({
                            "link": link,
                            "title": title_tag.text if title_tag else ""
                        })
        
        time.sleep(0.5)
    except:
        pass
    
    return results

def normalize_url(url):
    try:
        if not url.startswith("http"):
            url = "http://" + url
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except:
        return None

def get_contact_pages(root_url):
    pages = [
        "/", "/contact", "/contact-us", "/contactus", "/reach-us",
        "/about", "/about-us", "/get-quote", "/free-estimate",
        "/team", "/staff", "/services", "/locations"
    ]
    return [urljoin(root_url, p) for p in pages]

def extract_emails(html):
    try:
        return set([m.group(0).lower() for m in EMAIL_REGEX.finditer(html)])
    except:
        return set()

def fetch_page(url):
    try:
        r = session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ""

def scan_domain(domain_root):
    found = set()
    pages = get_contact_pages(domain_root)[:MAX_PAGES_PER_SITE]
    
    for url in pages:
        html = fetch_page(url)
        if html:
            emails = extract_emails(html)
            for e in emails:
                found.add((e, url))
        time.sleep(0.1)
    
    return found

def generate_queries(industry, location):
    return [
        f'{industry} {location} contact email',
        f'{industry} {location} "@hotmail.com"',
        f'{industry} {location} "@outlook.com"',
        f'{industry} {location} "@live.com"',
        f'{industry} companies {location} email',
        f'{industry} {location} free estimate contact'
    ]

def create_progress_ui(stage, pct, stats):
    colors = {"searching": "#3498db", "scanning": "#e67e22", "complete": "#2ecc71"}
    color = colors.get(stage, "#3498db")
    
    return f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0;">🔍 {stage.title()}</h2>
            <span style="color: white; font-size: 24px; font-weight: bold;">{pct}%</span>
        </div>
        <div style="background: rgba(255,255,255,0.2); height: 25px; border-radius: 12px; overflow: hidden;">
            <div style="background: {color}; height: 100%; width: {pct}%; transition: width 0.3s; border-radius: 12px;"></div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 25px;">
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: white; font-size: 32px; font-weight: bold;">{stats['queries']}</div>
                <div style="color: rgba(255,255,255,0.8);">QUERIES</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: white; font-size: 32px; font-weight: bold;">{stats['domains']}</div>
                <div style="color: rgba(255,255,255,0.8);">DOMAINS</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: {color}; font-size: 32px; font-weight: bold;">{stats['leads']}</div>
                <div style="color: rgba(255,255,255,0.8);">LEADS</div>
            </div>
        </div>
    </div>
    """

def run_search(industries, cities):
    excluded = get_all_saved_emails()
    
    queries = []
    for ind in industries:
        if cities:
            for city in cities:
                queries.extend(generate_queries(ind, city))
        else:
            queries.extend(generate_queries(ind, country))
    
    queries = list(dict.fromkeys(queries))[:25]  # Limit to avoid rate limits
    
    progress = st.empty()
    stats = {'queries': len(queries), 'domains': 0, 'leads': 0}
    
    progress.markdown(create_progress_ui("searching", 10, stats), unsafe_allow_html=True)
    
    # Scrape Google and Bing
    all_results = []
    for i, q in enumerate(queries):
        # Google
        all_results.extend(scrape_google(q))
        # Bing (alternative source)
        all_results.extend(scrape_bing(q))
        
        pct = 10 + int(((i + 1) / len(queries)) * 40)
        progress.markdown(create_progress_ui("searching", pct, stats), unsafe_allow_html=True)
    
    # Extract domains
    domain_map = {}
    for r in all_results:
        url = r.get("link")
        if url:
            root = normalize_url(url)
            if root and root not in domain_map:
                domain_map[root] = {"title": r.get("title", "")}
    
    domains = list(domain_map.keys())[:MAX_DOMAINS]
    stats['domains'] = len(domains)
    
    progress.markdown(create_progress_ui("scanning", 50, stats), unsafe_allow_html=True)
    
    # Scan domains
    leads = []
    seen = set()
    filtered = 0
    
    def worker(root):
        found = scan_domain(root)
        results = []
        nonlocal filtered
        
        for email, url in found:
            email_l = email.lower()
            if email_l in excluded:
                filtered += 1
                continue
            if email_l not in seen:
                seen.add(email_l)
                results.append({
                    "email": email_l,
                    "found_on": url,
                    "domain_root": root,
                    "confidence": 70,
                    "title": domain_map.get(root, {}).get("title", "")
                })
        return results
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(worker, d): d for d in domains}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            leads.extend(future.result())
            stats['leads'] = len(leads)
            pct = 50 + int((i / len(domains)) * 50)
            progress.markdown(create_progress_ui("scanning", pct, stats), unsafe_allow_html=True)
    
    progress.markdown(create_progress_ui("complete", 100, stats), unsafe_allow_html=True)
    time.sleep(1)
    progress.empty()
    
    return leads, {"industries": industries, "cities": cities or [country], "filtered": filtered}, filtered

# LAUNCH
if st.button("⚡ LAUNCH SEARCH", type="primary", use_container_width=True):
    if not selected_industries:
        st.error("❌ Select at least one industry")
    else:
        start = time.time()
        
        with st.spinner("Searching..."):
            leads, meta, filtered = run_search(selected_industries, selected_cities)
        
        elapsed = time.time() - start
        
        if leads:
            st.balloons()
            st.session_state.last_search_results = {
                "leads": leads,
                "metadata": meta,
                "elapsed": elapsed,
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.show_save_dialog = True
            
            st.success(f"🎯 Found **{len(leads)}** emails in {elapsed:.1f}s!")
            if filtered > 0:
                st.info(f"🛡️ Filtered {filtered} duplicates")
        else:
            st.warning("⚠️ No leads found. Try different industries or cities.")

# RESULTS
if st.session_state.last_search_results:
    results = st.session_state.last_search_results
    leads = results["leads"]
    meta = results["metadata"]
    
    if st.session_state.show_save_dialog:
        st.divider()
        with st.form("save_form"):
            st.subheader("💾 Save Search")
            
            ind_str = "+".join(meta["industries"][:2])
            city_str = "+".join(meta["cities"][:2])
            default = f"{ind_str}_{city_str}_{datetime.now().strftime('%m%d_%H%M')}"
            
            name = st.text_input("Name", value=default)
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("💾 Save", use_container_width=True):
                    if name:
                        if name in load_saved_searches():
                            st.error("❌ Name exists!")
                        else:
                            save_search_to_file(name, leads, meta)
                            st.success("✅ Saved!")
                            st.session_state.show_save_dialog = False
                            time.sleep(1)
                            st.rerun()
            
            with col2:
                if st.form_submit_button("Skip", use_container_width=True):
                    st.session_state.show_save_dialog = False
                    st.rerun()
    
    # Display
    df = pd.DataFrame(leads).sort_values('confidence', ascending=False)
    df.insert(0, '#', range(1, len(df) + 1))
    
    st.write("## 📊 Results")
    st.dataframe(df[['#', 'email', 'confidence', 'domain_root', 'title']], 
                 use_container_width=True, height=400)
    
    # Download
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["email"])
    for lead in leads:
        writer.writerow([lead["email"]])
    
    st.download_button("📧 Download CSV", csv_buf.getvalue(),
                      f"emails_{int(time.time())}.csv", "text/csv",
                      use_container_width=True)

st.divider()
st.caption(f"⚡ {current_user_email} | Direct Scraping Engine")