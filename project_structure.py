# ====================================
# UNIFIED AI EMAIL ASSISTANT - PROJECT STRUCTURE SETUP
# ====================================
# Creates complete folder structure and organizes files for the email assistant project
# Ensures proper separation of concerns and clean project organization

import os
import shutil

def create_directory_structure():
    """
    Creates the complete directory structure for the email assistant project
    """
    
    # Define the project structure
    project_structure = {
        "backend": {
            "api": ["__init__.py"],
            "workflows": ["__init__.py"], 
            "models": ["__init__.py"],
            "services": {
                "gmail": ["__init__.py"],
                "outlook": ["__init__.py"],
                "qdrant": ["__init__.py"]
            },
            "utils": ["__init__.py"]
        },
        "frontend": {
            "pages": ["__init__.py"],
            "components": ["__init__.py"],
            "static": {
                "css": [],
                "js": [],
                "images": []
            }
        },
        "database": {
            "migrations": [],
            "seeds": []
        },
        "tests": {
            "unit": ["__init__.py"],
            "integration": ["__init__.py"],
            "fixtures": []
        },
        "docs": {
            "api": [],
            "user_guides": []
        },
        "logs": [],
        "uploads": [],
        "scripts": [],
        "config": {
            "environments": []
        }
    }
    
    def create_dirs_and_files(structure, base_path=""):
        """Recursively create directories and files"""
        for name, contents in structure.items():
            dir_path = os.path.join(base_path, name)
            
            # Create directory
            os.makedirs(dir_path, exist_ok=True)
            print(f"📁 Created directory: {dir_path}")
            
            if isinstance(contents, dict):
                # Recursively create subdirectories
                create_dirs_and_files(contents, dir_path)
            elif isinstance(contents, list):
                # Create files in this directory
                for file_name in contents:
                    file_path = os.path.join(dir_path, file_name)
                    if not os.path.exists(file_path):
                        with open(file_path, 'w') as f:
                            if file_name == "__init__.py":
                                f.write(f'"""\n{name.title()} module for Email Assistant\n"""\n')
                            else:
                                f.write("")
                        print(f"📄 Created file: {file_path}")
    
    print("🏗️ Creating project directory structure...")
    create_dirs_and_files(project_structure)
    
    return True

def create_gitignore():
    """
    Creates .gitignore file with appropriate exclusions
    """
    gitignore_content = """# ====================================
# EMAIL ASSISTANT - GIT IGNORE
# ====================================

# Environment variables (NEVER commit secrets!)
.env
.env.local
.env.production
.env.staging

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
env.bak/
venv.bak/
cloudspace/

# IDE and editors
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Database
*.db
*.sqlite
*.sqlite3

# OAuth credentials (NEVER commit!)
*client_secret*.json
*credentials*.json
*token*.json

# Uploads and temporary files
uploads/
temp/
tmp/
*.tmp

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Jupyter Notebook
.ipynb_checkpoints

# PyCharm
.idea/

# Streamlit
.streamlit/

# Email data (sensitive)
email_data/
message_cache/

# API keys backup
api_keys_backup/

# Test outputs
test_outputs/
test_reports/

# Documentation builds
docs/_build/
"""
    
    gitignore_path = ".gitignore"
    with open(gitignore_path, 'w') as f:
        f.write(gitignore_content)
    
    print(f"🛡️ Created .gitignore file")

