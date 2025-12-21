# pages/0_Dashboard.py
import streamlit as st
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from login import is_logged_in, get_current_user, logout, get_user_data_dir

st.set_page_config(page_title="Dashboard", page_icon="⚡", layout="wide")

# Hide Auth from sidebar
st.markdown('<style>[data-testid="stSidebarNav"] li:first-child{display:none}</style>', unsafe_allow_html=True)

# Check login
if not is_logged_in():
    st.warning("🔒 Please login first")
    if st.button("Go to Login", type="primary"):
        st.switch_page("Auth.py")
    st.stop()

# Add logout to sidebar
with st.sidebar:
    st.divider()
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        logout()
        st.switch_page("Auth.py")

# Rest of your dashboard code...
user_email = get_current_user()
st.title(f"⚡ Welcome, {user_email}")