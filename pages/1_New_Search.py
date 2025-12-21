# pages/1_New_Search.py - DUAL MODE: QUALITY FOCUSED
import streamlit as st
import requests
import re
import time
import concurrent.futures
from urllib.parse import urlparse, urljoin
import csv
import io
import dns.resolver
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys
import threading

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
user_data_dir.mkdir(exist_ok=True)
SAVED_SEARCHES_FILE = user_data_dir / "saved_searches.json"

# SESSION STATE
if 'last_search_results' not in st.session_state:
    st.session_state.last_search_results = None
if 'show_save_dialog' not in st.session_state:
    st.session_state.show_save_dialog = False

# API KEYS
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "").strip()
SERPER_KEY = st.secrets.get("SERPER_KEY", "").strip()
SERPSTACK_KEY = st.secrets.get("SERPSTACK_KEY", "").strip()

api_status = []
if SERPAPI_KEY: api_status.append("SerpAPI ✅")
if SERPER_KEY: api_status.append("Serper ✅")
if SERPSTACK_KEY: api_status.append("SerpStack ✅")

if not any([SERPAPI_KEY, SERPER_KEY, SERPSTACK_KEY]):
    st.error("❌ NO API KEYS! Add to `.streamlit/secrets.toml`")
    st.stop()

# SEARCH MODE CONFIGS
QUICK_MODE = {
    'name': 'Quick Search',
    'max_workers': 50,
    'http_timeout': 1.8,
    'max_pages_per_domain': 4,
    'target_leads': 40,
    'max_domains': 400,
    'queries_per_combo': 2,
    'estimated_time': '10-40s',
    'expected_leads': '30-50'
}

DEEP_MODE = {
    'name': 'Deep Search',
    'max_workers': 50,
    'http_timeout': 2.5,
    'max_pages_per_domain': 8,
    'target_leads': 150,
    'max_domains': 300,
    'queries_per_combo': 4,
    'estimated_time': '30-90s',
    'expected_leads': '80-150'
}

# OPTIMIZED SESSION
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=200,
    pool_maxsize=200,
    max_retries=2
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# QUALITY EMAIL REGEX - Hotmail/Outlook/Live only
EMAIL_REGEX = re.compile(
    r'\b[a-zA-Z0-9._%+\-]+@(?:hotmail|outlook|live)\.(?:com|co\.uk|ca|au|de|fr|it|es|net|org)\b',
    re.IGNORECASE
)

# CACHED DNS LOOKUP
@st.cache_data(ttl=3600)
def cached_dns_lookup(domain):
    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=2)
        return True, [str(r.exchange) for r in answers]
    except:
        return False, []

# DATA FUNCTIONS
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

# DROPDOWN DATA
industries = [
    "Roofing", "Home Renovations", "Restoration / Construction",
    "General Contracting", "Contracting", "Excavation", "Tile / Flooring",
    "Home Upgrades", "Cleaning Service", "Realtor", "Plumbing",
    "HVAC", "Landscaping", "Electrical", "Painting", "Solar Installation",
    "Pool Services", "Pest Control", "Moving Services", "Handyman",
    "Window Installation", "Siding", "Gutter Services", "Fence Installation"
]

