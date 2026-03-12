# AI Email Assistant

**Full-stack AI-powered email management system with Gmail OAuth, smart search, and AI draft generation**

![Status](https://img.shields.io/badge/Status-Complete-success)
![Tech](https://img.shields.io/badge/Tech-FastAPI%20%7C%20Gemini%20AI%20%7C%20Supabase-blue)
![Frontend](https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS%20SPA-indigo)

---

## What This Project Does

A B.Tech capstone project that connects to your Gmail account via OAuth 2.0, stores emails in a Supabase PostgreSQL database, and uses Google Gemini AI to generate smart draft replies. A custom Single-Page Application (SPA) built with HTML, CSS, and vanilla JavaScript is served directly by the FastAPI backend.

**Core Features:**
- Connect Gmail via OAuth 2.0 (supports multiple accounts)
- Sync emails from Gmail into a database
- Smart search — keyword + semantic hybrid search using Qdrant vector database
- AI Draft generation using Google Gemini 1.5 Flash
- Review, approve and send AI-generated replies
- Responsive dashboard with live stats

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.10+) |
| Frontend | Vanilla HTML / CSS / JavaScript (SPA) |
| Database | Supabase (PostgreSQL) |
| AI Model | Google Gemini 1.5 Flash |
| Vector Search | Qdrant Cloud |
| Email | Gmail API (OAuth 2.0) |
| Workflow Engine | LangGraph |

---

## Project Structure

```
├── unified_app.py              ← Single entry point (FastAPI server)
├── requirements.txt
├── .env                        ← All credentials (see setup below)
├── email-assistant/
│   └── config.py               ← App configuration (pydantic-settings)
├── backend/
│   ├── workflows/
│   │   ├── search_workflow.py  ← LangGraph smart search pipeline
│   │   └── draft_workflow.py   ← LangGraph AI draft pipeline
│   └── services/
│       ├── gmail/
│       │   ├── gmail_service.py
│       │   └── oauth_handler.py
│       └── qdrant/
│           ├── qdrant_service.py
│           └── embedding_service.py
└── static/                     ← Frontend SPA
    ├── index.html
    ├── css/
    │   ├── style.css
    │   └── components.css
    └── js/
        ├── api.js              ← All fetch() calls to FastAPI
        ├── app.js              ← Client-side router
        └── pages/
            ├── dashboard.js
            ├── emails.js
            ├── search.js
            └── drafts.js
```

---

## System Architecture

```
Browser (SPA)
     │  fetch() calls
     ▼
FastAPI  (unified_app.py — port 8000)
     │
     ├── Gmail API  (OAuth 2.0 — email sync + send)
     ├── Google Gemini AI  (draft generation)
     ├── Supabase PostgreSQL  (email storage, drafts, accounts)
     └── Qdrant Cloud  (vector embeddings for semantic search)
```

---

## Download

The packaged zip is available on Cloudflare R2:

```
https://pub-725e73d2257147cba36190922a682fce.r2.dev/AIEmailAssistant_v1.0.zip
```

**PowerShell:**
```powershell
Invoke-RestMethod `
    -Uri "https://pub-725e73d2257147cba36190922a682fce.r2.dev/AIEmailAssistant_v1.0.zip" `
    -OutFile "AIEmailAssistant_v1.0.zip" `
    -Method GET

Expand-Archive -Path "AIEmailAssistant_v1.0.zip" -DestinationPath "AIEmailAssistant" -Force
```

---

## Setup & Running

### 1. Fix Hardcoded Paths

The project was developed on Lightning AI (`/teamspace/studios/this_studio`). On a new machine you must update this path in **3 files** before the app will start:

**`unified_app.py`** — lines 45–55, replace:
```python
# FIND:
sys.path.append('/teamspace/studios/this_studio')
sys.path.append('/teamspace/studios/this_studio/email-assistant')
config_path = '/teamspace/studios/this_studio/email-assistant/config.py'

# REPLACE WITH:
import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.append(_BASE)
sys.path.append(_os.path.join(_BASE, 'email-assistant'))
config_path = _os.path.join(_BASE, 'email-assistant', 'config.py')
```

**`backend/services/gmail/gmail_service.py`** — lines 28, 38
**`backend/services/gmail/oauth_handler.py`** — line 42
Apply the same pattern using `os.path.dirname(os.path.abspath(__file__))` to compute the root path dynamically.

### 2. Configure .env

Create a `.env` file at the project root with:

```env
# Gmail OAuth (Google Cloud Console → APIs & Services → Credentials)
GMAIL_CLIENT_ID=your_client_id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REDIRECT_URI=http://localhost:8000/auth/gmail/callback

# Gemini AI (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=AIza...

# Supabase (Supabase dashboard → Settings → Database)
DB_HOST=your-project.supabase.co
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_PORT=6543
DB_NAME=postgres

# Security (generate random strings)
SECRET_KEY=your_32_plus_character_secret_key_here
ENCRYPTION_KEY=exactly32characterkeyhere123456

# Qdrant Cloud (optional — https://cloud.qdrant.io)
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key
```

### 3. Install & Run

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
.\venv\Scripts\Activate.ps1     # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Start the server
python unified_app.py
```

Open browser at: **http://localhost:8000**

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves the SPA frontend |
| GET | `/docs` | Interactive Swagger API docs |
| GET | `/api/auth/status` | Connected Gmail accounts |
| GET | `/api/auth/gmail` | Start Gmail OAuth flow |
| GET | `/auth/gmail/callback` | OAuth callback |
| GET | `/api/emails` | List synced emails (DB) |
| POST | `/api/sync` | Sync emails from Gmail |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/search` | Smart search |
| POST | `/api/drafts` | Generate AI draft reply |
| GET | `/api/drafts` | Draft history |
| POST | `/api/drafts/{id}/approve` | Approve and send draft |
| POST | `/api/drafts/{id}/reject` | Reject draft |
| GET | `/health` | Health check |

---

## Using the App

1. **Connect Gmail** — Dashboard → "+ Connect Gmail" → complete OAuth
2. **Sync Emails** — Click "Sync Now" on the Dashboard
3. **View Emails** — Emails page shows synced emails with database ID badges
4. **Create AI Draft** — Go to AI Drafts → enter the email's ID → choose tone & length → Generate
5. **Smart Search** — Search page → type any natural language query

---

## Known Limitations

- Gmail OAuth tokens expire after 7 days in Google "Testing" mode — re-authenticate when the account shows Inactive
- Semantic search requires Qdrant to be configured with real embeddings
- `Emails Today` stat on dashboard always shows 0 (not yet implemented)

---

## Academic Info

**Project**: B.Tech Capstone — AI Email Management System
**Student**: Charan (sreedevichintalapudi0612@gmail.com)
**Stack**: FastAPI · LangGraph · Google Gemini · Supabase · Qdrant · Vanilla JS SPA