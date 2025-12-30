# ====================================
# UNIFIED AI EMAIL ASSISTANT - STREAMLIT TEST INTERFACE
# ====================================
# Simple Streamlit interface to test Gmail OAuth functionality
# Allows users to connect their Gmail accounts and test the OAuth flow

import streamlit as st
import sys
import os

# Add project root to path
sys.path.append('/teamspace/studios/this_studio')
sys.path.append('/teamspace/studios/this_studio/email-assistant')

# Import our modules
from backend.services.gmail.oauth_handler import create_oauth_handler
from backend.services.gmail.gmail_service import create_gmail_service

# Page configuration
st.set_page_config(
    page_title="Gmail Assistant Test",
    page_icon="📧",
    layout="wide"
)

# Title and description
st.title("📧 Gmail Assistant Test Interface")
st.markdown("Test Gmail OAuth integration and email management")

# Sidebar for configuration
with st.sidebar:
    st.header("🔧 Configuration")
    st.info("This is a test interface for Gmail OAuth functionality")
    
    # Test if OAuth handler can be initialized
    try:
        handler = create_oauth_handler()
        st.success("✅ OAuth Handler Ready")
    except Exception as e:
        st.error(f"❌ OAuth Handler Error: {e}")

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.header("🔐 Gmail OAuth Test")
    st.markdown("Test the Gmail OAuth authentication flow")
    
    # Generate authorization URL
    try:
        handler = create_oauth_handler()
        user_id = st.text_input("User ID", value="test_user", help="Unique identifier for this session")
        
        if st.button("🚀 Generate Auth URL"):
            auth_url, state = handler.generate_authorization_url(user_id)
            st.success("✅ Authorization URL generated!")
            st.code(auth_url, language=None)
            st.info("Open this URL in your browser to authorize Gmail access")
            
            # Display state token
            with st.expander("🔑 State Token (for debugging)"):
                st.code(state)
                
    except Exception as e:
        st.error(f"❌ Error generating auth URL: {e}")

with col2:
    st.header("📊 Account Status")
    st.markdown("Check connected Gmail accounts")
    
    # Test account status
    try:
        # This would normally query the database for connected accounts
        # For now, show a placeholder
        st.info("Account status checking requires database connection")
        
        if st.button("🔍 Check Account Status"):
            st.warning("Database connection required for full functionality")
            
    except Exception as e:
        st.error(f"❌ Error checking status: {e}")

# Gmail Service Test
st.header("📧 Gmail Service Test")
st.markdown("Test Gmail API functionality")

try:
    # Test Gmail service creation
    test_account_id = 1
    gmail_service = create_gmail_service(test_account_id)
    st.success("✅ Gmail Service Created")
    
    # Test buttons
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("📋 Get Labels"):
            labels = gmail_service.get_labels()
            st.write(f"Found {len(labels)} labels")
            if labels:
                st.json([label['name'] for label in labels[:5]])  # Show first 5
            
    with col4:
        if st.button("👤 Get Account Info"):
            account_info = gmail_service.get_account_info()
            if account_info:
                st.json(account_info)
            else:
                st.warning("No valid credentials found")
                
except Exception as e:
    st.error(f"❌ Gmail Service Error: {e}")
    st.info("Make sure you have valid OAuth credentials configured")

# Footer
st.divider()
st.markdown("""
### 📋 Test Instructions:
1. **Generate Auth URL**: Click "Generate Auth URL" to create a Gmail authorization link
2. **Authorize**: Open the link in your browser and authorize access to your Gmail account
3. **Test Features**: Use the Gmail service buttons to test API functionality

### 💡 Notes:
- Any Gmail account can be used (including charanch53030@gmail.com)
- The app needs to be registered with Google Cloud Console for OAuth
- This is a development/testing interface
""")

st.info("💡 This interface allows you to test Gmail OAuth with any Gmail account")