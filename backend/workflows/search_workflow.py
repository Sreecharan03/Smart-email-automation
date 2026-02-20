# ====================================
# UNIFIED AI EMAIL ASSISTANT - SEARCH WORKFLOW
# ====================================
# LangGraph workflow for intelligent email search
# Combines natural language processing, keyword search, and vector similarity

import psycopg2
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# Our services
import sys
import os

# Add relevant directories to sys.path for module resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
services_dir = os.path.abspath(os.path.join(current_dir, '../services'))
qdrant_dir = os.path.abspath(os.path.join(current_dir, '../services/qdrant'))
email_assistant_dir = os.path.abspath(os.path.join(current_dir, '../../email-assistant'))

sys.path.append(project_root)
sys.path.append(services_dir)
sys.path.append(qdrant_dir)
sys.path.append(email_assistant_dir)

from config import get_config, get_supabase_connection_params
from embedding_service import EmbeddingService
from qdrant_service import QdrantService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchType(Enum):
    """Types of search operations"""
    SEMANTIC = "semantic"      # Vector similarity search
    KEYWORD = "keyword"        # Text-based search
    HYBRID = "hybrid"          # Combined approach
    FILTERED = "filtered"      # With date/sender filters

@dataclass
class SearchFilters:
    """Search filters extracted from query"""
    sender_emails: List[str] = field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    labels: List[str] = field(default_factory=list)
    has_attachments: Optional[bool] = None
    is_important: Optional[bool] = None
    keywords: List[str] = field(default_factory=list)

@dataclass
class SearchResult:
    """Individual search result"""
    message_id: int
    external_message_id: str
    subject: str
    snippet: str
    sender_email: str
    sender_name: str
    date_sent: datetime
    relevance_score: float
    search_type: str
    labels: List[str]
    has_attachments: bool

@dataclass
class SearchState:
    """State object for search workflow"""
    # Input
    query: str
    account_id: int
    max_results: int = 20
    
    # Processed query components
    search_type: SearchType = SearchType.HYBRID
    filters: SearchFilters = field(default_factory=SearchFilters)
    cleaned_query: str = ""
    query_vector: List[float] = field(default_factory=list)
    
    # Results
    keyword_results: List[SearchResult] = field(default_factory=list)
    semantic_results: List[SearchResult] = field(default_factory=list)
    final_results: List[SearchResult] = field(default_factory=list)
    
    # Statistics
    total_keyword_matches: int = 0
    total_semantic_matches: int = 0
    total_final_results: int = 0
    processing_time: float = 0
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=lambda: time.time())