def create_readme():
    """
    Creates README.md with project information
    """
    readme_content = """# Unified AI Email Assistant

A B.Tech level project that unifies Gmail and Outlook into a single smart interface with AI-powered features.

## 🚀 Features

- **Unified Inbox**: Connect Gmail and Outlook accounts via OAuth
- **Smart Search**: Natural language search across all emails using hybrid search (BM25 + vector similarity)
- **AI-Assisted Drafting**: Generate email drafts with human approval using Google Gemini
- **Daily Summaries**: Automated morning email digests with action items
- **Secure**: OAuth-based authentication with encrypted token storage

## 🏗️ Architecture

- **Backend**: FastAPI with LangGraph workflows
- **Database**: Supabase (PostgreSQL) with vector embeddings
- **Vector Search**: Qdrant for semantic search
- **AI**: Google Gemini API for draft generation and summarization
- **Frontend**: Streamlit web interface

## 📋 Project Structure

```
email-assistant/
├── backend/              # FastAPI backend services
│   ├── api/             # REST API endpoints
│   ├── workflows/       # LangGraph workflow definitions
│   ├── models/          # Database models
│   └── services/        # Email provider services
├── frontend/            # Streamlit web interface
├── database/            # Database migrations and setup
├── config/              # Configuration files
├── logs/                # Application logs
└── docs/               # Documentation
```

## 🛠️ Setup Instructions

### Phase 1: Foundation Setup ✅
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Test configuration
python config.py

# Setup database
python supabase_setup.py
```

### Phase 2: Email Connection (Next)
- Implement Gmail OAuth flow
- Add email ingestion pipeline
- Set up embedding generation

### Phase 3: Smart Search
- Implement hybrid search with Qdrant
- Create LangGraph search workflow
- Add natural language query processing

### Phase 4: AI Drafting
- Build draft generation service
- Implement human approval workflow
- Add safety checks

### Phase 5: Frontend & Daily Summary
- Create Streamlit interface
- Implement daily email summarization
- Add scheduling for morning digests

### Phase 6: Demo & Polish
- Prepare demonstration
- Add error handling
- Create documentation

## 🔑 Required API Keys

1. **Google Cloud Console**: Gmail API + OAuth credentials
2. **Google AI Studio**: Gemini API key
3. **Supabase**: Database connection (included)
4. **Qdrant Cloud**: Vector database (optional)
5. **Azure Portal**: Microsoft Graph API (optional)

## 🎯 Current Status

- ✅ Environment configuration
- ✅ Database setup (7 tables created)
- ✅ Configuration management
- ⏳ Email connection (Phase 2)

## 📊 Database Schema

### Core Tables:
- `email_accounts` - OAuth connections
- `email_messages` - All email data
- `message_embeddings` - Vector search data
- `email_drafts` - AI-generated drafts
- `importance_scores` - Email prioritization
- `daily_digests` - Summary reports
- `system_logs` - Application monitoring

## 🔒 Security Features

- OAuth 2.0 for email access
- Encrypted token storage
- SSL connections to Supabase
- Human approval for AI drafts
- No plaintext credential storage

## 🚦 Development Phases

Each phase builds upon the previous one:

1. **Foundation** ✅ - Environment, database, configuration
2. **Connection** ⏳ - OAuth flows, email ingestion
3. **Search** - Hybrid search implementation
4. **Drafting** - AI-powered reply generation
5. **Interface** - Web UI and daily summaries
6. **Polish** - Testing, documentation, demo

## 📝 License

This is a B.Tech academic project for demonstration purposes.

## 👨‍💻 Author

Developed as part of B.Tech curriculum to demonstrate:
- OAuth integration
- Vector databases and semantic search
- LLM orchestration with LangGraph
- Modern web application architecture
"""

    readme_path = "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"📖 Created README.md")

def organize_existing_files():
    """
    Move existing files to their proper locations in the project structure
    """
    print("\n📦 Organizing existing project files...")
    
    # Define file movements
    file_mappings = {
        # Keep these in root
        "config.py": "config.py",
        "config_fixed.py": "config_fixed.py", 
        "config_supabase.py": "config_supabase.py",
        "requirements.txt": "requirements.txt",
        ".env": ".env",
        
        # Move to appropriate directories
        "database_models.py": "backend/models/database_models.py",
        "supabase_setup.py": "database/supabase_setup.py",
    }
    
    moved_files = []
    for source, destination in file_mappings.items():
        if os.path.exists(source) and source != destination:
            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(destination)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            
            # Move file
            try:
                shutil.move(source, destination)
                moved_files.append(f"{source} → {destination}")
                print(f"📁 Moved: {source} → {destination}")
            except Exception as e:
                print(f"⚠️ Could not move {source}: {e}")
    
    return moved_files

