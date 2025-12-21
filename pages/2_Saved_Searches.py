# pages/2_Saved_Searches.py
import streamlit as st
import json
import pandas as pd
import csv
import io
import time
from datetime import datetime
from pathlib import Path
import sys

st.markdown('<style>[data-testid="stSidebarNav"] li:first-child{display:none}</style>', unsafe_allow_html=True)

# USER ISOLATION
sys.path.insert(0, str(Path(__file__).parent.parent))
from login import is_logged_in, get_current_user, logout, get_user_data_dir

# Check authentication
if not is_logged_in():
    st.warning("🔒 Please login first")
    if st.button("Go to Login", type="primary"):
        st.switch_page("Auth.py")
    st.stop()

# Get THIS user's data directory
current_user_email = get_current_user()
user_data_dir = get_user_data_dir(current_user_email)
SAVED_SEARCHES_FILE = user_data_dir / "saved_searches.json"

def load_saved_searches():
    """Load THIS USER's saved searches"""
    if SAVED_SEARCHES_FILE.exists():
        try:
            with open(SAVED_SEARCHES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_all_searches(searches):
    """Save searches to THIS USER's file"""
    with open(SAVED_SEARCHES_FILE, 'w') as f:
        json.dump(searches, f, indent=2)

def delete_search(search_name):
    """Delete a specific search"""
    searches = load_saved_searches()
    if search_name in searches:
        del searches[search_name]
        save_all_searches(searches)
        return True
    return False

def rename_search(old_name, new_name):
    """Rename a search"""
    searches = load_saved_searches()
    if old_name in searches and new_name not in searches:
        searches[new_name] = searches.pop(old_name)
        save_all_searches(searches)
        return True
    return False

def update_search_leads(search_name, updated_leads):
    """Update leads for a specific search"""
    searches = load_saved_searches()
    if search_name in searches:
        searches[search_name]["leads"] = updated_leads
        searches[search_name]["lead_count"] = len(updated_leads)
        searches[search_name]["last_modified"] = datetime.now().isoformat()
        save_all_searches(searches)
        return True
    return False

# Session state
if 'selected_search' not in st.session_state:
    st.session_state.selected_search = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'emails_to_delete' not in st.session_state:
    st.session_state.emails_to_delete = set()

# Header
col1, col2 = st.columns([5, 1])
with col1:
    st.title("💾 Saved Searches")
    st.caption(f"Logged in as: **{current_user_email}**")
with col2:
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.switch_page("Auth.py")

st.divider()

# Load THIS USER's searches
saved_searches = load_saved_searches()

if not saved_searches:
    st.info("🔭 No saved searches yet. Complete a search on the 'New Search' page and save the results!")
    st.stop()

# Calculate stats
total_leads = sum(s.get('lead_count', 0) for s in saved_searches.values())
total_searches = len(saved_searches)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Saved Searches", total_searches)
with col2:
    st.metric("Total Leads Saved", total_leads)
with col3:
    avg_per_search = total_leads / total_searches if total_searches > 0 else 0
    st.metric("Avg Leads/Search", f"{avg_per_search:.0f}")

st.divider()

# LIST OR DETAIL VIEW
if st.session_state.selected_search is None:
    st.subheader("📋 Your Saved Searches")
    
    sorted_searches = sorted(
        saved_searches.items(),
        key=lambda x: x[1].get('timestamp', ''),
        reverse=True
    )
    
    for search_name, search_data in sorted_searches:
        lead_count = search_data.get('lead_count', 0)
        timestamp = search_data.get('timestamp', '')
        metadata = search_data.get('metadata', {})
        
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%B %d, %Y at %I:%M %p')
        except:
            time_str = "Unknown date"
        
        industries = metadata.get('industries', [])
        cities = metadata.get('cities', [])
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                if st.button(f"📊 **{search_name}**", key=f"view_{search_name}", use_container_width=True):
                    st.session_state.selected_search = search_name
                    st.session_state.edit_mode = False
                    st.session_state.emails_to_delete = set()
                    st.rerun()
            
            with col2:
                st.write(f"**{lead_count} leads**")
                st.caption(time_str)
            
            with col3:
                st.write("**Industries:**")
                for ind in industries[:2]:
                    st.caption(f"• {ind}")
            
            with col4:
                st.write("**Locations:**")
                for city in cities[:2]:
                    st.caption(f"• {city}")
            
            st.divider()
    
    # Bulk operations
    st.subheader("⚙️ Bulk Operations")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Delete ALL Searches", use_container_width=True, type="secondary"):
            st.session_state.confirm_delete_all = True
    
    with col2:
        if st.button("📧 Export ALL Emails", use_container_width=True):
            all_emails = set()
            for search_data in saved_searches.values():
                for lead in search_data.get('leads', []):
                    all_emails.add(lead['email'])
            
            email_csv = io.StringIO()
            email_writer = csv.writer(email_csv)
            email_writer.writerow(["email"])
            for email in sorted(all_emails):
                email_writer.writerow([email])
            
            st.download_button(
                "⬇️ Download All Emails CSV",
                email_csv.getvalue(),
                file_name=f"all_emails_{int(time.time())}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    if st.session_state.get('confirm_delete_all', False):
        st.error("⚠️ **WARNING:** Delete ALL saved searches? This cannot be undone!")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✓ Yes, Delete Everything", use_container_width=True, type="primary"):
                SAVED_SEARCHES_FILE.unlink(missing_ok=True)
                st.session_state.selected_search = None
                st.session_state.confirm_delete_all = False
                st.success("All searches deleted!")
                time.sleep(1)
                st.rerun()
        
        with col2:
            if st.button("✗ Cancel", use_container_width=True):
                st.session_state.confirm_delete_all = False
                st.rerun()

else:
    # DETAIL VIEW
    search_name = st.session_state.selected_search
    search_data = saved_searches.get(search_name)
    
    if not search_data:
        st.error("Search not found!")
        st.session_state.selected_search = None
        st.stop()
    
    leads = search_data.get('leads', [])
    metadata = search_data.get('metadata', {})
    timestamp = search_data.get('timestamp', '')
    
    if st.button("⬅️ Back to All Searches", type="secondary"):
        st.session_state.selected_search = None
        st.session_state.edit_mode = False
        st.session_state.emails_to_delete = set()
        st.rerun()
    
    st.divider()
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.header(f"📊 {search_name}")
        try:
            dt = datetime.fromisoformat(timestamp)
            st.caption(f"Saved on {dt.strftime('%B %d, %Y at %I:%M %p')}")
        except:
            pass
    
    with col2:
        if st.button("✏️ Rename", use_container_width=True):
            st.session_state.show_rename_dialog = True
    
    with col3:
        if st.button("🗑️ Delete Search", use_container_width=True, type="secondary"):
            st.session_state.confirm_delete = True
    
    if st.session_state.get('show_rename_dialog', False):
        with st.form("rename_form"):
            st.subheader("✏️ Rename Search")
            new_name = st.text_input("New name", value=search_name)
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("✓ Rename", use_container_width=True):
                    if new_name and new_name != search_name:
                        if rename_search(search_name, new_name):
                            st.success(f"Renamed to '{new_name}'!")
                            st.session_state.selected_search = new_name
                            st.session_state.show_rename_dialog = False
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Name already exists or invalid!")
            
            with col2:
                if st.form_submit_button("✗ Cancel", use_container_width=True):
                    st.session_state.show_rename_dialog = False
                    st.rerun()
    
    if st.session_state.get('confirm_delete', False):
        st.error(f"⚠️ Delete '{search_name}' with {len(leads)} leads? This cannot be undone!")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✓ Yes, Delete This Search", use_container_width=True, type="primary"):
                if delete_search(search_name):
                    st.success("Deleted successfully!")
                    st.session_state.selected_search = None
                    st.session_state.confirm_delete = False
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            if st.button("✗ Cancel", use_container_width=True):
                st.session_state.confirm_delete = False
                st.rerun()
    
    st.divider()
    
    # Display leads
    st.subheader(f"📧 {len(leads)} Leads in This Search")
    
    if not leads:
        st.info("No leads in this search.")
    else:
        df = pd.DataFrame(leads)
        
        if 'confidence' in df.columns:
            df = df.sort_values('confidence', ascending=False)
        
        display_cols = ['email', 'confidence', 'domain_root', 'title']
        display_cols = [col for col in display_cols if col in df.columns]
        
        if display_cols:
            display_df = df[display_cols].copy()
            
            column_names = {
                'email': 'Email',
                'confidence': 'Confidence %',
                'domain_root': 'Domain',
                'title': 'Site Title'
            }
            display_df.rename(columns=column_names, inplace=True)
            
            st.dataframe(display_df, use_container_width=True, height=500)

st.divider()
st.caption(f"👤 {current_user_email} • Data: {user_data_dir}")