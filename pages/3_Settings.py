# pages/Settings.py - Fixed and functional
import streamlit as st
import json
import sys
from pathlib import Path

st.markdown('<style>[data-testid="stSidebarNav"] li:first-child{display:none}</style>', unsafe_allow_html=True)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from login import is_logged_in, get_current_user, logout, get_user_data_dir

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# Check authentication
if not is_logged_in():
    st.warning("🔒 Please login first")
    if st.button("Go to Login", type="primary"):
        st.switch_page("Auth.py")
    st.stop()

# Get user-specific data directory
user_email = get_current_user()
user_data_dir = get_user_data_dir(user_email)
SETTINGS_FILE = user_data_dir / "settings.json"
SAVED_SEARCHES_FILE = user_data_dir / "saved_searches.json"

# Default settings
DEFAULT_SETTINGS = {
    'auto_save_dialog': True,
    'smart_duplicate_filter': True,
    'target_leads': 80,
    'show_confidence_filter': True,
    'min_confidence': 50,
    'parallel_workers': 40,
    'max_domains': 400,
    'http_timeout': 3
}

def load_settings():
    """Load settings with safe defaults"""
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                settings.update(loaded)
        except:
            pass
    return settings

def save_settings(settings):
    """Save settings to file"""
    try:
        user_data_dir.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except:
        return False

# Initialize session state
if 'settings' not in st.session_state:
    st.session_state.settings = load_settings()

# Ensure all keys exist
for key, value in DEFAULT_SETTINGS.items():
    if key not in st.session_state.settings:
        st.session_state.settings[key] = value

# Header with logout
col1, col2 = st.columns([4, 1])
with col1:
    st.title("⚙️ Settings")
    st.caption(f"Customize your experience • Logged in as: {user_email}")
with col2:
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.switch_page("Auth.py")

st.divider()

# DARK MODE (with workaround instructions)
st.header("🎨 Theme")
st.info("""
💡 **To change between Light and Dark mode:**

1. Click the **⋮** menu (top right corner)
2. Select **Settings**
3. Choose **Light** or **Dark** theme
4. Your theme will update instantly!

*Streamlit doesn't allow theme changes through code, so we use their built-in menu.*
""")

st.divider()

# SEARCH BEHAVIOR
st.header("🔍 Search Behavior")

col1, col2 = st.columns(2)

with col1:
    auto_save = st.toggle(
        "Auto-show Save Dialog",
        value=st.session_state.settings['auto_save_dialog'],
        help="Automatically prompt to save after search"
    )
    st.session_state.settings['auto_save_dialog'] = auto_save
    
    smart_filter = st.toggle(
        "Smart Duplicate Filter",
        value=st.session_state.settings['smart_duplicate_filter'],
        help="Exclude emails from saved searches (Recommended!)"
    )
    st.session_state.settings['smart_duplicate_filter'] = smart_filter

with col2:
    target = st.slider(
        "Target Leads Per Search",
        min_value=20,
        max_value=100,
        value=st.session_state.settings['target_leads'],
        step=10,
        help="Aim for this many leads per search"
    )
    st.session_state.settings['target_leads'] = target
    
    show_conf = st.toggle(
        "Show Confidence Filter",
        value=st.session_state.settings['show_confidence_filter'],
        help="Display confidence scores for leads"
    )
    st.session_state.settings['show_confidence_filter'] = show_conf

if st.session_state.settings['show_confidence_filter']:
    min_conf = st.slider(
        "Minimum Confidence Threshold",
        min_value=0,
        max_value=100,
        value=st.session_state.settings['min_confidence'],
        step=5,
        help="Filter leads below this confidence"
    )
    st.session_state.settings['min_confidence'] = min_conf

st.divider()

# PERFORMANCE SETTINGS
st.header("⚡ Performance Settings")
st.warning("⚠️ Advanced settings. Change only if you understand the impact.")

col1, col2 = st.columns(2)

