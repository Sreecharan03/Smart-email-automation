# ====================================
# UNIFIED AI EMAIL ASSISTANT - STREAMLIT RUNNER
# ====================================
# Simple script to run the Streamlit test interface
# Usage: python run_streamlit.py

import os
import sys
import subprocess

def main():
    """Run the Streamlit test app"""
    print("🚀 Starting Gmail Assistant Test Interface")
    print("=" * 50)
    
    # Set working directory to project root
    project_root = "/teamspace/studios/this_studio"
    os.chdir(project_root)
    
    # Add project root to Python path
    sys.path.insert(0, project_root)
    
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python path: {sys.path[0]}")
    
    # Streamlit configuration
    streamlit_config = [
        "streamlit", "run",
        "frontend/streamlit_app.py",
        "--server.port=30000",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false"
    ]
    
    print(f"🌐 Starting Streamlit on http://localhost:30000")
    print(f"💡 Use this interface to test real Gmail OAuth!")
    print(f"📧 You can connect your actual Gmail account safely")
    print("=" * 50)
    
    try:
        # Run Streamlit
        subprocess.run(streamlit_config)
    except KeyboardInterrupt:
        print("\n👋 Streamlit stopped by user")
    except Exception as e:
        print(f"❌ Error running Streamlit: {e}")

if __name__ == "__main__":
    main()