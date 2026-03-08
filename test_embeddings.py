import unittest
import os
from ai_processor import AIProcessor
from dotenv import load_dotenv

load_dotenv()

class TestEmbeddings(unittest.TestCase):
    def setUp(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.skipTest("OPENAI_API_KEY nicht gesetzt. Test übersprungen.")
        
        self.ai = AIProcessor(api_key=api_key)

    def test_create_embedding_single(self):
        text = "Dies ist ein Test für einen einzelnen Embedding-Vektor."
        vector = self.ai.create_embedding(text)
        
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 1536, "Der Vektor sollte genau 1536 Dimensionen haben (text-embedding-3-small)")
        self.assertIsInstance(vector[0], float)

    def test_create_embeddings_batch(self):
        texts = [
            "Das ist der erste Text.",
            "Hier kommt ein weiterer, zweiter Text.",
            "Und noch ein ganz kurzer."
        ]
        
        vectors = self.ai.create_embeddings_batch(texts)
        
        self.assertIsInstance(vectors, list)
        self.assertEqual(len(vectors), 3, "Es sollten 3 Vektoren zurückgegeben werden")
        self.assertEqual(len(vectors[0]), 1536)
        self.assertEqual(len(vectors[1]), 1536)
        self.assertEqual(len(vectors[2]), 1536)
        
    def test_empty_text_handling(self):
        text = "   "
        vector = self.ai.create_embedding(text)
        self.assertEqual(vector, [], "Leerer Text sollte eine leere Liste zurückgeben")

if __name__ == '__main__':
    unittest.main()
