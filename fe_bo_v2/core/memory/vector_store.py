"""Vector memory using Chroma for semantic search and retrieval.
Provides similarity-based fact storage and retrieval.
"""

import time
from typing import List, Optional, Dict, Any

try:
    import chromadb
except ImportError:
    chromadb = None

from core.logging_config import get_logger

logger = get_logger("memory.vector_store")


class VectorMemory:
    """Semantic memory using vector embeddings."""

    def __init__(self) -> None:
        """Initialize vector memory with Chroma."""
        try:
            if not chromadb:
                logger.warning("Chroma not available, vector storage disabled")
                self.collection = None
                return

            from pathlib import Path
            chroma_path = Path("memory/chroma")
            chroma_path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(chroma_path))
            self.collection = self.client.get_or_create_collection("facts")
            logger.info("VectorMemory initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vector memory: {e}", exc_info=True)
            self.collection = None

    def add_fact(self, fact_text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Add fact to vector memory.

        Args:
            fact_text: Fact text to store
            metadata: Optional metadata dictionary

        Returns:
            Fact ID or None if failed
        """
        try:
            if not self.collection:
                logger.debug("Vector memory not available")
                return None
            
            fact_id = f"fact_{time.time()}"
            self.collection.add(
                documents=[fact_text],
                metadatas=[metadata or {}],
                ids=[fact_id]
            )
            logger.debug(f"Fact added: {fact_id}")
            return fact_id
        except Exception as e:
            logger.error(f"Error adding fact to vector memory: {e}")
            return None

    def search(self, query: str, n: int = 5) -> List[str]:
        """
        Search for similar facts.

        Args:
            query: Search query
            n: Maximum results to return

        Returns:
            List of matching fact texts
        """
        try:
            if not self.collection:
                logger.debug("Vector memory not available")
                return []
            
            results = self.collection.query(query_texts=[query], n_results=n)
            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []


# Global vector memory instance
try:
    vector_memory = VectorMemory()
except Exception as e:
    logger.critical(f"Failed to initialize global vector memory: {e}")
    raise
