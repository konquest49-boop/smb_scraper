# pages/1_New_Search.py - DEBUGGED WITH ERROR HANDLING (DNS removed for deployment)
import streamlit as st
import requests
import re
import time
import concurrent.futures
from urllib.parse import urlparse, urljoin
import csv
import io
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys

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

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False

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
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# LOAD API KEYS WITH VALIDATION
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "").strip()
SERPER_KEY = st.secrets.get("SERPER_KEY", "").strip()
SERPSTACK_KEY = st.secrets.get("SERPSTACK_KEY", "").strip()

# Show API status
api_status = []
if SERPAPI_KEY:
    api_status.append("SerpAPI ✅")
if SERPER_KEY:
    api_status.append("Serper ✅")
if SERPSTACK_KEY:
    api_status.append("SerpStack ✅")

if not any([SERPAPI_KEY, SERPER_KEY, SERPSTACK_KEY]):
    st.error("❌ **NO API KEYS FOUND!** Please add at least one API key to `.streamlit/secrets.toml`")
    st.code("""
# .streamlit/secrets.toml
SERPAPI_KEY = "your_key_here"
SERPER_KEY = "your_key_here"
SERPSTACK_KEY = "your_key_here"
    """)
    st.stop()

# CONFIG
MAX_WORKERS = 25
HTTP_TIMEOUT = 5
REQUEST_DELAY = 0.01
MAX_LINKS_PER_SITE = 12
MAX_DOMAINS_TO_SCAN = 250

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=150, pool_maxsize=150)
session.mount('http://', adapter)
session.mount('https://', adapter)

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

# UI HEADER
st.title("⚡ HYPER-TURBO — SMB Lead Harvester")
st.caption(f"👤 {current_user_email} | Active APIs: {', '.join(api_status)}")
st.divider()

col1, col2 = st.columns(2)
with col1:
    selected_industries = st.multiselect("Industry / Niche", industries, default=["Roofing"])
    country = st.selectbox("Country", countries)
with col2:
    available_cities = city_map.get(country, [])
    selected_cities = st.multiselect("Cities (optional)", available_cities, default=available_cities[:3])
    ultra_mode = st.checkbox("Ultra Mode (JS rendering)", value=False)
    mx_check = st.checkbox("MX verification", value=True)

# Debug mode toggle
with st.expander("🔧 Debug Options"):
    st.session_state.debug_mode = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)

