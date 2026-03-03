from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TextChunker:

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Teilt Text in überlappende Chunks auf.

        Beispiel mit chunk_size=10, overlap=3:
        "Der schnelle braune Fuchs springt über den Zaun"
        → Chunk 1: "Der schnelle braune Fuchs"
        → Chunk 2: "Fuchs springt über den"← "Fuchs" überlappt!
        → Chunk 3: "den Zaun"

        Warum Overlap? Damit kein Kontext an Chunk-Grenzen verloren geht.
        """

        if not text:
            return []

        if chunk_size <= 0:
            raise ValueError("chunk_size muss größer als 0 sein")

        if overlap < 0:
            raise ValueError("overlap kann nicht negativ sein")

        if overlap >= chunk_size:
            raise ValueError("overlap muss kleiner als chunk_size sein")

        chunks = []
        start = 0

        while start < len(text):
            # Ende des aktuellen Chunks bestimmen
            end = min(start + chunk_size, len(text))

            # Chunk extrahieren
            chunk = text[start:end]
            chunks.append(chunk)

            # Wenn wir am Ende des Textes sind, beenden
            if end >= len(text):
                break

            # Nächste Startposition mit Overlap berechnen
            start = end - overlap

        return chunks

    def chunk_document(self, pages_data: List[Dict[str, Any]], doc_id: str,
                       chunk_size: int = 500, overlap: int = 50,
                       include_empty_pages: bool = False) -> List[Dict[str, Any]]:
        """
        Chunked alle Seiten eines Dokuments.

        Args:
            pages_data: Liste von Page-Dicts aus pdf_processor.extract_text_from_pdf().
                        Format: [{"page_num": int, "raw_text": str, "text_length": int}, ...]
            doc_id: Eindeutige Dokument-ID (UUID aus MongoDB)
            chunk_size: Größe der Chunks in Zeichen
            overlap: Überlappung zwischen Chunks in Zeichen
            include_empty_pages: Ob leere Seiten als Chunk gespeichert werden sollen

        Returns:
            Liste von Chunk-Dicts mit Metadaten:
            [{"text": str, "doc_id": str, "page_num": int, "chunk_index": int, ...}, ...]
        """
        if not pages_data:
            return []

        all_chunks = []
        global_chunk_index = 0

        for page in pages_data:
            # pages_data kommt als List[Dict] aus pdf_processor.extract_text_from_pdf()
            page_num = page.get("page_num", 0)
            page_content = page.get("raw_text", "")

            # Behandlung leerer Seiten
            if not page_content or not page_content.strip():
                if include_empty_pages:
                    chunk_data = {
                        "text": "",
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "chunk_index": global_chunk_index,
                        "is_empty_page": True
                    }
                    all_chunks.append(chunk_data)
                    global_chunk_index += 1
                continue

            # Chunke den Inhalt der aktuellen Seite
            page_chunks = self.chunk_text(page_content, chunk_size, overlap)

            # Erstelle Chunk-Objekte mit Metadaten
            for local_chunk_index, chunk_content in enumerate(page_chunks):
                chunk_data = {
                    "text": chunk_content,
                    "doc_id": doc_id,
                    "page_num": page_num,
                    "chunk_index": global_chunk_index,
                    "page_chunk_index": local_chunk_index,
                    "total_chunks_on_page": len(page_chunks),
                    "character_count": len(chunk_content)
                }
                all_chunks.append(chunk_data)
                global_chunk_index += 1

        logger.info(f"Dokument {doc_id}: {len(pages_data)} Seiten → {global_chunk_index} Chunks")
        return all_chunks