class SmartSearchWorkflow:
    """
    LangGraph workflow for intelligent email search
    
    Workflow Steps:
    1. Parse Query - Extract filters and clean search terms
    2. Generate Query Vector - Create embedding for semantic search
    3. Keyword Search - SQL-based text matching
    4. Semantic Search - Vector similarity in Qdrant
    5. Hybrid Fusion - Combine and rank results
    6. Apply Filters - Date, sender, label filtering
    7. Return Results - Final ranked list
    """
    
    def __init__(self):
        """Initialize search workflow with services"""
        self.config = get_config()
        self.db_params = get_supabase_connection_params(self.config)
        
        # Initialize services
        try:
            self.embedding_service = EmbeddingService()
            self.qdrant_service = QdrantService()
        except Exception as e:
            logger.warning(f"Service initialization warning: {e}")
            self.embedding_service = None
            self.qdrant_service = None
        
        # Create workflow
        self.workflow = self._create_workflow()
        
        logger.info("Smart Search Workflow initialized")
    
    def _create_workflow(self) -> Any:
        """Create the LangGraph search workflow"""
        workflow = StateGraph(SearchState)
        
        # Add workflow nodes
        workflow.add_node("parse_query", self._parse_query)
        workflow.add_node("generate_vector", self._generate_query_vector)
        workflow.add_node("keyword_search", self._keyword_search)
        workflow.add_node("semantic_search", self._semantic_search)
        workflow.add_node("fuse_results", self._fuse_results)
        workflow.add_node("apply_filters", self._apply_filters)
        workflow.add_node("finalize_results", self._finalize_results)
        
        # Define workflow edges
        workflow.add_edge(START, "parse_query")
        workflow.add_edge("parse_query", "generate_vector")
        workflow.add_edge("generate_vector", "keyword_search")
        workflow.add_edge("keyword_search", "semantic_search")
        workflow.add_edge("semantic_search", "fuse_results")
        workflow.add_edge("fuse_results", "apply_filters")
        workflow.add_edge("apply_filters", "finalize_results")
        workflow.add_edge("finalize_results", END)
        
        return workflow.compile()
    
    def _parse_query(self, state: SearchState) -> SearchState:
        """
        Parse natural language query to extract filters and search terms
        
        Examples:
        - "emails from john about meetings last week"
        - "important invoices from december"
        - "attachments from sarah yesterday"
        """
        logger.info(f"Parsing query: '{state.query}'")
        
        try:
            query = state.query.lower().strip()
            filters = SearchFilters()
            
            # Extract sender filters
            sender_patterns = [
                r'from\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # from email@domain.com
                r'from\s+(\w+)',  # from john
                r'sender:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # sender: email
            ]
            
            for pattern in sender_patterns:
                matches = re.findall(pattern, query)
                for match in matches:
                    if '@' in match:
                        filters.sender_emails.append(match)
                        query = re.sub(pattern, '', query)
                    else:
                        # Convert name to potential email patterns
                        filters.keywords.append(match)
                        query = re.sub(r'from\s+' + re.escape(match), '', query)
            
            # Extract date filters
            today = datetime.now(timezone.utc)
            
            date_patterns = {
                r'\btoday\b': (today.replace(hour=0, minute=0, second=0, microsecond=0), today),
                r'\byesterday\b': (
                    (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                    (today - timedelta(days=1)).replace(hour=23, minute=59, second=59)
                ),
                r'\blast\s+week\b': (today - timedelta(weeks=1), today),
                r'\bthis\s+week\b': (today - timedelta(days=today.weekday()), today),
                r'\blast\s+month\b': (today - timedelta(days=30), today),
                r'\bthis\s+month\b': (today.replace(day=1), today),
                r'\blast\s+year\b': (today - timedelta(days=365), today),
            }
            
            for pattern, (date_from, date_to) in date_patterns.items():
                if re.search(pattern, query):
                    filters.date_from = date_from
                    filters.date_to = date_to
                    query = re.sub(pattern, '', query)
                    break
            
            # Extract specific month/year
            month_match = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b', query)
            if month_match:
                month_name, year = month_match.groups()
                month_num = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }[month_name]
                
                filters.date_from = datetime(int(year), month_num, 1, tzinfo=timezone.utc)
                if month_num == 12:
                    filters.date_to = datetime(int(year) + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    filters.date_to = datetime(int(year), month_num + 1, 1, tzinfo=timezone.utc)
                
                query = re.sub(month_match.group(0), '', query)
            
            # Extract label/category filters
            if 'important' in query:
                filters.is_important = True
                query = query.replace('important', '')
            
            if 'attachment' in query:
                filters.has_attachments = True
                query = query.replace('attachment', '').replace('attachments', '')
            
            # Extract label patterns
            label_patterns = [
                (r'\binbox\b', 'INBOX'),
                (r'\bsent\b', 'SENT'),
                (r'\bdraft\b', 'DRAFT'),
                (r'\bspam\b', 'SPAM'),
                (r'\btrash\b', 'TRASH')
            ]
            
            for pattern, label in label_patterns:
                if re.search(pattern, query):
                    filters.labels.append(label)
                    query = re.sub(pattern, '', query)
            
            # Clean up the query
            query = re.sub(r'\s+', ' ', query).strip()
            query = re.sub(r'\b(about|regarding|re:|fw:)\b', '', query).strip()
            
            # Extract remaining keywords
            if query:
                keywords = [word.strip() for word in query.split() if len(word.strip()) > 2]
                filters.keywords.extend(keywords)
            
            state.filters = filters
            state.cleaned_query = ' '.join(filters.keywords) if filters.keywords else query
            
            # Determine search type
            if state.cleaned_query and len(state.cleaned_query) > 3:
                if filters.sender_emails or filters.date_from or filters.labels:
                    state.search_type = SearchType.FILTERED
                else:
                    state.search_type = SearchType.HYBRID
            else:
                state.search_type = SearchType.KEYWORD
            
            logger.info(f"Parsed query - Type: {state.search_type.value}")
            logger.info(f"Cleaned query: '{state.cleaned_query}'")
            logger.info(f"Filters: {filters.sender_emails}, {filters.date_from}, {filters.keywords}")
            
        except Exception as e:
            error_msg = f"Failed to parse query: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _generate_query_vector(self, state: SearchState) -> SearchState:
        """Generate embedding vector for semantic search"""
        
        if state.search_type in [SearchType.SEMANTIC, SearchType.HYBRID, SearchType.FILTERED]:
            if state.cleaned_query and self.embedding_service:
                try:
                    logger.info(f"Generating vector for: '{state.cleaned_query}'")
                    
                    result = self.embedding_service.generate_single_embedding(state.cleaned_query)
                    
                    if result.success:
                        state.query_vector = result.vector
                        logger.info(f"Generated {result.dimensions}D vector")
                    else:
                        error_msg = f"Failed to generate vector: {result.error_message}"
                        logger.warning(error_msg)
                        state.errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Vector generation error: {str(e)}"
                    logger.warning(error_msg)
                    state.errors.append(error_msg)
            else:
                logger.info("Skipping vector generation (no embedding service or query)")
        
        return state
    
    def _keyword_search(self, state: SearchState) -> SearchState:
        """Perform keyword-based SQL search"""
        logger.info("Performing keyword search")
        
        try:
            keyword_results = []
            
            if state.cleaned_query or state.filters.keywords:
                search_terms = state.filters.keywords if state.filters.keywords else [state.cleaned_query]
                
                with psycopg2.connect(**self.db_params) as conn:
                    with conn.cursor() as cur:
                        # Build search query
                        search_conditions = []
                        search_params = [state.account_id]
                        
                        # Text search in subject and snippet
                        if search_terms:
                            text_conditions = []
                            for term in search_terms:
                                text_conditions.append("(LOWER(subject) LIKE %s OR LOWER(snippet) LIKE %s)")
                                search_params.append(f'%{term.lower()}%')
                                search_params.append(f'%{term.lower()}%')
                            
                            if text_conditions:
                                search_conditions.append(f"({' OR '.join(text_conditions)})")
                        
                        # Build final query
                        base_query = """
                            SELECT id, external_message_id, subject, snippet, sender_email, 
                                   sender_name, date_sent, labels, has_attachments
                            FROM email_messages 
                            WHERE account_id = %s
                        """
                        
                        if search_conditions:
                            base_query += " AND " + " AND ".join(search_conditions)
                        
                        base_query += " ORDER BY date_sent DESC LIMIT %s"
                        search_params.append(state.max_results)
                        
                        cur.execute(base_query, search_params)
                        rows = cur.fetchall()
                        
                        # Convert to SearchResult objects
                        for row in rows:
                            result = SearchResult(
                                message_id=row[0],
                                external_message_id=row[1],
                                subject=row[2] or "",
                                snippet=row[3] or "",
                                sender_email=row[4],
                                sender_name=row[5] or "",
                                date_sent=row[6],
                                relevance_score=self._calculate_keyword_score(row[2], row[3], search_terms),
                                search_type="keyword",
                                labels=row[7] if row[7] else [],
                                has_attachments=row[8] or False
                            )
                            keyword_results.append(result)
            
            state.keyword_results = sorted(keyword_results, key=lambda x: x.relevance_score, reverse=True)
            state.total_keyword_matches = len(keyword_results)
            
            logger.info(f"Keyword search found {state.total_keyword_matches} results")
            
        except Exception as e:
            error_msg = f"Keyword search failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _semantic_search(self, state: SearchState) -> SearchState:
        """Perform vector similarity search using Qdrant"""
        logger.info("Performing semantic search")
        
        try:
            semantic_results = []
            
            if state.query_vector and self.qdrant_service:
                # Search in Qdrant
                vector_results = self.qdrant_service.search_similar_vectors(
                    query_vector=state.query_vector,
                    limit=state.max_results,
                    score_threshold=0.3  # Minimum similarity threshold
                )
                
                # Convert to SearchResult objects
                for vector_result in vector_results:
                    result = SearchResult(
                        message_id=vector_result.message_id,
                        external_message_id=vector_result.external_message_id,
                        subject=vector_result.subject,
                        snippet=vector_result.snippet,
                        sender_email=vector_result.sender_email,
                        sender_name="",  # Could enhance this
                        date_sent=datetime.fromisoformat(vector_result.date_sent) if vector_result.date_sent else datetime.now(timezone.utc),
                        relevance_score=vector_result.score,
                        search_type="semantic",
                        labels=[],  # Could enhance this
                        has_attachments=False  # Could enhance this
                    )
                    semantic_results.append(result)
                
                state.semantic_results = semantic_results
                state.total_semantic_matches = len(semantic_results)
                
                logger.info(f"Semantic search found {state.total_semantic_matches} results")
            else:
                logger.info("Skipping semantic search (no vector or Qdrant service)")
        
        except Exception as e:
            error_msg = f"Semantic search failed: {str(e)}"
            logger.warning(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _fuse_results(self, state: SearchState) -> SearchState:
        """Fuse keyword and semantic search results"""
        logger.info("Fusing search results")
        
        try:
            # Create a combined results list
            combined_results = {}
            
            # Add keyword results
            for result in state.keyword_results:
                key = result.message_id
                if key not in combined_results:
                    combined_results[key] = result
                    combined_results[key].search_type = "keyword"
                else:
                    # Boost score if found in both searches
                    combined_results[key].relevance_score = max(
                        combined_results[key].relevance_score,
                        result.relevance_score
                    )
                    combined_results[key].search_type = "hybrid"
            
            # Add semantic results
            for result in state.semantic_results:
                key = result.message_id
                if key not in combined_results:
                    combined_results[key] = result
                    combined_results[key].search_type = "semantic"
                else:
                    # Hybrid scoring: combine keyword and semantic scores
                    keyword_score = combined_results[key].relevance_score
                    semantic_score = result.relevance_score
                    
                    # Weighted combination (60% semantic, 40% keyword)
                    combined_score = (semantic_score * 0.6) + (keyword_score * 0.4)
                    combined_results[key].relevance_score = combined_score
                    combined_results[key].search_type = "hybrid"
            
            # Convert back to list and sort by relevance
            fused_results = list(combined_results.values())
            fused_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            state.final_results = fused_results[:state.max_results]
            
            logger.info(f"Fused results: {len(state.final_results)} total")
            
        except Exception as e:
            error_msg = f"Result fusion failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _apply_filters(self, state: SearchState) -> SearchState:
        """Apply date, sender, and other filters to results"""
        logger.info("Applying filters")
        
        try:
            filtered_results = []
            
            for result in state.final_results:
                # Apply sender filter
                if state.filters.sender_emails:
                    if not any(sender in result.sender_email.lower() for sender in state.filters.sender_emails):
                        continue
                
                # Apply date filter
                if state.filters.date_from and result.date_sent < state.filters.date_from:
                    continue
                
                if state.filters.date_to and result.date_sent > state.filters.date_to:
                    continue
                
                # Apply importance filter
                if state.filters.is_important is not None:
                    # This would need to be enhanced based on your label structure
                    has_important = "IMPORTANT" in result.labels
                    if state.filters.is_important != has_important:
                        continue
                
                # Apply attachment filter
                if state.filters.has_attachments is not None:
                    if state.filters.has_attachments != result.has_attachments:
                        continue
                
                # Apply label filter
                if state.filters.labels:
                    if not any(label in result.labels for label in state.filters.labels):
                        continue
                
                filtered_results.append(result)
            
            state.final_results = filtered_results
            
            logger.info(f"Applied filters: {len(filtered_results)} results remaining")
            
        except Exception as e:
            error_msg = f"Filter application failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _finalize_results(self, state: SearchState) -> SearchState:
        """Finalize search results and generate statistics"""
        
        state.processing_time = time.time() - state.start_time
        state.total_final_results = len(state.final_results)
        
        logger.info("=== SEARCH COMPLETE ===")
        logger.info(f"Query: '{state.query}'")
        logger.info(f"Search Type: {state.search_type.value}")
        logger.info(f"Processing Time: {state.processing_time:.3f}s")
        logger.info(f"Keyword Results: {state.total_keyword_matches}")
        logger.info(f"Semantic Results: {state.total_semantic_matches}")
        logger.info(f"Final Results: {state.total_final_results}")
        
        if state.errors:
            logger.warning(f"Errors: {len(state.errors)}")
            for error in state.errors:
                logger.warning(f"  - {error}")
        
        return state
    
    def _calculate_keyword_score(self, subject: str, snippet: str, search_terms: List[str]) -> float:
        """Calculate relevance score for keyword search"""
        if not search_terms:
            return 0.0
        
        score = 0.0
        subject_text = (subject or "").lower()
        snippet_text = (snippet or "").lower()
        
        for term in search_terms:
            term_lower = term.lower()
            
            # Subject matches get higher weight
            if term_lower in subject_text:
                score += 2.0
            
            # Snippet matches
            if term_lower in snippet_text:
                score += 1.0
        
        # Normalize by number of terms
        return score / len(search_terms) if search_terms else 0.0
    
    def search_emails(self, query: str, account_id: int, max_results: int = 20) -> Dict[str, Any]:
        """
        Run the complete smart search workflow
        
        Args:
            query: Natural language search query
            account_id: Database ID of the email account
            max_results: Maximum number of results to return
            
        Returns:
            Dict: Search results and statistics
        """
        logger.info(f"Starting smart search for query: '{query}'")
        
        # Create initial state
        initial_state = SearchState(
            query=query,
            account_id=account_id,
            max_results=max_results
        )
        
        # Run the workflow
        final_state = self.workflow.invoke(initial_state)
        
        # Convert results to serializable format
        results = []
        for result in final_state['final_results']:
            results.append({
                'message_id': result.message_id,
                'external_message_id': result.external_message_id,
                'subject': result.subject,
                'snippet': result.snippet,
                'sender_email': result.sender_email,
                'sender_name': result.sender_name,
                'date_sent': result.date_sent.isoformat(),
                'relevance_score': round(result.relevance_score, 3),
                'search_type': result.search_type,
                'has_attachments': result.has_attachments
            })
        
        return {
            'success': len(final_state['errors']) == 0,
            'query': query,
            'search_type': final_state['search_type'].value,
            'total_results': len(results),
            'results': results,
            'processing_time': round(final_state['processing_time'], 3),
            'statistics': {
                'keyword_matches': final_state['total_keyword_matches'],
                'semantic_matches': final_state['total_semantic_matches'],
                'final_results': final_state['total_final_results']
            },
            'errors': final_state['errors']
        }

def main():
    """
    Test function for smart search workflow
    Tests various search scenarios
    """
    print("🔍 Testing Smart Search Workflow")
    print("=" * 60)
    
    try:
        # Initialize search workflow
        search_workflow = SmartSearchWorkflow()
        print("✅ Smart search workflow initialized successfully")
        
        # Test queries
        test_queries = [
            "meetings last week",
            "emails from sender0@example.com",
            "important emails about project",
            "attachments from december",
            "invoice payment reminder"
        ]
        
        test_account_id = 2  # Your Gmail account
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 Test {i}: '{query}'")
            print("-" * 40)
            
            # Run search
            results = search_workflow.search_emails(
                query=query,
                account_id=test_account_id,
                max_results=5
            )
            
            # Display results
            print(f"Success: {results['success']}")
            print(f"Search Type: {results['search_type']}")
            print(f"Total Results: {results['total_results']}")
            print(f"Processing Time: {results['processing_time']}s")
            
            # Show top results
            for j, result in enumerate(results['results'][:3], 1):
                print(f"  {j}. Score: {result['relevance_score']} | {result['subject'][:40]}...")
                print(f"     From: {result['sender_email']} | {result['date_sent'][:10]}")
            
            if results['errors']:
                print(f"⚠️ Errors: {results['errors']}")
        
        print("\n🎉 Smart search workflow tests completed!")
        
    except Exception as e:
        print(f"❌ Search workflow test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()