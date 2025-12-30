# Unified AI Email Assistant

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