def create_phase_checklists():
    """
    Create phase checklist files for project tracking
    """
    
    phases = {
        "phase_1_checklist.md": """# Phase 1: Foundation Setup ✅

## Completed Tasks
- ✅ Environment configuration (.env)
- ✅ Python dependencies (requirements.txt) 
- ✅ Configuration management (config.py)
- ✅ Database models (database_models.py)
- ✅ Database setup (supabase_setup.py)
- ✅ Project structure organization

## Verified Working
- ✅ Supabase connection successful
- ✅ All 7 database tables created
- ✅ Indexes and triggers set up
- ✅ Gmail OAuth credentials configured
- ✅ Gemini API key working

## Ready for Phase 2! 🚀
""",
        
        "phase_2_checklist.md": """# Phase 2: Email Connection & Data Ingestion ⏳

## Tasks to Complete
- ⏳ Gmail OAuth flow implementation
- ⏳ Email service classes (Gmail/Outlook)
- ⏳ Message fetching and normalization
- ⏳ Embedding generation pipeline
- ⏳ Background sync service
- ⏳ Error handling and logging

## Files to Create
- `backend/services/gmail/gmail_service.py`
- `backend/services/gmail/oauth_handler.py`
- `backend/api/auth_routes.py`
- `backend/workflows/email_ingestion.py`

## Success Criteria
- [ ] Successfully connect Gmail account via OAuth
- [ ] Fetch and store latest 100 emails
- [ ] Generate embeddings for email content
- [ ] Set up periodic background sync
""",
        
        "phase_3_checklist.md": """# Phase 3: Smart Search Implementation ⏳

## Tasks to Complete
- ⏳ Qdrant vector database setup
- ⏳ Hybrid search implementation (BM25 + vector)
- ⏳ LangGraph search workflow
- ⏳ Natural language query processing
- ⏳ Search API endpoints

## Success Criteria
- [ ] Natural language search working
- [ ] Combined keyword and semantic search
- [ ] Search results ranked by relevance
- [ ] Response time under 3 seconds
""",
        
        "remaining_phases_overview.md": """# Remaining Phases Overview

## Phase 4: AI Draft Generation
- AI-powered reply drafting with Gemini
- Human-in-the-loop approval system
- Safety checks and content filtering
- Tone and style matching

## Phase 5: Frontend & Daily Summary  
- Streamlit web interface
- Daily email summarization
- Morning digest delivery
- User settings and preferences

## Phase 6: Polish & Demo
- End-to-end testing
- Error handling improvement
- Documentation completion
- Demo preparation and recording
"""
    }
    
    # Create docs directory if it doesn't exist
    os.makedirs("docs", exist_ok=True)
    
    for filename, content in phases.items():
        filepath = os.path.join("docs", filename)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"📋 Created: {filepath}")

def main():
    """
    Main function to set up complete project structure
    """
    print("🏗️ Email Assistant Project Structure Setup")
    print("=" * 50)
    
    try:
        # Create directory structure
        create_directory_structure()
        
        # Create essential files
        print(f"\n📄 Creating project files...")
        create_gitignore()
        create_readme()
        
        # Create phase tracking files  
        print(f"\n📋 Creating phase checklists...")
        create_phase_checklists()
        
        # Organize existing files
        moved_files = organize_existing_files()
        
        # Show summary
        print(f"\n🎉 Project structure setup complete!")
        print(f"📁 Directory structure created")
        print(f"📄 Essential files created")
        print(f"📦 {len(moved_files)} files organized")
        
        print(f"\n📋 What's Next:")
        print(f"1. Review the project structure")
        print(f"2. Check docs/phase_1_checklist.md - ✅ Complete!")
        print(f"3. Start Phase 2: Email Connection")
        print(f"4. Follow docs/phase_2_checklist.md")
        
        print(f"\n🚀 Ready to begin Phase 2 development!")
        
        return True
        
    except Exception as e:
        print(f"❌ Project structure setup failed: {e}")
        return False

if __name__ == "__main__":
    main()