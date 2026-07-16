"""
Qdrant vector database client wrapper.

Provides health_check, search, and collection listing for the LIMS RAG pipeline.
No embedding logic — that's Phase 1 (AI QMS integration).
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Filter


class QdrantService:
    """
    Thin wrapper around qdrant-client for the LIMS RAG pipeline.

    EU GMP Annex 11: external dependencies must fail gracefully with
    clear error responses — never crash the application.
    """

    def __init__(self, url: str, api_key: str | None = None):
        """
        Initialize the Qdrant client.

        Args:
            url: Qdrant server URL (e.g., http://localhost:6333).
            api_key: Optional API key for cloud deployments.
        """
        self.url = url
        self._client = QdrantClient(url=url, api_key=api_key)

    def health_check(self) -> dict:
        """
        Check Qdrant server connectivity.

        Returns:
            {"status": "connected", "collections": [...]} if reachable,
            {"status": "unreachable", "error": "..."} otherwise.
            Never raises an unhandled exception.

        AC-06: QdrantService.health_check() never raises unhandled exception.
        """
        try:
            collections = self._client.get_collections()
            collection_names = [c.name for c in collections.collections]
            return {
                "status": "connected",
                "collections": collection_names,
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "error": str(exc),
            }

    def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        filter_obj: Filter | None = None,
    ) -> list[dict]:
        """
        Search a Qdrant collection for nearest neighbours.

        Args:
            collection: Collection name (e.g., 'pp_qms_sops').
            query_vector: Embedding vector (1024d for voyage-3).
            limit: Maximum results to return.
            filter_obj: Optional Qdrant Filter for metadata filtering.

        Returns:
            List of dicts with 'id', 'score', and 'payload' keys.

        Raises:
            ConnectionError: If Qdrant is unreachable.
        """
        results = self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_obj,
        )
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

    def get_collections(self) -> list[str]:
        """
        List all collection names.

        Returns:
            List of collection name strings.

        Raises:
            ConnectionError: If Qdrant is unreachable.
        """
        collections = self._client.get_collections()
        return [c.name for c in collections.collections]


# Module-level instance (lazily initialized from settings)
_singleton: "QdrantService | None" = None


def get_qdrant_service(url: str, api_key: str | None = None) -> QdrantService:
    """
    Get or create a QdrantService instance.

    Args:
        url: Qdrant server URL.
        api_key: Optional API key.

    Returns:
        Configured QdrantService.
    """
    global _singleton
    if _singleton is None:
        _singleton = QdrantService(url=url, api_key=api_key)
    return _singleton
