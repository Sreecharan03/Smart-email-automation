# ====================================
# UNIFIED AI EMAIL ASSISTANT - QDRANT SERVICE
# ====================================
# Service for vector database operations using Qdrant
# Handles storing, searching, and managing email embeddings

import qdrant_client
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, 
    FieldCondition, SearchRequest, UpdateResult
)
from typing import List, Dict, Any, Optional, Tuple
import uuid
import time
import logging
from dataclasses import dataclass
import psycopg2

# Configuration imports
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../email-assistant')))

from config import get_config, get_supabase_connection_params

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class VectorSearchResult:
    """
    Result from vector similarity search
    """
    message_id: int
    external_message_id: str
    score: float
    subject: str
    snippet: str
    sender_email: str
    date_sent: str
    metadata: Dict[str, Any]

@dataclass 
class QdrantStats:
    """
    Statistics about Qdrant collection
    """
    total_vectors: int = 0
    collection_exists: bool = False
    vector_dimensions: int = 0
    distance_metric: str = ""
    collection_name: str = ""

class QdrantService:
    """
    Service for Qdrant vector database operations
    
    Features:
    1. Collection management (create, delete, info)
    2. Vector storage with metadata
    3. Similarity search with filtering
    4. Batch operations for efficiency
    5. Integration with email embeddings
    """
    
    def __init__(self):
        """
        Initialize Qdrant service with configuration
        """
        self.config = get_config()
        self.db_params = get_supabase_connection_params(self.config)
        
        # Qdrant configuration
        self.collection_name = self.config.qdrant_collection_name
        self.vector_dimensions = 768  # Standard for text embeddings
        self.distance_metric = Distance.COSINE  # Best for text similarity
        
        # Initialize Qdrant client
        try:
            if self.config.qdrant_url and self.config.qdrant_api_key:
                self.client = qdrant_client.QdrantClient(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key
                )
                logger.info(f"Connected to Qdrant at {self.config.qdrant_url}")
            else:
                # For development - use local Qdrant or in-memory
                self.client = qdrant_client.QdrantClient(":memory:")
                logger.info("Using in-memory Qdrant for development")
            
            # Ensure collection exists
            self._ensure_collection_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise
    
    def _ensure_collection_exists(self):
        """
        Ensure the email vectors collection exists with proper configuration
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_dimensions,
                        distance=self.distance_metric
                    )
                )
                
                logger.info(f"Created collection {self.collection_name} successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise
    
    def store_vector(self, vector_id: str, vector: List[float], 
                    metadata: Dict[str, Any]) -> bool:
        """
        Store a single vector with metadata in Qdrant
        
        Args:
            vector_id: Unique identifier for the vector
            vector: Embedding vector (768 dimensions)
            metadata: Associated metadata (message_id, field_name, etc.)
            
        Returns:
            bool: True if successful
        """
        try:
            # Create point for Qdrant
            point = PointStruct(
                id=vector_id,
                vector=vector,
                payload=metadata
            )
            
            # Store in Qdrant
            result = self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored vector {vector_id} in Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store vector {vector_id}: {e}")
            return False
    
    def store_vectors_batch(self, vectors_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Store multiple vectors in batch for efficiency
        
        Args:
            vectors_data: List of dicts with 'id', 'vector', 'metadata' keys
            
        Returns:
            Tuple[int, int]: (successful_count, failed_count)
        """
        logger.info(f"Storing batch of {len(vectors_data)} vectors")
        
        successful = 0
        failed = 0
        
        try:
            # Prepare points for batch insertion
            points = []
            for data in vectors_data:
                try:
                    point = PointStruct(
                        id=data['id'],
                        vector=data['vector'],
                        payload=data['metadata']
                    )
                    points.append(point)
                except KeyError as e:
                    logger.error(f"Missing key in vector data: {e}")
                    failed += 1
                    continue
            
            if points:
                # Batch upsert to Qdrant
                result = self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                successful = len(points)
                logger.info(f"Successfully stored {successful} vectors in batch")
            
        except Exception as e:
            logger.error(f"Batch vector storage failed: {e}")
            failed = len(vectors_data)
        
        return successful, failed
    
    def search_similar_vectors(self, query_vector: List[float], 
                              limit: int = 10,
                              score_threshold: float = 0.5,
                              metadata_filter: Optional[Dict] = None) -> List[VectorSearchResult]:
        """
        Search for similar vectors in Qdrant
        
        Args:
            query_vector: Vector to search for
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            metadata_filter: Optional filter on metadata fields
            
        Returns:
            List[VectorSearchResult]: Search results with metadata
        """
        try:
            # Build search request
            search_params = {
                "collection_name": self.collection_name,
                "query_vector": query_vector,
                "limit": limit,
                "score_threshold": score_threshold
            }
            
            # Add metadata filter if provided
            if metadata_filter:
                # Build Qdrant filter from metadata_filter dict
                # Example: {"field_name": "subject"} or {"sender_email": "user@example.com"}
                conditions = []
                for key, value in metadata_filter.items():
                    conditions.append(
                        FieldCondition(key=key, match={"value": value})
                    )
                
                if conditions:
                    search_params["query_filter"] = Filter(must=conditions)
            
            # Perform search
            search_results = self.client.search(
                collection_name=search_params["collection_name"],
                query_vector=search_params["query_vector"],
                limit=search_params["limit"],
                score_threshold=search_params["score_threshold"],
                query_filter=search_params.get("query_filter")
            )
            
            # Convert to our result format
            results = []
            for hit in search_results:
                # Get additional email data from database
                email_data = self._get_email_data_by_vector_id(hit.id)
                
                if email_data:
                    result = VectorSearchResult(
                        message_id=email_data['message_id'],
                        external_message_id=email_data['external_message_id'],
                        score=hit.score,
                        subject=email_data['subject'],
                        snippet=email_data['snippet'],
                        sender_email=email_data['sender_email'],
                        date_sent=email_data['date_sent'],
                        metadata=hit.payload
                    )
                    results.append(result)
            
            logger.info(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def sync_embeddings_to_qdrant(self, limit: int = 100) -> Dict[str, Any]:
        """
        Sync embedding records from database to Qdrant
        Useful for initial setup or recovery
        
        Args:
            limit: Maximum number of embeddings to sync
            
        Returns:
            Dict: Sync results and statistics
        """
        logger.info(f"Starting sync of embeddings to Qdrant (limit: {limit})")
        
        sync_results = {
            "total_embeddings": 0,
            "synced_to_qdrant": 0,
            "already_in_qdrant": 0,
            "failed_sync": 0,
            "errors": []
        }
        
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    # Get embeddings that need syncing to Qdrant
                    cur.execute("""
                        SELECT 
                            me.vector_id,
                            me.message_id,
                            me.field_name,
                            me.embedding_model,
                            me.vector_dimensions,
                            em.external_message_id,
                            em.subject,
                            em.snippet,
                            em.sender_email,
                            em.date_sent
                        FROM message_embeddings me
                        JOIN email_messages em ON me.message_id = em.id
                        ORDER BY me.created_at DESC
                        LIMIT %s
                    """, (limit,))
                    
                    embeddings = cur.fetchall()
                    sync_results["total_embeddings"] = len(embeddings)
                    
                    vectors_to_store = []
                    
                    for embedding_row in embeddings:
                        (vector_id, message_id, field_name, embedding_model, 
                         vector_dimensions, external_message_id, subject, 
                         snippet, sender_email, date_sent) = embedding_row
                        
                        try:
                            # Check if vector already exists in Qdrant
                            try:
                                existing = self.client.retrieve(
                                    collection_name=self.collection_name,
                                    ids=[vector_id]
                                )
                                if existing:
                                    sync_results["already_in_qdrant"] += 1
                                    continue
                            except:
                                # Vector doesn't exist, proceed with storage
                                pass
                            
                            # Generate simulated vector (in real implementation, retrieve from embedding service)
                            simulated_vector = self._generate_simulated_vector(
                                f"{subject or ''} {snippet or ''}"
                            )
                            
                            # Prepare vector data for batch storage
                            vector_data = {
                                "id": vector_id,
                                "vector": simulated_vector,
                                "metadata": {
                                    "message_id": message_id,
                                    "external_message_id": external_message_id,
                                    "field_name": field_name,
                                    "embedding_model": embedding_model,
                                    "subject": subject[:100] if subject else "",  # Truncate for metadata
                                    "sender_email": sender_email,
                                    "date_sent": date_sent.isoformat() if date_sent else ""
                                }
                            }
                            
                            vectors_to_store.append(vector_data)
                            
                        except Exception as e:
                            error_msg = f"Failed to prepare vector {vector_id}: {str(e)}"
                            logger.error(error_msg)
                            sync_results["errors"].append(error_msg)
                            sync_results["failed_sync"] += 1
                    
                    # Batch store vectors in Qdrant
                    if vectors_to_store:
                        successful, failed = self.store_vectors_batch(vectors_to_store)
                        sync_results["synced_to_qdrant"] = successful
                        sync_results["failed_sync"] += failed
        
        except Exception as e:
            error_msg = f"Database error during sync: {str(e)}"
            logger.error(error_msg)
            sync_results["errors"].append(error_msg)
        
        logger.info(f"Embedding sync complete:")
        logger.info(f"  Total: {sync_results['total_embeddings']}")
        logger.info(f"  Synced: {sync_results['synced_to_qdrant']}")
        logger.info(f"  Already existed: {sync_results['already_in_qdrant']}")
        logger.info(f"  Failed: {sync_results['failed_sync']}")
        
        return sync_results
    
    def _get_email_data_by_vector_id(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        Get email data from database using vector_id
        
        Args:
            vector_id: Vector ID to look up
            
        Returns:
            Optional[Dict]: Email data if found
        """
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            em.id as message_id,
                            em.external_message_id,
                            em.subject,
                            em.snippet,
                            em.sender_email,
                            em.date_sent
                        FROM message_embeddings me
                        JOIN email_messages em ON me.message_id = em.id
                        WHERE me.vector_id = %s
                        LIMIT 1
                    """, (vector_id,))
                    
                    row = cur.fetchone()
                    if row:
                        return {
                            "message_id": row[0],
                            "external_message_id": row[1],
                            "subject": row[2] or "",
                            "snippet": row[3] or "",
                            "sender_email": row[4],
                            "date_sent": row[5].isoformat() if row[5] else ""
                        }
        
        except Exception as e:
            logger.error(f"Failed to get email data for vector {vector_id}: {e}")
        
        return None
    
    def _generate_simulated_vector(self, text: str) -> List[float]:
        """
        Generate simulated embedding vector for testing
        In production, this would retrieve the actual stored embedding
        
        Args:
            text: Text to generate vector for
            
        Returns:
            List[float]: Normalized 768-dimensional vector
        """
        import numpy as np
        
        # Use text hash for consistency
        hash_value = hash(text)
        np.random.seed(abs(hash_value) % 2147483647)
        
        # Generate and normalize vector
        vector = np.random.normal(0, 0.1, self.vector_dimensions)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector.tolist()
    
    def get_collection_stats(self) -> QdrantStats:
        """
        Get statistics about the Qdrant collection
        
        Returns:
            QdrantStats: Collection statistics
        """
        stats = QdrantStats(collection_name=self.collection_name)
        
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name in collection_names:
                stats.collection_exists = True
                
                # Get collection info
                collection_info = self.client.get_collection(self.collection_name)
                stats.total_vectors = collection_info.points_count
                stats.vector_dimensions = collection_info.config.params.vectors.size
                stats.distance_metric = collection_info.config.params.vectors.distance.name
                
            logger.info(f"Collection stats: {stats.total_vectors} vectors, {stats.vector_dimensions}D")
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
        
        return stats
    
    def delete_collection(self) -> bool:
        """
        Delete the entire collection (careful!)
        
        Returns:
            bool: True if successful
        """
        try:
            result = self.client.delete_collection(self.collection_name)
            logger.warning(f"Deleted collection {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

def main():
    """
    Test function for Qdrant service
    Tests vector storage, search, and collection management
    """
    print("🔍 Testing Qdrant Service")
    print("=" * 50)
    
    try:
        # Initialize Qdrant service
        qdrant_service = QdrantService()
        print("✅ Qdrant service initialized successfully")
        
        # Test 1: Collection stats
        print("\n📊 Test 1: Collection Statistics")
        stats = qdrant_service.get_collection_stats()
        print(f"Collection exists: {stats.collection_exists}")
        print(f"Total vectors: {stats.total_vectors}")
        print(f"Vector dimensions: {stats.vector_dimensions}")
        print(f"Distance metric: {stats.distance_metric}")
        
        # Test 2: Store test vector
        print("\n💾 Test 2: Store Test Vector")
        test_vector_id = str(uuid.uuid4())
        test_vector = qdrant_service._generate_simulated_vector("test email about meetings")
        test_metadata = {
            "message_id": 999,
            "field_name": "test",
            "subject": "Test Email Subject",
            "sender_email": "test@example.com"
        }
        
        success = qdrant_service.store_vector(test_vector_id, test_vector, test_metadata)
        print(f"Vector storage success: {success}")
        
        # Test 3: Search similar vectors
        print("\n🔎 Test 3: Vector Similarity Search")
        query_vector = qdrant_service._generate_simulated_vector("meeting agenda tomorrow")
        search_results = qdrant_service.search_similar_vectors(
            query_vector=query_vector,
            limit=5,
            score_threshold=0.3
        )
        
        print(f"Search returned {len(search_results)} results")
        for i, result in enumerate(search_results[:3], 1):
            print(f"  {i}. Score: {result.score:.3f} | Subject: {result.subject[:50]}...")
        
        # Test 4: Sync embeddings from database
        print("\n🔄 Test 4: Sync Embeddings from Database")
        sync_results = qdrant_service.sync_embeddings_to_qdrant(limit=10)
        
        print(f"Total embeddings found: {sync_results['total_embeddings']}")
        print(f"Synced to Qdrant: {sync_results['synced_to_qdrant']}")
        print(f"Already in Qdrant: {sync_results['already_in_qdrant']}")
        print(f"Failed sync: {sync_results['failed_sync']}")
        
        if sync_results['errors']:
            print(f"\n⚠️ Sync errors ({len(sync_results['errors'])}):")
            for error in sync_results['errors']:
                print(f"  - {error}")
        
        # Test 5: Final collection stats
        print("\n📈 Test 5: Final Collection Statistics")
        final_stats = qdrant_service.get_collection_stats()
        print(f"Total vectors after sync: {final_stats.total_vectors}")
        
        print("\n🎉 Qdrant service tests completed!")
        
    except Exception as e:
        print(f"❌ Qdrant service test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()