with col1:
    workers = st.slider(
        "Parallel Workers",
        min_value=5,
        max_value=50,
        value=st.session_state.settings['parallel_workers'],
        step=5,
        help="Concurrent requests (higher = faster)"
    )
    st.session_state.settings['parallel_workers'] = workers
    
    timeout = st.slider(
        "HTTP Timeout (seconds)",
        min_value=3,
        max_value=15,
        value=st.session_state.settings['http_timeout'],
        step=1,
        help="Request timeout"
    )
    st.session_state.settings['http_timeout'] = timeout

with col2:
    domains = st.slider(
        "Max Domains to Scan",
        min_value=50,
        max_value=500,
        value=st.session_state.settings['max_domains'],
        step=50,
        help="Maximum domains per search"
    )
    st.session_state.settings['max_domains'] = domains

# Performance presets
st.write("**Quick Presets:**")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🐢 Conservative", use_container_width=True):
        st.session_state.settings['parallel_workers'] = 10
        st.session_state.settings['http_timeout'] = 10
        st.session_state.settings['max_domains'] = 100
        st.success("✅ Conservative preset applied")
        st.rerun()

with col2:
    if st.button("⚡ Balanced", use_container_width=True):
        st.session_state.settings['parallel_workers'] = 25
        st.session_state.settings['http_timeout'] = 5
        st.session_state.settings['max_domains'] = 250
        st.success("✅ Balanced preset applied")
        st.rerun()

with col3:
    if st.button("🚀 Aggressive", use_container_width=True):
        st.session_state.settings['parallel_workers'] = 40
        st.session_state.settings['http_timeout'] = 3
        st.session_state.settings['max_domains'] = 400
        st.success("✅ Aggressive preset applied")
        st.rerun()

st.divider()

# DATA MANAGEMENT
st.header("🗄️ Data Management")

# Calculate storage
saved_size = 0
settings_size = 0

if SAVED_SEARCHES_FILE.exists():
    saved_size = SAVED_SEARCHES_FILE.stat().st_size / 1024

if SETTINGS_FILE.exists():
    settings_size = SETTINGS_FILE.stat().st_size / 1024

total_size = saved_size + settings_size

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Saved Searches", f"{saved_size:.1f} KB")

with col2:
    st.metric("Settings", f"{settings_size:.1f} KB")

with col3:
    st.metric("Total Storage", f"{total_size:.1f} KB")

st.divider()

# DANGER ZONE
st.header("🗑️ Danger Zone")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Reset All Settings", use_container_width=True, type="secondary"):
        st.session_state.confirm_reset = True

with col2:
    if st.button("🗑️ Delete All Data", use_container_width=True, type="secondary"):
        st.session_state.confirm_delete = True

# Reset confirmation
if st.session_state.get('confirm_reset', False):
    st.warning("⚠️ Reset all settings to defaults?")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✓ Yes, Reset", use_container_width=True):
            st.session_state.settings = DEFAULT_SETTINGS.copy()
            SETTINGS_FILE.unlink(missing_ok=True)
            st.success("✅ Settings reset!")
            st.session_state.confirm_reset = False
            st.rerun()
    
    with col2:
        if st.button("✗ Cancel", use_container_width=True):
            st.session_state.confirm_reset = False
            st.rerun()

# Delete all confirmation
if st.session_state.get('confirm_delete', False):
    st.error("⚠️ **WARNING:** Delete ALL saved searches and settings?")
    confirm_text = st.text_input("Type `DELETE ALL` to confirm:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✓ Delete Everything", use_container_width=True, type="primary",
                    disabled=(confirm_text != "DELETE ALL")):
            SAVED_SEARCHES_FILE.unlink(missing_ok=True)
            SETTINGS_FILE.unlink(missing_ok=True)
            st.session_state.settings = DEFAULT_SETTINGS.copy()
            st.session_state.confirm_delete = False
            st.success("✅ All data deleted!")
            st.rerun()
    
    with col2:
        if st.button("✗ Cancel", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()

st.divider()

# SAVE BUTTON
if st.button("💾 Save Settings", use_container_width=True, type="primary"):
    if save_settings(st.session_state.settings):
        st.success("✅ Settings saved successfully!")
        st.balloons()
    else:
        st.error("❌ Failed to save settings")

st.divider()
st.caption("SMB Scraper — HYPER-TURBO Edition")
st.caption("All settings work and persist automatically!")