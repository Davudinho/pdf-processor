import unittest
from text_chunker import TextChunker

class TestTextChunker(unittest.TestCase):
    def setUp(self):
        # Initialisiere den Chunker
        self.chunker = TextChunker()

    def test_chunk_text(self):
        # Ein Test-Text mit ca 100 Zeichen
        text = "Das ist ein kurzer Testtext, der in mehrere Chunks aufgeteilt werden soll, um die Logik zu testen."
        
        chunks = self.chunker.chunk_text(text, chunk_size=50, overlap=10)
        
        self.assertGreater(len(chunks), 1, "Der Text sollte in mindestens zwei Chunks geteilt werden")
        self.assertTrue(all(len(chunk) <= 50 for chunk in chunks), "Kein Chunk sollte größer als chunk_size sein")
        
        # Prüfe den Overlap (grob anhand von gemeinsamen Wörtern)
        # Da wir nach Wörtern splitten, sollte der Overlap ungefähr passen
        self.assertTrue(any(word in chunks[1] for word in chunks[0].split()[-3:]), "Es sollte einen Overlap zwischen Chunk 0 und 1 geben")

    def test_chunk_document(self):
        pages_data = [
            {"page_num": 1, "raw_text": "Seite 1 Text. " * 10},
            {"page_num": 2, "raw_text": "Seite 2 Text. " * 10}
        ]
        doc_id = "test-doc-123"
        
        doc_chunks = self.chunker.chunk_document(pages_data, doc_id, chunk_size=50, overlap=10)
        
        self.assertGreater(len(doc_chunks), 0)
        
        # Prüfe ob die Metadaten in den Chunks korrekt sind
        first_chunk = doc_chunks[0]
        self.assertIn("text", first_chunk)
        self.assertIn("doc_id", first_chunk)
        self.assertEqual(first_chunk["doc_id"], doc_id)
        self.assertEqual(first_chunk["page_num"], 1)
        self.assertIn("chunk_index", first_chunk)

if __name__ == '__main__':
    unittest.main()
