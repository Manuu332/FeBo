"""
Semantic Memory - fact-based knowledge storage with vector embeddings.

Complements episodic memory by storing:
- Facts and abstractions
- Learned generalizations
- Semantic relationships
- Abstracted knowledge from experiences
"""

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

from core.logging_config import get_logger

logger = get_logger("memory.semantic")

SEMANTIC_DB = Path("memory/semantic.db")
SEMANTIC_DB.parent.mkdir(parents=True, exist_ok=True)


class SemanticMemory:
    """
    Stores semantic knowledge with vector embeddings.
    
    Unlike episodic memory (what happened), semantic memory stores:
    - Facts and generalizations
    - Learned relationships
    - Abstracted knowledge
    - Cross-domain associations
    """
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialize semantic memory.
        
        Args:
            embedding_model: Sentence transformer model for embeddings
        """
        self._lock = threading.RLock()
        
        # Initialize Chroma vector database
        self.chroma = None
        self.collection = None
        if HAS_CHROMA:
            try:
                chroma_path = Path("memory/chroma")
                chroma_path.mkdir(parents=True, exist_ok=True)
                import os
                # Suppress ChromaDB's own ONNX download telemetry
                os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
                self.chroma = chromadb.PersistentClient(path=str(chroma_path))
                # Use a null embedding function — we provide our own embeddings explicitly
                try:
                    from chromadb.utils import embedding_functions
                    null_ef = None   # will be set below if sentence-transformers available
                except Exception:
                    null_ef = None
                self.collection = self.chroma.get_or_create_collection(
                    "semantic",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.debug("Chroma vector store initialized")
            except Exception as e:
                logger.warning(f"Chroma initialization failed: {e}")
        
        # Initialize embedding model
        self.encoder = None
        if HAS_EMBEDDINGS:
            try:
                self.encoder = SentenceTransformer(embedding_model)
                logger.debug(f"Embedding model loaded: {embedding_model}")
            except Exception as e:
                logger.warning(f"Embedding model failed to load: {e}")
        
        # Initialize SQL database for metadata
        try:
            self.db = sqlite3.connect(
                str(SEMANTIC_DB),
                check_same_thread=False,
                timeout=10.0
            )
            self._init_schema()
            logger.debug("Semantic memory database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize semantic database: {e}")
            raise
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._lock:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY,
                    key TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    accessed_at REAL NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.8,
                    metadata TEXT
                )
            """)
            
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY,
                    source_key TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    strength REAL DEFAULT 0.5,
                    FOREIGN KEY(source_key) REFERENCES facts(key),
                    FOREIGN KEY(target_key) REFERENCES facts(key)
                )
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_key ON facts(key)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed ON facts(accessed_at DESC)
            """)
            
            self.db.commit()
    
    def store(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 0.8
    ) -> bool:
        """
        Store a fact in semantic memory.
        
        Args:
            key: Unique identifier for this fact
            content: The fact/knowledge content
            metadata: Optional metadata
            confidence: Confidence level [0, 1]
            
        Returns:
            True if stored successfully
        """
        try:
            with self._lock:
                now = time.time()
                meta_json = json.dumps(metadata or {})
                
                # Try insert, fall back to update
                try:
                    self.db.execute(
                        """INSERT INTO facts (key, content, created_at, accessed_at, confidence, metadata)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (key, content, now, now, confidence, meta_json)
                    )
                except sqlite3.IntegrityError:
                    # Update existing
                    self.db.execute(
                        """UPDATE facts SET content=?, accessed_at=?, frequency=frequency+1, 
                           confidence=?, metadata=? WHERE key=?""",
                        (content, now, confidence, meta_json, key)
                    )
                
                self.db.commit()
                
                # Store embedding vector if available
                if self.encoder and self.collection:
                    try:
                        embedding = self.encoder.encode(content)
                        self.collection.add(
                            ids=[key],
                            documents=[content],
                            embeddings=[embedding.tolist()],
                            metadatas=[{"type": "fact", "confidence": confidence}]
                        )
                    except Exception as e:
                        logger.debug(f"Embedding storage failed for {key}: {e}")
                
                logger.debug(f"Fact stored: {key}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing fact {key}: {e}")
            return False
    
    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific fact by key.
        
        Args:
            key: Fact identifier
            
        Returns:
            Fact dict or None if not found
        """
        try:
            with self._lock:
                cursor = self.db.execute(
                    "SELECT key, content, created_at, accessed_at, frequency, confidence, metadata "
                    "FROM facts WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Update access time
                    self.db.execute(
                        "UPDATE facts SET accessed_at = ? WHERE key = ?",
                        (time.time(), key)
                    )
                    self.db.commit()
                    
                    return {
                        "key": row[0],
                        "content": row[1],
                        "created_at": row[2],
                        "accessed_at": row[3],
                        "frequency": row[4],
                        "confidence": row[5],
                        "metadata": json.loads(row[6])
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving fact {key}: {e}")
            return None
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for facts semantically (if embeddings available) or by keyword.
        
        Args:
            query: Search query
            top_k: Maximum results to return
            
        Returns:
            List of matching facts
        """
        try:
            # Try vector search first
            if self.encoder and self.collection:
                try:
                    query_embedding = self.encoder.encode(query)
                    results = self.collection.query(
                        query_embeddings=[query_embedding.tolist()],
                        n_results=top_k
                    )
                    
                    facts = []
                    if results and results['ids']:
                        for doc_id, distance in zip(results['ids'][0], results['distances'][0]):
                            fact = self.retrieve(doc_id)
                            if fact:
                                fact['similarity'] = 1.0 - distance
                                facts.append(fact)
                    
                    if facts:
                        return facts
                except Exception as e:
                    logger.debug(f"Vector search failed: {e}")
            
            # Fall back to keyword search
            query_lower = query.lower()
            try:
                with self._lock:
                    cursor = self.db.execute(
                        """SELECT key, content, confidence FROM facts 
                           WHERE content LIKE ? OR key LIKE ?
                           ORDER BY frequency DESC LIMIT ?""",
                        (f"%{query_lower}%", f"%{query_lower}%", top_k)
                    )
                    
                    facts = []
                    for row in cursor.fetchall():
                        fact = self.retrieve(row[0])
                        if fact:
                            fact['similarity'] = 0.5  # keyword match
                            facts.append(fact)
                    
                    return facts
                    
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Search error for query '{query}': {e}")
            return []
    
    def add_relationship(
        self,
        source_key: str,
        target_key: str,
        relationship_type: str,
        strength: float = 0.5
    ) -> bool:
        """
        Create a semantic relationship between two facts.
        
        Args:
            source_key: Source fact key
            target_key: Target fact key
            relationship_type: Type of relationship (e.g., "related_to", "caused_by")
            strength: Relationship strength [0, 1]
            
        Returns:
            True if relationship created
        """
        try:
            with self._lock:
                self.db.execute(
                    """INSERT INTO relationships (source_key, target_key, relationship_type, strength)
                       VALUES (?, ?, ?, ?)""",
                    (source_key, target_key, relationship_type, max(0, min(1, strength)))
                )
                self.db.commit()
                logger.debug(f"Relationship created: {source_key} -{relationship_type}-> {target_key}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return False
    
    def get_related_facts(self, key: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get facts related to a given fact.
        
        Args:
            key: Source fact key
            relationship_type: Optional filter by relationship type
            
        Returns:
            List of related facts
        """
        try:
            with self._lock:
                if relationship_type:
                    cursor = self.db.execute(
                        """SELECT target_key, relationship_type, strength
                           FROM relationships
                           WHERE source_key = ? AND relationship_type = ?""",
                        (key, relationship_type)
                    )
                else:
                    cursor = self.db.execute(
                        """SELECT target_key, relationship_type, strength
                           FROM relationships
                           WHERE source_key = ?""",
                        (key,)
                    )
                
                related = []
                for row in cursor.fetchall():
                    target_fact = self.retrieve(row[0])
                    if target_fact:
                        target_fact['relationship_type'] = row[1]
                        target_fact['relationship_strength'] = row[2]
                        related.append(target_fact)
                
                return related
                
        except Exception as e:
            logger.error(f"Error retrieving related facts: {e}")
            return []
    
    def get_most_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recently accessed facts.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of recent facts
        """
        try:
            with self._lock:
                cursor = self.db.execute(
                    """SELECT key FROM facts
                       ORDER BY accessed_at DESC LIMIT ?""",
                    (limit,)
                )
                
                facts = []
                for row in cursor.fetchall():
                    fact = self.retrieve(row[0])
                    if fact:
                        facts.append(fact)
                
                return facts
                
        except Exception as e:
            logger.error(f"Error retrieving recent facts: {e}")
            return []
    
    def consolidate_memory(self, age_threshold: float = 3600.0) -> Dict[str, int]:
        """
        Consolidate memory by abstracting frequently accessed older facts.
        
        Args:
            age_threshold: Age in seconds before consolidation considered
            
        Returns:
            Statistics on consolidation actions
        """
        try:
            with self._lock:
                now = time.time()
                stats = {
                    "abstracted": 0,
                    "merged": 0,
                    "deleted": 0
                }
                
                # Find frequently accessed old facts
                cursor = self.db.execute(
                    """SELECT key, content, frequency FROM facts
                       WHERE (? - created_at) > ?
                       AND frequency > 5
                       ORDER BY frequency DESC""",
                    (now, age_threshold)
                )
                
                for row in cursor.fetchall():
                    old_key, content, freq = row
                    # Create abstracted summary
                    abstract_key = f"{old_key}_abstract"
                    abstract_content = f"[Abstraction] {content[:50]}... (accessed {freq} times)"
                    
                    self.store(abstract_key, abstract_content, confidence=0.6)
                    self.add_relationship(abstract_key, old_key, "abstracts", strength=0.8)
                    
                    stats["abstracted"] += 1
                
                logger.info(f"Memory consolidation complete: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error consolidating memory: {e}")
            return {"abstracted": 0, "merged": 0, "deleted": 0}
    
    def close(self) -> None:
        """Close database connections."""
        try:
            if self.db:
                self.db.close()
                logger.debug("Semantic memory closed")
        except Exception as e:
            logger.error(f"Error closing semantic memory: {e}")


# Global semantic memory instance
try:
    semantic = SemanticMemory()
except Exception as e:
    logger.critical(f"Failed to initialize global semantic memory: {e}")
    raise
