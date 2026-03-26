import unittest
import os
from ai_processor import AIProcessor
from dotenv import load_dotenv

load_dotenv()

class TestEmbeddings(unittest.TestCase):
    def setUp(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.skipTest("GEMINI_API_KEY nicht gesetzt. Test übersprungen.")
        
        self.ai = AIProcessor(api_key=api_key)

    def test_create_embedding_single(self):
        text = "Dies ist ein Test für einen einzelnen Embedding-Vektor."
        vector = self.ai.create_embedding(text)
        
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 3072, "Der Vektor sollte genau 3072 Dimensionen haben (gemini-embedding-001)")
        self.assertTrue(len(vector) > 0 and isinstance(vector[0], float))

    def test_create_embeddings_batch(self):
        texts = [
            "Das ist der erste Text.",
            "Hier kommt ein weiterer, zweiter Text.",
            "Und noch ein ganz kurzer."
        ]
        
        vectors = self.ai.create_embeddings_batch(texts)
        
        self.assertIsInstance(vectors, list)
        self.assertEqual(len(vectors), 3, "Es sollten 3 Vektoren zurückgegeben werden")
        self.assertEqual(len(vectors[0]), 3072)
        self.assertEqual(len(vectors[1]), 3072)
        self.assertEqual(len(vectors[2]), 3072)
        
    def test_empty_text_handling(self):
        text = "   "
        vector = self.ai.create_embedding(text)
        self.assertEqual(vector, [], "Leerer Text sollte eine leere Liste zurückgeben")

if __name__ == '__main__':
    unittest.main()
