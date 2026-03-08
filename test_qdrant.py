import unittest
import uuid
from qdrant_manager import QdrantManager

class TestQdrantManager(unittest.TestCase):
    def setUp(self):
        self.qdrant = QdrantManager(host="localhost", port=6333)
        if not self.qdrant.is_connected():
            self.skipTest("Qdrant ist nicht erreichbar. Läuft der Docker-Container?")
        
        # Stelle sicher dass wir einen sauberen Zustand für unseren Test-Doc haben
        self.test_doc_id = str(uuid.uuid4())

    def test_full_qdrant_lifecycle(self):
        # 1. Chunks speichern
        chunks = [
            {"text": "Dies ist ein wichtiger Satz über Finanzen.", "doc_id": self.test_doc_id, "page_num": 1, "chunk_index": 0},
            {"text": "Hier geht es um die Mitarbeiter und Personalpolitik.", "doc_id": self.test_doc_id, "page_num": 2, "chunk_index": 1}
        ]
        
        # Zwei Dummy-Embeddings mit 1536 Dimensionen
        # Wir machen die Vektoren künstlich "ähnlich" zu bestimmten Richtungen
        emb1 = [0.1] * 1536
        emb2 = [0.9] * 1536
        emb1[0] = 1.0 # Eindeutige Signatur
        emb2[1] = 1.0 # Eindeutige Signatur
        embeddings = [emb1, emb2]
        
        success = self.qdrant.store_chunks(chunks, embeddings)
        self.assertTrue(success, "Chunks sollten erfolgreich gespeichert werden")
        
        # 2. Suche testen (wir suchen nach emb1, sollte den ersten Satz finden)
        # Hinzufügen einer leichten Abweichung zur Suchanfrage
        query_emb = [0.1] * 1536
        query_emb[0] = 0.95 
        
        results = self.qdrant.search_similar(query_emb, limit=2, doc_id=self.test_doc_id)
        
        self.assertGreater(len(results), 0, "Suche sollte Ergebnisse liefern")
        self.assertEqual(results[0]["page_num"], 1, "Das erste Ergebnis sollte der Finanzen-Satz (Seite 1) sein")
        self.assertIn("score", results[0], "Die Ergebnisse sollten einen Ähnlichkeits-Score haben")
        
        # 3. Löschen testen
        delete_success = self.qdrant.delete_document(self.test_doc_id)
        self.assertTrue(delete_success, "Dokument sollte erfolgreich gelöscht werden")
        
        # Erneute Suche sollte keine Ergebnisse mehr liefern für diesen doc_id
        empty_results = self.qdrant.search_similar(query_emb, limit=2, doc_id=self.test_doc_id)
        self.assertEqual(len(empty_results), 0, "Nach Löschung sollten keine Chunks mehr gefunden werden")

    def tearDown(self):
        # Sicherstellen dass alles gelöscht wird, auch wenn ein Test fehlschlägt
        if self.qdrant.is_connected():
            self.qdrant.delete_document(self.test_doc_id)

if __name__ == '__main__':
    unittest.main()
