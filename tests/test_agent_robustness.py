import unittest
import sys
import os

# Füge das Hauptverzeichnis zum Python-Pfad hinzu, damit wir agent.py importieren können
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import PdfAgent

class MockAI:
    def __init__(self):
        self.client = True  # Täuscht vor, dass wir einen Client haben

class MockDB:
    def __init__(self):
        pass

class MockQdrant:
    def is_connected(self):
        return False

class TestAgentRobustness(unittest.TestCase):
    """
    Testet die Stabilität des Agenten, wenn das LLM (Gemini) fehlerhafte 
    oder unerwartete Parameter an die internen Werkzeuge (Tools) schickt.
    """

    def setUp(self):
        self.agent = PdfAgent(ai_processor=MockAI(), db_manager=MockDB(), qdrant_manager=MockQdrant())

    def test_invalid_type_casting(self):
        """Testet, ob falsche Datentypen vom LLM abgefangen werden (z.B. top_k = 'fünf' statt 5)."""
        
        bad_args = {
            "query": "Rechnung",
            "top_k": "fünf"  # Falscher Datentyp (String statt Int)
        }
        
        # Aufruf des Dispatchers
        result = self.agent._execute_tool("search_in_documents", bad_args)
        
        # Erwartung: Es soll NICHT abstürzen, sondern ein Dict mit {"error": ...} zurückgeben.
        self.assertIn("error", result, "SCHWACHSTELLE: Agent fängt TypeCasting-Fehler nicht als API-Antwort ab!")
        print("✓ Agent fängt fehlerhafte Datentypen des LLMs ab:", result["error"])

    def test_missing_required_params(self):
        """Testet, ob fehlende Parameter das System zum Absturz bringen."""
        
        # doc_id_1 und doc_id_2 fehlen komplett
        bad_args = {}
        
        # Das Tool erwartet eigentlich strings und versucht self._get_document_summary(doc_id_1)
        result = self.agent._execute_tool("compare_two_documents", bad_args)
        
        self.assertIn("error", result)
        print("✓ Agent behandelt fehlende Parameter sicher:", result["error"])

    def test_unknown_tool(self):
        """Testet den Fallback, wenn das LLM ein Werkzeug erfindet."""
        result = self.agent._execute_tool("mache_kaffee", {"zucker": True})
        self.assertIn("error", result)
        self.assertIn("Unbekanntes Werkzeug", result["error"])
        print("✓ Agent lehnt erfundene Werkzeuge sicher ab.")

if __name__ == "__main__":
    print("Starte Agent Robustness Tests...")
    unittest.main()
