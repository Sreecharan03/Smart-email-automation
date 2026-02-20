# 🤖 Unified AI Email Assistant

**Intelligent email management system with semantic search and AI-powered workflows**

![Project Status](https://img.shields.io/badge/Status-Phase%203%20Complete-success)
![Progress](https://img.shields.io/badge/Progress-85%25-brightgreen)
![Tech Stack](https://img.shields.io/badge/Tech-LangGraph%20%7C%20FastAPI%20%7C%20Qdrant-blue)

## 📖 Project Overview

The Unified AI Email Assistant is a B.Tech capstone project that transforms email management through AI-powered semantic search, multi-agent workflows, and intelligent automation. It consolidates Gmail and Outlook accounts into a single smart interface with natural language search capabilities.

### 🎯 Core Problem Solved
- **Email Overload**: Users struggle with high-volume email management across multiple accounts
- **Poor Search**: Traditional keyword search fails to capture semantic intent
- **Time Waste**: Manual email processing, drafting, and prioritization consumes significant time

### 💡 Solution Approach
- **Semantic Search**: Vector embeddings for intelligent email retrieval
- **Multi-Agent Workflows**: LangGraph orchestration for complex email processing
- **Hybrid Search**: Combines keyword matching with vector similarity
- **Natural Language Interface**: Chat-style email queries like "payments from last week"

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Services      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Streamlit Chat  │───▶│ FastAPI Server  │───▶│ Gmail API       │
│ Search Interface│    │ LangGraph       │    │ Google Gemini   │
│ Result Display  │    │ Workflows       │    │ Qdrant Vector   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Database      │
                       ├─────────────────┤
                       │ Supabase        │
                       │ PostgreSQL      │
                       │ 7 Tables        │
                       │ Vector Storage  │
                       └─────────────────┘
```

## 🔄 Workflow Architecture

### 1. Email Ingestion Pipeline
```
Gmail API → Parse Headers → Store Database → Generate Embeddings → Index Vectors
```

### 2. Smart Search Pipeline
```
Natural Query → Parse Filters → Keyword Search → Vector Search → Hybrid Fusion → Ranked Results
```

### 3. Multi-Agent System (LangGraph)
- **Ingestion Agent**: Processes and stores emails
- **Search Agent**: Handles intelligent search queries
- **Embedding Agent**: Generates vector representations
- **Fusion Agent**: Combines search results

## 📊 Project Progress

### ✅ **Phase 1: Foundation (100% Complete)**
- [x] Project structure setup
- [x] Database schema design (7 tables)
- [x] Configuration management
- [x] OAuth integration planning

### ✅ **Phase 2: Core Infrastructure (100% Complete)**
- [x] Supabase PostgreSQL setup
- [x] Gmail OAuth authentication
- [x] Database models and migrations
- [x] FastAPI backend foundation

### ✅ **Phase 3: AI Intelligence (95% Complete)**
- [x] Email ingestion workflows (3 variants)
- [x] Google Gemini embedding service
- [x] Qdrant vector database integration
- [x] Smart search workflow
- [x] Hybrid search (keyword + semantic)
- [x] Natural language query parsing
- [x] LangGraph multi-agent orchestration
- [x] Streamlit chatbot interface
- [ ] Production optimization (pending)

### ⏳ **Phase 4: Advanced Features (Planned)**
- [ ] AI email drafting
- [ ] Daily summary generation
- [ ] Microsoft Outlook integration
- [ ] Advanced analytics dashboard

## 📁 File Structure

```
unified-ai-email-assistant/
├── backend/
│   ├── workflows/                 # LangGraph Workflows
│   │   ├── email_ingestion_workflow.py      ✅
│   │   ├── real_gmail_ingestion_workflow.py ✅
│   │   ├── endpoint_gmail_ingestion.py      ✅
│   │   └── search_workflow.py               ✅
│   └── services/                  # Core Services
│       ├── embedding_service.py             ✅
│       └── qdrant/
│           └── qdrant_service.py            ✅
├── frontend/
│   └── streamlit_chatbot.py                 ✅
├── email-assistant/               # Configuration
│   ├── config.py                            ✅
│   ├── database_models.py                   ✅
│   ├── supabase_setup.py                    ✅
│   └── requirements.txt                     ✅
└── docs/                         # Documentation
    └── README.md                            ✅
```

**Total Files Created: 11 Production Files**

## 🛠️ Technology Stack

### **Backend**
- **LangGraph**: Multi-agent workflow orchestration
- **FastAPI**: High-performance web framework
- **PostgreSQL**: Primary data storage via Supabase
- **Qdrant**: Vector database for semantic search

### **AI Services**
- **Google Gemini API**: Text embeddings and AI processing
- **Vector Embeddings**: 768-dimensional semantic representations
- **Hybrid Search**: BM25 + Cosine similarity fusion

### **Frontend**
- **Streamlit**: Interactive web interface
- **Custom CSS**: Cyberpunk-themed design
- **Real-time Chat**: Conversational search interface

### **Infrastructure**
- **Supabase**: Database hosting and management
- **Qdrant Cloud**: Vector database hosting
- **Lightning AI**: Development environment

## 🎯 Key Features Implemented

### 🔍 **Smart Search Engine**
- Natural language query processing
- Date range filtering ("last week", "december 2024")
- Sender-based filtering ("emails from john@company.com")
- Semantic similarity search using vector embeddings
- Hybrid result fusion with relevance scoring
- Sub-2-second response times

### 📧 **Email Processing**
- Real Gmail API integration with OAuth2
- Incremental sync with cursor-based pagination
- Email normalization and metadata extraction
- Automatic embedding generation for search
- Deduplication and error handling

### 🤖 **AI-Powered Interface**
- Conversational chatbot with memory
- Search suggestions and examples
- Beautiful result cards with relevance scores
- Real-time search statistics
- Mobile-responsive design

## 📈 Performance Metrics

- **Search Speed**: < 2 seconds average response time
- **Data Processing**: 1,355+ real emails ingested and processed
- **Embedding Generation**: 15+ vector embeddings created
- **Search Accuracy**: Hybrid scoring with relevance ranking
- **Database Efficiency**: 7-table normalized schema with indexes

## 🧪 Testing Results

### **Email Ingestion Test**
```bash
✅ Successfully ingested 10 real Gmail emails
✅ Processing Time: 0.00 seconds  
✅ Zero errors in workflow execution
```

### **Search Functionality Test**
```bash
Query: "invoice payment reminder"
✅ Found 5 relevant results
✅ Processing Time: 1.726 seconds
✅ Real emails from PhonePe, Razorpay, YouTube
```

### **Vector Database Test**
```bash
✅ 12 vectors stored in Qdrant cloud
✅ 768-dimensional embeddings
✅ Cosine similarity search working
```

## 🚀 How to Run

### Prerequisites
```bash
pip install -r requirements.txt
```

### Environment Setup
```bash
cp email-assistant/env.txt .env
# Configure your API keys and database credentials
```

### Start the Chatbot
```bash
streamlit run frontend/streamlit_chatbot.py --server.port 8501
```

### Test Search Workflow
```bash
python -m backend.workflows.search_workflow
```

## 🎯 Demo Scenarios

### **Scenario 1: Payment Search**
```
User: "payments from last week"
System: Found 5 emails in 1.7s
Results: PhonePe, Razorpay payment confirmations
```

### **Scenario 2: Semantic Search**
```
User: "important emails about project"  
System: Hybrid search finds 3 relevant emails
Results: Ranked by relevance with scores
```

### **Scenario 3: Natural Language**
```
User: "attachments from december"
System: Filters by date + attachment presence  
Results: Emails with actual attachments
```

## 📝 Academic Deliverables

- **Abstract**: ✅ Complete
- **System Design**: ✅ Complete  
- **Literature Review**: ✅ Complete
- **Implementation**: ✅ 95% Complete
- **Testing Results**: ✅ Complete
- **Demo Video**: 📋 Pending
- **Final Report**: 📋 In Progress

## 🔮 Future Enhancements

1. **AI Email Drafting**: Generate contextual email replies
2. **Daily Summaries**: Automated morning email digests  
3. **Outlook Integration**: Microsoft Graph API support
4. **Advanced Analytics**: Email patterns and insights
5. **Mobile App**: React Native companion app

## 🤝 Contributing

This is an academic project by **Charan** for B.Tech capstone demonstration.

## 📄 License

Academic project - All rights reserved.

---

**🎉 Project Status: 85% Complete - Ready for Phase 4 Development**

*Built with ❤️ using LangGraph, FastAPI, and Google Gemini AI*
