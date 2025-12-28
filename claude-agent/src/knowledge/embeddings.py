"""ChromaDB-based knowledge base for RAG."""

import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb

from ..config import settings

logger = logging.getLogger(__name__)

# Global knowledge base instance
_knowledge_base: "KnowledgeBase | None" = None


def get_knowledge_base() -> "KnowledgeBase | None":
    """Get the global knowledge base instance."""
    return _knowledge_base


def set_knowledge_base(kb: "KnowledgeBase") -> None:
    """Set the global knowledge base instance."""
    global _knowledge_base
    _knowledge_base = kb


class KnowledgeBase:
    """ChromaDB-based knowledge base for storing and searching documentation."""

    def __init__(self, knowledge_dir: str | Path = "/app/knowledge"):
        """Initialize the knowledge base.

        Args:
            knowledge_dir: Directory containing markdown files to index
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.client: chromadb.HttpClient | None = None
        self.collection = None

    async def initialize(self) -> None:
        """Initialize connection to ChromaDB and index documents."""
        logger.info(f"Connecting to ChromaDB at {settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}")

        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMADB_HOST,
                port=settings.CHROMADB_PORT,
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="unifi_knowledge",
                metadata={"hnsw:space": "cosine"},
            )

            logger.info(f"Collection 'unifi_knowledge' ready with {self.collection.count()} documents")

            # Index knowledge files
            await self._index_knowledge_files()

            # Set global instance
            set_knowledge_base(self)

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    async def _index_knowledge_files(self) -> None:
        """Index all markdown files in the knowledge directory."""
        if not self.knowledge_dir.exists():
            logger.warning(f"Knowledge directory not found: {self.knowledge_dir}")
            return

        indexed_count = 0
        for md_file in self.knowledge_dir.glob("*.md"):
            count = await self._index_file(md_file)
            indexed_count += count

        logger.info(f"Indexed {indexed_count} chunks from knowledge files")

    async def _index_file(self, file_path: Path) -> int:
        """Index a single markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            Number of chunks indexed
        """
        content = file_path.read_text(encoding="utf-8")
        chunks = self._split_into_chunks(content)

        indexed = 0
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            # Create deterministic ID based on file and chunk position
            doc_id = hashlib.md5(f"{file_path.name}:{i}".encode()).hexdigest()

            # Check if already indexed
            existing = self.collection.get(ids=[doc_id])
            if existing["ids"]:
                continue

            # Add to collection
            self.collection.add(
                documents=[chunk],
                metadatas=[{
                    "source": file_path.name,
                    "chunk_index": i,
                }],
                ids=[doc_id],
            )
            indexed += 1

        if indexed > 0:
            logger.debug(f"Indexed {indexed} new chunks from {file_path.name}")

        return indexed

    def _split_into_chunks(
        self,
        content: str,
        max_chunk_size: int = 1000,
        overlap: int = 100,
    ) -> list[str]:
        """Split content into overlapping chunks for better retrieval.

        Args:
            content: The text content to split
            max_chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        # Split by headers first for better semantic boundaries
        sections = []
        current_section = ""
        current_header = ""

        for line in content.split("\n"):
            # Check for markdown headers
            if line.startswith("#"):
                if current_section.strip():
                    sections.append((current_header, current_section.strip()))
                current_header = line
                current_section = line + "\n"
            else:
                current_section += line + "\n"

        if current_section.strip():
            sections.append((current_header, current_section.strip()))

        # Now split large sections into smaller chunks
        chunks = []
        for header, section in sections:
            if len(section) <= max_chunk_size:
                chunks.append(section)
            else:
                # Split by paragraphs
                paragraphs = section.split("\n\n")
                current_chunk = ""

                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 <= max_chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = para + "\n\n"

                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

        return chunks

    async def search(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base.

        Args:
            query: Search query string
            n_results: Number of results to return

        Returns:
            List of result dictionaries with 'document' and 'metadata' keys
        """
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            # Format results
            formatted = []
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0] if results["distances"] else [0] * len(results["documents"][0]),
            ):
                formatted.append({
                    "document": doc,
                    "metadata": meta,
                    "relevance": 1 - distance,  # Convert distance to similarity
                })

            return formatted

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def add_document(
        self,
        content: str,
        source: str,
        metadata: dict | None = None,
    ) -> str:
        """Add a new document to the knowledge base.

        Args:
            content: Document content
            source: Source identifier
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = hashlib.md5(f"{source}:{content[:100]}".encode()).hexdigest()

        meta = {"source": source}
        if metadata:
            meta.update(metadata)

        self.collection.add(
            documents=[content],
            metadatas=[meta],
            ids=[doc_id],
        )

        return doc_id

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics.

        Returns:
            Dictionary with count and other stats
        """
        if not self.collection:
            return {"status": "not initialized"}

        return {
            "status": "ready",
            "document_count": self.collection.count(),
            "collection_name": "unifi_knowledge",
        }
