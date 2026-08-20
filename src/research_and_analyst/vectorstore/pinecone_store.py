"""
Pinecone storage for completed interview sections.

Each analyst's interview produces a written section (see
`InterviewGraphBuilder._write_section`). We embed and upsert that section
into Pinecone, namespaced by report thread_id, so that:

  - past interview sections are retrievable for a given topic/thread without
    re-running interviews
  - future reports on similar topics can retrieve related prior sections as
    additional context (a natural extension point — not wired into the
    report-writing prompt by default, to avoid changing generation behaviour
    without an explicit decision to do so)

Silently no-ops if PINECONE_API_KEY isn't set, so the pipeline runs fine
without Pinecone configured (interviews just aren't persisted to a vector
store).
"""

import os
import uuid
import logging
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_INDEX_NAME = "research-analyst-sections"
EMBEDDING_DIMENSION = 768  # matches models/text-embedding-004 (Google), used elsewhere in this project


class InterviewSectionStore:
    """Thin wrapper around a Pinecone index for storing/retrieving interview sections."""

    def __init__(self, embeddings, index_name: str = DEFAULT_INDEX_NAME):
        self.embeddings = embeddings
        self.index_name = index_name
        self._index = None
        self._available = False

        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            log.info("PINECONE_API_KEY not set — interview sections will not be persisted to Pinecone")
            return

        try:
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=api_key)
            existing = [idx["name"] for idx in pc.list_indexes()]

            if self.index_name not in existing:
                log.info("Creating Pinecone index | index=%s", self.index_name)
                pc.create_index(
                    name=self.index_name,
                    dimension=EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=os.getenv("PINECONE_CLOUD", "aws"),
                        region=os.getenv("PINECONE_REGION", "us-east-1"),
                    ),
                )

            self._index = pc.Index(self.index_name)
            self._available = True
            log.info("Pinecone interview section store ready | index=%s", self.index_name)
        except ImportError:
            log.warning("pinecone package not installed — run `pip install pinecone` to enable this feature")
        except Exception as e:
            log.error("Failed to initialise Pinecone index | error=%s", str(e), exc_info=True)

    @property
    def available(self) -> bool:
        return self._available

    def upsert_section(self, thread_id: str, analyst_name: str, topic: str, section_text: str) -> Optional[str]:
        """Embed and store a single interview section. Returns the vector id, or None if unavailable."""
        if not self._available or not section_text:
            return None

        try:
            vector = self.embeddings.embed_query(section_text)
            vector_id = f"{thread_id}:{uuid.uuid4().hex[:8]}"

            self._index.upsert(
                vectors=[{
                    "id": vector_id,
                    "values": vector,
                    "metadata": {
                        "thread_id": thread_id,
                        "analyst": analyst_name,
                        "topic": topic,
                        "text": section_text[:4000],  # metadata size limits
                    },
                }],
                namespace=thread_id,
            )
            log.info("Interview section upserted to Pinecone | thread_id=%s | analyst=%s", thread_id, analyst_name)
            return vector_id
        except Exception as e:
            log.error("Pinecone upsert failed | error=%s", str(e), exc_info=True)
            return None

    def query_similar_sections(self, topic: str, top_k: int = 3) -> list:
        """Retrieve sections from prior reports similar to `topic`, across all namespaces isn't
        supported by a single query in Pinecone, so this queries the default namespace only
        unless a namespace is supplied — kept simple as an extension point."""
        if not self._available:
            return []

        try:
            vector = self.embeddings.embed_query(topic)
            result = self._index.query(vector=vector, top_k=top_k, include_metadata=True)
            return [match["metadata"] for match in result.get("matches", [])]
        except Exception as e:
            log.error("Pinecone query failed | error=%s", str(e), exc_info=True)
            return []