# SEARCH FUNCTIONS WITH ERROR LOGGING
def serpapi_search(q, num=25):
    if not SERPAPI_KEY:
        return []
    try:
        r = session.get("https://serpapi.com/search", 
                       params={"engine":"google","q":q,"api_key":SERPAPI_KEY,"num":num}, 
                       timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            results = r.json().get("organic_results", [])[:num]
            if st.session_state.debug_mode:
                st.write(f"✅ SerpAPI: {len(results)} results for '{q}'")
            return results
        else:
            if st.session_state.debug_mode:
                st.warning(f"⚠️ SerpAPI status {r.status_code} for '{q}'")
    except Exception as e:
        if st.session_state.debug_mode:
            st.error(f"❌ SerpAPI error: {str(e)}")
    return []

def serper_search(q, num=25):
    if not SERPER_KEY:
        return []
    try:
        r = session.post("https://google.serper.dev/search", 
                        json={"q": q, "num": num}, 
                        headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}, 
                        timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            results = r.json().get("organic", [])[:num]
            if st.session_state.debug_mode:
                st.write(f"✅ Serper: {len(results)} results for '{q}'")
            return results
        else:
            if st.session_state.debug_mode:
                st.warning(f"⚠️ Serper status {r.status_code} for '{q}'")
    except Exception as e:
        if st.session_state.debug_mode:
            st.error(f"❌ Serper error: {str(e)}")
    return []

def serpstack_search(q, num=25):
    if not SERPSTACK_KEY:
        return []
    try:
        r = session.get("http://api.serpstack.com/search", 
                       params={"access_key": SERPSTACK_KEY, "q": q, "num": num}, 
                       timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            results = r.json().get("organic_results", [])[:num]
            if st.session_state.debug_mode:
                st.write(f"✅ SerpStack: {len(results)} results for '{q}'")
            return results
        else:
            if st.session_state.debug_mode:
                st.warning(f"⚠️ SerpStack status {r.status_code} for '{q}'")
    except Exception as e:
        if st.session_state.debug_mode:
            st.error(f"❌ SerpStack error: {str(e)}")
    return []

def normalize_url(url):
    try:
        if not url.startswith("http"):
            url = "http //" + url
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except:
        return None

def get_priority_pages(root_url):
    priority = [
        "/", "/contact", "/contact-us", "/about", "/about-us",
        "/get-quote", "/free-estimate", "/team", "/staff", 
        "/services", "/locations", "/franchise"
    ]
    return [urljoin(root_url, p) for p in priority]

def extract_emails_from_html(html):
    try:
        emails = set([m.group(0).lower() for m in EMAIL_REGEX.finditer(html)])
        return emails
    except:
        return set()

def fetch_page_fast(url):
    try:
        r = session.get(url, timeout=HTTP_TIMEOUT, 
                       headers={"User-Agent":"Mozilla/5.0"}, 
                       allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ""

def scan_domain_ultra(domain_root, use_playwright=False):
    found = set()
    pages = get_priority_pages(domain_root)
    
    for url in pages[:MAX_LINKS_PER_SITE]:
        html = fetch_page_fast(url)
        
        if html:
            emails = extract_emails_from_html(html)
            for e in emails:
                if e:
                    found.add((e, url))
        
        time.sleep(REQUEST_DELAY)
    
    return found

def generate_optimized_queries(industry, city_or_country):
    return [
        f'{industry} {city_or_country} contact email',
        f'{industry} {city_or_country} "@hotmail.com"',
        f'{industry} {city_or_country} "@outlook.com"',
        f'{industry} {city_or_country} "@live.com"',
        f'"{industry}" "{city_or_country}" contact us',
        f'{industry} {city_or_country} "get quote" email'
    ]

def create_progress_display(stage, progress_val, stats):
    stages = {
        "init": {"icon": "🔍", "label": "Initializing", "color": "#3498db"},
        "serp": {"icon": "🌐", "label": "Searching", "color": "#9b59b6"},
        "scan": {"icon": "⚡", "label": "Scanning", "color": "#e67e22"},
        "verify": {"icon": "✓", "label": "Verifying", "color": "#27ae60"},
        "complete": {"icon": "🎯", "label": "Complete", "color": "#2ecc71"}
    }
    
    current = stages.get(stage, stages["init"])
    
    return f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0;">{current['icon']} {current['label']}</h2>
            <span style="color: white; font-size: 24px; font-weight: bold;">{progress_val}%</span>
        </div>
        <div style="background: rgba(255,255,255,0.2); height: 25px; border-radius: 12px; overflow: hidden;">
            <div style="background: {current['color']}; height: 100%; width: {progress_val}%; transition: width 0.3s; border-radius: 12px;"></div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 25px;">
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: white; font-size: 32px; font-weight: bold;">{stats.get('queries', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 14px;">QUERIES</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: white; font-size: 32px; font-weight: bold;">{stats.get('domains', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 14px;">DOMAINS</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center;">
                <div style="color: {current['color']}; font-size: 32px; font-weight: bold;">{stats.get('leads', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 14px;">LEADS</div>
            </div>
        </div>
    </div>
    """

def run_ultra_search(selected_industries, selected_cities, use_playwright=False, do_mx=True):
    excluded_emails = get_all_saved_emails()
    
    queries = []
    for ind in selected_industries:
        if selected_cities:
            for c in selected_cities:
                queries.extend(generate_optimized_queries(ind, c))
        else:
            queries.extend(generate_optimized_queries(ind, country))
    
    queries = list(dict.fromkeys(queries))[:30]
    
    if st.session_state.debug_mode:
        st.write(f"📝 Generated {len(queries)} queries")
        with st.expander("View Queries"):
            for i, q in enumerate(queries, 1):
                st.write(f"{i}. {q}")
    
    progress_placeholder = st.empty()
    stats = {'queries': len(queries), 'domains': 0, 'leads': 0}
    
    progress_placeholder.markdown(create_progress_display("init", 5, stats), unsafe_allow_html=True)
    time.sleep(0.2)
    
    progress_placeholder.markdown(create_progress_display("serp", 10, stats), unsafe_allow_html=True)
    
    all_links = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for q in queries:
            if SERPAPI_KEY:
                futures.append(executor.submit(serpapi_search, q, 25))
            if SERPER_KEY:
                futures.append(executor.submit(serper_search, q, 25))
            if SERPSTACK_KEY:
                futures.append(executor.submit(serpstack_search, q, 25))
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            for r in res:
                link = r.get("link") or r.get("url") or r.get("position_link")
                title = r.get("title") or r.get("position") or ""
                if link:
                    all_links.append({"link": link, "title": title})
            completed += 1
            progress = 10 + (completed / len(futures) * 25)
            progress_placeholder.markdown(create_progress_display("serp", int(progress), stats), unsafe_allow_html=True)
    
    if st.session_state.debug_mode:
        st.write(f"🔗 Found {len(all_links)} total links from search engines")
    
    domain_map = {}
    for item in all_links:
        root = normalize_url(item["link"])
        if root and root not in domain_map:
            domain_map[root] = item
    
    domains = list(domain_map.keys())[:MAX_DOMAINS_TO_SCAN]
    stats['domains'] = len(domains)
    
    if st.session_state.debug_mode:
        st.write(f"🌐 Extracted {len(domains)} unique domains to scan")
    
    progress_placeholder.markdown(create_progress_display("scan", 35, stats), unsafe_allow_html=True)
    
    leads = []
    seen_emails = set()
    filtered_count = 0
    
    def worker(root_url):
        found = scan_domain_ultra(root_url, use_playwright)
        results = []
        nonlocal filtered_count
        
        for email, found_on in found:
            email_l = email.lower()
            
            if email_l in excluded_emails:
                filtered_count += 1
                continue
                
            if email_l not in seen_emails:
                seen_emails.add(email_l)
                # Skip MX verification for deployment (no dns.resolver)
                confidence = 70  # Default confidence
                mx_hosts = []
                
                results.append({
                    "email": email_l,
                    "found_on": found_on,
                    "domain_root": root_url,
                    "confidence": confidence,
                    "mx_hosts": mx_hosts,
                    "title": domain_map.get(root_url, {}).get("title", "")
                })
        return results
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(worker, d): d for d in domains}
        completed = 0
        
        for future in concurrent.futures.as_completed(futures):
            results = future.result()
            leads.extend(results)
            stats['leads'] = len(leads)
            completed += 1
            progress = 35 + (completed / len(domains) * 50)
            
            if completed % 10 == 0 or completed == len(domains):
                stage = "scan" if progress < 85 else "verify"
                progress_placeholder.markdown(create_progress_display(stage, int(progress), stats), unsafe_allow_html=True)
    
    progress_placeholder.markdown(create_progress_display("complete", 100, stats), unsafe_allow_html=True)
    
    metadata = {
        "industries": selected_industries,
        "cities": selected_cities if selected_cities else [country],
        "country": country,
        "filtered_duplicates": filtered_count,
        "ultra_mode": use_playwright,
        "mx_verified": False  # Disabled for deployment
    }
    
    return leads, metadata, filtered_count

# LAUNCH BUTTON
if st.button("⚡ LAUNCH HYPER-TURBO", type="primary", use_container_width=True):
    if not selected_industries:
        st.error("❌ Select at least one industry")
    else:
        start_time = time.time()
        
        try:
            leads, metadata, filtered = run_ultra_search(
                selected_industries, 
                selected_cities, 
                ultra_mode, 
                mx_check
            )
            
            elapsed = time.time() - start_time
            
            if leads:
                st.balloons()
                st.session_state.last_search_results = {
                    "leads": leads,
                    "metadata": metadata,
                    "elapsed": elapsed,
                    "timestamp": datetime.now().isoformat()
                }
                st.session_state.show_save_dialog = True
                
                st.success(f"🎯 Found **{len(leads)}** emails in {elapsed:.1f}s!")
                if filtered > 0:
                    st.info(f"🛡️ Filtered {filtered} duplicates")
            else:
                st.warning("⚠️ No leads found. Try:")
                st.write("• Different industries or cities")
                st.write("• Check if API keys are valid")
                st.write("• Enable debug mode to see details")
                
        except Exception as e:
            st.error(f"❌ Search failed: {str(e)}")
            if st.session_state.debug_mode:
                st.exception(e)

# RESULTS DISPLAY
if st.session_state.last_search_results:
    results = st.session_state.last_search_results
    leads = results["leads"]
    meta = results["metadata"]
    elapsed = results["elapsed"]
    
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
                        existing = load_saved_searches()
                        if name in existing:
                            st.error("❌ Name exists!")
                        else:
                            save_search_to_file(name, leads, meta)
                            st.success(f"✅ Saved {len(leads)} leads!")
                            st.session_state.show_save_dialog = False
                            time.sleep(1)
                            st.rerun()
            
            with col2:
                if st.form_submit_button("Skip", use_container_width=True):
                    st.session_state.show_save_dialog = False
                    st.rerun()
    
    # Display results
    df = pd.DataFrame(leads)
    df = df.sort_values('confidence', ascending=False)
    df.insert(0, '#', range(1, len(df) + 1))
    
    st.write("## 📊 Results")
    st.dataframe(df[['#', 'email', 'confidence', 'domain_root', 'title']], 
                 use_container_width=True, height=400)
    
    # Downloads
    st.write("### 📥 Downloads")
    col1, col2 = st.columns(2)
    
    with col1:
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["email"])
        for lead in leads:
            writer.writerow([lead["email"]])
        
        st.download_button("📧 Emails CSV", csv_buf.getvalue(),
                          f"emails_{int(time.time())}.csv", "text/csv",
                          use_container_width=True)
    
    with col2:
        if not st.session_state.show_save_dialog:
            if st.button("💾 Save", use_container_width=True):
                st.session_state.show_save_dialog = True
                st.rerun()

st.divider()
st.caption(f"⚡ {current_user_email}")