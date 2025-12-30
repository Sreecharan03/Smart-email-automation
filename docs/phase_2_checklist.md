# Phase 2: Email Connection & Data Ingestion ⏳

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
