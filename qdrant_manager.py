import logging
import uuid
from typing import List, Dict, Any, Optional, Union

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)

logger = logging.getLogger(__name__)

# Konstanten
COLLECTION_NAME = "pdf_chunks"
VECTOR_SIZE = 768        # gemini-embedding-001 hat 768 Dimensionen
CHUNK_SIZE_DEFAULT = 500
OVERLAP_DEFAULT = 50


class QdrantManager:
    """
    Verwaltet die Verbindung zur Qdrant Vektor-Datenbank.

    Qdrant speichert sogenannte "Points". Jeder Point besteht aus:
    - id:      Eindeutige ID (UUID)
    - vector:  Liste von 1536 Floats (das Embedding)
    - payload: Metadaten als Dict (text, doc_id, page_num, ...)

    Ablauf:
    1. store_chunks()    → Chunks + Embeddings werden als Points gespeichert
    2. search_similar()  → Qdrant findet die ähnlichsten Points zur Frage
    """

    def __init__(self, host: str = "localhost", port: int = 6333):
        """
        Stellt Verbindung zu Qdrant her.

        :param host: Hostname des Qdrant-Containers (Standard: localhost)
        :param port: Port der REST API (Standard: 6333)
        """
        self.host = host
        self.port = port
        self.client: Optional[QdrantClient] = None
        self._connect()

    def _connect(self):
        """Verbindung zu Qdrant aufbauen und Collection sicherstellen."""
        try:
            self.client = QdrantClient(host=self.host, port=self.port, timeout=5)
            # Verbindungstest
            self.client.get_collections()
            logger.info(f"Qdrant verbunden: {self.host}:{self.port}")
            # Collection anlegen falls nicht vorhanden
            self._ensure_collection()
        except Exception as e:
            logger.error(f"Qdrant Verbindung fehlgeschlagen: {e}")
            logger.error("Stelle sicher, dass Docker läuft: docker compose up -d")
            self.client = None

    def _ensure_collection(self):
        """
        Legt die Collection an, falls sie noch nicht existiert.

        Eine Collection in Qdrant ist vergleichbar mit einer Tabelle in SQL
        oder einer Collection in MongoDB — sie fasst gleichartige Daten zusammen.
        Hier: alle PDF-Chunks aus allen Dokumenten.
        """
        if not self.client:
            return

        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=VECTOR_SIZE,
                        distance=Distance.COSINE  # Cosine Similarity für Textähnlichkeit
                    )
                )
                logger.info(f"Qdrant Collection '{COLLECTION_NAME}' erstellt (Vectorgröße: {VECTOR_SIZE})")
            else:
                logger.info(f"Qdrant Collection '{COLLECTION_NAME}' bereits vorhanden")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Collection: {e}")

    def is_connected(self) -> bool:
        """Gibt True zurück, wenn Qdrant erreichbar ist."""
        return self.client is not None

    def store_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> bool:
        """
        Speichert Chunks zusammen mit ihren Embeddings in Qdrant.

        Jeder Chunk wird zu einem "Point" in Qdrant:
        - vector  = das Embedding (1536 Zahlen, die die Bedeutung repräsentieren)
        - payload = die Metadaten (Text, Dokument-ID, Seitennummer, ...)

        :param chunks:     Liste von Chunk-Dicts aus text_chunker.chunk_document()
                           Format: [{text, doc_id, page_num, chunk_index, ...}, ...]
        :param embeddings: Liste von Vektoren aus ai_processor.create_embeddings_batch()
                           Format: [[1536 floats], [1536 floats], ...]
        :return: True wenn erfolgreich, False bei Fehler
        """
        if not self.client:
            logger.error("store_chunks: Keine Qdrant-Verbindung.")
            return False

        if len(chunks) != len(embeddings):
            logger.error(f"store_chunks: Anzahl Chunks ({len(chunks)}) ≠ Embeddings ({len(embeddings)})")
            return False

        if not chunks:
            logger.warning("store_chunks: Keine Chunks zum Speichern.")
            return True

        try:
            # Erstelle Qdrant Points aus den Chunks und Embeddings
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                if not embedding:
                    logger.warning(f"Chunk {chunk.get('chunk_index')} hat leeres Embedding, wird übersprungen.")
                    continue

                point = PointStruct(
                    id=uuid.uuid4(),        # UUID-Objekt (nicht String!) — Qdrant-Anforderung
                    vector=embedding,        # Das Embedding-Vektor
                    payload={               # Metadaten, die bei der Suche zurückgegeben werden
                        "text": chunk.get("text", ""),
                        "doc_id": chunk.get("doc_id", ""),
                        "page_num": chunk.get("page_num", 0),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "page_chunk_index": chunk.get("page_chunk_index", 0),
                        "character_count": chunk.get("character_count", 0),
                    }
                )
                points.append(point)

            if not points:
                logger.warning("store_chunks: Keine gültigen Points zum Speichern (alle Embeddings leer?).")
                return False

            # Alle Points auf einmal hochladen (effizienter als einzeln)
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            logger.info(f"Qdrant: {len(points)} Chunks gespeichert für doc_id={chunks[0].get('doc_id', '?')}")
            return True

        except Exception as e:
            logger.error(f"store_chunks: Fehler beim Speichern in Qdrant: {e}")
            return False

    def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 5,
        doc_ids: Optional[Union[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Findet die ähnlichsten Chunks zu einem Query-Embedding.

        Das ist der Kern der semantischen Suche:
        - Qdrant vergleicht den query_embedding-Vektor mit allen gespeicherten Vektoren
        - Es misst die "Cosine Similarity" (Winkel zwischen den Vektoren)
        - Die Chunks mit dem kleinsten Winkel = höchste Ähnlichkeit werden zurückgegeben

        :param query_embedding: Embedding der Benutzer-Frage (1536 Floats)
        :param limit:           Wie viele Ergebnisse zurückgeben (Standard: 5)
        :param doc_ids:         Optional: Suche in einem oder mehreren bestimmten Dokumenten (ID oder Liste von IDs)
        :return: Liste der ähnlichsten Chunks mit Score und Metadaten
        """
        if not self.client:
            logger.error("search_similar: Keine Qdrant-Verbindung.")
            return []

        if not query_embedding:
            logger.error("search_similar: Leeres Query-Embedding.")
            return []

        try:
            # Filter: Optional auf Listen von Dokumenten einschränken
            search_filter = None
            if doc_ids:
                if isinstance(doc_ids, str):
                    doc_ids = [doc_ids]
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchAny(any=doc_ids)
                        )
                    ]
                )

            # Similarity Search ausführen
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_embedding,
                query_filter=search_filter,
                limit=limit
            )
            
            # Ergebnisse in ein lesbares Format umwandeln
            hits = []
            for point in results.points:
                hits.append({
                    "score": round(point.score, 4),    # Ähnlichkeitswert: 1.0 = identisch
                    "text": point.payload.get("text", ""),
                    "doc_id": point.payload.get("doc_id", ""),
                    "page_num": point.payload.get("page_num", 0),
                    "chunk_index": point.payload.get("chunk_index", 0),
                })

            logger.info(f"search_similar: {len(hits)} Treffer gefunden (doc_ids={doc_ids or 'alle'})")
            return hits

        except Exception as e:
            logger.error(f"search_similar: Fehler bei der Suche: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """
        Löscht alle Chunks eines Dokuments aus Qdrant.

        Wird aufgerufen wenn ein Dokument aus dem System gelöscht wird,
        damit keine verwaisten Chunks in Qdrant verbleiben.

        :param doc_id: Dokument-ID (UUID aus MongoDB)
        :return: True wenn erfolgreich
        """
        if not self.client:
            logger.error("delete_document: Keine Qdrant-Verbindung.")
            return False

        try:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                )
            )
            logger.info(f"Qdrant: Alle Chunks für doc_id={doc_id} gelöscht")
            return True
        except Exception as e:
            logger.error(f"delete_document: Fehler: {e}")
            return False

    def get_chunk_count(self, doc_id: Optional[str] = None) -> int:
        """
        Gibt die Anzahl der gespeicherten Chunks zurück.
        Nützlich für Tests und Debugging.

        :param doc_id: Optional: Nur Chunks dieses Dokuments zählen
        """
        if not self.client:
            return 0
        try:
            if doc_id:
                result = self.client.count(
                    collection_name=COLLECTION_NAME,
                    count_filter=Filter(
                        must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                    )
                )
            else:
                result = self.client.count(collection_name=COLLECTION_NAME)
            return result.count
        except Exception as e:
            logger.error(f"get_chunk_count: Fehler: {e}")
            return 0