countries = ["United States", "Canada", "Australia", "United Kingdom", "Germany"]
city_map = {
    "United States": ["Miami", "New York", "Chicago", "Houston", "Los Angeles", 
                     "Dallas", "Atlanta", "Phoenix", "Seattle", "Denver", 
                     "Boston", "San Francisco", "Portland", "Austin", "Tampa",
                     "Philadelphia", "San Diego", "Las Vegas", "Charlotte"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "United Kingdom": ["London", "Manchester", "Birmingham", "Glasgow", "Bristol"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"]
}

# QUERY GENERATION
def generate_quality_queries(industry, location, mode):
    """Generate queries optimized for quality"""
    if mode['queries_per_combo'] == 2:  # Quick mode
        return [
            f'{industry} {location} ("@hotmail.com" OR "@outlook.com")',
            f'{industry} {location} contact email'
        ]
    else:  # Deep mode
        return [
            f'{industry} {location} contact "@hotmail.com"',
            f'{industry} {location} contact "@outlook.com"',
            f'{industry} {location} email "@live.com"',
            f'"{industry}" "{location}" owner email contact'
        ]

# API SEARCH FUNCTIONS
def serpapi_search(q, num=15):
    if not SERPAPI_KEY:
        return []
    try:
        r = session.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": q, "api_key": SERPAPI_KEY, "num": num},
            timeout=3
        )
        if r.status_code == 200:
            return r.json().get("organic_results", [])[:num]
    except:
        pass
    return []

def serper_search(q, num=15):
    if not SERPER_KEY:
        return []
    try:
        r = session.post(
            "https://google.serper.dev/search",
            json={"q": q, "num": num},
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            timeout=3
        )
        if r.status_code == 200:
            return r.json().get("organic", [])[:num]
    except:
        pass
    return []

def serpstack_search(q, num=15):
    if not SERPSTACK_KEY:
        return []
    try:
        r = session.get(
            "http://api.serpstack.com/search",
            params={"access_key": SERPSTACK_KEY, "q": q, "num": num},
            timeout=3
        )
        if r.status_code == 200:
            return r.json().get("organic_results", [])[:num]
    except:
        pass
    return []

# URL TOOLS
def normalize_url(url):
    try:
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except:
        return None

def get_priority_pages(root_url, max_pages):
    """Get most valuable pages for contact info"""
    priority_paths = [
        "/", "/contact", "/contact-us", "/about", 
        "/get-quote", "/free-estimate", "/team", "/services"
    ]
    return [urljoin(root_url, path) for path in priority_paths[:max_pages]]

# EMAIL EXTRACTION
def extract_emails_from_html(html):
    if not html:
        return set()
    try:
        found = EMAIL_REGEX.findall(html)
        return {email.lower() for email in found if email}
    except:
        return set()

# FAST PAGE FETCH
def fetch_page_fast(url, timeout):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = session.get(url, timeout=timeout, headers=headers, allow_redirects=False)
        if r.status_code == 200:
            return r.text[:60000]  # First 60KB only
    except:
        pass
    return ""

# DOMAIN SCANNER
def scan_domain_quality(domain_root, mode):
    """Scan domain with quality focus"""
    found = set()
    pages = get_priority_pages(domain_root, mode['max_pages_per_domain'])
    
    for page_url in pages:
        html = fetch_page_fast(page_url, mode['http_timeout'])
        if html:
            emails = extract_emails_from_html(html)
            for email in emails:
                found.add((email, page_url))
            if found and mode['name'] == 'Quick Search':
                break  # Quick mode: exit on first find
    
    return found

# PROGRESS UI
def create_progress_ui(stage, progress, stats, mode_name):
    stages = {
        "init": {"icon": "🔍", "label": "Initializing", "color": "#3498db"},
        "search": {"icon": "🌐", "label": "Searching APIs", "color": "#9b59b6"},
        "scan": {"icon": "⚡", "label": "Scanning Domains", "color": "#e67e22"},
        "verify": {"icon": "✓", "label": "Verifying Quality", "color": "#27ae60"},
        "done": {"icon": "🎯", "label": "Complete", "color": "#2ecc71"}
    }
    current = stages.get(stage, stages["init"])
    
    return f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin: 10px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <h3 style="color: white; margin: 0;">{current['icon']} {current['label']} ({mode_name})</h3>
            <span style="color: white; font-size: 20px; font-weight: bold;">{progress}%</span>
        </div>
        <div style="background: rgba(255,255,255,0.2); height: 18px; border-radius: 9px; overflow: hidden;">
            <div style="background: {current['color']}; height: 100%; width: {progress}%; 
                        transition: width 0.3s; border-radius: 9px;"></div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px;">
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px; text-align: center;">
                <div style="color: white; font-size: 24px; font-weight: bold;">{stats.get('queries', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 11px;">QUERIES</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px; text-align: center;">
                <div style="color: white; font-size: 24px; font-weight: bold;">{stats.get('domains', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 11px;">SCANNED</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px; text-align: center;">
                <div style="color: {current['color']}; font-size: 24px; font-weight: bold;">{stats.get('leads', 0)}</div>
                <div style="color: rgba(255,255,255,0.8); font-size: 11px;">QUALITY LEADS</div>
            </div>
        </div>
    </div>
    """

# MAIN SEARCH ENGINE
def quality_search_engine(industries, cities, country, mode):
    """Quality-focused search with MX verification"""
    
    excluded_emails = get_all_saved_emails()
    
    # Generate queries
    queries = []
    locations = cities if cities else [country]
    
    for industry in industries:
        for location in locations:
            queries.extend(generate_quality_queries(industry, location, mode))
    
    queries = list(dict.fromkeys(queries))
    
    progress_ph = st.empty()
    stats = {'queries': len(queries), 'domains': 0, 'leads': 0}
    
    # STAGE 1: Init
    progress_ph.markdown(create_progress_ui("init", 5, stats, mode['name']), unsafe_allow_html=True)
    time.sleep(0.1)
    
    # STAGE 2: Search APIs
    progress_ph.markdown(create_progress_ui("search", 10, stats, mode['name']), unsafe_allow_html=True)
    
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for q in queries:
            if SERPAPI_KEY:
                futures.append(executor.submit(serpapi_search, q, 15))
            if SERPER_KEY:
                futures.append(executor.submit(serper_search, q, 15))
            if SERPSTACK_KEY:
                futures.append(executor.submit(serpstack_search, q, 15))
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                all_results.extend(future.result())
                progress = 10 + ((i + 1) / len(futures) * 25)
                progress_ph.markdown(create_progress_ui("search", int(progress), stats, mode['name']), unsafe_allow_html=True)
            except:
                pass
    
    # Filter domains - Skip aggregators
    domain_map = {}
    bad_domains = {'facebook', 'linkedin', 'yelp', 'indeed', 'glassdoor', 
                   'bbb.org', 'yellowpages', 'thumbtack', 'homeadvisor', 'angieslist'}
    
    for result in all_results:
        link = result.get("link") or result.get("url")
        title = result.get("title", "")
        
        if link:
            root = normalize_url(link)
            if root and root not in domain_map:
                if not any(bad in root.lower() for bad in bad_domains):
                    domain_map[root] = {"title": title}
    
    domains = list(domain_map.keys())[:mode['max_domains']]
    stats['domains'] = len(domains)
    
    # STAGE 3: Scan Domains
    progress_ph.markdown(create_progress_ui("scan", 35, stats, mode['name']), unsafe_allow_html=True)
    
    all_leads = []
    seen_emails = set()
    stop_flag = threading.Event()
    
    def worker(domain_root):
        if stop_flag.is_set():
            return []
        
        found_emails = scan_domain_quality(domain_root, mode)
        results = []
        
        for email, found_url in found_emails:
            email_l = email.lower()
            
            if email_l in excluded_emails or email_l in seen_emails:
                continue
            
            seen_emails.add(email_l)
            results.append({
                "email": email_l,
                "found_on": found_url,
                "domain_root": domain_root,
                "title": domain_map.get(domain_root, {}).get("title", ""),
                "confidence": 50,
                "mx_verified": False
            })
        
        if len(all_leads) >= mode['target_leads']:
            stop_flag.set()
        
        return results
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=mode['max_workers']) as executor:
        futures = {executor.submit(worker, d): d for d in domains}
        completed = 0
        
        for future in concurrent.futures.as_completed(futures):
            try:
                results = future.result()
                all_leads.extend(results)
                stats['leads'] = len(all_leads)
                completed += 1
                
                progress = 35 + (completed / len(domains) * 45)
                if completed % 5 == 0:
                    progress_ph.markdown(create_progress_ui("scan", int(progress), stats, mode['name']), unsafe_allow_html=True)
                
                if stop_flag.is_set():
                    break
            except:
                completed += 1
    
    # STAGE 4: ALWAYS Verify MX (Quality guarantee)
    progress_ph.markdown(create_progress_ui("verify", 80, stats, mode['name']), unsafe_allow_html=True)
    
    def verify_mx_quality(lead):
        try:
            domain = lead["email"].split("@")[1]
            has_mx, mx_hosts = cached_dns_lookup(domain)
            lead["confidence"] = 85 if has_mx else 35
            lead["mx_verified"] = has_mx
            lead["mx_hosts"] = mx_hosts if has_mx else []
        except:
            lead["confidence"] = 40
        return lead
    
    if all_leads:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            all_leads = list(executor.map(verify_mx_quality, all_leads))
    
    # Filter LOW quality leads
    quality_leads = [l for l in all_leads if l['confidence'] >= 70]
    
    progress_ph.markdown(create_progress_ui("done", 100, stats, mode['name']), unsafe_allow_html=True)
    
    metadata = {
        "industries": industries,
        "cities": cities if cities else [country],
        "country": country,
        "mode": mode['name'],
        "mx_verified": True,
        "quality_filtered": True,
        "total_found": len(all_leads),
        "quality_leads": len(quality_leads)
    }
    
    return quality_leads, metadata

# ========================================
# UI
# ========================================

st.title("⚡ Quality Lead Harvester")
st.caption(f"👤 {current_user_email} | {', '.join(api_status)}")
st.divider()

# MODE SELECTION
mode_choice = st.radio(
    "🎯 Search Mode",
    ["Quick Search (30-50 leads in 20-40s)", "Deep Search (80-150 leads in 2-3 min)"],
    horizontal=True
)

mode = QUICK_MODE if "Quick" in mode_choice else DEEP_MODE

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("⏱️ Time", mode['estimated_time'])
with col2:
    st.metric("🎯 Target", mode['expected_leads'])
with col3:
    st.metric("✓ Quality", "85% MX Verified")

st.divider()

# FORM
col1, col2 = st.columns(2)

with col1:
    selected_industries = st.multiselect(
        "🏭 Select Industries",
        industries,
        default=["Roofing"],
        help="No limits - choose as many as needed"
    )
    country = st.selectbox("🌍 Country", countries)

with col2:
    available_cities = city_map.get(country, [])
    selected_cities = st.multiselect(
        "🏙️ Select Cities",
        available_cities,
        default=available_cities[:2] if len(available_cities) >= 2 else available_cities,
        help="Leave empty to search entire country"
    )

# Estimate warning
if selected_industries and selected_cities:
    total_combos = len(selected_industries) * len(selected_cities)
    if total_combos > 10 and mode == QUICK_MODE:
        st.warning(f"⚠️ {total_combos} combinations may take 60-90s. Consider Deep Search mode.")

st.info("✅ **Quality Guarantee:** All leads are MX-verified (85% confidence) | Duplicates auto-filtered")

# LAUNCH
if st.button(f"⚡ LAUNCH {mode['name'].upper()}", type="primary", use_container_width=True):
    if not selected_industries:
        st.error("❌ Select at least one industry")
    else:
        start_time = time.time()
        
        try:
            leads, metadata = quality_search_engine(
                selected_industries,
                selected_cities,
                country,
                mode
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
                
                st.success(f"🎯 **{len(leads)} quality leads** in **{elapsed:.1f}s**!")
                
                high_conf = len([l for l in leads if l['confidence'] >= 85])
                st.info(f"✅ **{high_conf}** leads are 85%+ confidence (MX verified)")
                
            else:
                st.warning("⚠️ No quality leads found. Try different industries/cities or check API keys.")
                
        except Exception as e:
            st.error(f"❌ Search error: {str(e)}")

# ========================================
# RESULTS
# ========================================

if st.session_state.last_search_results:
    results = st.session_state.last_search_results
    leads = results["leads"]
    meta = results["metadata"]
    elapsed = results["elapsed"]
    
    # SAVE DIALOG
    if st.session_state.show_save_dialog:
        st.divider()
        with st.form("save_form"):
            st.subheader("💾 Save Search")
            
            ind_str = "+".join(meta["industries"][:2])
            city_str = "+".join(meta["cities"][:2])
            default_name = f"{ind_str}_{city_str}_{datetime.now().strftime('%m%d_%H%M')}"
            
            search_name = st.text_input("Search Name", value=default_name)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Save", use_container_width=True):
                    if search_name:
                        existing = load_saved_searches()
                        if search_name in existing:
                            st.error("❌ Name exists!")
                        else:
                            save_search_to_file(search_name, leads, meta)
                            st.success(f"✅ Saved {len(leads)} leads!")
                            st.session_state.show_save_dialog = False
                            time.sleep(1)
                            st.rerun()
            
            with col2:
                if st.form_submit_button("Skip", use_container_width=True):
                    st.session_state.show_save_dialog = False
                    st.rerun()
    
    # TABLE
    st.divider()
    st.subheader(f"📊 {len(leads)} Quality Leads Found")
    
    df = pd.DataFrame(leads)
    df = df.sort_values('confidence', ascending=False)
    df.insert(0, '#', range(1, len(df) + 1))
    
    st.dataframe(
        df[['#', 'email', 'confidence', 'mx_verified', 'domain_root', 'title']],
        use_container_width=True,
        height=400,
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "Confidence",
                format="%d%%",
                min_value=0,
                max_value=100
            ),
            "mx_verified": st.column_config.CheckboxColumn(
                "MX ✓",
                help="Email domain verified"
            )
        }
    )
    
    # DOWNLOADS
    st.subheader("📥 Export Results")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        email_csv = io.StringIO()
        writer = csv.writer(email_csv)
        writer.writerow(["email"])
        for lead in leads:
            writer.writerow([lead["email"]])
        
        st.download_button(
            "📧 Emails Only CSV",
            email_csv.getvalue(),
            f"emails_{int(time.time())}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        full_csv = io.StringIO()
        pd.DataFrame(leads).to_csv(full_csv, index=False)
        
        st.download_button(
            "📊 Full Data CSV",
            full_csv.getvalue(),
            f"full_data_{int(time.time())}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col3:
        if not st.session_state.show_save_dialog:
            if st.button("💾 Save Search", use_container_width=True, type="primary"):
                st.session_state.show_save_dialog = True
                st.rerun()

st.divider()
st.caption(f"⚡ {current_user_email} | Quality-First Search Engine")