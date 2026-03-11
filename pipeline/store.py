"""Qdrant vector store — collection management and upsert logic."""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, MatchValue, PointStruct, VectorParams


class VectorStore:
    """Manages a Qdrant collection for El Paso document chunks."""

    def __init__(
        self,
        collection_name: str = "el_paso",
        host: str = "localhost",
        port: int = 6333,
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(host=host, port=port)

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            )

    def upsert_chunks(
        self,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> int:
        """Upsert embedded chunks with metadata payloads. Returns count upserted."""
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )
            for vector, payload in zip(vectors, payloads)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return len(points)

    def delete_by_filter(self, **field_matches) -> None:
        """Delete points matching exact field values."""
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in field_matches.items()
        ]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=conditions),
        )

    def delete_collection(self) -> None:
        """Drop the entire collection."""
        self.client.delete_collection(self.collection_name)

    def search(
        self, query_vector: list[float], top_k: int = 5,
        source_types: list[str] | None = None,
        repo_name: str = "",
        space_key: str = "",
    ) -> list[dict]:
        """Search for similar vectors with optional filters."""
        conditions = []
        if source_types:
            conditions.append(
                FieldCondition(key="source_type", match=MatchAny(any=source_types))
            )
        if repo_name:
            conditions.append(
                FieldCondition(key="repo_name", match=MatchValue(value=repo_name))
            )
        if space_key:
            conditions.append(
                FieldCondition(key="space_key", match=MatchValue(value=space_key))
            )

        query_filter = Filter(must=conditions) if conditions else None

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return [
            {
                "score": point.score,
                **point.payload,
            }
            for point in results.points
        ]

    def collection_info(self) -> dict:
        """Return collection point count and status."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": info.status.value,
        }
