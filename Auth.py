# Auth.py - Standalone Login/Signup Page (NOT in sidebar)
import streamlit as st
import sys
import re
from pathlib import Path

# Add directory to path
sys.path.insert(0, str(Path(__file__).parent))

from login import (
    is_logged_in, 
    get_current_user, 
    login_user, 
    logout, 
    create_user, 
    verify_user, 
    authenticate_user
)

# Configure page WITHOUT sidebar
st.set_page_config(
    page_title="SMB Scraper - Login", 
    page_icon="🔐", 
    layout="centered",
    initial_sidebar_state="collapsed"
)
st.set_page_config(
    page_title="SMB Scraper - Login", 
    page_icon="🔐", 
    layout="centered",
    initial_sidebar_state="collapsed"
)
st.markdown('<style>[data-testid="stSidebarNav"] li:first-child{display:none}</style>', unsafe_allow_html=True)

# ADD THIS NEW CODE HERE:
# Custom sidebar control - hide Auth, show only pages
st.markdown("""
<style>
    /* Hide the main script from sidebar */
    [data-testid="stSidebarNav"] li:first-child {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Hide sidebar completely with CSS
st.markdown("""
<style>
    [data-testid="collapsedControl"] {display: none}
    section[data-testid="stSidebar"] {display: none}
</style>
""", unsafe_allow_html=True)

def is_valid_email(email):
    """Validate email format - must be a real email structure"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Check if already logged in - redirect to dashboard
if is_logged_in():
    st.success(f"✅ You're already logged in as {get_current_user()}")
    st.info("👉 Please navigate to **Dashboard** using the sidebar menu.")
    
    # Show sidebar for logged-in users
    st.markdown("""
    <style>
        [data-testid="collapsedControl"] {display: block !important}
        section[data-testid="stSidebar"] {display: block !important}
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()
    st.stop()

# Header
st.title("⚡ SMB Scraper")
st.caption("Sign in to start finding leads")
st.divider()

# Tabs
tab1, tab2 = st.tabs(["🔑 Sign In", "📝 Sign Up"])

# SIGN IN TAB
with tab1:
    st.subheader("Sign In")
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="your@email.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        
        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("❌ Please fill in all fields")
            elif not is_valid_email(email):
                st.error("❌ Please enter a valid email address")
            else:
                success, message = authenticate_user(email, password)
                if success:
                    login_user(email)
                    st.success("✅ Login successful!")
                    st.balloons()
                    st.info("👉 Now navigate to **Dashboard** using the sidebar menu (☰)")
                    # Show sidebar after login
                    st.markdown("""
                    <style>
                        [data-testid="collapsedControl"] {display: block !important}
                        section[data-testid="stSidebar"] {display: block !important}
                    </style>
                    """, unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

# SIGN UP TAB
with tab2:
    st.subheader("Create Account")
    
    with st.form("signup_form"):
        new_email = st.text_input("Email", placeholder="your@email.com", key="signup_email")
        new_password = st.text_input("Password", type="password", placeholder="••••••••", key="signup_pass")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="••••••••")
        
        submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        
        if submitted:
            if not new_email or not new_password or not confirm_password:
                st.error("❌ Please fill in all fields")
            elif not is_valid_email(new_email):
                st.error("❌ Please enter a valid email address (e.g., user@example.com)")
            elif len(new_password) < 6:
                st.error("❌ Password must be at least 6 characters")
            elif new_password != confirm_password:
                st.error("❌ Passwords don't match")
            else:
                success, message, code = create_user(new_email, new_password)
                if success:
                    st.success("✅ Account created!")
                    st.info("**📧 Your verification code:**")
                    st.code(code, language=None)
                    st.caption("⚠️ Save this code! You'll need it to verify your email.")
                    st.session_state.pending_email = new_email
                else:
                    st.error(f"❌ {message}")
    
    # Verification section
    if st.session_state.get('pending_email'):
        st.divider()
        st.subheader("✉️ Verify Your Email")
        
        with st.form("verify_form"):
            st.write(f"Verifying: **{st.session_state.pending_email}**")
            verify_code = st.text_input("Enter Verification Code", placeholder="ABC123")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("✓ Verify", use_container_width=True, type="primary"):
                    success, message = verify_user(st.session_state.pending_email, verify_code)
                    if success:
                        st.success("✅ Email verified! You can now sign in.")
                        st.balloons()
                        del st.session_state.pending_email
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            
            with col2:
                if st.form_submit_button("✗ Cancel", use_container_width=True):
                    del st.session_state.pending_email
                    st.rerun()

# Footer
st.divider()
st.caption("🔐 Secure authentication • User data isolated • Valid email required")
st.caption("⚠️ Each user has their own isolated data directory")