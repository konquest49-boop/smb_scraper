# login.py - Simple authentication system
import streamlit as st
import json
import hashlib
import secrets
import string
from pathlib import Path
from datetime import datetime

# User data directory
USERS_DIR = Path("users")
USERS_DIR.mkdir(exist_ok=True)
USERS_FILE = USERS_DIR / "users.json"

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_unique_code():
    """Generate a unique 6-character verification code"""
    chars = string.ascii_uppercase + string.digits
    code = ''.join(secrets.choice(chars) for _ in range(6))
    return code

def load_users():
    """Load users from file"""
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """Save users to file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def create_user(email, password):
    """Create new user account"""
    users = load_users()
    
    if email in users:
        return False, "Email already registered", None
    
    verification_code = generate_unique_code()
    
    users[email] = {
        "password": hash_password(password),
        "created_at": datetime.now().isoformat(),
        "verified": False,
        "verification_code": verification_code
    }
    
    save_users(users)
    return True, "Account created", verification_code

def verify_user(email, code):
    """Verify user email with code"""
    users = load_users()
    
    if email not in users:
        return False, "Email not found"
    
    if users[email].get("verification_code") == code:
        users[email]["verified"] = True
        users[email]["verified_at"] = datetime.now().isoformat()
        save_users(users)
        return True, "Email verified"
    
    return False, "Invalid code"

def authenticate_user(email, password):
    """Authenticate user with email and password"""
    users = load_users()
    
    if email not in users:
        return False, "Email not found"
    
    user = users[email]
    
    if not user.get("verified", False):
        return False, "Please verify your email first"
    
    if user["password"] == hash_password(password):
        return True, "Login successful"
    
    return False, "Incorrect password"

def get_user_data_dir(email):
    """Get user-specific data directory"""
    user_dir = USERS_DIR / email.replace("@", "_at_").replace(".", "_")
    user_dir.mkdir(exist_ok=True)
    return user_dir

def is_logged_in():
    """Check if user is logged in"""
    return st.session_state.get('logged_in', False)

def get_current_user():
    """Get current logged in user email"""
    return st.session_state.get('user_email', None)

def login_user(email):
    """Log in a user"""
    st.session_state.logged_in = True
    st.session_state.user_email = email

def logout():
    """Logout current user"""
    st.session_state.logged_in = False
    st.session_state.user_email = None